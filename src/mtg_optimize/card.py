from __future__ import annotations

from dataclasses import dataclass, field
from typing import Counter, Iterable, List, Sequence, Tuple

Color = str


@dataclass(frozen=True)
class Card:
    """Minimal MTG card descriptor used by the simulator.

    Attributes:
        name: Display name.
        type_line: Simplified type. Only ``"land"`` and ``"spell"``
            are differentiated by the simulator.
        mana_cost: Converted mana cost of the spell. Lands should
            use ``0``.
        colors: Iterable of color symbols a spell requires or a land
            can produce (e.g. ``["G", "U"]``). For colorless spells
            or basic lands that produce colorless mana, leave empty.
        is_basic_land: True for basic lands (unlimited copies), False otherwise.
    """

    name: str
    type_line: str
    mana_cost: int = 0
    colors: Tuple[Color, ...] = field(default_factory=tuple)
    is_basic_land: bool = False

    @property
    def is_land(self) -> bool:
        return self.type_line.lower() == "land"


@dataclass(frozen=True)
class CardChoice:
    """Input constraints for deck search.

    The searcher can select any count in ``range(min_count, max_count + 1)``
    for the given card.
    """

    card: Card
    min_count: int
    max_count: int

    def iter_options(self) -> Iterable[int]:
        return range(self.min_count, self.max_count + 1)


DeckList = Counter[Card]


def flatten_deck(deck: DeckList) -> List[Card]:
    """Expand a ``Counter`` deck into a list of individual cards."""

    expanded: List[Card] = []
    for card, count in deck.items():
        expanded.extend([card] * count)
    return expanded


def deck_size(deck: DeckList) -> int:
    """Return the total number of cards in the deck."""

    return sum(deck.values())


def color_string(colors: Sequence[Color]) -> str:
    return ",".join(colors) if colors else "colorless"
