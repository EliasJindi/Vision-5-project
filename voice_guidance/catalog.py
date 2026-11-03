# ===================== NY FIL AV CLAUDE (2026-11-03) =====================
# Produktlistan som röstvägledningen slår upp varunamn i. Motorn känner bara till
# ProductCatalog, så butikens riktiga sortiment kan kopplas in senare utan ändringar i motorn.
# =========================================================================
"""
catalog.py - Varunamn per EAN.
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Optional, Protocol, Sequence


class ProductCatalog(Protocol):
    def name_of(self, ean: str) -> Optional[str]:
        """Varans namn, eller None om varan inte finns i listan."""


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

    @classmethod
    def from_geojson(cls, path: str) -> "DictProductCatalog":
        """Läser bara ean och namn ur kartan. Används av replay, där kameran och depthai saknas."""
        with open(path, encoding="utf-8") as f:
            features = json.load(f).get("features", [])
        products: dict = {}
        for feature in features:
            props = feature.get("properties", {})
            ean = str(props.get("ean", "")).strip()
            if ean:
                products.setdefault(ean, []).append({"namn": props.get("namn", "")})
        return cls(products)


class EmptyProductCatalog:
    """Ingen vara är känd. Alla säkra läsningar blir 'Okänd vara'."""

    def name_of(self, ean: str) -> Optional[str]:
        return None
