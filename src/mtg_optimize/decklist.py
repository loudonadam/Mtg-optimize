from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from dataclasses import dataclass
from typing import Iterable, List, Optional

from .card import Card


@dataclass
class DecklistEntry:
    name: str
    count: Optional[int]


class DecklistError(RuntimeError):
    """Raised when a decklist line cannot be interpreted."""


DECKLIST_LINE = re.compile(r"^(?:(?P<count>\d+)\s+)?(?P<name>.+)$")


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
        count = match.group("count")
        entries.append(DecklistEntry(name=match.group("name"), count=int(count) if count else None))
    return entries


def fetch_card_metadata(name: str) -> Card:
    """Lookup card details using the public Scryfall API.

    The returned ``Card`` uses the card's converted mana cost (rounded to an
    integer) and color identity. Lands are detected from the type line.
    """

    base_url = "https://api.scryfall.com/cards/named"
    query = urllib.parse.urlencode({"exact": name})
    url = f"{base_url}?{query}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:  # pragma: no cover - network
            payload = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:  # pragma: no cover - network
        detail = _extract_error_detail(exc)
        raise DecklistError(
            f"Scryfall lookup failed for {name!r} (HTTP {exc.code}){detail}"
        ) from exc
    except URLError as exc:  # pragma: no cover - network
        raise DecklistError(f"Scryfall lookup failed for {name!r}: {exc.reason}") from exc
    type_line = payload.get("type_line", "")
    lowered_type = type_line.lower()
    is_land = "land" in lowered_type
    is_basic = is_land and "basic" in lowered_type
    colors = tuple(payload.get("color_identity") or payload.get("colors", []))
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
        is_basic_land=is_basic,
    )


def _extract_error_detail(exc: HTTPError) -> str:
    try:
        body = exc.read()
    except Exception:
        return ""
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        return ""
    detail = payload.get("details") or payload.get("error") or payload.get("message")
    return f": {detail}" if detail else ""
