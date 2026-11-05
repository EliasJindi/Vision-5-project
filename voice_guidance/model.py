# ===================== NY FIL AV CLAUDE (2026-11-03) =====================
# Datatyperna som röstvägledningen arbetar med. Inga beroenden utöver standardbiblioteket
# och scan_filters.py, så att allt går att testa utan kamera.
# =========================================================================
"""
model.py - Vad motorn får in (en läsning, en bildruta) och vad den ger ut (en handling).

CodeRead.from_record() är den enda platsen som känner till loggradens format. Ändras
formatet i barcode_scanner.py är det här man ändrar, ingen annanstans.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional, Tuple

from scan_filters import is_thin, size_from_corners

Point = Tuple[float, float]
IMAGE_CENTER: Point = (0.5, 0.5)


class ActionKind(Enum):
    """Vad användaren ska få veta. Värdet är nyckeln i phrases.py och i länkens JSON."""
    CONFIRMED = "confirmed"                # säker läsning av en känd vara: säg namnet
    UNKNOWN_PRODUCT = "unknown_product"    # säker läsning av en vara som inte finns i kartan
    CLOSER = "closer"                      # koden syns men är för liten eller tunn
    CODE_LEFT = "code_left"                # koden ligger till vänster i bilden
    CODE_RIGHT = "code_right"
    CODE_ABOVE = "code_above"
    CODE_BELOW = "code_below"
    HOLD_STILL = "hold_still"              # två olika koder från samma ställe: osäkert
    NO_CODE = "no_code"                    # ingen kod på ett tag: håll varan i mitten (första tipset)
    NO_CODE_TURN = "no_code_turn"          # ...vänd varan, koden kan sitta på en annan sida (andra tipset)
    NO_CODE_DISTANCE = "no_code_distance"  # ...håll varan ungefär 30 cm bort (tredje tipset, sedan om igen)
    READY = "ready"                        # en stund efter en lyckad scanning: redo för nästa vara (Elias 5/11)
    CODE_SEEN = "code_seen"                # ett kort pip, inget tal: en kod syns men är inte läsbar än


class AimConvention(Enum):
    """
    Hur riktningen uttrycks. Motorn säger bara var koden ligger i bilden, och konventionen
    avgör orden. Kameran sitter på huvudet.
      HEAD: användaren vrider huvudet mot koden ("lite åt vänster" om koden ligger till vänster).
      HAND: användaren flyttar varan ("lite åt höger" om koden ligger till vänster).
    """
    HEAD = "head"
    HAND = "hand"


@dataclass(frozen=True)
class CodeRead:
    """En avläsning av en streckkod i en bildruta."""
    ean: Optional[str]        # giltig EAN, eller None om kontrollsumman inte stämde
    center: Point             # kodens mitt, normaliserad: (0,0) = övre vänstra hörnet, (1,1) = nedre högra
    thin: bool                # läsningen kommer från en tunn remsa av koden (se scan_filters.is_thin)

    @property
    def reliable(self) -> bool:
        """Säker nog att säga varans namn: giltig kod och inte en tunn remsa."""
        return self.ean is not None and not self.thin

    @classmethod
    def from_record(cls, rec: Mapping[str, Any]) -> "CodeRead":
        """
        Bygger en läsning ur en loggrad från barcode_scanner.py. Äldre loggar utan fältet "filter"
        räknas om ur hörnen. Ger ValueError om raden saknar fält eller är trasig.
        """
        try:
            corners = [(float(x), float(y)) for x, y in rec["hornen"]]
            frame_w, frame_h = (float(v) for v in rec["bild"])
            if len(corners) != 4 or frame_w <= 0 or frame_h <= 0:
                raise ValueError("hörn eller bildstorlek har fel form")
            cx = sum(x for x, _ in corners) / 4 / frame_w
            cy = sum(y for _, y in corners) / 4 / frame_h
            if "filter" in rec:
                thin = "tunn" in rec["filter"]
            else:
                width, height = size_from_corners(*corners)
                thin = width <= 0 or is_thin(height / width)
            ean = rec.get("ean")
        except (KeyError, TypeError) as e:
            raise ValueError(f"loggraden saknar eller har trasigt fält: {e!r}") from e
        return cls(ean=str(ean) if ean else None, center=(_clamp01(cx), _clamp01(cy)), thin=thin)

    def distance_from_center(self) -> float:
        return math.dist(self.center, IMAGE_CENTER)


@dataclass(frozen=True)
class FrameObservation:
    """Allt som lästes i en avkodad bildruta. reads är tom när ingen kod syntes."""
    t: float                          # tid i sekunder (samma klocka som loggen, time.time())
    reads: Tuple[CodeRead, ...] = ()


@dataclass(frozen=True)
class GuidanceAction:
    """Ett besked till användaren. Orden bestäms av GuidanceVoice, inte här."""
    kind: ActionKind
    ean: Optional[str] = None
    name: Optional[str] = None
    details: Tuple[str, ...] = ()   # mer om varan ur kartan, t.ex. ("140 gram", "hylla 3"). Bara vid CONFIRMED

    def __post_init__(self) -> None:
        if self.kind in (ActionKind.CONFIRMED, ActionKind.UNKNOWN_PRODUCT) and not self.ean:
            raise ValueError(f"{self.kind.name} kräver en EAN")
        if self.kind is ActionKind.CONFIRMED and not self.name:
            raise ValueError("CONFIRMED kräver ett varunamn (annars UNKNOWN_PRODUCT)")
        if self.details and self.kind is not ActionKind.CONFIRMED:
            raise ValueError("details hör bara till CONFIRMED")


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))
