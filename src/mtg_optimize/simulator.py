from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Counter, Iterable, List, Mapping, MutableMapping, Sequence

from .card import Card, DeckList, deck_size, flatten_deck


@dataclass
class GameResult:
    spells_cast: int
    mana_spent: int
    total_board_power: int
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
        board_pressure = self.total_board_power * 0.3 + self.finishers * 1.5
        interaction = self.interaction_spells * 0.9 + self.counterspells * 0.7
        resilience = self.card_draw_spells * 0.8
        return proactive + board_pressure + interaction + resilience - penalties


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
    average_board_power: float
    average_interaction: float
    average_counters: float
    average_card_draw: float
    average_finishers: float
    average_color_screw: float
    average_land_miss: float


class DrawSimulator:
    def __init__(self, deck: DeckList, rng: random.Random):
        self.deck = deck
        self.rng = rng

    def simulate(self, turns: int) -> GameResult:
        library = flatten_deck(self.deck)
        self.rng.shuffle(library)

        hand = [library.pop() for _ in range(7)]
        battlefield: List[Card] = []
        spells_cast = 0
        mana_spent = 0
        total_board_power = 0
        interaction_spells = 0
        counterspells = 0
        card_draw_spells = 0
        finishers = 0
        color_screw_turns = 0
        land_drops_missed = 0

        for _turn in range(1, turns + 1):
            if library:
                hand.append(library.pop())
            mana_pool: Counter[str] = Counter()

            land_played_this_turn = False
            for idx, card in enumerate(list(hand)):
                if card.is_land:
                    hand.pop(idx)
                    battlefield.append(card)
                    land_played_this_turn = True
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
            spells_cast_this_turn = 0
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
                casted_indices.append(idx)
                battlefield.append(card)

                if "removal" in card.tags:
                    interaction_spells += 1
                if "counter" in card.tags:
                    counterspells += 1
                if "card_draw" in card.tags:
                    card_draw_spells += 1
                if "finisher" in card.tags:
                    finishers += 1

            for idx in sorted(casted_indices, reverse=True):
                hand.pop(idx)

            board_power = sum(card.power or 0 for card in battlefield if not card.is_land)
            total_board_power += board_power

            if castable_indices and not spells_cast_this_turn:
                color_screw_turns += 1
            elif not castable_indices and sum(mana_pool.values()) > 0:
                color_screw_turns += 1

        return GameResult(
            spells_cast=spells_cast,
            mana_spent=mana_spent,
            total_board_power=total_board_power,
            interaction_spells=interaction_spells,
            counterspells=counterspells,
            card_draw_spells=card_draw_spells,
            finishers=finishers,
            color_screw_turns=color_screw_turns,
            land_drops_missed=land_drops_missed,
        )


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
        average_board_power=avg("total_board_power"),
        average_interaction=avg("interaction_spells"),
        average_counters=avg("counterspells"),
        average_card_draw=avg("card_draw_spells"),
        average_finishers=avg("finishers"),
        average_color_screw=avg("color_screw_turns"),
        average_land_miss=avg("land_drops_missed"),
    )


def summary_string(summary: SimulationSummary) -> str:
    lines = [
        f"Avg score: {summary.average_score:.2f}",
        f"Spells cast: {summary.average_spells_cast:.2f}",
        f"Mana spent: {summary.average_mana_spent:.2f}",
        f"Board power: {summary.average_board_power:.2f}",
        f"Interaction: {summary.average_interaction:.2f} (counters {summary.average_counters:.2f})",
        f"Card draw: {summary.average_card_draw:.2f}",
        f"Finishers: {summary.average_finishers:.2f}",
        f"Color screw turns: {summary.average_color_screw:.2f}",
        f"Missed land drops: {summary.average_land_miss:.2f}",
        "Deck:",
    ]
    for card, count in summary.deck.items():
        if count > 0:
            lines.append(f"{count} {card.name}")
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
