# ===================== NY FIL AV CLAUDE (2026-11-13) =====================
# Steg 1 av dialogen med användaren (HANDOFF avsnitt 7, Elias 13/11): knappar från laptopen, utan AI och
# utan nät. Programmet ansluter till skannerns länk (--lank), lyssnar på besked och korg, och ber rösten
# svara med kommandot "say". Skannern ändras inte. Svaren spelas på nivå 3 i ljudkön, som vägledningen,
# så de går aldrig före ett akutlarm.
#   Terminal 1:  python3 barcode_scanner.py --4k --vagledning tal --sikte hand --filter --lank 5555
#   Terminal 2:  python3 tools/knappar.py        (starta den innan varor läggs i korgen)
# Tangenter: mellanslag = upprepa, S = senaste varan, K = korgen, H = hjälp, Q = avsluta.
# 13/11 kväll: svaren är hela meningar utan kolon, och bokstäverna i hjälpen stavas som de låter ("Ess",
# "Kå", "Hå"). Elias provlyssnade på Pi:n: "Senast: Tomatpure." och "S, senaste varan." lät konstigt,
# "Senaste varan var Tomatpure, 500 gram." och "Ess, senaste varan." mycket bättre.
# =========================================================================
import argparse
import json
import os
import selectors
import socket
import sys
import time
from typing import Dict, List, Mapping, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # projektets rot

from voice_guidance.link import MAX_SAY_CHARS   # noqa: E402

CUE_TEXT = "♪"   # pipet (voice_guidance.voice), inget att upprepa
NUMBERS = {2: "två", 3: "tre", 4: "fyra", 5: "fem", 6: "sex", 7: "sju", 8: "åtta", 9: "nio", 10: "tio"}
HELP = "Mellanslag, hör igen. Ess, senaste varan. Kå, korgen. Hå, hjälp."   # bokstäverna stavade som de låter
KEYS = {" ": "repeat", "s": "last", "k": "basket", "h": "help"}


def _sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "!", "?")) else text + "."


def _fit(text: str, limit: int = MAX_SAY_CHARS) -> str:
    """Länken tar högst limit tecken. Kortar vid ett ordslut."""
    if len(text) <= limit:
        return text
    cut = text[:limit - 1].rsplit(" ", 1)[0].rstrip(",.")
    return cut + "."


class ButtonState:
    """Det programmet vet från länkens händelser: senaste beskedet, senaste varan och korgen."""

    def __init__(self) -> None:
        self.last_text: Optional[str] = None
        self.last_product: Optional[str] = None
        self._basket: Dict[str, str] = {}   # ean -> namn, i den ordning de lades i

    def on_event(self, event: Mapping) -> None:
        if event.get("type") != "guidance":
            return
        text = event.get("text")
        if isinstance(text, str) and text.strip() and text != CUE_TEXT:
            self.last_text = text.strip()
        action = event.get("action")
        if action == "confirmed" and event.get("name"):
            details = [d.strip().rstrip(".") for d in (event.get("details") or []) if isinstance(d, str) and d.strip()]
            self.last_product = ", ".join([str(event["name"]).strip().rstrip("."), *details])
            if event.get("basket") == "added" and event.get("ean"):
                self._basket.setdefault(str(event["ean"]), str(event["name"]))
        elif action == "unknown_product":
            self.last_product = "en okänd vara"

    def basket(self) -> List[str]:
        return list(self._basket.values())

    def answer(self, what: str) -> str:
        if what == "repeat":
            return _fit(self.last_text) if self.last_text else "Inget att upprepa än."
        if what == "last":
            return _fit(_sentence(f"Senaste varan var {self.last_product}")) if self.last_product else "Ingen vara är skannad än."
        if what == "basket":
            return basket_text(self.basket())
        if what == "help":
            return HELP
        raise ValueError(f"okänd fråga {what!r}")


def basket_text(names: List[str], limit: int = MAX_SAY_CHARS) -> str:
    """"Korgen är tom.", "Du har Tomatpure i korgen.", "Du har två varor i korgen, Tomatpure och Linser."
    Ryms alltid i limit."""
    n = len(names)
    if n == 0:
        return "Korgen är tom."
    if n == 1:
        return _fit(f"Du har {names[0]} i korgen.", limit)
    head = f"Du har {NUMBERS.get(n, str(n))} varor i korgen"
    for shown in range(n, 0, -1):
        rest = n - shown
        listed = names[:shown]
        if rest:
            body = ", ".join(listed) + f" och {rest} till"
        elif shown > 1:
            body = ", ".join(listed[:-1]) + " och " + listed[-1]
        else:
            body = listed[0]
        text = f"{head}, {body}."
        if len(text) <= limit:
            return text
    return _fit(f"{head}.", limit)


class LinkClient:
    """En anslutning till skannerns länk: händelser in, say-kommandon ut."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5555, timeout: float = 3.0) -> None:
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(None)
        self._buffer = b""

    def say(self, text: str) -> None:
        self.sock.sendall(json.dumps({"cmd": "say", "text": text}, ensure_ascii=False).encode("utf-8") + b"\n")

    def receive(self) -> Optional[List[dict]]:
        """Läser det som finns och ger händelserna. None när skannern stängt länken."""
        data = self.sock.recv(65536)
        if not data:
            return None
        self._buffer += data
        events = []
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict):
                events.append(obj)
        return events

    def close(self) -> None:
        self.sock.close()


def handle_key(client: LinkClient, state: ButtonState, key: str) -> Optional[str]:
    """Skickar svaret på en tangent till rösten. Ger texten, eller None för en tangent utan funktion."""
    what = KEYS.get(key.lower())
    if what is None:
        return None
    text = state.answer(what)
    client.say(text)
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description="Knappar från laptopen: upprepa, senaste varan, korgen, hjälp")
    ap.add_argument("--port", type=int, default=5555, help="skannerns --lank (standard 5555)")
    args = ap.parse_args()
    try:
        client = LinkClient(port=args.port)
    except OSError as e:
        print(f"❌ Kunde inte ansluta till 127.0.0.1:{args.port} ({e}). Starta skannern med --lank {args.port} först.")
        return 1
    state = ButtonState()
    print(f"⌨️  Ansluten till skannern på port {args.port}. {HELP} Q avslutar.")
    fd = sys.stdin.fileno()
    tty_state = None
    if sys.stdin.isatty():
        import termios
        import tty
        tty_state = termios.tcgetattr(fd)
        tty.setcbreak(fd)   # en tangent i taget, utan Enter
    sel = selectors.DefaultSelector()
    sel.register(client.sock, selectors.EVENT_READ, "link")
    sel.register(fd, selectors.EVENT_READ, "keys")
    try:
        while True:
            for key, _ in sel.select():
                if key.data == "link":
                    events = client.receive()
                    if events is None:
                        print("Skannern stängde länken. Avslutar.")
                        return 0
                    for event in events:
                        state.on_event(event)
                        if event.get("type") == "error":
                            print(f"⚠️  Skannern svarade: {event.get('reason')}")
                else:
                    chunk = os.read(fd, 64).decode("utf-8", "ignore")
                    if not chunk:
                        return 0
                    for ch in (chunk if tty_state else (chunk.strip()[:1] or " ")):
                        if ch.lower() == "q":
                            print("Avslutar.")
                            return 0
                        text = handle_key(client, state, ch)
                        if text:
                            label = "mellanslag" if ch == " " else ch.upper()
                            print(f"[{time.strftime('%H:%M:%S')}] ⌨️  {label} → {text}")
    except KeyboardInterrupt:
        print("\nAvslutar.")
        return 0
    finally:
        if tty_state is not None:
            import termios
            termios.tcsetattr(fd, termios.TCSADRAIN, tty_state)
        client.close()


if __name__ == "__main__":
    sys.exit(main())
