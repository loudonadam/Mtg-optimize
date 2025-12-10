import io
import sys
from pathlib import Path
from urllib.error import HTTPError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mtg_optimize.decklist import DecklistError, fetch_card_metadata


def test_fetch_card_metadata_reports_not_found(monkeypatch):
    """User-friendly message is raised when Scryfall returns 404."""

    def fake_urlopen(url, timeout):
        raise HTTPError(url, 404, "Not Found", hdrs=None, fp=io.BytesIO(b'{"details":"No card found"}'))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(DecklistError) as excinfo:
        fetch_card_metadata("Nonexistent Card")

    assert "Nonexistent Card" in str(excinfo.value)
    assert "404" in str(excinfo.value)
