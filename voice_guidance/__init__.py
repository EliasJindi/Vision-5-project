# ===================== NY FIL AV CLAUDE (2026-11-03) =====================
# Röstvägledning för streckkodsskannern. Se docs/ROSTVAGLEDNING.md.
# =========================================================================
"""
voice_guidance - Säger åt användaren vad hen ska göra för att få en streckkod läst säkert,
och bekräftar varan när den är läst.

    model.py    vad motorn får in och ger ut (CodeRead, FrameObservation, GuidanceAction)
    engine.py   beslutslogiken (GuidanceEngine), ren och utan ljud eller kamera
    catalog.py  varunamn per EAN
    voice.py    handling -> svenska -> Speaker (audio_manager eller utskrift)
    link.py     JSON-rader över localhost till andra program (t.ex. en C#-tjänst)
    session.py  binder ihop allt: skannern anropar bara GuidanceSession.on_frame()
    replay.py   spelar upp motorn mot gamla loggar, utan kamera
"""
from .catalog import DictProductCatalog, EmptyProductCatalog, ProductCatalog
from .engine import GuidanceConfig, GuidanceEngine
from .link import CommandError, EventPublisher, NullPublisher, SayCommand, TcpJsonLink, parse_command
from .model import ActionKind, AimConvention, CodeRead, FrameObservation, GuidanceAction
from .session import GuidanceMode, GuidanceSession, create_session
from .voice import AudioManagerSpeaker, ConsoleSpeaker, GuidanceVoice, Speaker

__all__ = [
    "ActionKind", "AimConvention", "AudioManagerSpeaker", "CodeRead", "CommandError", "ConsoleSpeaker",
    "DictProductCatalog", "EmptyProductCatalog", "EventPublisher", "FrameObservation", "GuidanceAction",
    "GuidanceConfig", "GuidanceEngine", "GuidanceMode", "GuidanceSession", "GuidanceVoice", "NullPublisher",
    "ProductCatalog", "SayCommand", "Speaker", "TcpJsonLink", "create_session", "parse_command",
]
