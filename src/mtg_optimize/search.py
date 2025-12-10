from __future__ import annotations

import time
import random
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable, Iterable, List, Sequence

from .card import CardChoice, DeckList
from .simulator import SimulationConfig, SimulationSummary, simulate_deck


@dataclass
class SearchConfig:
    deck_size: int = 60
    brute_force_limit: int | None = 5000
    deck_rules: "DeckRules | None" = None
    simulation: SimulationConfig = field(default_factory=SimulationConfig)


@dataclass
class DeckCount:
    total: int
    estimated: bool = False
    lower_bound: int | None = None
    upper_bound: int | None = None


@dataclass
class DeckRules:
    min_lands: int | None = None
    max_lands: int | None = None
    min_creatures: int | None = None
    max_creatures: int | None = None

    def validate(self, lands: int, creatures: int) -> bool:
        if self.min_lands is not None and lands < self.min_lands:
            return False
        if self.max_lands is not None and lands > self.max_lands:
            return False
        if self.min_creatures is not None and creatures < self.min_creatures:
            return False
        if self.max_creatures is not None and creatures > self.max_creatures:
            return False
        return True


def count_possible_decks(
    choices: Sequence[CardChoice],
    deck_size: int,
    rules: DeckRules | None = None,
    estimate_cutoff: int = 10_000_000,
) -> DeckCount:
    """Return the total number of distinct decks that satisfy the constraints.

    When the search space is massive, counting caps at ``estimate_cutoff`` and
    reports the result as an estimate so the CLI can stay responsive.
    """

    total_cards = len(choices)

    if rules is None:
        # Simple bounded knapsack count to avoid enumerating each combination.
        ways = [0] * (deck_size + 1)
        ways[0] = 1
        for choice in choices:
            next_ways = [0] * (deck_size + 1)
            for current_cards in range(deck_size + 1):
                if ways[current_cards] == 0:
                    continue
                for take in range(choice.min_count, choice.max_count + 1):
                    total = current_cards + take
                    if total > deck_size:
                        break
                    next_ways[total] += ways[current_cards]
                    if next_ways[total] > estimate_cutoff:
                        next_ways[total] = estimate_cutoff
            ways = next_ways
        total = ways[deck_size]
        estimated = total >= estimate_cutoff
        lower_bound = estimate_cutoff if estimated else total
        upper_bound = total + estimate_cutoff if estimated else total
        return DeckCount(
            total=total,
            estimated=estimated,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
        )

    min_lands = rules.min_lands or 0
    max_lands = rules.max_lands or deck_size
    min_creatures = rules.min_creatures or 0
    max_creatures = rules.max_creatures or deck_size
    estimated = False

    @lru_cache(maxsize=None)
    def helper(slot: int, remaining: int, lands: int, creatures: int) -> int:
        nonlocal estimated
        if remaining < 0:
            return 0
        if lands > max_lands or creatures > max_creatures:
            return 0
        if slot == total_cards:
            if remaining == 0 and rules.validate(lands, creatures):
                return 1
            return 0

        choice = choices[slot]
        total = 0
        is_land = choice.card.is_land
        is_creature = choice.card.is_creature

        for take in range(choice.min_count, choice.max_count + 1):
            next_remaining = remaining - take
            if next_remaining < 0:
                break
            next_lands = lands + (take if is_land else 0)
            next_creatures = creatures + (take if is_creature else 0)

            result = helper(slot + 1, next_remaining, next_lands, next_creatures)
            total += result
            if total > estimate_cutoff:
                estimated = True
                return estimate_cutoff
        return total

    total = helper(0, deck_size, 0, 0)
    lower_bound = estimate_cutoff if estimated else total
    upper_bound = total + estimate_cutoff if estimated else total
    return DeckCount(
        total=total,
        estimated=estimated,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
    )


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
    rng = random.Random(config.simulation.seed)
    shuffled_choices = list(choices)
    rng.shuffle(shuffled_choices)
    total_cards = len(shuffled_choices)

    # Precompute suffix bounds to prune impossible branches quickly.
    min_suffix: List[int] = [0] * (total_cards + 1)
    max_suffix: List[int] = [0] * (total_cards + 1)
    land_min_suffix: List[int] = [0] * (total_cards + 1)
    land_max_suffix: List[int] = [0] * (total_cards + 1)
    creature_min_suffix: List[int] = [0] * (total_cards + 1)
    creature_max_suffix: List[int] = [0] * (total_cards + 1)
    for idx in range(total_cards - 1, -1, -1):
        choice = shuffled_choices[idx]
        min_suffix[idx] = min_suffix[idx + 1] + choice.min_count
        max_suffix[idx] = max_suffix[idx + 1] + choice.max_count
        if choice.card.is_land:
            land_min_suffix[idx] = land_min_suffix[idx + 1] + choice.min_count
            land_max_suffix[idx] = land_max_suffix[idx + 1] + choice.max_count
        else:
            land_min_suffix[idx] = land_min_suffix[idx + 1]
            land_max_suffix[idx] = land_max_suffix[idx + 1]
        if choice.card.is_creature:
            creature_min_suffix[idx] = creature_min_suffix[idx + 1] + choice.min_count
            creature_max_suffix[idx] = creature_max_suffix[idx + 1] + choice.max_count
        else:
            creature_min_suffix[idx] = creature_min_suffix[idx + 1]
            creature_max_suffix[idx] = creature_max_suffix[idx + 1]

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

    rules = config.deck_rules

    def rules_pruned(lands: int, creatures: int, slot: int) -> bool:
        if rules is None:
            return False
        min_lands_left = land_min_suffix[slot]
        max_lands_left = land_max_suffix[slot]
        min_creatures_left = creature_min_suffix[slot]
        max_creatures_left = creature_max_suffix[slot]

        if rules.min_lands is not None and lands + max_lands_left < rules.min_lands:
            return True
        if rules.max_lands is not None and lands + min_lands_left > rules.max_lands:
            return True
        if (
            rules.min_creatures is not None
            and creatures + max_creatures_left < rules.min_creatures
        ):
            return True
        if (
            rules.max_creatures is not None
            and creatures + min_creatures_left > rules.max_creatures
        ):
            return True
        return False

    def backtrack(slot: int, remaining: int, chosen: List[int], lands: int, creatures: int) -> None:
        nonlocal counter
        if config.brute_force_limit is not None and counter >= config.brute_force_limit:
            return

        if remaining < min_suffix[slot] or remaining > max_suffix[slot]:
            return

        if rules_pruned(lands, creatures, slot):
            return

        if slot == total_cards:
            if remaining == 0 and (rules is None or rules.validate(lands, creatures)):
                deck: DeckList = DeckList()
                for idx, count in enumerate(chosen):
                    deck[shuffled_choices[idx].card] = count
                decks.append(deck)
                counter += 1
                report()
            return

        choice = shuffled_choices[slot]
        min_next = min_suffix[slot + 1]
        max_next = max_suffix[slot + 1]
        max_allowed = min(choice.max_count, remaining - min_next)
        counts = list(range(choice.min_count, max_allowed + 1))
        rng.shuffle(counts)
        for count in counts:
            next_remaining = remaining - count
            if next_remaining > max_next:
                continue
            chosen.append(count)
            backtrack(
                slot + 1,
                next_remaining,
                chosen,
                lands + (count if choice.card.is_land else 0),
                creatures + (count if choice.card.is_creature else 0),
            )
            chosen.pop()

    backtrack(0, config.deck_size, [], 0, 0)

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
    rules = config.deck_rules
    if rules is not None:
        filtered: List[DeckList] = []
        for deck in deck_list:
            lands = sum(count for card, count in deck.items() if card.is_land)
            creatures = sum(count for card, count in deck.items() if card.is_creature)
            if rules.validate(lands, creatures):
                filtered.append(deck)
        deck_list = filtered
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
