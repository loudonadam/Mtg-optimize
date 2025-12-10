from mtg_optimize.card import Card, CardChoice
from mtg_optimize.search import (
    DeckRules,
    SearchConfig,
    brute_force_decks,
    count_possible_decks,
)


def test_count_possible_decks_estimates_when_capped():
    choices = [
        CardChoice(Card(name="Land", type_line="Land"), min_count=0, max_count=20),
        CardChoice(Card(name="Creature", type_line="Creature"), min_count=0, max_count=20),
        CardChoice(Card(name="Spell", type_line="Instant"), min_count=0, max_count=20),
    ]

    result = count_possible_decks(choices, deck_size=20, estimate_cutoff=5)

    assert result.estimated is True
    assert result.total == 5


def test_bruteforce_respects_deck_rules():
    land = Card(name="Forest", type_line="Land")
    creature = Card(name="Elf", type_line="Creature", power=1, toughness=1)
    burn = Card(name="Bolt", type_line="Instant", mana_cost=1)

    choices = [
        CardChoice(land, min_count=0, max_count=4),
        CardChoice(creature, min_count=0, max_count=4),
        CardChoice(burn, min_count=0, max_count=4),
    ]

    rules = DeckRules(min_lands=2, max_lands=4, min_creatures=1, max_creatures=3)
    config = SearchConfig(deck_size=6, brute_force_limit=None, deck_rules=rules)

    decks = brute_force_decks(choices, config)

    assert decks  # at least one deck found
    for deck in decks:
        land_count = deck[land]
        creature_count = deck[creature]
        assert rules.min_lands <= land_count <= rules.max_lands
        assert rules.min_creatures <= creature_count <= rules.max_creatures
