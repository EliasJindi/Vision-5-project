# ===================== NY FIL AV CLAUDE (2026-11-03) =====================
# Det enda skannerns huvudloop behöver känna till: en GuidanceSession som får varje avkodad
# bildruta (on_frame) och sköter motor, röst och länk. Skannern bygger sessionen med
# create_session() utifrån kommandoradsflaggorna.
# =========================================================================
"""
session.py - Binder ihop GuidanceEngine, GuidanceVoice och länken till andra program.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Mapping, Optional, Sequence

from .catalog import DictProductCatalog
from .engine import GuidanceEngine
from .link import EventPublisher, NullPublisher, SayCommand, TcpJsonLink
from .model import AimConvention, CodeRead, FrameObservation, GuidanceAction
from .voice import AudioManagerSpeaker, ConsoleSpeaker, GuidanceVoice, Speaker


class GuidanceMode(Enum):
    OFF = "off"      # ingen vägledning (länken kan ändå vara på)
    TEXT = "text"    # vägledningen skrivs bara ut
    VOICE = "voice"  # vägledningen läses upp


class GuidanceSession:
    def __init__(self, engine: Optional[GuidanceEngine], voice: Optional[GuidanceVoice],
                 link: EventPublisher) -> None:
        if (engine is None) != (voice is None):
            raise ValueError("motor och röst hör ihop: båda eller ingen")
        self._engine, self._voice, self._link = engine, voice, link
        self._malformed = 0

    def on_frame(self, t: float, records: Sequence[Mapping[str, Any]]) -> Optional[GuidanceAction]:
        """
        Anropas för varje avkodad bildruta, även när ingen kod syntes (records tom): motorn behöver
        tiden för att glömma gamla läsningar. records är loggraderna från handle_barcode().
        """
        for rec in records:
            self._link.publish({**rec, "type": "read"})
        if self._engine is None:
            return None
        action = self._engine.update(FrameObservation(t, self._reads(records)))
        if action is not None:
            text = self._voice.announce(action)
            self._link.publish({"type": "guidance", "t": round(t, 3), "action": action.kind.value,
                                "ean": action.ean, "name": action.name, "text": text})
        return action

    def close(self) -> None:
        self._link.close()

    def _reads(self, records: Sequence[Mapping[str, Any]]) -> tuple:
        reads = []
        for rec in records:
            try:
                reads.append(CodeRead.from_record(rec))
            except ValueError as e:
                self._malformed += 1
                if self._malformed == 1:   # en varning räcker: raderna kommer från vår egen kod
                    print(f"⚠️  [Vägledning] hoppar över en trasig loggrad: {e}")
        return tuple(reads)


def create_session(products: Mapping[str, Any], mode: GuidanceMode = GuidanceMode.OFF,
                   convention: AimConvention = AimConvention.HEAD,
                   link_port: Optional[int] = None) -> GuidanceSession:
    """
    Bygger sessionen utifrån skannerns flaggor. products är kartan från load_products().
    link_port=None stänger länken. Med länk men utan vägledning läser skannern ändå upp
    say-kommandon, så att ett externt program kan styra rösten.
    """
    speaker: Optional[Speaker] = None
    if mode is GuidanceMode.TEXT:
        speaker = ConsoleSpeaker()
    elif mode is GuidanceMode.VOICE or link_port is not None:
        speaker = _voice_speaker()

    link: EventPublisher = NullPublisher()
    if link_port is not None:
        def on_say(command: SayCommand) -> None:
            speaker.say(command.text, key="link")
        tcp = TcpJsonLink(port=link_port, on_say=on_say)
        print(f"🔌 Länk: 127.0.0.1:{tcp.start()} (JSON-rader, se docs/ROSTVAGLEDNING.md)")
        link = tcp

    if mode is GuidanceMode.OFF:
        return GuidanceSession(None, None, link)
    return GuidanceSession(GuidanceEngine(DictProductCatalog(products)), GuidanceVoice(speaker, convention), link)


def _voice_speaker() -> Speaker:
    try:
        return AudioManagerSpeaker()
    except Exception as e:   # t.ex. Piper eller pw-play saknas: säg det högt i stället för att tiga
        print(f"⚠️  [Vägledning] ljudsystemet kunde inte startas ({e!r}). Skriver ut i stället.")
        return ConsoleSpeaker()
