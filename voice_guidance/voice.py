# ===================== NY FIL AV CLAUDE (2026-11-03) =====================
# Från handling till tal. Speaker är det enda motorn och rösten vet om ljudsystemet: en
# adapter mot audio_manager.py (nivå 3 i ljudkön, under akutlarm och Gemini) och en som
# bara skriver ut. audio_manager.py importeras först när adaptern skapas, eftersom importen
# startar Piper och telemetrin.
# =========================================================================
"""
voice.py - Gör GuidanceAction till ord och skickar dem till en Speaker.
"""
from __future__ import annotations

import time
from typing import Any, Optional, Protocol

from phrases import guidance_phrases, guidance_text

from .model import AimConvention, GuidanceAction

GUIDANCE_PRIORITY = 3   # audio_manager: 1 = akutlarm, 2 = Gemini, 3 = övrigt. Vägledning får aldrig gå före säkerhet.


class Speaker(Protocol):
    def say(self, text: str, key: Optional[str] = None) -> None:
        """Läs upp text. key identifierar typen av besked (används bara för loggning)."""


class ConsoleSpeaker:
    """Skriver bara ut. För test på dator, och när ljudsystemet saknas."""

    def say(self, text: str, key: Optional[str] = None) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] 🗨️  {text}" + (f"   ({key})" if key else ""))


class AudioManagerSpeaker:
    """Spelar upp via audio_manager.py. Fraserna ligger i Pi:ns ljudcache (python3 tts_engine.py --prewarm)."""

    def __init__(self, audio: Optional[Any] = None) -> None:
        if audio is None:
            from audio_manager import audio_system   # startar Piper-processen och telemetrin
            audio = audio_system
            audio.prewarm(guidance_phrases())         # ladda röstmodellen nu, inte vid första beskedet
        self._audio = audio

    def say(self, text: str, key: Optional[str] = None) -> None:
        self._audio.speak(text, priority=GUIDANCE_PRIORITY, key=key)


class GuidanceVoice:
    """Översätter en handling till svenska och läser upp den. Returnerar texten (för loggning och länk)."""

    def __init__(self, speaker: Speaker, convention: AimConvention = AimConvention.HEAD) -> None:
        self._speaker = speaker
        self._convention = convention

    @property
    def convention(self) -> AimConvention:
        return self._convention

    def announce(self, action: GuidanceAction) -> str:
        text = guidance_text(action.kind.value, self._convention.value, action.name)
        self._speaker.say(text, key=action.kind.value)
        return text
