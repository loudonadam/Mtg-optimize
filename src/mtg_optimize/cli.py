from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from .card import Card, CardChoice
from .decklist import DecklistError, fetch_card_metadata, parse_decklist_lines
from .search import DeckRules, SearchConfig, brute_force_decks, count_possible_decks, rank_decks
from .simulator import SimulationConfig, summary_string

BASIC_LANDS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}


def load_config(path: Path) -> Dict[str, Any]:
    with path.open() as f:
        return json.load(f)


def load_rules(path: Path) -> DeckRules:
    data = load_config(path)
    return DeckRules(
        min_lands=data.get("min_lands"),
        max_lands=data.get("max_lands"),
        min_creatures=data.get("min_creatures"),
        max_creatures=data.get("max_creatures"),
    )


def progress_printer(stage: str):
    def _printer(done: int, total: int) -> None:
        if total:
            pct = done / total * 100
            print(f"[{stage}] {done}/{total} ({pct:.1f}%)", file=sys.stderr)
        else:
            print(f"[{stage}] {done} completed", file=sys.stderr)

    return _printer


def abbreviate(value: int) -> str:
    for unit in ("", "K", "M", "B", "T"):
        if abs(value) < 1000:
            return f"{value}{unit}"
        value = value / 1000
    return f"{value:.1f}P"


def render_deck_count(deck_count: DeckCount) -> str:
    lower = deck_count.lower_bound or deck_count.total
    upper = deck_count.upper_bound or deck_count.total
    estimate_note = " (estimated)" if deck_count.estimated else ""
    if lower == upper:
        return f"{abbreviate(lower)}{estimate_note}"
    return f"{abbreviate(lower)}-{abbreviate(upper)}{estimate_note}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate MTG Pauper deck candidates")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", type=Path, help="Path to deck search JSON config")
    source.add_argument("--decklist", type=Path, help="Path to MTGO/Arena-style decklist text")
    parser.add_argument("--deck-size", type=int, default=None, help="Target deck size (default: 60)")
    parser.add_argument("--rules", type=Path, help="Optional JSON file with deck construction rules")
    parser.add_argument(
        "--brute-limit",
        type=int,
        default=None,
        help="Maximum deck combinations to explore (default: 5000 or config value)",
    )
    parser.add_argument(
        "--fixed-deck",
        action="store_true",
        help="When using --decklist, keep counts exactly as written instead of treating them as a pool",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=1,
        help="How many top decks to print (default: 1)",
    )
    parser.add_argument("--games", type=int, default=None, help="Override simulation game count")
    parser.add_argument("--turns", type=int, default=None, help="Override simulation turn horizon")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for deterministic runs")
    args = parser.parse_args()

    choices: List[CardChoice] = []
    deck_size: int
    brute_limit: int | None = None
    sim_games: int
    sim_turns: int
    seed = args.seed
    rules: DeckRules | None = load_rules(args.rules) if args.rules else None

    if args.config:
        cfg = load_config(args.config)
        deck_size = args.deck_size or cfg.get("deck_size", 60)
        brute_limit = args.brute_limit or cfg.get("brute_force_limit")
        sim_games = args.games or cfg.get("games", 500)
        sim_turns = args.turns or cfg.get("turns", 6)
        if seed is None:
            seed = cfg.get("seed")
        if rules is None and "deck_rules" in cfg:
            rules_cfg = cfg.get("deck_rules", {})
            rules = DeckRules(
                min_lands=rules_cfg.get("min_lands"),
                max_lands=rules_cfg.get("max_lands"),
                min_creatures=rules_cfg.get("min_creatures"),
                max_creatures=rules_cfg.get("max_creatures"),
            )

        for entry in cfg["cards"]:
            card = Card(
                name=entry["name"],
                type_line=entry.get("type", "spell"),
                mana_cost=entry.get("mana_cost", 0),
                colors=tuple(entry.get("colors", [])),
                power=entry.get("power"),
                toughness=entry.get("toughness"),
                impact_score=entry.get("impact_score", 0.0),
                tags=tuple(entry.get("tags", [])),
            )
            choices.append(
                CardChoice(
                    card=card,
                    min_count=entry.get("min", 0),
                    max_count=entry.get("max", 4),
                )
            )
    else:
        assert args.decklist
        default_deck_size = args.deck_size or 60
        try:
            lines = args.decklist.read_text().splitlines()
            deck_entries = parse_decklist_lines(lines)
        except OSError as exc:  # pragma: no cover - CLI concerns
            raise SystemExit(f"Failed to read decklist: {exc}") from exc
        except DecklistError as exc:  # pragma: no cover - CLI concerns
            raise SystemExit(str(exc)) from exc

        for entry in deck_entries:
            if args.fixed_deck and entry.count is None:
                raise SystemExit("Counts are required for --fixed-deck decklists")

            card = fetch_card_metadata(entry.name)
            if entry.impact_score:
                card = Card(
                    name=card.name,
                    type_line=card.type_line,
                    mana_cost=card.mana_cost,
                    colors=card.colors,
                    power=card.power,
                    toughness=card.toughness,
                    impact_score=entry.impact_score,
                    tags=card.tags,
                    is_basic_land=card.is_basic_land,
                )
            is_basic = card.is_basic_land or card.name in BASIC_LANDS
            if args.fixed_deck:
                min_count = entry.count
                max_count = entry.count
            else:
                min_count = 0
                if entry.count is None:
                    max_count = default_deck_size if is_basic else 4
                else:
                    max_count = entry.count
                if not is_basic:
                    max_count = min(max_count, 4)
            choices.append(CardChoice(card=card, min_count=min_count, max_count=max_count))

        deck_size = args.deck_size or (
            sum(entry.count for entry in deck_entries if entry.count is not None)
            if args.fixed_deck
            else 60
        )
        brute_limit = args.brute_limit or (1 if args.fixed_deck else None)
        sim_games = args.games or 500
        sim_turns = args.turns or 6

    if rules is None:
        default_rules_path = Path("deck_rules.json")
        if default_rules_path.exists():
            rules = load_rules(default_rules_path)

    deck_count = count_possible_decks(choices, deck_size, rules=rules)
    total_possible = deck_count.total
    deck_count_label = render_deck_count(deck_count)
    if total_possible == 0:
        raise SystemExit("No valid decks can be constructed with the supplied constraints")

    if brute_limit is None:
        suggested = min(5000, total_possible if total_possible else 5000)
        print(
            f"Found {deck_count_label} valid deck combinations."
            f" Simulate how many? [default: {suggested}]",
            file=sys.stderr,
        )
        user_choice = ""
        if sys.stdin.isatty():
            try:
                user_choice = input().strip()
            except EOFError:
                user_choice = ""
        if user_choice:
            try:
                brute_limit = max(1, min(int(user_choice), total_possible))
            except ValueError:
                brute_limit = suggested
        else:
            brute_limit = suggested
    else:
        brute_limit = max(1, min(brute_limit, total_possible))

    search_config = SearchConfig(
        deck_size=deck_size,
        brute_force_limit=brute_limit,
        deck_rules=rules,
        simulation=SimulationConfig(games=sim_games, turns=sim_turns, seed=seed),
    )

    deck_progress = progress_printer("Deck search")
    decks = brute_force_decks(choices, search_config, progress=deck_progress)
    if not decks:
        raise SystemExit("No valid decks found; adjust constraints or deck size")

    sim_progress = progress_printer("Simulations")
    summaries = rank_decks(decks, search_config, progress=sim_progress)
    for idx, summary in enumerate(summaries[: args.top], start=1):
        print(f"=== Deck {idx} ===")
        print(summary_string(summary))
        print()


if __name__ == "__main__":
    main()
