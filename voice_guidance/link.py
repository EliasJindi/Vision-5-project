# ===================== NY FIL AV CLAUDE (2026-11-03) =====================
# Länken mellan skannern (Python, äger kameran) och program som vill bygga ovanpå den, till
# exempel en C#-tjänst med applikationslogiken. Protokollet står i docs/ROSTVAGLEDNING.md.
# Säkerhet: lyssnar bara på localhost, tar bara emot kommandot "say", och det spelas alltid på
# nivå 3 i ljudkön. Ett externt program kan alltså aldrig utlösa eller klippa ett akutlarm.
# =========================================================================
"""
link.py - JSON-rader över en lokal TCP-port (en händelse eller ett kommando per rad).

Ut (skanner -> klient):  {"type": "hello", "protocol": 1}
                         {"type": "read", ...loggraden...}
                         {"type": "guidance", "t": ..., "action": ..., "ean": ..., "name": ..., "text": ...}
                         {"type": "error", "reason": "..."}   (svar på ett felaktigt kommando)
In (klient -> skanner):  {"cmd": "say", "text": "Lite närmare."}
"""
from __future__ import annotations

import json
import socket
import threading
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Protocol, Set, Union

PROTOCOL_VERSION = 1
LOOPBACK_HOSTS = ("127.0.0.1", "::1", "localhost")
MAX_LINE_BYTES = 4096
MAX_SAY_CHARS = 120


class EventPublisher(Protocol):
    def publish(self, event: Mapping[str, Any]) -> None: ...
    def close(self) -> None: ...


class NullPublisher:
    """Ingen länk. Används när ingen annan tjänst ska ansluta."""

    def publish(self, event: Mapping[str, Any]) -> None:
        pass

    def close(self) -> None:
        pass


class CommandError(ValueError):
    """Ett kommando från en klient som inte går att tolka eller inte är tillåtet."""


@dataclass(frozen=True)
class SayCommand:
    text: str


def parse_command(line: Union[bytes, str]) -> SayCommand:
    """Tolkar en rad från en klient. Ger CommandError med en förklaring som skickas tillbaka till klienten."""
    try:
        obj = json.loads(line)
    except (ValueError, UnicodeDecodeError):
        raise CommandError("raden är inte giltig JSON") from None
    if not isinstance(obj, dict) or obj.get("cmd") != "say":
        raise CommandError('okänt kommando, bara {"cmd": "say", "text": "..."} stöds')
    text = obj.get("text")
    if not isinstance(text, str) or not text.strip():
        raise CommandError('"text" måste vara en icke-tom sträng')
    text = text.strip()
    if len(text) > MAX_SAY_CHARS or not text.isprintable():
        raise CommandError(f'"text" får vara högst {MAX_SAY_CHARS} tecken och inga styrtecken')
    return SayCommand(text)


class TcpJsonLink:
    """
    Skickar händelser till alla anslutna klienter och tar emot say-kommandon.
    publish() blockerar aldrig kameraloopen länge: en klient som inte hänger med
    (skrivning tar längre än send_timeout_s) kopplas bort.
    """

    def __init__(self, port: int = 0, host: str = "127.0.0.1",
                 on_say: Optional[Callable[[SayCommand], None]] = None,
                 send_timeout_s: float = 0.2) -> None:
        if host not in LOOPBACK_HOSTS:
            raise ValueError(f"länken får bara lyssna på localhost, inte {host!r}")
        self._host, self._port = host, port
        self._on_say = on_say
        self._send_timeout_s = send_timeout_s
        self._lock = threading.Lock()
        self._clients: Set[socket.socket] = set()
        self._closed = threading.Event()
        self._server: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None

    # ---------- livscykel ----------
    def start(self) -> int:
        """Börjar lyssna. Returnerar porten (användbart när port=0 väljer en ledig)."""
        server = socket.socket(socket.AF_INET6 if ":" in self._host else socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self._host, self._port))
        server.listen()
        server.settimeout(0.2)
        self._server = server
        self._thread = threading.Thread(target=self._accept_loop, name="link-accept", daemon=True)
        self._thread.start()
        return self.port

    @property
    def port(self) -> int:
        if self._server is None:
            raise RuntimeError("länken är inte startad")
        return self._server.getsockname()[1]

    def close(self) -> None:
        self._closed.set()
        if self._server is not None:
            self._server.close()
        with self._lock:
            for conn in list(self._clients):
                self._drop_locked(conn)
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    # ---------- ut ----------
    def publish(self, event: Mapping[str, Any]) -> None:
        data = _encode(event)
        with self._lock:
            for conn in list(self._clients):
                self._send_locked(conn, data)

    def _send_locked(self, conn: socket.socket, data: bytes) -> None:
        try:
            conn.sendall(data)
        except OSError:   # inkl. timeout: klienten hänger inte med eller har gått
            self._drop_locked(conn)

    def _drop_locked(self, conn: socket.socket) -> None:
        self._clients.discard(conn)
        try:
            conn.close()
        except OSError:
            pass

    # ---------- in ----------
    def _accept_loop(self) -> None:
        while not self._closed.is_set():
            try:
                conn, _ = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            conn.settimeout(self._send_timeout_s)
            with self._lock:
                self._clients.add(conn)
                self._send_locked(conn, _encode({"type": "hello", "protocol": PROTOCOL_VERSION}))
            threading.Thread(target=self._read_loop, args=(conn,), name="link-client", daemon=True).start()

    def _read_loop(self, conn: socket.socket) -> None:
        buffer = b""
        while not self._closed.is_set():
            try:
                chunk = conn.recv(1024)
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                self._handle_line(conn, line)
            if len(buffer) > MAX_LINE_BYTES:
                self._reply_error(conn, "raden är för lång")
                break
        with self._lock:
            self._drop_locked(conn)

    def _handle_line(self, conn: socket.socket, line: bytes) -> None:
        if not line.strip():
            return
        try:
            command = parse_command(line)
        except CommandError as e:
            self._reply_error(conn, str(e))
            return
        if self._on_say is None:
            self._reply_error(conn, "skannern tar inte emot say-kommandon just nu")
            return
        try:
            self._on_say(command)
        except Exception as e:   # en trasig callback får inte döda läsartråden
            print(f"⚠️  [Länk] say-kommandot misslyckades: {e!r}")
            self._reply_error(conn, "kommandot kunde inte utföras")

    def _reply_error(self, conn: socket.socket, reason: str) -> None:
        with self._lock:
            if conn in self._clients:
                self._send_locked(conn, _encode({"type": "error", "reason": reason}))


def _encode(event: Mapping[str, Any]) -> bytes:
    return (json.dumps(event, ensure_ascii=False, separators=(",", ":"), default=str) + "\n").encode("utf-8")
