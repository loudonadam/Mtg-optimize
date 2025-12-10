from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterable, List

from .card import Card


@dataclass
class DecklistEntry:
    name: str
    count: int


class DecklistError(RuntimeError):
    """Raised when a decklist line cannot be interpreted."""


DECKLIST_LINE = re.compile(r"^(?P<count>\d+)\s+(?P<name>.+)$")


def parse_decklist_lines(lines: Iterable[str]) -> List[DecklistEntry]:
    """Parse MTG text decklists like those exported by MTGO/Arena.

    Lines such as ``4 Lightning Bolt`` are accepted. Sideboard prefixes like
    ``SB:`` are ignored. Blank lines and section headers are skipped.
    """

    entries: List[DecklistEntry] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.lower().startswith("sideboard"):
            continue
        if line.startswith("SB:"):
            line = line[3:].strip()
        match = DECKLIST_LINE.match(line)
        if not match:
            raise DecklistError(f"Could not parse decklist line: {raw!r}")
        entries.append(DecklistEntry(name=match.group("name"), count=int(match.group("count"))))
    return entries


def fetch_card_metadata(name: str) -> Card:
    """Lookup card details using the public Scryfall API.

    The returned ``Card`` uses the card's converted mana cost (rounded to an
    integer) and color identity. Lands are detected from the type line.
    """

    base_url = "https://api.scryfall.com/cards/named"
    query = urllib.parse.urlencode({"exact": name})
    url = f"{base_url}?{query}"
    with urllib.request.urlopen(url, timeout=10) as resp:  # pragma: no cover - network
        payload = json.loads(resp.read().decode("utf-8"))
    type_line = payload.get("type_line", "")
    is_land = "land" in type_line.lower()
    colors = tuple(payload.get("colors", []))
    cmc = payload.get("cmc", 0)
    try:
        mana_cost = int(round(float(cmc)))
    except (TypeError, ValueError):
        mana_cost = 0

    return Card(
        name=payload.get("name", name),
        type_line="land" if is_land else "spell",
        mana_cost=0 if is_land else mana_cost,
        colors=colors,
    )
