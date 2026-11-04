# ===================== NY FIL AV CLAUDE (2026-11-03) =====================
# Produktlistan som röstvägledningen slår upp varunamn i. Motorn känner bara till
# ProductCatalog, så butikens riktiga sortiment kan kopplas in senare utan ändringar i motorn.
# =========================================================================
"""
catalog.py - Varunamn och lite mer om varan, per EAN.

Kartans fält "info" (valfritt) läses upp efter namnet: en text eller en lista, t.ex.
    "info": ["140 gram", "hylla 3"]   ->   "Tomatpure. 140 gram. Hylla 3."
Högst MAX_DETAILS delar, eftersom varje ord kostar tid innan användaren kan gå vidare.
"""
from __future__ import annotations

import json
from typing import Any, List, Mapping, Optional, Protocol, Sequence, Tuple

from phrases import guidance_text

MAX_DETAILS = 2
MAX_DETAIL_CHARS = 40


class ProductCatalog(Protocol):
    def name_of(self, ean: str) -> Optional[str]:
        """Varans namn, eller None om varan inte finns i listan."""

    def details_of(self, ean: str) -> Tuple[str, ...]:
        """Det som läses upp efter namnet (kan vara tomt)."""


def parse_details(raw: Any) -> Tuple[str, ...]:
    """Kartans "info": text eller lista. Tomma delar tas bort, för långa kortas inte utan ger ValueError."""
    if raw is None or raw == "":
        return ()
    items = [raw] if isinstance(raw, str) else raw
    if not isinstance(items, (list, tuple)):
        raise ValueError(f"info ska vara text eller lista, inte {type(raw).__name__}")
    details: List[str] = []
    for item in items:
        text = str(item).strip()
        if len(text) > MAX_DETAIL_CHARS:
            raise ValueError(f"info-delen {text!r} är längre än {MAX_DETAIL_CHARS} tecken")
        if text:
            details.append(text)
    if len(details) > MAX_DETAILS:
        raise ValueError(f"info har {len(details)} delar, högst {MAX_DETAILS} läses upp")
    return tuple(details)


class DictProductCatalog:
    """
    Slår upp namn i produktkartan som barcode_scanner.load_products() läser in:
    {ean: [{"namn": ..., "x": ..., ...}, ...]}. Samma vara på flera platser har samma namn.
    """

    def __init__(self, products: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
        self._products = products

    def name_of(self, ean: str) -> Optional[str]:
        candidates = self._products.get(ean)
        name = str(candidates[0].get("namn", "")).strip() if candidates else ""
        return name or None

    def details_of(self, ean: str) -> Tuple[str, ...]:
        candidates = self._products.get(ean)
        return parse_details(candidates[0].get("info")) if candidates else ()

    def announcements(self) -> List[str]:
        """Allt som kan sägas vid en bekräftelse, för att förgenerera ljudet (ingen paus första gången)."""
        texts = set()
        for ean in self._products:
            name = self.name_of(ean)
            if name:
                texts.add(guidance_text("confirmed", name=name, details=self.details_of(ean)))
        return sorted(texts)

    @classmethod
    def from_geojson(cls, path: str) -> "DictProductCatalog":
        """Läser bara ean, namn och info ur kartan. Används av replay och prewarm, där kameran saknas."""
        with open(path, encoding="utf-8") as f:
            features = json.load(f).get("features", [])
        products: dict = {}
        for feature in features:
            props = feature.get("properties", {})
            ean = str(props.get("ean", "")).strip()
            if ean:
                products.setdefault(ean, []).append({"namn": props.get("namn", ""), "info": props.get("info")})
        return cls(products)


class EmptyProductCatalog:
    """Ingen vara är känd. Alla säkra läsningar blir 'Okänd vara'."""

    def name_of(self, ean: str) -> Optional[str]:
        return None

    def details_of(self, ean: str) -> Tuple[str, ...]:
        return ()
