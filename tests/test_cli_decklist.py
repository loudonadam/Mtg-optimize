import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mtg_optimize import cli
from mtg_optimize.card import Card


def test_decklist_defaults_to_pool(monkeypatch, tmp_path, capsys):
    deck_text = "4 Test Spell\n6 Forest\n"
    deck_path = tmp_path / "deck.txt"
    deck_path.write_text(deck_text)

    rules_path = tmp_path / "rules.json"
    rules_path.write_text("{}")

    def fake_fetch_card(name):
        return Card(
            name=name,
            type_line="land" if name == "Forest" else "spell",
            mana_cost=0,
            colors=("G",) if "Spell" in name else tuple(),
            is_basic_land=name == "Forest",
        )

    captured = {}

    def fake_brute_force(choices, config, progress=None):
        captured["choices"] = choices
        captured["config"] = config
        captured["progress"] = progress
        if progress:
            progress(0, 1)
        return ["deck"]

    def fake_rank(decks, config, progress=None):
        captured["rank_config"] = config
        captured["rank_progress"] = progress
        if progress:
            progress(1, 1)

        class Dummy:
            average_score = 1.0
            deck = {}

        return [Dummy()]

    monkeypatch.setattr(cli, "fetch_card_metadata", fake_fetch_card)
    monkeypatch.setattr(cli, "brute_force_decks", fake_brute_force)
    monkeypatch.setattr(cli, "rank_decks", fake_rank)
    monkeypatch.setattr(cli, "summary_string", lambda summary: "summary")
    monkeypatch.setattr(cli, "example_simulation_trace", lambda deck, config: "trace")
    monkeypatch.setattr(cli, "format_simulation_trace", lambda trace: "trace output")
    monkeypatch.setattr(cli, "describe_card_rating", lambda card: "rating")

    argv = [
        "prog",
        "--decklist",
        str(deck_path),
        "--rules",
        str(rules_path),
        "--deck-size",
        "10",
        "--games",
        "1",
        "--turns",
        "1",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.chdir(tmp_path)

    cli.main()

    # Pool mode allows choosing fewer than the provided counts and caps spells at four.
    spell_choice = next(c for c in captured["choices"] if c.card.name == "Test Spell")
    land_choice = next(c for c in captured["choices"] if c.card.name == "Forest")

    assert spell_choice.min_count == 0
    assert spell_choice.max_count == 4  # four-of rule enforced
    assert land_choice.min_count == 0
    assert land_choice.max_count == 6

    assert captured["config"].deck_size == 10
    assert captured["config"].brute_force_limit == 1

    # rank_decks receives the same config object
    assert captured["rank_config"] is captured["config"]
    assert callable(captured["progress"])
    assert callable(captured["rank_progress"])

    # CLI output is produced
    out = capsys.readouterr().out
    assert "Deck 1" in out
    assert "summary" in out


def test_decklist_accepts_names_only(monkeypatch, tmp_path):
    deck_text = "Test Spell\nIsland\nGuildgate\n"
    deck_path = tmp_path / "deck.txt"
    deck_path.write_text(deck_text)

    rules_path = tmp_path / "rules.json"
    rules_path.write_text("{}")

    def fake_fetch_card(name):
        return Card(
            name=name,
            type_line="land" if name != "Test Spell" else "spell",
            mana_cost=0,
            colors=tuple(),
            is_basic_land=name == "Island",
        )

    captured = {}

    def fake_brute_force(choices, config, progress=None):
        captured["choices"] = choices
        return ["deck"]

    def fake_rank(decks, config, progress=None):
        class Dummy:
            average_score = 1.0
            deck = {}

        return [Dummy()]

    monkeypatch.setattr(cli, "fetch_card_metadata", fake_fetch_card)
    monkeypatch.setattr(cli, "brute_force_decks", fake_brute_force)
    monkeypatch.setattr(cli, "rank_decks", fake_rank)
    monkeypatch.setattr(cli, "summary_string", lambda summary: "summary")
    monkeypatch.setattr(cli, "example_simulation_trace", lambda deck, config: "trace")
    monkeypatch.setattr(cli, "format_simulation_trace", lambda trace: "trace output")
    monkeypatch.setattr(cli, "describe_card_rating", lambda card: "rating")

    argv = [
        "prog",
        "--decklist",
        str(deck_path),
        "--rules",
        str(rules_path),
        "--deck-size",
        "70",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.chdir(tmp_path)

    cli.main()

    spell = next(c for c in captured["choices"] if c.card.name == "Test Spell")
    basic = next(c for c in captured["choices"] if c.card.name == "Island")
    non_basic = next(c for c in captured["choices"] if c.card.name == "Guildgate")

    assert spell.max_count == 4  # names-only spells default to four-of cap
    assert basic.max_count == 70  # basic lands can fill the deck
    assert non_basic.max_count == 4  # non-basic lands still respect four-of rule


def test_default_rules_are_enforced(monkeypatch, tmp_path):
    deck_text = "4 Test Spell\n"
    deck_path = tmp_path / "deck.txt"
    deck_path.write_text(deck_text)

    deck_rules = tmp_path / "deck_rules.json"
    deck_rules.write_text(json.dumps({"min_lands": 2}))

    def fake_fetch_card(name):
        return Card(
            name=name,
            type_line="sorcery",
            mana_cost=1,
            colors=("G",),
            impact_score=1.0,
        )

    monkeypatch.setattr(cli, "fetch_card_metadata", fake_fetch_card)
    monkeypatch.chdir(tmp_path)
    argv = [
        "prog",
        "--decklist",
        str(deck_path),
        "--deck-size",
        "4",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit, match="No valid decks can be constructed"):
        cli.main()


def test_decklist_loads_rules_from_source_directory(monkeypatch, tmp_path):
    deck_dir = tmp_path / "deck_data"
    run_dir = tmp_path / "runner"
    deck_dir.mkdir()
    run_dir.mkdir()

    deck_path = deck_dir / "deck.txt"
    deck_path.write_text("4 Test Spell\n")

    deck_rules = deck_dir / "deck_rules.json"
    deck_rules.write_text(json.dumps({"min_lands": 2}))

    def fake_fetch_card(name):
        return Card(
            name=name,
            type_line="sorcery",
            mana_cost=1,
            colors=("G",),
        )

    monkeypatch.setattr(cli, "fetch_card_metadata", fake_fetch_card)
    monkeypatch.chdir(run_dir)
    argv = [
        "prog",
        "--decklist",
        str(deck_path),
        "--deck-size",
        "4",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit, match="No valid decks can be constructed"):
        cli.main()
