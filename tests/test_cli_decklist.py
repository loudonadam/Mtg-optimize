import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mtg_optimize import cli
from mtg_optimize.card import Card


def test_decklist_defaults_to_pool(monkeypatch, tmp_path, capsys):
    deck_text = "4 Test Spell\n6 Test Land\n"
    deck_path = tmp_path / "deck.txt"
    deck_path.write_text(deck_text)

    def fake_fetch_card(name):
        return Card(
            name=name,
            type_line="land" if "Land" in name else "spell",
            mana_cost=0,
            colors=("G",) if "Spell" in name else tuple(),
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

        return [Dummy()]

    monkeypatch.setattr(cli, "fetch_card_metadata", fake_fetch_card)
    monkeypatch.setattr(cli, "brute_force_decks", fake_brute_force)
    monkeypatch.setattr(cli, "rank_decks", fake_rank)
    monkeypatch.setattr(cli, "summary_string", lambda summary: "summary")

    argv = [
        "prog",
        "--decklist",
        str(deck_path),
        "--games",
        "1",
        "--turns",
        "1",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    cli.main()

    # Pool mode allows choosing fewer than the provided counts and caps spells at four.
    spell_choice = next(c for c in captured["choices"] if c.card.name == "Test Spell")
    land_choice = next(c for c in captured["choices"] if c.card.name == "Test Land")

    assert spell_choice.min_count == 0
    assert spell_choice.max_count == 4  # four-of rule enforced
    assert land_choice.min_count == 0
    assert land_choice.max_count == 6

    assert captured["config"].deck_size == 60
    assert captured["config"].brute_force_limit == 5000

    # rank_decks receives the same config object
    assert captured["rank_config"] is captured["config"]
    assert callable(captured["progress"])
    assert callable(captured["rank_progress"])

    # CLI output is produced
    out = capsys.readouterr().out
    assert "Deck 1" in out
    assert "summary" in out
