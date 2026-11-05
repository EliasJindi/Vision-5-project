# ===================== NY FIL AV CLAUDE (2026-11-05) =====================
# Korgen: vad användaren har skannat under körningen. Elias 5/11: efter namnet ska rösten
# säga att varan är tillagd. Applikationslogik, inte vägledning: motorn vet inget om korgen,
# GuidanceSession fyller den. Kan senare tas över av t.ex. en C#-tjänst via länken.
# =========================================================================
"""
basket.py - Varorna som lagts i korgen.

En vara läggs bara till en gång: skannas samma vara igen säger rösten att den redan finns i
korgen. Antal och att ta bort varor kommer med inköpslistan, inte nu, eftersom en oavsiktlig
dubbelscanning annars skulle ge två i korgen utan att användaren märker det.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Tuple


class BasketResult(Enum):
    """Värdet är nyckeln i phrases.BASKET_PHRASES och i länkens JSON."""
    ADDED = "added"
    ALREADY = "already"


class Basket:
    def __init__(self) -> None:
        self._items: Dict[str, str] = {}   # ean -> namn, i den ordning de lades till

    def add(self, ean: str, name: str) -> BasketResult:
        if not ean or not name:
            raise ValueError("en vara i korgen behöver både EAN och namn")
        if ean in self._items:
            return BasketResult.ALREADY
        self._items[ean] = name
        return BasketResult.ADDED

    def __contains__(self, ean: object) -> bool:
        return ean in self._items

    def __len__(self) -> int:
        return len(self._items)

    def items(self) -> List[Tuple[str, str]]:
        return list(self._items.items())

    def summary(self) -> str:
        if not self._items:
            return "Korgen: tom"
        return f"Korgen ({len(self)}): " + ", ".join(self._items.values())
