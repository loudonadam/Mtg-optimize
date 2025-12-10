from mtg_optimize.card import Card
from mtg_optimize.simulator import DrawSimulator, LandPermanent, _can_pay_for_spell, _pay_for_spell


def test_tapped_land_cannot_pay_spell():
    tapped_land = Card(
        name="Thornwood Falls",
        type_line="Land",
        produced_mana=("G", "U"),
        enters_tapped=True,
    )
    land_perm = LandPermanent(card=tapped_land, tapped=True)

    spell = Card(
        name="Lose Focus",
        type_line="Instant",
        mana_cost=2,
        mana_cost_symbols=("U",),
        generic_cost=1,
        colors=("U",),
    )

    assert _can_pay_for_spell(spell, [land_perm]) is False


def test_payment_taps_required_lands():
    land = Card(name="Island", type_line="Land", produced_mana=("U",))
    land_two = Card(name="Forest", type_line="Land", produced_mana=("G",))
    lands = [LandPermanent(card=land), LandPermanent(card=land_two)]

    spell = Card(
        name="River Heralds' Boon",
        type_line="Instant",
        mana_cost=2,
        mana_cost_symbols=("G",),
        generic_cost=1,
        colors=("G",),
    )

    actions = _pay_for_spell(spell, lands)
    assert actions is not None
    assert all(l.tapped for l in lands)


class _StaticRng:
    def shuffle(self, seq):
        # Deterministic shuffle for tests
        return None


def test_enters_tapped_lands_only_produce_on_later_turns():
    tapped_land = Card(
        name="Thornwood Falls",
        type_line="Land",
        produced_mana=("G", "U"),
        enters_tapped=True,
    )
    cheap_spell = Card(
        name="Spell Pierce",
        type_line="Instant",
        mana_cost=1,
        mana_cost_symbols=("U",),
        colors=("U",),
    )

    deck = {cheap_spell: 6, tapped_land: 1}
    simulator = DrawSimulator(deck, _StaticRng())
    trace = simulator.simulate_with_trace(turns=2)

    # Turn 1: land enters tapped, cannot cast spells
    assert trace.turns[0].land_missed is False
    assert trace.turns[0].spells_cast == 0

    # Turn 2: land untaps and can pay for the blue spell
    assert trace.turns[1].spells_cast == 1
