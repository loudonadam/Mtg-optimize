import io
import sys
from pathlib import Path
from urllib.error import HTTPError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mtg_optimize.decklist import DecklistError, fetch_card_metadata, parse_decklist_lines


def test_fetch_card_metadata_reports_not_found(monkeypatch):
    """User-friendly message is raised when Scryfall returns 404."""

    def fake_urlopen(url, timeout):
        raise HTTPError(url, 404, "Not Found", hdrs=None, fp=io.BytesIO(b'{"details":"No card found"}'))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(DecklistError) as excinfo:
        fetch_card_metadata("Nonexistent Card")

    assert "Nonexistent Card" in str(excinfo.value)
    assert "404" in str(excinfo.value)


def test_parse_decklist_lines_supports_impact_scores():
    entries = parse_decklist_lines(["4 Lightning Bolt;2.5", "Forest;0.5"])

    assert len(entries) == 2
    assert entries[0].name == "Lightning Bolt"
    assert entries[0].count == 4
    assert entries[0].impact_score == 2.5
    assert entries[1].name == "Forest"
    assert entries[1].count is None
    assert entries[1].impact_score == 0.5


def test_parse_decklist_lines_rejects_bad_impact_scores():
    with pytest.raises(DecklistError):
        parse_decklist_lines(["Ponder;bad"])
