from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Counter, Iterable, List, Mapping, MutableMapping, Sequence

from .card import Card, DeckList, deck_size, flatten_deck


@dataclass
class GameResult:
    spells_cast: int
    mana_spent: int
    total_board_impact: float
    spell_impact: float
    interaction_spells: int
    counterspells: int
    card_draw_spells: int
    finishers: int
    color_screw_turns: int
    land_drops_missed: int

    @property
    def score(self) -> float:
        """Composite score preferring proactive starts.

        A higher score is better. Color screw and missing land drops are
        penalised because they indicate starts where spells cannot be cast.
        """

        penalties = self.color_screw_turns * 0.5 + self.land_drops_missed * 0.25
        proactive = self.spells_cast * 1.2 + self.mana_spent * 0.1
        board_pressure = self.total_board_impact * 0.25 + self.finishers * 1.5
        impact = self.spell_impact * 0.6
        interaction = self.interaction_spells * 0.9 + self.counterspells * 0.7
        resilience = self.card_draw_spells * 0.8
        return proactive + board_pressure + impact + interaction + resilience - penalties


@dataclass
class SimulationConfig:
    games: int = 500
    turns: int = 6
    seed: int | None = None


@dataclass
class SimulationSummary:
    deck: DeckList
    average_score: float
    average_spells_cast: float
    average_mana_spent: float
    average_board_impact: float
    average_spell_impact: float
    average_interaction: float
    average_counters: float
    average_card_draw: float
    average_finishers: float
    average_color_screw: float
    average_land_miss: float


@dataclass
class TurnTrace:
    turn: int
    draw: Card | None
    actions: list[str]
    spells_cast: int
    mana_spent: int
    board_impact: float
    spell_impact: float
    interaction_spells: int
    counterspells: int
    card_draw_spells: int
    finishers: int
    color_screw: bool
    land_missed: bool


@dataclass
class SimulationTrace:
    opening_hand: list[Card]
    turns: list[TurnTrace]
    result: GameResult


class DrawSimulator:
    def __init__(self, deck: DeckList, rng: random.Random):
        self.deck = deck
        self.rng = rng

    def _simulate(self, turns: int, capture_trace: bool = False):
        library = flatten_deck(self.deck)
        self.rng.shuffle(library)

        hand = [library.pop() for _ in range(7)]
        battlefield: List[Card] = []
        spells_cast = 0
        mana_spent = 0
        total_board_impact = 0.0
        spell_impact = 0.0
        interaction_spells = 0
        counterspells = 0
        card_draw_spells = 0
        finishers = 0
        color_screw_turns = 0
        land_drops_missed = 0

        trace_turns: List[TurnTrace] = []
        opening_hand = list(hand)

        for _turn in range(1, turns + 1):
            turn_actions: list[str] = []
            spells_cast_this_turn = 0
            mana_spent_this_turn = 0
            spell_impact_this_turn = 0.0
            interaction_this_turn = 0
            counters_this_turn = 0
            card_draw_this_turn = 0
            finishers_this_turn = 0

            draw: Card | None = None
            if library:
                draw = library.pop()
                hand.append(draw)
                if capture_trace:
                    turn_actions.append(f"Drew {draw.name}")

            mana_pool: Counter[str] = Counter()

            land_played_this_turn = False
            for idx, card in enumerate(list(hand)):
                if card.is_land:
                    hand.pop(idx)
                    battlefield.append(card)
                    land_played_this_turn = True
                    if capture_trace:
                        turn_actions.append(f"Played land {card.name}")
                    break

            if not land_played_this_turn:
                land_drops_missed += 1

            for card in battlefield:
                if card.is_land:
                    if card.colors:
                        for color in card.colors:
                            mana_pool[color] += 1
                    else:
                        mana_pool["C"] += 1

            castable_indices: List[int] = []
            for idx, card in enumerate(hand):
                if card.is_land:
                    continue
                if card.mana_cost <= sum(mana_pool.values()) and _has_colors(
                    card.colors, mana_pool
                ):
                    castable_indices.append(idx)

            cast_plan = sorted(
                castable_indices, key=lambda i: (hand[i].mana_cost, i), reverse=True
            )
            casted_indices: List[int] = []
            for idx in cast_plan:
                card = hand[idx]
                if card.mana_cost > sum(mana_pool.values()):
                    continue
                if not _has_colors(card.colors, mana_pool):
                    continue
                _spend_mana(card.colors, mana_pool, card.mana_cost)
                spells_cast += 1
                spells_cast_this_turn += 1
                mana_spent += card.mana_cost
                mana_spent_this_turn += card.mana_cost
                casted_indices.append(idx)
                battlefield.append(card)

                details: list[str] = []
                if card.impact_score:
                    if card.is_creature:
                        details.append(
                            f"adds {card.impact_score:.1f} creature impact each turn"
                        )
                    else:
                        spell_impact += card.impact_score
                        spell_impact_this_turn += card.impact_score
                        details.append(f"spell impact +{card.impact_score:.1f}")

                if "removal" in card.tags:
                    interaction_spells += 1
                    interaction_this_turn += 1
                    details.append("counts as interaction")
                if "counter" in card.tags:
                    counterspells += 1
                    counters_this_turn += 1
                    details.append("counts as counterspell")
                if "card_draw" in card.tags:
                    card_draw_spells += 1
                    card_draw_this_turn += 1
                    details.append("draws extra cards")
                if "finisher" in card.tags:
                    finishers += 1
                    finishers_this_turn += 1
                    details.append("counts as finisher")

                if capture_trace:
                    note = f" (" + "; ".join(details) + ")" if details else ""
                    turn_actions.append(
                        f"Cast {card.name} for {card.mana_cost} mana{note}".rstrip()
                    )

            for idx in sorted(casted_indices, reverse=True):
                hand.pop(idx)

            board_impact = sum(
                (card.power or 0)
                + (card.toughness or 0)
                + (card.impact_score if card.is_creature else 0)
                for card in battlefield
                if not card.is_land
            )
            total_board_impact += board_impact

            color_screw_this_turn = False
            if castable_indices and not spells_cast_this_turn:
                color_screw_turns += 1
                color_screw_this_turn = True
            elif not castable_indices and sum(mana_pool.values()) > 0:
                color_screw_turns += 1
                color_screw_this_turn = True

            if capture_trace:
                turn_actions.append(
                    f"Board impact this turn: {board_impact:.2f} (running total {total_board_impact:.2f})"
                )
                if color_screw_this_turn:
                    turn_actions.append("Could not use available colors effectively")

                trace_turns.append(
                    TurnTrace(
                        turn=_turn,
                        draw=draw,
                        actions=turn_actions,
                        spells_cast=spells_cast_this_turn,
                        mana_spent=mana_spent_this_turn,
                        board_impact=board_impact,
                        spell_impact=spell_impact_this_turn,
                        interaction_spells=interaction_this_turn,
                        counterspells=counters_this_turn,
                        card_draw_spells=card_draw_this_turn,
                        finishers=finishers_this_turn,
                        color_screw=color_screw_this_turn,
                        land_missed=not land_played_this_turn,
                    )
                )

        result = GameResult(
            spells_cast=spells_cast,
            mana_spent=mana_spent,
            total_board_impact=total_board_impact,
            spell_impact=spell_impact,
            interaction_spells=interaction_spells,
            counterspells=counterspells,
            card_draw_spells=card_draw_spells,
            finishers=finishers,
            color_screw_turns=color_screw_turns,
            land_drops_missed=land_drops_missed,
        )

        if capture_trace:
            return result, SimulationTrace(opening_hand=opening_hand, turns=trace_turns, result=result)
        return result, None

    def simulate(self, turns: int) -> GameResult:
        result, _ = self._simulate(turns, capture_trace=False)
        return result

    def simulate_with_trace(self, turns: int) -> SimulationTrace:
        _, trace = self._simulate(turns, capture_trace=True)
        assert trace is not None
        return trace


def simulate_deck(deck: DeckList, config: SimulationConfig) -> SimulationSummary:
    if config.seed is not None:
        rng = random.Random(config.seed)
    else:
        rng = random.Random()

    results = [DrawSimulator(deck, rng).simulate(config.turns) for _ in range(config.games)]

    def avg(field: str) -> float:
        return sum(getattr(r, field) for r in results) / len(results)

    return SimulationSummary(
        deck=deck,
        average_score=avg("score"),
        average_spells_cast=avg("spells_cast"),
        average_mana_spent=avg("mana_spent"),
        average_board_impact=avg("total_board_impact"),
        average_spell_impact=avg("spell_impact"),
        average_interaction=avg("interaction_spells"),
        average_counters=avg("counterspells"),
        average_card_draw=avg("card_draw_spells"),
        average_finishers=avg("finishers"),
        average_color_screw=avg("color_screw_turns"),
        average_land_miss=avg("land_drops_missed"),
    )


def summary_string(summary: SimulationSummary) -> str:
    def format_section(title: str, items: list[tuple[Card, int]]) -> list[str]:
        if not items:
            return []
        section = ["", f"{title}:"]
        for card, count in sorted(items, key=lambda item: item[0].name):
            section.append(f"{count} {card.name}")
        return section

    deck_entries = [(card, count) for card, count in summary.deck.items() if count > 0]
    creatures = [(card, count) for card, count in deck_entries if card.is_creature and not card.is_land]
    lands = [(card, count) for card, count in deck_entries if card.is_land]
    spells = [
        (card, count)
        for card, count in deck_entries
        if not card.is_land and not card.is_creature
    ]

    lines = [
        f"Avg score: {summary.average_score:.2f}",
        f"Spells cast: {summary.average_spells_cast:.2f}",
        f"Mana spent: {summary.average_mana_spent:.2f}",
        f"Board impact (pow+tough+impact): {summary.average_board_impact:.2f}",
        f"Spell impact: {summary.average_spell_impact:.2f}",
        f"Interaction: {summary.average_interaction:.2f} (counters {summary.average_counters:.2f})",
        f"Card draw: {summary.average_card_draw:.2f}",
        f"Finishers: {summary.average_finishers:.2f}",
        f"Color screw turns: {summary.average_color_screw:.2f}",
        f"Missed land drops: {summary.average_land_miss:.2f}",
        "Deck:",
    ]
    lines.extend(format_section("Creatures", creatures))
    lines.extend(format_section("Spells", spells))
    lines.extend(format_section("Lands", lands))
    return "\n".join(lines)


def example_simulation_trace(deck: DeckList, config: SimulationConfig) -> SimulationTrace:
    rng = random.Random(config.seed) if config.seed is not None else random.Random()
    simulator = DrawSimulator(deck, rng)
    return simulator.simulate_with_trace(config.turns)


def format_simulation_trace(trace: SimulationTrace) -> str:
    lines: list[str] = []
    lines.append(
        "Opening hand: " + ", ".join(card.name for card in trace.opening_hand)
    )

    totals = dict(
        spells_cast=0,
        mana_spent=0,
        board_impact=0.0,
        spell_impact=0.0,
        interaction=0,
        counters=0,
        card_draw=0,
        finishers=0,
        color_screw=0,
        land_miss=0,
    )

    for turn in trace.turns:
        lines.append(f"Turn {turn.turn}:")
        if turn.draw is None:
            lines.append("- Draw: (no card, library empty)")
        else:
            lines.append(f"- Draw: {turn.draw.name}")
        for action in turn.actions:
            lines.append(f"  {action}")

        totals["spells_cast"] += turn.spells_cast
        totals["mana_spent"] += turn.mana_spent
        totals["board_impact"] += turn.board_impact
        totals["spell_impact"] += turn.spell_impact
        totals["interaction"] += turn.interaction_spells
        totals["counters"] += turn.counterspells
        totals["card_draw"] += turn.card_draw_spells
        totals["finishers"] += turn.finishers
        totals["color_screw"] += 1 if turn.color_screw else 0
        totals["land_miss"] += 1 if turn.land_missed else 0

        running_result = GameResult(
            spells_cast=totals["spells_cast"],
            mana_spent=totals["mana_spent"],
            total_board_impact=totals["board_impact"],
            spell_impact=totals["spell_impact"],
            interaction_spells=totals["interaction"],
            counterspells=totals["counters"],
            card_draw_spells=totals["card_draw"],
            finishers=totals["finishers"],
            color_screw_turns=totals["color_screw"],
            land_drops_missed=totals["land_miss"],
        )
        lines.append(
            "  Turn summary: spells cast +"
            f"{turn.spells_cast}, mana spent +{turn.mana_spent}, board impact +{turn.board_impact:.2f}"
        )
        lines.append(
            "  Running score: "
            f"{running_result.score:.2f} (color screw {totals['color_screw']}, land drops missed {totals['land_miss']})"
        )

    lines.append(
        "Final example game score: "
        f"{trace.result.score:.2f} (spells cast {trace.result.spells_cast}, mana spent {trace.result.mana_spent})"
    )
    return "\n".join(lines)


def describe_card_rating(card: Card) -> str:
    base_board_pressure = (
        (card.power or 0) + (card.toughness or 0) + (card.impact_score if card.is_creature else 0)
    )
    spell_impact = 0.0 if card.is_creature else card.impact_score
    interaction = 1 if "removal" in card.tags else 0
    counters = 1 if "counter" in card.tags else 0
    draw_spells = 1 if "card_draw" in card.tags else 0
    finishers = 1 if "finisher" in card.tags else 0

    evaluation = GameResult(
        spells_cast=1,
        mana_spent=card.mana_cost,
        total_board_impact=base_board_pressure,
        spell_impact=spell_impact,
        interaction_spells=interaction,
        counterspells=counters,
        card_draw_spells=draw_spells,
        finishers=finishers,
        color_screw_turns=0,
        land_drops_missed=0,
    )

    board_pressure_score = base_board_pressure * 0.25
    spell_impact_score = spell_impact * 0.6
    mana_score = card.mana_cost * 0.1
    interaction_score = interaction * 0.9 + counters * 0.7
    draw_score = draw_spells * 0.8
    finisher_score = finishers * 1.5

    lines = [
        f"Casting {card.name} with available mana would add approximately {evaluation.score:.2f} to the game score.",
        "  - Spells cast: +1 (adds 1.20)",
        f"  - Mana spent: +{card.mana_cost} (adds {mana_score:.2f})",
    ]

    if card.is_creature:
        lines.append(
            "  - Creature board impact per turn: "
            f"{base_board_pressure:.2f} (adds {board_pressure_score:.2f} to the score each turn it stays)"
        )
    elif spell_impact:
        lines.append(
            f"  - Spell impact on resolution: +{spell_impact:.2f} (adds {spell_impact_score:.2f})"
        )

    if interaction:
        lines.append(f"  - Counts as interaction: adds {interaction * 0.9:.2f}")
    if counters:
        lines.append(f"  - Counts as counterspell: adds {counters * 0.7:.2f}")
    if draw_spells:
        lines.append(f"  - Card draw utility: adds {draw_score:.2f}")
    if finishers:
        lines.append(f"  - Finisher bonus: adds {finisher_score:.2f}")

    if not any([interaction, counters, draw_spells, finishers, base_board_pressure, spell_impact]):
        lines.append("  - This spell does not add immediate impact beyond being cast.")

    return "\n".join(lines)


def _has_colors(spell_colors: Sequence[str], mana_pool: Mapping[str, int]) -> bool:
    if not spell_colors:
        return True
    required = Counter(spell_colors)
    for color, need in required.items():
        if mana_pool.get(color, 0) < need:
            return False
    return True


def _spend_mana(spell_colors: Sequence[str], mana_pool: MutableMapping[str, int], cost: int) -> None:
    required = Counter(spell_colors)
    paid = 0
    for color, need in required.items():
        available = mana_pool.get(color, 0)
        used = min(available, need)
        mana_pool[color] = available - used
        paid += used
    colorless_needed = max(0, cost - paid)
    if colorless_needed:
        spend_sources: List[str] = [c for c, v in mana_pool.items() for _ in range(v)]
        spend_sources = spend_sources[:colorless_needed]
        for color in spend_sources:
            mana_pool[color] -= 1
