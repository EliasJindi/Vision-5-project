# ===================== NY FIL AV CLAUDE (2026-11-03) =====================
# Gemensamma byggstenar för testerna av voice_guidance. Hörnen är riktiga värden ur loggen
# 2026-10-20 (hel kod) och 2026-10-20 15:59 (tunn remsa på 1-2 px).
# =========================================================================
from typing import Any, Dict, List, Optional, Tuple

from voice_guidance import CodeRead, FrameObservation

EAN_A = "7340083497834"   # tomatpuré
EAN_B = "7311043006847"   # kaffefilter

FRAME_SIZE = [1920, 1080]
FULL_CORNERS = [[742, 583], [953, 583], [950, 712], [738, 712]]    # 211 x 129 px: en hel kod
THIN_CORNERS = [[950, 702], [738, 702], [738, 703], [950, 703]]    # 212 x 1 px: en tunn remsa


def read(ean: Optional[str] = EAN_A, x: float = 0.5, y: float = 0.5, thin: bool = False) -> CodeRead:
    return CodeRead(ean=ean, center=(x, y), thin=thin)


def frame(t: float, *reads: CodeRead) -> FrameObservation:
    return FrameObservation(t, tuple(reads))


def record(t: float, ean: Optional[str] = EAN_A, corners: Optional[List[List[int]]] = None,
           filter: Optional[List[str]] = None, facit: Optional[str] = None) -> Dict[str, Any]:
    """En loggrad som barcode_scanner.handle_barcode() skriver, med de fält röstvägledningen läser."""
    rec: Dict[str, Any] = {"t": t, "mode": "1080p", "ean": ean, "hornen": corners or FULL_CORNERS,
                           "bild": FRAME_SIZE}
    if filter is not None:
        rec["filter"] = filter
    if facit:
        rec["facit"] = facit
        rec["correct"] = ean == facit
    return rec


class FakeSpeaker:
    """Samlar det som sägs i stället för att läsa upp det."""

    def __init__(self) -> None:
        self.said: List[Tuple[str, Optional[str]]] = []

    def say(self, text: str, key: Optional[str] = None) -> None:
        self.said.append((text, key))

    @property
    def texts(self) -> List[str]:
        return [text for text, _ in self.said]


class FakePublisher:
    """Samlar det som skickas ut i stället för att öppna en port."""

    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []
        self.closed = False

    def publish(self, event: Dict[str, Any]) -> None:
        self.events.append(dict(event))

    def close(self) -> None:
        self.closed = True

    def of_type(self, kind: str) -> List[Dict[str, Any]]:
        return [e for e in self.events if e.get("type") == kind]
