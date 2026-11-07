# ===================== NY FIL AV CLAUDE (2026-11-03) =====================
# Beslutslogiken för röstvägledningen. Ren logik: ingen kamera, inget ljud, ingen klocka
# (tiden kommer med varje bildruta). Därför är den deterministisk och går att spela upp mot
# gamla loggar (voice_guidance.replay).
# Alla trösklar är startvärden från mätningarna 17-29/10 och ligger i GuidanceConfig.
# =========================================================================
"""
engine.py - Vad ska användaren få veta just nu?

Reglerna, i prioritetsordning (se docs/ROSTVAGLEDNING.md):
  1. Konflikt: två olika säkra koder från samma ställe inom några sekunder betyder att minst en är fel.
     Säg "håll stilla" och bekräfta ingenting under en stund. Varar konflikten länge: "lite närmare".
  2. Bekräfta en vara först när den lästs säkert (inte tunn) flera gånger i rad och ingen konflikt råder.
     Har bara en säker läsning kommit och den andra dröjer: "håll stilla" (Elias 6/11: rör man sig då tappas koden).
  3. Annars, om koden syns men inte är säker: säg vart den ska (om den ligger i kanten, eftersom
     autofokus följer bildens mitt) eller "lite närmare".
  3b. Ingen kod gick att läsa, men detektorn SER en streckkod (7/11, Elias: "vänd inte varan när den
     faktiskt hittar en etikett"): ligger den i kanten säg vart, annars "håll stilla". Bara under en
     sökning och när ingen vara är bekräftad. Detektorn kan aldrig bekräfta en vara.
  4. Syns ingen kod alls på ett tag: korta tips i tur och ordning ("håll varan framför dig, en halv armlängd
     bort", "vrid varan sakta", "vänd varan upp och ner"), först tätt och sedan glesare, utan slut tills en kod syns. Tystnad
     lämnade användaren ensam i en minut (Elias, 4-5/11).
     Efter en lyckad scanning sägs i stället "redo för nästa vara" en gång, när varan varit borta en stund
     (användaren har då kanske ingen vara i handen, så "vänd varan" vore fel). Elias 5/11.
  5. Annars tystnad. Motorn pratar hellre för lite än för mycket.

Pip: när regel 3 hade velat säga något men takten håller tillbaka talet hörs ett kort pip i stället
(högst ett per sekund). Användaren vet då att en kod syns och kan sluta vrida, utan att rösten pratar
oavbrutet. Inget pip under konflikt eller när varan redan är bekräftad.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Sequence, Set, Tuple

from .catalog import ProductCatalog
from .model import (ActionKind, CodeRead, FrameObservation, GuidanceAction, Point,
                    IMAGE_CENTER)

_NEVER = float("-inf")
_CONFIRMATIONS = (ActionKind.CONFIRMED, ActionKind.UNKNOWN_PRODUCT)
_NO_CODE_HINTS = (ActionKind.NO_CODE, ActionKind.NO_CODE_TURN, ActionKind.NO_CODE_FLIP)   # i den ordningen
_AIMS = (ActionKind.CLOSER, ActionKind.CODE_LEFT, ActionKind.CODE_RIGHT, ActionKind.CODE_ABOVE,
         ActionKind.CODE_BELOW)


@dataclass(frozen=True)
class GuidanceConfig:
    """Trösklar. Startvärden, ska finjusteras mot nya körningar och med replay."""
    confirm_reads: int = 2           # säkra läsningar av samma vara som krävs för att säga namnet
    confirm_window_s: float = 2.0    # ...inom så här lång tid
    lost_after_s: float = 5.0        # varan räknas som borta efter så här lång tid utan läsning
    conflict_window_s: float = 3.0   # två olika koder inom så här lång tid räknas som konflikt...
    conflict_radius: float = 0.10    # ...om de ligger så nära varandra (andel av bildens bredd/höjd)
    conflict_hold_s: float = 3.0     # tyst tid efter en konflikt
    conflict_escalate_s: float = 5.0   # varar en konflikt så länge byts "håll stilla" mot "lite närmare"
    conflict_from_thin: bool = False   # tunna läsningar startar ingen konflikt: replay 5/11, 81 loggar, 0 fel vara båda
                                       # sätten, en bekräftelse till med False (köket 4/11: 4 s väntan i onödan)
    deadzone_x: float = 0.15         # koden räknas som "i mitten" så länge den ligger inom detta från mitten (0,20 före 5/11)
    deadzone_y: float = 0.25
    min_interval_s: float = 1.5      # minst så här lång tid mellan två vägledningar (1,8 före 5/11: "lite snabbare")
    repeat_after_s: float = 3.0      # samma vägledning upprepas inte oftare än så här
    no_code_after_s: float = 4.0     # ingen kod på så här lång tid: första tipset (8 s före 5/11: för långsamt)
    no_code_repeat_s: float = 6.0    # ...nästa tips så här tätt...
    no_code_fast: int = 3            # ...de första så här många gångerna...
    no_code_slow_repeat_s: float = 10.0   # ...sedan så här glest tills en kod syns (0 = tyst efter de täta; båda 0 = aldrig)
    ready_after_s: float = 8.0       # "redo för nästa vara" så här länge efter att en bekräftad vara försvann (0 = aldrig; 15 s före 7/11: för tyst)
    steady_after_s: float = 0.9      # "håll stilla" om den andra säkra läsningen dröjer så här länge (0 = aldrig)
    cue_interval_s: float = 1.0      # pip när en osäker kod syns men talet hålls tillbaka, högst så här ofta (0 = av)
    cue_quiet_s: float = 1.2         # inget pip så här snart efter tal, så att pipet inte hamnar mitt i en fras

    def __post_init__(self) -> None:
        if self.confirm_reads < 1:
            raise ValueError("confirm_reads måste vara minst 1")
        if self.no_code_fast < 0 or self.no_code_slow_repeat_s < 0:
            raise ValueError("no_code_fast och no_code_slow_repeat_s får inte vara negativa")
        if min(self.cue_interval_s, self.cue_quiet_s, self.ready_after_s, self.steady_after_s) < 0:
            raise ValueError("cue_interval_s, cue_quiet_s, ready_after_s och steady_after_s får inte vara negativa")
        for name in ("confirm_window_s", "lost_after_s", "conflict_window_s", "conflict_radius",
                     "conflict_hold_s", "conflict_escalate_s", "min_interval_s", "repeat_after_s",
                     "no_code_after_s", "no_code_repeat_s"):
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
        self._conflict_since = _NEVER       # när den pågående konflikten började
        self._last_conflict = _NEVER        # senaste gången en konflikt syntes
        self._last_spoken = _NEVER
        self._last_by_kind: Dict[ActionKind, float] = {}
        self._search_since: Optional[float] = None   # när en kod senast syntes (eller när sökningen började)
        self._no_code_said = 0                        # hur många tips om "ingen kod" som sagts i den här sökningen
        self._searching = True                        # False efter en lyckad scanning, tills en ny kod syns
        self._last_success: Optional[str] = None      # varan som senast bekräftades
        self._last_cue = _NEVER
        self._ready_pending = False                   # en vara har bekräftats: säg "redo" när den varit borta en stund

    @property
    def config(self) -> GuidanceConfig:
        return self._cfg

    def update(self, obs: FrameObservation) -> Optional[GuidanceAction]:
        t = obs.t
        self._expire(t)
        self._track_search(obs)
        self._record(obs)
        conflict = self._in_conflict()
        if conflict:
            self._note_conflict(t)
        decided = self._decide(obs, conflict)
        action = self._admit(decided, t)
        if action is None and decided is not None and decided.kind in _AIMS and not conflict:
            action = self._cue(t)   # talet hölls tillbaka av takten: pipa i stället
        return action

    def _cue(self, t: float) -> Optional[GuidanceAction]:
        """Ett pip räknas inte som tal: det skjuter inte upp nästa vägledning."""
        cfg = self._cfg
        if cfg.cue_interval_s == 0 or t - self._last_spoken < cfg.cue_quiet_s or t - self._last_cue < cfg.cue_interval_s:
            return None
        self._last_cue = t
        return GuidanceAction(ActionKind.CODE_SEEN)

    def _note_conflict(self, t: float) -> None:
        if t - self._last_conflict > self._cfg.conflict_hold_s:
            self._conflict_since = t   # en ny konflikt, inte en fortsättning på den förra
        self._last_conflict = t
        self._conflict_until = t + self._cfg.conflict_hold_s
        self._votes.clear()   # röster som samlats under konflikten får inte räknas

    # ---------- beslut ----------
    def _decide(self, obs: FrameObservation, conflict: bool) -> Optional[GuidanceAction]:
        if conflict:
            # Har användaren redan fått varan bekräftad är en ny avvikande läsning troligen en felläsning.
            if self._confirmed:
                return None
            # Går konflikten inte över av att hålla stilla hjälper det att gå närmare (felläsningarna 29/10
            # försvann när koden blev större), annars sitter användaren fast med "håll stilla".
            persistent = obs.t - self._conflict_since >= self._cfg.conflict_escalate_s
            return GuidanceAction(ActionKind.CLOSER if persistent else ActionKind.HOLD_STILL)
        if obs.t < self._conflict_until:
            return None

        ean = self._ready_to_confirm()
        if ean is not None:
            name = self._catalog.name_of(ean)
            return (GuidanceAction(ActionKind.CONFIRMED, ean=ean, name=name, details=self._catalog.details_of(ean))
                    if name else GuidanceAction(ActionKind.UNKNOWN_PRODUCT, ean=ean))

        steady = self._steady_prompt(obs.t)
        if steady is not None:
            return steady
        if not obs.reads and self._sees_new_code(obs):
            return self._direction([p for p in obs.seen], ActionKind.STEADY)   # regel 3b
        if not obs.reads:
            return self._no_code_prompt(obs.t)
        if self._confirmed or any(r.reliable for r in obs.reads):
            return None   # redan bekräftad, eller en säker läsning som väntar på sin andra röst
        return self._aim(obs.reads)

    def _steady_prompt(self, t: float) -> Optional[GuidanceAction]:
        """En säker läsning av en ny vara väntar på sin andra och den dröjer: be användaren stå still.
        Gäller även bildrutor utan kod, eftersom koden ofta tappas just när användaren rör sig."""
        if self._cfg.steady_after_s == 0:
            return None
        waiting = [votes[0] for ean, votes in self._votes.items()
                   if ean not in self._confirmed and not self._just_scanned(ean)]
        if waiting and t - min(waiting) >= self._cfg.steady_after_s:
            return GuidanceAction(ActionKind.STEADY)
        return None

    def _no_code_prompt(self, t: float) -> Optional[GuidanceAction]:
        """Ingen kod syns. Ge tips i tur och ordning, först tätt och sedan glesare. Efter en lyckad scanning: "redo"."""
        if self._ready_pending:
            ready = self._cfg.ready_after_s and t - self._search_since >= self._cfg.ready_after_s
            return GuidanceAction(ActionKind.READY) if ready else None
        if not self._searching:
            return None
        due = self._no_code_due(self._no_code_said)
        if due is None or t - self._search_since < due:
            return None
        return GuidanceAction(_NO_CODE_HINTS[self._no_code_said % len(_NO_CODE_HINTS)])

    def _no_code_due(self, n: int) -> Optional[float]:
        """Sekunder utan kod innan tips nummer n (0 = första). None = inga fler tips."""
        cfg = self._cfg
        if n < cfg.no_code_fast:
            return cfg.no_code_after_s + n * cfg.no_code_repeat_s
        if cfg.no_code_slow_repeat_s == 0:
            return None
        if cfg.no_code_fast:
            first_slow = cfg.no_code_after_s + (cfg.no_code_fast - 1) * cfg.no_code_repeat_s + cfg.no_code_slow_repeat_s
        else:
            first_slow = cfg.no_code_after_s
        return first_slow + (n - cfg.no_code_fast) * cfg.no_code_slow_repeat_s

    def _ready_to_confirm(self) -> Optional[str]:
        ready = [(len(v), v[-1], ean) for ean, v in self._votes.items()
                 if len(v) >= self._cfg.confirm_reads and ean not in self._confirmed]
        return max(ready)[2] if ready else None

    def _aim(self, reads: Sequence[CodeRead]) -> GuidanceAction:
        """Koden syns men är osäker. Ligger den i kanten: säg vart. Annars: närmare."""
        return self._direction([r.center for r in reads], ActionKind.CLOSER)

    def _sees_new_code(self, obs: FrameObservation) -> bool:
        """Detektorn ser en kod under en pågående sökning (inte efter en lyckad scanning)."""
        return bool(obs.seen) and self._searching and not self._confirmed

    def _direction(self, centers: Sequence[Point], centered: ActionKind) -> GuidanceAction:
        """Riktning mot koden närmast mitten om den ligger utanför mittzonen, annars centered."""
        target = min(centers, key=lambda c: math.dist(c, IMAGE_CENTER))
        dx = target[0] - IMAGE_CENTER[0]
        dy = target[1] - IMAGE_CENTER[1]
        excess_x = abs(dx) / self._cfg.deadzone_x
        excess_y = abs(dy) / self._cfg.deadzone_y
        if max(excess_x, excess_y) <= 1.0:
            return GuidanceAction(centered)
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
        if action.kind in _NO_CODE_HINTS:
            self._no_code_said += 1
        if action.kind is ActionKind.READY:
            self._ready_pending = False                  # en gång, sedan tyst tills en ny kod syns
        if action.ean is not None:
            self._confirmed.add(action.ean)
            self._votes.pop(action.ean, None)
            self._searching = False                      # sökningen lyckades: inga tips när varan läggs ner
            self._last_success = action.ean
            self._ready_pending = True
        return action

    # ---------- minne ----------
    def _track_search(self, obs: FrameObservation) -> None:
        """
        En ny sökning börjar vid start och när en kod syns som inte redan är bekräftad. Efter en lyckad
        scanning räknas inte samma vara som en ny sökning, även om den hunnit glömmas (borta i mer än
        lost_after_s): annars börjar tipsen om när varan skymtar förbi (provet 5/11, 16:05:38).
        """
        def starts_search(read: CodeRead) -> bool:
            return read.ean not in self._confirmed and not self._just_scanned(read.ean)
        if self._search_since is None or any(starts_search(r) for r in obs.reads):
            self._no_code_said = 0
            self._searching = True
            self._ready_pending = False
        if self._search_since is None or obs.reads or self._sees_new_code(obs):
            self._search_since = obs.t   # en kod som syns (läst eller bara sedd) betyder att sökningen går framåt

    def _just_scanned(self, ean: Optional[str]) -> bool:
        """Varan som precis skannades, innan en ny sökning börjat. Den ger varken tips eller "håll stilla"."""
        return not self._searching and ean == self._last_success

    def _record(self, obs: FrameObservation) -> None:
        for read in obs.reads:
            if read.ean is None:
                continue
            self._last_seen[read.ean] = obs.t
            if read.reliable or self._cfg.conflict_from_thin:
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
