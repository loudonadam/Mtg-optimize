from mtg_optimize.card import Card, CardChoice
from mtg_optimize.search import SearchConfig, brute_force_decks
from mtg_optimize.simulator import SimulationConfig


def _deck_signatures(decks):
    return [
        tuple(sorted(card.name for card, count in deck.items() for _ in range(count)))
        for deck in decks
    ]


def _choices():
    return [
        CardChoice(Card("One", type_line="spell"), min_count=0, max_count=2),
        CardChoice(Card("Two", type_line="spell"), min_count=0, max_count=2),
        CardChoice(Card("Three", type_line="spell"), min_count=0, max_count=2),
    ]


def test_brute_force_randomizes_with_reproducible_seed():
    limited = SearchConfig(
        deck_size=3,
        brute_force_limit=4,
        simulation=SimulationConfig(seed=5),
    )

    first = _deck_signatures(brute_force_decks(_choices(), limited))
    second = _deck_signatures(brute_force_decks(_choices(), limited))

    assert first == second  # seed ensures determinism for debugging

    alternate = _deck_signatures(
        brute_force_decks(
            _choices(),
            SearchConfig(
                deck_size=3,
                brute_force_limit=4,
                simulation=SimulationConfig(seed=6),
            ),
        )
    )

    assert alternate != first  # different seeds explore different subsets first
