# ===================== NY FIL AV CLAUDE (2026-11-03) =====================
# Spelar upp GuidanceEngine mot sparade skannerloggar (logs/scan_*.jsonl), utan kamera och
# utan ljud. Syftet: se vad motorn hade sagt, och framför allt hur ofta den hade sagt FEL
# vara (--facit i loggen), innan något testas på riktigt. Läser bara loggarna.
# Loggarna innehåller bara bildrutor där en kod lästes. Tiden i loggen räcker för motorn,
# som glömmer gamla läsningar utifrån tidsstämplarna.
# =========================================================================
"""
replay.py - Vad hade röstvägledningen sagt under de här körningarna?

    python3 -m voice_guidance.replay logs/scan_20261029_*.jsonl
    python3 -m voice_guidance.replay logs/scan_*.jsonl --karta kartor/produkter.geojson --sikte hand
    python3 -m voice_guidance.replay logs/scan_20261029_*.jsonl --satt lost_after_s=8 --satt min_interval_s=2.5
"""
from __future__ import annotations

import argparse
import dataclasses
import glob
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

from analyze_scans import read_log
from phrases import guidance_text

from .catalog import DictProductCatalog, EmptyProductCatalog, ProductCatalog
from .engine import GuidanceConfig, GuidanceEngine
from .model import ActionKind, AimConvention, CodeRead, FrameObservation, GuidanceAction

_CONFIRMATIONS = (ActionKind.CONFIRMED, ActionKind.UNKNOWN_PRODUCT)


@dataclass(frozen=True)
class ReplayEvent:
    t: float
    action: GuidanceAction
    correct: Optional[bool]   # bara för bekräftelser och bara om loggen har --facit: stämde varan?


@dataclass
class ReplayReport:
    name: str
    frames: int = 0
    events: List[ReplayEvent] = field(default_factory=list)

    def count(self, kind: ActionKind) -> int:
        return sum(1 for e in self.events if e.action.kind is kind)

    @property
    def confirmations(self) -> List[ReplayEvent]:
        return [e for e in self.events if e.action.kind in _CONFIRMATIONS]

    @property
    def wrong_confirmations(self) -> List[ReplayEvent]:
        return [e for e in self.confirmations if e.correct is False]


def frames_from_records(records: Iterable[Mapping[str, Any]]) -> Iterator[Tuple[float, List[Mapping[str, Any]]]]:
    """Läsningar med samma tidsstämpel kommer från samma bildruta (handle_barcode får en tid per ruta)."""
    frame: List[Mapping[str, Any]] = []
    for rec in records:
        if frame and rec.get("t") != frame[0].get("t"):
            yield float(frame[0]["t"]), frame
            frame = []
        frame.append(rec)
    if frame:
        yield float(frame[0]["t"]), frame


def replay(records: Sequence[Mapping[str, Any]], engine: GuidanceEngine, name: str = "") -> ReplayReport:
    facit = next((r["facit"] for r in records if r.get("facit")), None)
    report = ReplayReport(name)
    for t, recs in frames_from_records(r for r in records if "t" in r):
        reads = []
        for rec in recs:
            try:
                reads.append(CodeRead.from_record(rec))
            except ValueError:
                pass   # äldre eller trasig rad: hoppa över, precis som GuidanceSession
        report.frames += 1
        action = engine.update(FrameObservation(t, tuple(reads)))
        if action is not None:
            correct = (action.ean == facit) if (facit and action.kind in _CONFIRMATIONS) else None
            report.events.append(ReplayEvent(t, action, correct))
    return report


def print_report(report: ReplayReport, records: Sequence[Mapping[str, Any]], convention: AimConvention) -> None:
    start = float(records[0]["t"]) if records else 0.0
    spoken = [e for e in report.events if e.action.kind is not ActionKind.CODE_SEEN]   # pip bara i summan
    print(f"\n== {report.name}: {report.frames} bildrutor med läsning, {len(spoken)} besked")
    for e in spoken:
        mark = {True: " ✅", False: " ❌ FEL VARA"}.get(e.correct, "")
        text = guidance_text(e.action.kind.value, convention.value, e.action.name, e.action.details)
        print(f"  +{e.t - start:6.1f} s  {text:28s} ({e.action.kind.value}){mark}")
    summary = ", ".join(f"{k.value} {report.count(k)}" for k in ActionKind if report.count(k))
    print(f"  Sammanfattning: {summary or 'tyst'}")


def _parse(raw: str, kind: type) -> object:
    """Ett värde från kommandoraden. bool('false') är True i Python, så ja/nej tolkas för sig."""
    if kind is bool:
        words = {"true": True, "ja": True, "1": True, "false": False, "nej": False, "0": False}
        if raw.lower() not in words:
            raise ValueError(raw)
        return words[raw.lower()]
    return kind(raw)


def build_config(overrides: Sequence[str]) -> GuidanceConfig:
    """Standardvärdena med några ändrade, ur flaggor som 'lost_after_s=8'. SystemExit med förklaring vid fel."""
    defaults = GuidanceConfig()
    values = {}
    for item in overrides:
        name, separator, raw = item.partition("=")
        if not separator or not hasattr(defaults, name):
            valid = ", ".join(f.name for f in dataclasses.fields(GuidanceConfig))
            raise SystemExit(f"❌ --satt {item!r}: använd NAMN=VÄRDE med något av: {valid}")
        try:
            values[name] = _parse(raw, type(getattr(defaults, name)))
        except ValueError:
            raise SystemExit(f"❌ --satt {item!r}: {raw!r} är inget giltigt värde") from None
    try:
        return dataclasses.replace(defaults, **values)
    except ValueError as e:
        raise SystemExit(f"❌ --satt: {e}") from None


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Spela upp röstvägledningen mot gamla skannerloggar")
    ap.add_argument("loggar", nargs="+", help="logs/scan_*.jsonl")
    ap.add_argument("--karta", help="produktkartan (geojson), för varunamn. Utan den blir allt 'okänd vara'")
    ap.add_argument("--sikte", choices=("huvud", "hand"), default="huvud")
    ap.add_argument("--satt", action="append", default=[], metavar="NAMN=VÄRDE",
                    help="ändra en tröskel för den här uppspelningen, t.ex. --satt lost_after_s=8 (kan upprepas)")
    args = ap.parse_args(argv)

    config = build_config(args.satt)
    if args.satt:
        print("Ändrade trösklar: " + ", ".join(args.satt))
    catalog: ProductCatalog = DictProductCatalog.from_geojson(args.karta) if args.karta else EmptyProductCatalog()
    convention = AimConvention.HEAD if args.sikte == "huvud" else AimConvention.HAND
    paths = sorted({p for pattern in args.loggar for p in (glob.glob(pattern) or [pattern])})

    totals: Counter = Counter()
    for path in paths:
        records = read_log(path)
        if not records:
            continue
        report = replay(records, GuidanceEngine(catalog, config), path.split("/")[-1])
        print_report(report, records, convention)
        totals["loggar"] += 1
        totals["bekräftelser"] += len(report.confirmations)
        totals["fel vara"] += len(report.wrong_confirmations)
        totals["vägledningar"] += len(report.events) - len(report.confirmations)
    print(f"\nTotalt: {totals['loggar']} loggar, {totals['bekräftelser']} bekräftelser varav "
          f"{totals['fel vara']} fel vara, {totals['vägledningar']} vägledningar.")
    return 1 if totals["fel vara"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
