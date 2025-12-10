from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Sequence

from .card import CardChoice, DeckList
from .simulator import SimulationConfig, SimulationSummary, simulate_deck


@dataclass
class SearchConfig:
    deck_size: int = 60
    brute_force_limit: int | None = 5000
    simulation: SimulationConfig = field(default_factory=SimulationConfig)


def brute_force_decks(
    choices: Sequence[CardChoice],
    config: SearchConfig,
    progress: Callable[[int, int], None] | None = None,
) -> List[DeckList]:
    """Generate deck lists that meet the supplied constraints.

    The combinatorial search is bounded by ``brute_force_limit``. If the
    limit is reached, any remaining combinations are skipped.
    """

    decks: List[DeckList] = []
    total_cards = len(choices)

    # Precompute suffix bounds to prune impossible branches quickly.
    min_suffix: List[int] = [0] * (total_cards + 1)
    max_suffix: List[int] = [0] * (total_cards + 1)
    for idx in range(total_cards - 1, -1, -1):
        min_suffix[idx] = min_suffix[idx + 1] + choices[idx].min_count
        max_suffix[idx] = max_suffix[idx + 1] + choices[idx].max_count

    target = config.brute_force_limit or 0
    counter = 0  # number of valid decks collected
    last_report = time.monotonic()

    def report(force: bool = False, total_override: int | None = None) -> None:
        nonlocal last_report
        if progress is None:
            return
        total = total_override if total_override is not None else target
        now = time.monotonic()
        if force or total == 0 or now - last_report >= 1 or counter == total:
            progress(counter, total)
            last_report = now

    if progress:
        report(force=True)

    def backtrack(slot: int, remaining: int, chosen: List[int]) -> None:
        nonlocal counter
        if config.brute_force_limit is not None and counter >= config.brute_force_limit:
            return

        if remaining < min_suffix[slot] or remaining > max_suffix[slot]:
            return

        if slot == total_cards:
            if remaining == 0:
                deck: DeckList = DeckList()
                for idx, count in enumerate(chosen):
                    deck[choices[idx].card] = count
                decks.append(deck)
                counter += 1
                report()
            return

        choice = choices[slot]
        min_next = min_suffix[slot + 1]
        max_next = max_suffix[slot + 1]
        max_allowed = min(choice.max_count, remaining - min_next)
        for count in range(choice.min_count, max_allowed + 1):
            next_remaining = remaining - count
            if next_remaining > max_next:
                continue
            chosen.append(count)
            backtrack(slot + 1, next_remaining, chosen)
            chosen.pop()

    backtrack(0, config.deck_size, [])

    if progress:
        total = target if target and counter >= target else counter
        report(force=True, total_override=total)

    return decks


def rank_decks(
    decks: Iterable[DeckList],
    config: SearchConfig,
    progress: Callable[[int, int], None] | None = None,
) -> List[SimulationSummary]:
    """Evaluate and sort decks by average score."""

    deck_list = list(decks)
    total = len(deck_list)
    processed = 0

    if progress:
        progress(processed, total)

    summaries = []
    last_report = time.monotonic()
    for deck in deck_list:
        summaries.append(simulate_deck(deck, config.simulation))
        processed += 1
        if progress:
            now = time.monotonic()
            if processed == total or now - last_report >= 1:
                progress(processed, total)
                last_report = now

    return sorted(summaries, key=lambda s: s.average_score, reverse=True)
