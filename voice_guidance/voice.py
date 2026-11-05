# ===================== NY FIL AV CLAUDE (2026-11-03) =====================
# Från handling till tal. Speaker är det enda motorn och rösten vet om ljudsystemet: en
# adapter mot audio_manager.py (nivå 3 i ljudkön, under akutlarm och Gemini) och en som
# bara skriver ut. audio_manager.py importeras först när adaptern skapas, eftersom importen
# startar Piper och telemetrin.
# =========================================================================
"""
voice.py - Gör GuidanceAction till ord (eller ett pip) och skickar dem till en Speaker.
"""
from __future__ import annotations

import math
import os
import struct
import time
import wave
from typing import Any, Optional, Protocol, Sequence

from phrases import guidance_phrases, guidance_text

from .basket import BasketResult
from .model import ActionKind, AimConvention, GuidanceAction

GUIDANCE_PRIORITY = 3   # audio_manager: 1 = akutlarm, 2 = Gemini, 3 = övrigt. Vägledning får aldrig gå före säkerhet.
CUE_PATH = "cache/cue_pip.wav"
CUE_TTL_S = 0.6         # ett pip som fått vänta längre än så i kön beskriver inte längre bilden: släng det
CUE_TEXT = "♪"          # så syns pipet i utskrift och länk


class Speaker(Protocol):
    def say(self, text: str, key: Optional[str] = None) -> None:
        """Läs upp text. key identifierar typen av besked (används bara för loggning)."""

    def cue(self) -> None:
        """Ett kort pip: en kod syns."""


class ConsoleSpeaker:
    """Skriver bara ut. För test på dator, och när ljudsystemet saknas."""

    def say(self, text: str, key: Optional[str] = None) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] 🗨️  {text}" + (f"   ({key})" if key else ""))

    def cue(self) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] {CUE_TEXT} pip")


def write_cue_wav(path: str, freq_hz: float = 1200.0, length_s: float = 0.07, volume: float = 0.35,
                  rate: int = 22050) -> str:
    """Skriver pipet som en WAV-fil (mono, 16 bit). Mjuk in- och uttoning, annars knäpper det."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    n = int(rate * length_s)
    fade = max(1, int(rate * 0.01))
    samples = bytearray()
    for i in range(n):
        envelope = min(1.0, i / fade, (n - 1 - i) / fade)
        samples += struct.pack("<h", int(32767 * volume * envelope * math.sin(2 * math.pi * freq_hz * i / rate)))
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(bytes(samples))
    return path


class AudioManagerSpeaker:
    """Spelar upp via audio_manager.py. Fraserna ligger i Pi:ns ljudcache (python3 tts_engine.py --prewarm)."""

    def __init__(self, audio: Optional[Any] = None, phrases: Sequence[str] = (), cue_path: str = CUE_PATH) -> None:
        if audio is None:
            from audio_manager import audio_system   # startar Piper-processen och telemetrin
            audio = audio_system
            # ladda röstmodellen nu och rapportera vad som saknas i cachen (varunamnen ingår)
            audio.prewarm(sorted(set(guidance_phrases()) | set(phrases)))
            self._ensure_cue(cue_path)
        self._audio = audio
        self._cue_path = cue_path

    @staticmethod
    def _ensure_cue(path: str) -> None:
        if not os.path.exists(path):
            write_cue_wav(path)   # några millisekunder, ingen Piper

    def say(self, text: str, key: Optional[str] = None) -> None:
        self._audio.speak(text, priority=GUIDANCE_PRIORITY, key=key)

    def cue(self) -> None:
        self._ensure_cue(self._cue_path)
        self._audio.speak(CUE_TEXT, priority=GUIDANCE_PRIORITY, key="cue", wav=self._cue_path, ttl=CUE_TTL_S)


class GuidanceVoice:
    """Översätter en handling till svenska och läser upp den. Returnerar texten (för loggning och länk)."""

    def __init__(self, speaker: Speaker, convention: AimConvention = AimConvention.HEAD) -> None:
        self._speaker = speaker
        self._convention = convention

    @property
    def convention(self) -> AimConvention:
        return self._convention

    def announce(self, action: GuidanceAction, basket: Optional[BasketResult] = None) -> str:
        """basket: vad som hände med varan i korgen. Läses efter namnet, bara vid CONFIRMED."""
        if action.kind is ActionKind.CODE_SEEN:
            self._speaker.cue()
            return CUE_TEXT
        text = guidance_text(action.kind.value, self._convention.value, action.name, action.details,
                             basket.value if basket else None)
        self._speaker.say(text, key=action.kind.value)
        return text
