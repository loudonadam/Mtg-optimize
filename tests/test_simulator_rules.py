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
        tags=("counter",),
    )

    deck = {cheap_spell: 6, tapped_land: 1}
    simulator = DrawSimulator(deck, _StaticRng())
    trace = simulator.simulate_with_trace(turns=2)

    # Turn 1: land enters tapped, cannot cast spells
    assert trace.turns[0].land_missed is False
    assert trace.turns[0].spells_cast == 0

    # Turn 2: land untaps and can pay for the blue spell
    assert trace.turns[1].spells_cast == 1


def test_choose_color_lands_pay_correct_color_after_untap():
    thriving_land = Card(
        name="Thriving Grove",
        type_line="Land",
        produced_mana=("W", "U", "B", "R", "G"),
        enters_tapped=True,
    )
    red_spell = Card(
        name="Lightning Bolt",
        type_line="Instant",
        mana_cost=1,
        mana_cost_symbols=("R",),
        colors=("R",),
        tags=("removal",),
    )

    deck = {red_spell: 6, thriving_land: 1}
    simulator = DrawSimulator(deck, _StaticRng())
    trace = simulator.simulate_with_trace(turns=2)

    # Turn 1: land is tapped and unusable
    assert trace.turns[0].spells_cast == 0

    # Turn 2: land untaps and can produce red to cast Lightning Bolt
    assert trace.turns[1].spells_cast == 1
    assert any("Tapped Thriving Grove for R mana" in action for action in trace.turns[1].actions)


def test_noninteractive_spells_wait_for_creatures():
    pump_spell = Card(
        name="Shape the Sands",
        type_line="Instant",
        mana_cost=1,
        mana_cost_symbols=("G",),
        colors=("G",),
    )
    land = Card(name="Forest", type_line="Land", produced_mana=("G",))

    deck = {land: 7, pump_spell: 2}
    simulator = DrawSimulator(deck, _StaticRng())
    trace = simulator.simulate_with_trace(turns=2)

    assert trace.turns[0].spells_cast == 0
    assert trace.turns[1].spells_cast == 0


def test_buffs_cast_after_creature_hits_battlefield():
    land = Card(name="Forest", type_line="Land", produced_mana=("G",))
    pump_spell = Card(
        name="Shape the Sands",
        type_line="Instant",
        mana_cost=1,
        mana_cost_symbols=("G",),
        colors=("G",),
    )
    creature = Card(
        name="Elvish Mystic",
        type_line="Creature",
        mana_cost=1,
        mana_cost_symbols=("G",),
        power=1,
        toughness=1,
        colors=("G",),
    )

    deck = {land: 7, pump_spell: 1, creature: 1}
    simulator = DrawSimulator(deck, _StaticRng())
    trace = simulator.simulate_with_trace(turns=2)

    # Turn 1: pump spell is held because no creatures are on the battlefield yet
    assert trace.turns[0].spells_cast == 1
    assert any(
        "Held Shape the Sands until a creature is on the battlefield"
        in action
        for action in trace.turns[0].actions
    )

    # Turn 2: with a creature now in play, the pump spell can be cast
    assert trace.turns[1].spells_cast == 1
