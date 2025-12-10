from __future__ import annotations

import itertools
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

    option_spaces = [tuple(c.iter_options()) for c in choices]
    total_combinations = 1
    for opts in option_spaces:
        total_combinations *= len(opts)
    target = config.brute_force_limit or total_combinations

    counter = 0
    last_report = time.monotonic()

    def maybe_report() -> None:
        nonlocal last_report
        if progress is None:
            return
        now = time.monotonic()
        if counter == target or now - last_report >= 1:
            progress(counter, target)
            last_report = now

    if progress:
        progress(0, target)

    for counts in itertools.product(*option_spaces):
        if config.brute_force_limit is not None and counter >= config.brute_force_limit:
            break
        counter += 1
        if sum(counts) != config.deck_size:
            maybe_report()
            continue
        deck: DeckList = DeckList()
        for idx in range(total_cards):
            deck[choices[idx].card] = counts[idx]
        decks.append(deck)
        maybe_report()

    if progress:
        progress(counter, target)

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
