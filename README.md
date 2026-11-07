# Vision-5

AI-glasögon för synskadade, med matinköp som scenario. Raspberry Pi 5 och en OAK-D Lite-kamera.
Den här filen visar vad som finns var. Hela bakgrunden, resultaten och nästa steg står i `HANDOFF.md`.

## Vad ligger var

| Var | Vad |
|---|---|
| `barcode_scanner.py` | **Streckkodsskannern.** Läser koder, slår upp varan i kartan och ger röstvägledning |
| `detect_spatial.py` | Hinder och akutlarm (YOLO + djup), Gemini-knapp. Körs inte samtidigt som skannern |
| `hand_region.py` | Fokus på handen: hittar det närmaste föremålet och ställer linsen efter avståndet |
| `scan_filters.py` | Höjd- och djupfilter som avvisar felläsningar |
| `voice_guidance/` | Röstvägledningen: beslutslogik, röst, korg, länk till andra program |
| `audio_manager.py`, `tts_engine.py`, `phrases.py` | Ljudkö, talsyntes (Piper) och alla fraser |
| `gemini_service.py`, `telemetry_logger.py` | Gemini-anrop och mätning av ström och temperatur |
| `analyze_scans.py`, `analyze_telemetry.py`, `measure_phrases.py` | Analys av loggar och fraslängd |
| `tools/` | Hjälpverktyg: USB-test, siktebild, mosaik av en körning, handtest, mätning av streckkodsdetektorn |
| `tests/` | Enhetstester |
| `docs/` | `ROSTVAGLEDNING.md` (regler och protokoll). `docs/rapporter/` har arbetsloggarna som PDF |
| `ej_anvant/` | Gammalt som inte används. Ligger i `.gitignore` |

Finns bara på Pi:n och aldrig på GitHub (repot är publikt): `.env`, `kartor/`, `logs/`, `cache/`, röstmodellen (`*.onnx`), `piper/` och alla bilder.

## Vanliga kommandon (på Pi:n, i `~/ai_glasses`)

```
git pull --ff-only                                    # hämta senaste koden
python3 tools/usb_hastighet.py                        # går kameran på USB 3?
clear && sleep 15 && python3 barcode_scanner.py --4k --vagledning tal --sikte hand --filter --diag
python3 tools/mosaik.py NAMN                          # vad såg kameran i senaste körningen?
python3 analyze_scans.py --pixlar                     # säkra och osäkra läsningar
python3 -m unittest discover -s tests -t .            # alla tester
```

Fler kommandon och förklaringar: `HANDOFF.md`, avsnitt 9.
