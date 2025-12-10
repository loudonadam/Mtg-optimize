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
    impact_score: float = 0.0


class DecklistError(RuntimeError):
    """Raised when a decklist line cannot be interpreted."""


DECKLIST_LINE = re.compile(r"^(?:(?P<count>\d+)\s+)?(?P<name>.+)$")


def _parse_line(line: str) -> tuple[str, Optional[int], float]:
    """Parse a single decklist line with optional impact score."""

    if ";" in line:
        card_part, impact_part = line.split(";", 1)
        try:
            impact_score = float(impact_part.strip() or 0)
        except ValueError:
            raise DecklistError(f"Invalid impact score in decklist line: {line!r}")
    else:
        card_part = line
        impact_score = 0.0

    match = DECKLIST_LINE.match(card_part)
    if not match:
        raise DecklistError(f"Could not parse decklist line: {line!r}")
    count = match.group("count")
    return match.group("name"), int(count) if count else None, impact_score


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
        name, count, impact_score = _parse_line(line)
        entries.append(DecklistEntry(name=name, count=count, impact_score=impact_score))
    return entries


def _parse_mana_cost_symbols(mana_cost: str | None) -> tuple[tuple[str, ...], int]:
    if not mana_cost:
        return tuple(), 0

    symbols: list[str] = []
    generic = 0
    for token in mana_cost.replace("}{", " }").replace("{", "").replace("}", "").split():
        if not token:
            continue
        if token.isdigit():
            generic += int(token)
        elif token in {"W", "U", "B", "R", "G", "C"}:
            symbols.append(token)
        else:
            # Hybrid and phyrexian symbols are treated as color-flexible and
            # contribute to generic cost when we cannot model them precisely.
            generic += 1
    return tuple(symbols), generic


def fetch_card_metadata(name: str) -> Card:
    """Lookup card details using the public Scryfall API.

    The returned ``Card`` uses the card's converted mana cost (rounded to an
    integer) and color identity. Lands are detected from the type line. Lands
    capture their produced mana colors and whether they enter tapped so the
    simulator can honor timing and tapping rules.
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
    printed_cost = payload.get("mana_cost")
    mana_symbols, generic_cost = _parse_mana_cost_symbols(printed_cost)
    try:
        mana_cost = int(round(float(cmc)))
    except (TypeError, ValueError):
        mana_cost = 0

    produced_mana = tuple(payload.get("produced_mana", []) if is_land else [])
    oracle_text = payload.get("oracle_text", "") or ""
    enters_tapped = is_land and "enters the battlefield tapped" in oracle_text.lower()

    return Card(
        name=payload.get("name", name),
        type_line=type_line or ("land" if is_land else "spell"),
        mana_cost=0 if is_land else mana_cost,
        colors=colors,
        is_basic_land=is_basic,
        mana_cost_symbols=mana_symbols if not is_land else tuple(),
        generic_cost=generic_cost if not is_land else 0,
        produced_mana=produced_mana if is_land else tuple(),
        enters_tapped=enters_tapped,
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
