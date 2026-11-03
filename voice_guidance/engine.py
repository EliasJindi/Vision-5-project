# ===================== NY FIL AV CLAUDE (2026-11-03) =====================
# Beslutslogiken för röstvägledningen. Ren logik: ingen kamera, inget ljud, ingen klocka
# (tiden kommer med varje bildruta). Därför är den deterministisk och går att spela upp mot
# gamla loggar (voice_guidance.replay).
# Alla trösklar är startvärden från mätningarna 17-29/10 och ligger i GuidanceConfig.
# =========================================================================
"""
engine.py - Vad ska användaren få veta just nu?

Reglerna, i prioritetsordning (se docs/ROSTVAGLEDNING.md):
  1. Konflikt: två olika koder från samma ställe inom några sekunder betyder att minst en är fel.
     Säg "håll stilla" och bekräfta ingenting under en stund.
  2. Bekräfta en vara först när den lästs säkert (inte tunn) flera gånger i rad och ingen konflikt råder.
  3. Annars, om koden syns men inte är säker: säg vart den ska (om den ligger i kanten, eftersom
     autofokus följer bildens mitt) eller "lite närmare".
  4. Annars tystnad. Motorn pratar hellre för lite än för mycket.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Sequence, Set, Tuple

from .catalog import ProductCatalog
from .model import (ActionKind, CodeRead, FrameObservation, GuidanceAction, Point,
                    IMAGE_CENTER)

_NEVER = float("-inf")
_CONFIRMATIONS = (ActionKind.CONFIRMED, ActionKind.UNKNOWN_PRODUCT)


@dataclass(frozen=True)
class GuidanceConfig:
    """Trösklar. Startvärden, ska finjusteras mot nya körningar och med replay."""
    confirm_reads: int = 2           # säkra läsningar av samma vara som krävs för att säga namnet
    confirm_window_s: float = 2.0    # ...inom så här lång tid
    lost_after_s: float = 2.0        # varan räknas som borta efter så här lång tid utan läsning
    conflict_window_s: float = 3.0   # två olika koder inom så här lång tid räknas som konflikt...
    conflict_radius: float = 0.10    # ...om de ligger så nära varandra (andel av bildens bredd/höjd)
    conflict_hold_s: float = 3.0     # tyst tid efter en konflikt
    deadzone_x: float = 0.20         # koden räknas som "i mitten" så länge den ligger inom detta från mitten
    deadzone_y: float = 0.25
    min_interval_s: float = 1.8      # minst så här lång tid mellan två vägledningar
    repeat_after_s: float = 3.0      # samma vägledning upprepas inte oftare än så här

    def __post_init__(self) -> None:
        if self.confirm_reads < 1:
            raise ValueError("confirm_reads måste vara minst 1")
        for name in ("confirm_window_s", "lost_after_s", "conflict_window_s", "conflict_radius",
                     "conflict_hold_s", "min_interval_s", "repeat_after_s"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} måste vara större än 0")
        for name in ("deadzone_x", "deadzone_y"):
            if not 0 < getattr(self, name) <= 0.5:
                raise ValueError(f"{name} måste ligga mellan 0 och 0,5")


class GuidanceEngine:
    """Tar emot en bildruta i taget och svarar med högst en handling."""

    def __init__(self, catalog: ProductCatalog, config: Optional[GuidanceConfig] = None) -> None:
        self._catalog = catalog
        self._cfg = config or GuidanceConfig()
        self._votes: Dict[str, Deque[float]] = {}                 # ean -> tider för säkra läsningar
        self._recent: Deque[Tuple[float, str, Point]] = deque()   # (tid, ean, mitt) för konfliktkoll
        self._last_seen: Dict[str, float] = {}
        self._confirmed: Set[str] = set()                         # redan sagda, tills de försvunnit
        self._conflict_until = _NEVER
        self._last_spoken = _NEVER
        self._last_by_kind: Dict[ActionKind, float] = {}

    @property
    def config(self) -> GuidanceConfig:
        return self._cfg

    def update(self, obs: FrameObservation) -> Optional[GuidanceAction]:
        t = obs.t
        self._expire(t)
        self._record(obs)
        conflict = self._in_conflict()
        if conflict:
            self._conflict_until = t + self._cfg.conflict_hold_s
            self._votes.clear()   # röster som samlats under konflikten får inte räknas
        return self._admit(self._decide(obs, conflict), t)

    # ---------- beslut ----------
    def _decide(self, obs: FrameObservation, conflict: bool) -> Optional[GuidanceAction]:
        if conflict:
            # Har användaren redan fått varan bekräftad är en ny avvikande läsning troligen en felläsning.
            return None if self._confirmed else GuidanceAction(ActionKind.HOLD_STILL)
        if obs.t < self._conflict_until:
            return None

        ean = self._ready_to_confirm()
        if ean is not None:
            name = self._catalog.name_of(ean)
            return (GuidanceAction(ActionKind.CONFIRMED, ean=ean, name=name) if name
                    else GuidanceAction(ActionKind.UNKNOWN_PRODUCT, ean=ean))

        if self._confirmed or not obs.reads or any(r.reliable for r in obs.reads):
            return None   # redan bekräftad, inget synligt, eller en säker läsning som väntar på sin andra röst
        return self._aim(obs.reads)

    def _ready_to_confirm(self) -> Optional[str]:
        ready = [(len(v), v[-1], ean) for ean, v in self._votes.items()
                 if len(v) >= self._cfg.confirm_reads and ean not in self._confirmed]
        return max(ready)[2] if ready else None

    def _aim(self, reads: Sequence[CodeRead]) -> GuidanceAction:
        """Koden syns men är osäker. Ligger den i kanten: säg vart. Annars: närmare."""
        target = min(reads, key=CodeRead.distance_from_center)
        dx = target.center[0] - IMAGE_CENTER[0]
        dy = target.center[1] - IMAGE_CENTER[1]
        excess_x = abs(dx) / self._cfg.deadzone_x
        excess_y = abs(dy) / self._cfg.deadzone_y
        if max(excess_x, excess_y) <= 1.0:
            return GuidanceAction(ActionKind.CLOSER)
        if excess_x >= excess_y:
            return GuidanceAction(ActionKind.CODE_LEFT if dx < 0 else ActionKind.CODE_RIGHT)
        return GuidanceAction(ActionKind.CODE_ABOVE if dy < 0 else ActionKind.CODE_BELOW)

    # ---------- takt: hur ofta får motorn prata? ----------
    def _admit(self, action: Optional[GuidanceAction], t: float) -> Optional[GuidanceAction]:
        if action is None:
            return None
        if action.kind not in _CONFIRMATIONS:
            # Bekräftelsen är poängen med hela flödet och går före. Allt annat tas med måtta.
            if t - self._last_spoken < self._cfg.min_interval_s:
                return None
            if t - self._last_by_kind.get(action.kind, _NEVER) < self._cfg.repeat_after_s:
                return None
        self._last_spoken = t
        self._last_by_kind[action.kind] = t
        if action.ean is not None:
            self._confirmed.add(action.ean)
            self._votes.pop(action.ean, None)
        return action

    # ---------- minne ----------
    def _record(self, obs: FrameObservation) -> None:
        for read in obs.reads:
            if read.ean is None:
                continue
            self._last_seen[read.ean] = obs.t
            self._recent.append((obs.t, read.ean, read.center))
            if read.reliable:
                self._votes.setdefault(read.ean, deque()).append(obs.t)

    def _expire(self, t: float) -> None:
        while self._recent and t - self._recent[0][0] > self._cfg.conflict_window_s:
            self._recent.popleft()
        for ean in list(self._votes):
            votes = self._votes[ean]
            while votes and t - votes[0] > self._cfg.confirm_window_s:
                votes.popleft()
            if not votes:
                del self._votes[ean]
        for ean in [e for e in self._confirmed if t - self._last_seen.get(e, _NEVER) > self._cfg.lost_after_s]:
            self._confirmed.discard(ean)

    def _in_conflict(self) -> bool:
        """Finns två olika koder som lästs från ungefär samma ställe nyligen?"""
        reads: List[Tuple[float, str, Point]] = list(self._recent)
        for i, (_, ean_a, pos_a) in enumerate(reads):
            for _, ean_b, pos_b in reads[i + 1:]:
                if ean_a != ean_b and _distance(pos_a, pos_b) <= self._cfg.conflict_radius:
                    return True
        return False


def _distance(a: Point, b: Point) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
