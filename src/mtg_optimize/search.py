from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Iterable, List, Sequence

from .card import CardChoice, DeckList
from .simulator import SimulationConfig, SimulationSummary, simulate_deck


@dataclass
class SearchConfig:
    deck_size: int = 60
    brute_force_limit: int | None = 5000
    simulation: SimulationConfig = field(default_factory=SimulationConfig)


def brute_force_decks(choices: Sequence[CardChoice], config: SearchConfig) -> List[DeckList]:
    """Generate deck lists that meet the supplied constraints.

    The combinatorial search is bounded by ``brute_force_limit``. If the
    limit is reached, any remaining combinations are skipped.
    """

    decks: List[DeckList] = []
    total_cards = len(choices)
    counter = 0
    for counts in itertools.product(*[c.iter_options() for c in choices]):
        if config.brute_force_limit is not None and counter >= config.brute_force_limit:
            break
        if sum(counts) != config.deck_size:
            continue
        deck: DeckList = DeckList()
        for idx in range(total_cards):
            deck[choices[idx].card] = counts[idx]
        decks.append(deck)
        counter += 1
    return decks


def rank_decks(decks: Iterable[DeckList], config: SearchConfig) -> List[SimulationSummary]:
    """Evaluate and sort decks by average score."""

    summaries = [simulate_deck(deck, config.simulation) for deck in decks]
    return sorted(summaries, key=lambda s: s.average_score, reverse=True)
