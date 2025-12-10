"""MTG deck optimization toolkit."""

from .card import Card, CardChoice, DeckList
from .simulator import simulate_deck
from .search import brute_force_decks, rank_decks

__all__ = [
    "Card",
    "CardChoice",
    "DeckList",
    "simulate_deck",
    "brute_force_decks",
    "rank_decks",
]
