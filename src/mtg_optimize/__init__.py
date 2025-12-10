"""MTG deck optimization toolkit."""

from .card import Card, CardChoice, DeckList
from .simulator import simulate_deck
from .search import DeckRules, brute_force_decks, count_possible_decks, rank_decks

__all__ = [
    "Card",
    "CardChoice",
    "DeckList",
    "DeckRules",
    "simulate_deck",
    "count_possible_decks",
    "brute_force_decks",
    "rank_decks",
]
