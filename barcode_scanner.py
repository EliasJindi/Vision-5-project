# ===================== NY FIL (2026-10-13) =====================
# Grund: Geminis utkast. Granskad och rättad av Claude:
#  1. time.timedelta -> datetime.timedelta (kraschade när pipelinen byggdes)
#  2. msg.get("color") -> msg["color"] (MessageGroup saknar .get(), kraschade)
#  3. Hastighetsbegränsningen gäller ALLA bildrutor, inte bara de med kod
#     (annars avkodas 30 bildrutor/s på full CPU -> strömproblem)
#  4. Position läses från kartans GEOMETRI, inte attributen x/y
#     (flyttar man en punkt i QGIS uppdateras inte attributen)
#  5. Avbryter med tydligt fel om kartan inte kan läsas
#  6. setVideoSize(1280, 720) efter setIspScale, 15 fps, bara EAN-13/UPC-A
# Runda 2 (efter första testet på Pi: koderna lästes men djupet saknades):
#  7. Extended disparity: minsta mätbara avstånd ca halveras (OAK-D Lite ~35 cm -> ~20 cm)
#  8. Färgbilden i 1080p så att koder kan läsas längre bort, där djupet fungerar
#  9. Reservruta: om mitten saknar djup används hela streckkodens yta
# 10. Diagnostik som visar VARFÖR djupet saknas
# 11. --diag: sparar en bild varannan sekund + skriver ut ljus och skärpa
#     (för att se varför koder inte läses, utan att flytta sig ur position)
# 12. --4k: färgbilden i 3840x2160 (dubbelt så många pixlar per streck) med
#     5 fps och 2 avkodningar/s. Kräver USB3, varnar annars.
# Runda 3 (2026-10-15, efter dagsljustestet): loggningen var för tunn. Felläsningar
# syntes bara i terminalen, och 4K/1080p sparades inte, så det fick gissas i efterhand.
# 13. Loggar ALLA avläsningar: även okända varor, utan djup och ogiltiga koder.
#     Nya fält per rad: mode, raw, ean, in_map, w_px, px_per_modul, rot_deg,
#     hornen, bild, depth_how (och facit/correct om --facit används)
# 14. px per modul (pixlar per grundstreck) mäts från kodens hörnpunkter LÄNGS läsriktningen
#     (top_left -> top_right), inte som bredden i x-led. Rak och 90° roterad kod ger rätt
#     värde (testat med syntetiska koder med känd modulstorlek).
#     BEGRÄNSNINGAR (testade, syntetiska bilder):
#     - Vid andra vinklar än 0/90/180/270 mäter zxing längs en rak skanrad, så px_per_modul
#       blir för högt med 1/cos(vinkeln): +3,5 % vid 15°. Alltså optimistiskt.
#     - För streckkoder ger zxing en RAKT rektangel även när koden lutar åt sidan
#       (vänster och höger kant lika höga). Lutning går därför INTE att läsa ur hörnen.
#       Den måste mätas ur djupet (vänster mot höger sida). Inte gjort än.
#     - Antar att positionen omfattar de 95 modulerna. Kontrollera mot en riktig körning.
# 15. --facit EAN: anger rätt streckkod i testet. Varje läsning loggas som rätt/fel,
#     felläsningar skrivs ut som FELLÄSNING, och vid Ctrl+C visas en sammanfattning.
# 16. Läget (4k eller 1080p) står i loggfilens namn och i varje rad.
# 17. Räknar försök: antal avkodade bildrutor efter 10 s uppvärmning (autofokus och exponering
#     ställer in sig), hur många som hade en kod och hur många som hade RÄTT kod (--facit).
#     Visas vid Ctrl+C, så att träffprocent per avstånd går att räkna utan stoppur.
#     Bara i sammanfattningen i terminalen, inte i loggen.
# Runda 4 (2026-10-17, efter 4K- och 1080p-serierna): läsningar kom ofta bara medan autofokus
# SÖKTE (efter att paketet rörts) och inte när den hade landat, även med gott om pixlar.
# 18. Linspositionen (lins, 0-255), exponeringstiden (exp_us) och ISO loggas per läsning och
#     visas i --diag-raden. Då syns var autofokus landar och vid vilken linsposition koden läses.
#     Sammanfattningen visar linsposition för alla bildrutor jämfört med de med rätt kod.
# 19. --fokus N (0-255): låser linsen manuellt (autofokus av). Hittar man ett N som läser stabilt
#     vet vi att fokus var begränsningen. Okänt vilket N som motsvarar vilket avstånd på just den här
#     kameran: ta fram det med lins-värdena från 18. Skalan är kamerans egen, inte centimeter.
#     Inte testat mot riktig kamera. Pipelinen byggs och ratten sätts i testet, ingen enhet fanns.
# Runda 5 (2026-10-20, efter fokustesten 18 och 20 oktober): felläsningar kom nästan alltid från
# en tunn remsa av koden, och djupet var 3-13 m fel de första sekunderna (både "mitten" och
# "kodens yta"). Filtren nedan LOGGAR alltid vad de skulle göra. De avvisar bara med --filter,
# så att de kan utvärderas på nya körningar utan att data går förlorad.
# 20. Kodens höjd i bilden loggas: h_px (längs kodens sidor, fungerar även roterad) och
#     hojd_andel = h_px / w_px. Rätta läsningar på tomatpurén: ~0,6-0,7. Felläsningar: oftast 1-14 px.
# 21. Höjdfilter "tunn": hojd_andel < MIN_HEIGHT_RATIO (0,15). På loggarna 17-20/10 stoppade det
#     60 av 62 fel och kastade 135 av 1409 rätta. KÄND RISK: en hel men kort kod (t.ex. avkortade
#     streck på små förpackningar eller hyllkantsetiketter) kan ha höjd/bredd ~0,1 och avvisas.
#     Regeln (andel, pixlar eller båda) ska väljas med analyze_scans.py på nya körningar.
# 22. Djupfilter "orimligt djup": djupet jämförs med vad kodens storlek säger,
#     forvantat_djup_m = DEPTH_K[läge] / px_per_modul. Avvisas om det skiljer mer än DEPTH_FACTOR (3)
#     gånger åt något håll. DEPTH_K är uppmätt på tomatpurén (modul ~0,35 mm): djup * px/modul
#     ~0,51-0,55 m i 1080p och ~1,0 m i 4K. Faktor 3 täcker moduler ~0,12-1 mm.
#     Behandlar symptomet: varför djupet är fel i början är inte utrett.
# 23. --filter slår på avvisandet. Utan --filter visas "[filter: ...]" efter raden. Fältet "filter"
#     i loggen listar skälen. Sammanfattningen visar hur många rätta och fel varje filter fångade.
# Runda 6 (2026-10-20, efter extern granskning av runda 5):
# 24. Gränserna och filterreglerna ligger i scan_filters.py, så att analyze_scans.py kan använda
#     samma regler utan kameran.
# 25. De två filtren har olika följd med --filter. "tunn": koden går inte att lita på, läsningen
#     avvisas helt. "orimligt djup": koden är godkänd men avståndet inte, så varan sägs utan
#     position. Samma sak när djup saknas helt (förut sades varan inte alls då).
# 26. Sammanfattningen visar bildrutor med rätt kod både före filter (jämförbart med äldre körningar)
#     och efter höjdfiltret.
# 27. Sammanfattningen visar hur många bildrutor per sekund kameran levererade (mottagna, och enligt
#     kamerans sekvensnummer). Skannerns egen gräns (3/s i 1080p, 2/s i 4K) säger inget om USB.
# Runda 7 (2026-10-29, varutest): en Coca-Cola-flaska har EAN-8, som skannern inte läste.
# 28. EAN-8 läses också. normalize_ean godtar 8 siffror (samma kontrollsumma som EAN-13 med nollor
#     framför) och behåller dem som 8 siffror, även i --facit och kartan. px/modul räknas med 67
#     moduler för EAN-8 i stället för 95 (scan_filters.modules_for), annars blir px/modul och djupfiltret
#     fel. RISK att följa upp: zxing kan i sällsynta fall läsa en del av en EAN-13 som en EAN-8. Med
#     --facit syns det som felläsningar med format EAN-8 på en vara med 13 siffror.
# Runda 8 (2026-11-03): röstvägledning och länk till andra program, i paketet voice_guidance/.
# 29. --vagledning text|tal: motorn (voice_guidance.GuidanceEngine) får varje avkodad bildruta och
#     säger "lite närmare", riktning eller "håll stilla" när koden är osäker, och varans namn när
#     den lästs säkert. "tal" läser upp via audio_manager.py på nivå 3 (aldrig före akutlarm).
#     --sikte väljer riktningsorden (huvud/hand). Motorn bygger på samma loggrader som filen skriver.
# 30. --lank PORT: öppnar en JSON-länk på localhost (läsningar och vägledning ut, say-kommandon in)
#     så att t.ex. en C#-tjänst kan bygga applikationslogiken ovanpå. Protokoll: docs/ROSTVAGLEDNING.md.
# 31. Enhetstester i tests/ (python3 -m unittest discover -s tests -t .). Uppspelning mot gamla loggar:
#     python3 -m voice_guidance.replay logs/scan_*.jsonl
# 32. Kartans fält "info" (valfritt, text eller lista med högst 2 delar) läses upp efter namnet:
#     "Tomatpure. 140 gram. Hylla 3." För lång info stoppar starten med en förklaring. (2026-11-04)
# 33. Med --vagledning läggs bekräftade varor i en korg: "Tomatpure. 500 gram. Tillagd.", och
#     "Finns redan i korgen." om samma vara skannas igen. Korgen skrivs ut när skannern avslutas. (2026-11-05)
# 34. --fokusruta [ANDEL]: autofokus ställer bara skarpt på en ruta mitt i bilden (standard 40 % av bredd
#     och höjd), så att bakgrunden inte drar iväg fokus (B2 i förslaget 20/10). Utan flaggan som förut.
#     Rutan räknas i ISP-bildens pixlar. Det är inte verifierat på kameran att DepthAI tolkar dem så: se
#     linspositionen i --diag. (2026-11-05)
# 35. --hand (Elias idé 6/11: "man visar alltid produkter med handen"): det närmaste föremålet inom en
#     armlängd i djupbilden (hand_region.py) räknas som handen med varan. a) Kamerans autofokus OCH
#     exponering ställs in på den rutan via en kontrollkanal (XLinkIn "control"), högst två gånger per
#     sekund och bara när handen flyttat sig. Borta i 1 s: tillbaka till hela bilden. b) Rutan (med
#     marginal) avkodas först; hittas inget där avkodas hela bilden som förut, så en felaktig ruta kan
#     aldrig dölja en kod. Loggen får "hand", "hand_m" och "avkodat_i"; sammanfattningen visar
#     avkodningstiden. Rutan är testad med tools/narmast.py (8 av 8 bilder på handen); styrningen av
#     fokus är inte testad på kameran när den skrevs. (2026-11-06)
#     Ändrat 7/11 efter provet: fokusrutan gav linsläge 26-37 (fokus långt bort) och suddig vara.
#     Nu ställs linsen efter handens avstånd (hand_region.lens_for_distance, tabell ur
#     analyze_scans.py --lins), ljuset följer fortfarande handrutan. Borta i 1 s: autofokus igen.
# 36. Handläget är standard (Elias 7/11, efter 13-15 % mot 4 % utan). --utan-hand stänger av det;
#     --fokus och --fokusruta stänger också av det. --hand finns kvar och gör ingenting nytt.
#     --diag sparar bilderna i en egen mapp per körning, logs/snapshots/<loggens namn>/, så att
#     tools/mosaik.py kan visa äldre körningar (förut skrevs allt i samma mapp och rensades). (2026-11-07)
# Ingen säkerhetsregel (gå närmare / vrid) är inlagd: tröskeln måste först mätas upp
# per läge ur dessa loggar och valideras på andra körningar än de den togs fram på.
# Fristående (läser bara scan_filters.py). Kör ALDRIG samtidigt som detect_spatial.py.
# ===============================================================
"""
barcode_scanner.py - Positionsbestämning med produkter som landmärken.

Läser en streckkod med OAK-D, slår upp produkten i kartan (GeoJSON från QGIS)
och räknar ut var användaren står: produktens position + avståndet från
djupkameran, i riktningen som hyllans "facing" anger.

Kräver:  pip install zxing-cpp numpy   (depthai finns redan i venv)
Kör:     python3 barcode_scanner.py [kartor/produkter.geojson] [--diag] [--4k] [--facit EAN] [--fokus N] [--filter]
         --diag   sparar logs/snapshots/*.jpg varannan sekund och visar ljus/skärpa
         --4k     läser i 3840x2160 (längre läsavstånd, mer CPU/USB)
         --facit  rätt streckkod i testet, t.ex. 7340083497834: markerar felläsningar
         --fokus  låser linsen på position N (0-255), i stället för autofokus
         --filter avvisar tunna remsor, och ger ingen position vid orimligt djup (utan flaggan loggas det bara)
         --vagledning text|tal  röstvägledning: skriv ut eller läs upp beskeden (voice_guidance/)
         --sikte huvud|hand     riktningarna: vrid huvudet mot koden, eller flytta varan
         --lank PORT            länk till andra program på 127.0.0.1:PORT (JSON-rader)
         --utan-hand            stäng av handläget (standard sedan ändring 36: fokus efter handens avstånd)
Logg:    logs/scan_<datum>_<tid>_<4k|1080p>.jsonl (en rad per avläsning)
"""
import argparse
import json
import math
import os
import sys
import time
from datetime import timedelta

import cv2
import depthai as dai
import numpy as np
import zxingcpp

from hand_region import HandFocus, find_near_region, lens_for_distance
from scan_filters import FILTER_TEXT, depth_plausible, expected_depth, is_thin, modules_for, size_from_corners
from voice_guidance import AimConvention, GuidanceMode, create_session
from voice_guidance.catalog import parse_details

DEFAULT_MAP = "kartor/produkter.geojson"
WARMUP_S = 10               # försök räknas först efter detta (autofokus och exponering ställer in sig)
SCAN_INTERVAL_S = 0.33      # max ~3 avkodningar per sekund (strömbudget)
CAMERA_FPS = 15
COLOR_W, COLOR_H = 1920, 1080   # full upplösning: koder går att läsa längre bort
# --4k: dubbelt så många pixlar per streck. 4K-video kräver mycket USB-bandbredd,
# därför lägre fps, och avkodningen av en 4K-bild tar längre tid -> färre per sekund.
UHD_W, UHD_H = 3840, 2160
UHD_FPS = 5
UHD_SCAN_INTERVAL_S = 0.5
DEPTH_W, DEPTH_H = 1280, 720     # djupbilden kan vara mindre, koordinaterna skalas om
ROI_HALF_PX = 15            # djupet tas som median i en ruta på 31x31 px runt koden
MIN_VALID_PX = 20           # minst så många giltiga djuppixlar för att lita på medianen
DIAG_INTERVAL_S = 2.0      # --diag: en bild varannan sekund
DIAG_MAX_IMAGES = 60       # --diag: sluta spara efter så många (skonar SD-kortet)
BARCODE_FORMATS = (zxingcpp.BarcodeFormat.EAN13, zxingcpp.BarcodeFormat.UPCA, zxingcpp.BarcodeFormat.EAN8)
GUIDANCE_MODES = {None: GuidanceMode.OFF, "text": GuidanceMode.TEXT, "tal": GuidanceMode.VOICE}


def normalize_ean(code):
    """
    Returnerar en giltig EAN, eller None.
    En 12-siffrig UPC-A (783935132243) blir EAN-13 med inledande nolla (0783935132243).
    En EAN-8 (54036796) behålls som 8 siffror (ändring 28).
    """
    code = str(code).strip()
    if not code.isdigit() or len(code) not in (8, 12, 13):
        return None
    full = code.zfill(13)   # nollor framför ändrar inte kontrollsumman, så samma regel gäller EAN-8
    total = sum(int(full[i]) * (1 if i % 2 == 0 else 3) for i in range(12))
    if (10 - total % 10) % 10 != int(full[12]):
        return None
    return code if len(code) == 8 else full


def load_products(path):
    """{ean: [kandidat, ...]} - samma EAN kan finnas på flera platser."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"❌ Kunde inte läsa kartan {path}: {e}")

    products = {}
    for feat in data.get("features", []):
        p = feat.get("properties", {})
        ean = normalize_ean(p.get("ean", ""))
        if not ean:
            print(f"⚠️  Hoppar över {p.get('namn', '?')}: ogiltig streckkod {p.get('ean')!r}")
            continue
        x, y = feat["geometry"]["coordinates"][:2]   # geometrin är sanningen, inte attributen
        try:
            info = parse_details(p.get("info"))       # läses upp efter namnet (ändring 32)
        except ValueError as e:
            sys.exit(f"❌ {p.get('namn', '?')} i kartan {path}: {e}")
        products.setdefault(ean, []).append({
            "namn": p.get("namn", "?"),
            "x": float(x),
            "y": float(y),
            "ligger_pa": p.get("ligger_pa", "okänd plats"),
            "facing": p.get("facing", ""),
            "info": info,
        })

    if not products:
        sys.exit(f"❌ Inga giltiga produkter i {path}")
    return products


def user_position(cand, d):
    """Användaren står d meter framför produkten, på hyllans framsida."""
    if cand["facing"] == "+x":
        return cand["x"] + d, cand["y"]
    if cand["facing"] == "-x":
        return cand["x"] - d, cand["y"]
    if cand["facing"] == "+y":
        return cand["x"], cand["y"] + d
    if cand["facing"] == "-y":
        return cand["x"], cand["y"] - d
    return None


FOCUS_REGION_DEFAULT = 0.4   # --fokusruta utan värde: rutan är 40 % av bildens bredd och höjd


def focus_region(width, height, share):
    """Ruta mitt i bilden för autofokus: (x, y, bredd, höjd) i pixlar. share = andel av bredd och höjd."""
    if not 0 < share <= 1:
        raise ValueError(f"andelen måste ligga mellan 0 och 1, inte {share}")
    w, h = max(1, round(width * share)), max(1, round(height * share))
    return (width - w) // 2, (height - h) // 2, w, h


def build_pipeline(uhd=False, focus=None, focus_share=None, hand=False):
    pipeline = dai.Pipeline()
    fps = UHD_FPS if uhd else CAMERA_FPS

    cam = pipeline.create(dai.node.ColorCamera)
    cam.setBoardSocket(dai.CameraBoardSocket.CAM_A)
    if uhd:
        cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_4_K)
        cam.setVideoSize(UHD_W, UHD_H)
    else:
        cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        cam.setVideoSize(COLOR_W, COLOR_H)
    cam.setInterleaved(False)
    cam.setFps(fps)
    if focus is not None:
        cam.initialControl.setManualFocus(focus)   # låst lins, autofokus av
    elif focus_share is not None:
        # Autofokus bara på mitten (ändring 34). ISP-storleken = bilden kameran räknar fram före beskärning.
        cam.initialControl.setAutoFocusRegion(*focus_region(cam.getIspWidth(), cam.getIspHeight(), focus_share))

    mono_l = pipeline.create(dai.node.MonoCamera)
    mono_r = pipeline.create(dai.node.MonoCamera)
    for mono, socket in ((mono_l, dai.CameraBoardSocket.CAM_B), (mono_r, dai.CameraBoardSocket.CAM_C)):
        mono.setBoardSocket(socket)
        mono.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P)
        mono.setFps(fps)

    stereo = pipeline.create(dai.node.StereoDepth)
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
    # Streckkoder läses nära kameran. Utan detta saknas djup närmare än ca 35 cm.
    stereo.setExtendedDisparity(True)
    stereo.setSubpixel(False)          # krävs tillsammans med extended disparity
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)   # djup pixel för pixel mot färgbilden
    stereo.setOutputSize(DEPTH_W, DEPTH_H)
    mono_l.out.link(stereo.left)
    mono_r.out.link(stereo.right)

    # Sync parar ihop färg- och djupbild från samma ögonblick
    sync = pipeline.create(dai.node.Sync)
    sync.setSyncThreshold(timedelta(milliseconds=50))
    cam.video.link(sync.inputs["color"])
    stereo.depth.link(sync.inputs["depth"])

    xout = pipeline.create(dai.node.XLinkOut)
    xout.setStreamName("out")
    sync.out.link(xout.input)

    if hand:
        # Kontrollkanal: skannern flyttar autofokus och exponering till handen medan den kör (ändring 35)
        control = pipeline.create(dai.node.XLinkIn)
        control.setStreamName("control")
        control.out.link(cam.inputControl)
    return pipeline


class _Point:
    def __init__(self, x, y):
        self.x, self.y = x, y


class _Position:
    def __init__(self, position, dx, dy):
        for corner in ("top_left", "top_right", "bottom_right", "bottom_left"):
            p = getattr(position, corner)
            setattr(self, corner, _Point(p.x + dx, p.y + dy))


class ShiftedResult:
    """En zxing-läsning från en utskuren ruta, med hörnen flyttade till hela bildens koordinater."""

    def __init__(self, result, dx, dy):
        self.text, self.format = result.text, result.format
        self.position = _Position(result.position, dx, dy)


def decode_frame(color, crop=None):
    """
    Avkodar rutan crop (hand_region.NearRegion) först, och hela bilden om inget hittades där (ändring 35).
    Returnerar (läsningar, "ruta" eller "hela").
    """
    if crop is not None:
        h, w = color.shape[:2]
        x, y, cw, ch = crop.to_pixels(w, h)
        found = zxingcpp.read_barcodes(np.ascontiguousarray(color[y:y + ch, x:x + cw]), formats=BARCODE_FORMATS)
        if found:
            return [ShiftedResult(r, x, y) for r in found], "ruta"
    return zxingcpp.read_barcodes(color, formats=BARCODE_FORMATS), "hela"


def send_focus(control_queue, command, width, height):
    """
    Handen syns: linsen ställs efter handens avstånd och exponeringen efter handrutan.
    Handen borta: vanlig autofokus och exponering över hela bilden igen.
    """
    ctrl = dai.CameraControl()
    if command.region is not None:
        ctrl.setManualFocus(lens_for_distance(command.region.depth_m))
        ctrl.setAutoExposureRegion(*command.region.to_pixels(width, height))
    else:
        ctrl.setAutoFocusMode(dai.CameraControl.AutoFocusMode.CONTINUOUS_VIDEO)
        ctrl.setAutoExposureRegion(0, 0, width, height)
    control_queue.send(ctrl)


def _median_m(region):
    valid = region[region > 0]
    return (float(np.median(valid)) / 1000.0 if valid.size >= MIN_VALID_PX else None), int(valid.size)


def depth_at(depth_frame, color_shape, corners):
    """
    Median-djup (meter) vid streckkoden. Returnerar (avstånd eller None, förklaring).
    Försöker först en liten ruta i mitten, sedan hela kodens yta (+50 % marginal).
    """
    dh, dw = depth_frame.shape[:2]
    ch, cw = color_shape[:2]
    sx, sy = dw / cw, dh / ch            # färgbild -> djupbild
    xs = [c.x * sx for c in corners]
    ys = [c.y * sy for c in corners]
    cx, cy = int(sum(xs) / 4), int(sum(ys) / 4)

    d, n_center = _median_m(depth_frame[max(0, cy - ROI_HALF_PX):min(dh, cy + ROI_HALF_PX + 1),
                                        max(0, cx - ROI_HALF_PX):min(dw, cx + ROI_HALF_PX + 1)])
    if d is not None:
        return d, "mitten"

    # Reserv: hela streckkodens yta med marginal
    mx = max(10, int((max(xs) - min(xs)) * 0.5))
    my = max(10, int((max(ys) - min(ys)) * 0.5))
    x0, x1 = max(0, int(min(xs)) - mx), min(dw, int(max(xs)) + mx + 1)
    y0, y1 = max(0, int(min(ys)) - my), min(dh, int(max(ys)) + my + 1)
    d, n_box = _median_m(depth_frame[y0:y1, x0:x1])
    if d is not None:
        return d, "kodens yta"

    # Diagnostik: saknas djup bara här, eller i hela bilden?
    whole = float(np.count_nonzero(depth_frame)) / depth_frame.size
    if whole < 0.05:
        why = f"nästan inget djup i hela bilden ({whole:.0%}), kameran ser troligen för nära eller för mörkt"
    else:
        why = (f"djup finns i {whole:.0%} av bilden men inte vid koden "
               f"({n_center}+{n_box} giltiga px). För nära (<~20 cm) eller blank yta?")
    return None, why


def code_geometry(position, frame_shape, modules=95):
    """
    Kodens mått i bilden, mätta längs läsriktningen (hörnpunkterna), inte i x-led.
    px_per_modul = pixlar per grundstreck. rot_deg är bara pålitlig för 0/90/180/270 grader.
    Lutning åt sidan syns INTE här: zxing ger en rak rektangel för streckkoder.
    """
    tl, tr, br, bl = ((c.x, c.y) for c in (position.top_left, position.top_right,
                                           position.bottom_right, position.bottom_left))
    width, height = size_from_corners(tl, tr, br, bl)
    return {
        "w_px": round(width, 1),
        "h_px": round(height, 1),
        "hojd_andel": round(height / width, 3) if width else 0.0,
        "px_per_modul": round(width / modules, 2),
        "rot_deg": round(math.degrees(math.atan2(tr[1] - tl[1], tr[0] - tl[0])), 1),
        "hornen": [[round(x), round(y)] for x, y in (tl, tr, br, bl)],
        "bild": [frame_shape[1], frame_shape[0]],
    }


def frame_meta(frame_msg):
    """Linsposition (0-255), exponeringstid (mikrosekunder) och ISO för bilden. Tom dict om det saknas."""
    try:
        return {"lins": int(frame_msg.getLensPosition()),
                "exp_us": int(frame_msg.getExposureTime().total_seconds() * 1e6),
                "iso": int(frame_msg.getSensitivity())}
    except Exception:
        return {}


def write_log(log, rec):
    log.write(json.dumps(rec, ensure_ascii=False) + "\n")
    log.flush()
    os.fsync(log.fileno())   # överlever strömavbrott


def count_filters(stats, rec):
    """
    Hur många läsningar varje filter fångade, och med --facit hur många av dem som var rätt/fel.
    "Efter filter" räknar läsningar vars KOD godkändes (inte tunn). Orimligt djup påverkar bara positionen.
    """
    for reason in rec["filter"]:
        f = stats["filtered"].setdefault(reason, {"n": 0, "right": 0, "wrong": 0})
        f["n"] += 1
        if "correct" in rec:
            f["right" if rec["correct"] else "wrong"] += 1
    if "correct" in rec and "tunn" not in rec["filter"]:
        stats["kept_right" if rec["correct"] else "kept_wrong"] += 1


def handle_barcode(res, color, depth, products, log, now, mode="1080p", facit=None, stats=None, meta=None,
                   use_filter=False):
    """
    Loggar ALLA avläsningar (även okända, felaktiga och filtrerade), skriver ut de som har ett användbart svar.
    use_filter (ändring 25): "tunn" avvisar läsningen helt, "orimligt djup" ger varan utan position.
    Utan use_filter loggas och märks de bara. Returnerar loggraden.
    """
    ean = normalize_ean(res.text)
    geo = code_geometry(res.position, color.shape, modules_for(res.text))
    expected = expected_depth(geo["px_per_modul"], mode)
    rec = {"t": round(now, 3), "mode": mode, "raw": res.text, "ean": ean,
           "format": str(res.format), **geo, **(meta or {}),
           "forvantat_djup_m": round(expected, 3) if expected else None,
           "filter": ["tunn"] if is_thin(geo["hojd_andel"]) else []}
    tag = ""
    if facit:
        rec["facit"] = facit
        rec["correct"] = ean == facit
        if not rec["correct"]:
            tag = f"  ❌ FELLÄSNING (facit {facit})"
    if stats is not None:
        stats["reads"] += 1
        if facit:
            stats["right" if rec["correct"] else "wrong"] += 1
            stats["px_right" if rec["correct"] else "px_wrong"].append(geo["px_per_modul"])

    def done():
        if stats is not None and ean:
            count_filters(stats, rec)
        write_log(log, rec)

    if not ean:
        rec.update(in_map=False, distance_m=None, depth_how="ogiltig streckkod")
        done()
        return rec

    d, how = depth_at(depth, color.shape, (res.position.top_left, res.position.top_right,
                                           res.position.bottom_right, res.position.bottom_left))
    rec["in_map"] = ean in products
    rec["depth_how"] = how
    rec["distance_m"] = round(d, 3) if d is not None else None
    if d is not None and not depth_plausible(d, expected):
        rec["filter"].append("orimligt djup")
    px = f"{geo['px_per_modul']:.1f} px/modul"

    if use_filter and "tunn" in rec["filter"]:
        print(f"[{ean}] ⛔ avvisad: {FILTER_TEXT['tunn']}, {px}{tag}")
        done()
        return rec
    if not use_filter and rec["filter"]:
        tag += f"  [filter: {', '.join(FILTER_TEXT[r] for r in rec['filter'])}]"

    # Ingen position: djup saknas, eller (med --filter) djupet stämmer inte med kodens storlek.
    # Koden är godkänd, så varan sägs ändå.
    if d is None or (use_filter and "orimligt djup" in rec["filter"]):
        why = how if d is None else f"djupet {d:.2f} m är orimligt (väntat ~{expected:.2f} m)"
        if ean in products:
            name = products[ean][0]["namn"]
            print(f"\n--- {name} ({ean}), {px}{tag} ---")
            print(f"   ⚠️  Ingen position: {why}")
            rec.update(namn=name, candidates=[], ambiguous=False)
        else:
            print(f"\n[OKÄND VARA] {ean}, ingen position ({why}), {px} (finns inte i kartan){tag}")
        done()
        return rec

    if ean not in products:
        print(f"\n[OKÄND VARA] {ean}, {d:.2f} m bort, {px} (finns inte i kartan){tag}")
        done()
        return rec

    cands = products[ean]
    positions = []
    print(f"\n--- {cands[0]['namn']} ({ean}), {d:.2f} m bort (djup från {how}), {px}{tag} ---")
    for c in cands:
        pos = user_position(c, d)
        if pos is None:
            print(f"   ⚠️  {c['ligger_pa']}: okänd facing {c['facing']!r}")
            continue
        positions.append({"x": round(pos[0], 3), "y": round(pos[1], 3), "ligger_pa": c["ligger_pa"]})
        print(f"   📍 Du står vid x={pos[0]:.2f}, y={pos[1]:.2f} (framför {c['ligger_pa']})")
    ambiguous = len(positions) > 1
    if ambiguous:
        print(f"   ⚠️  Tvetydigt: varan finns på {len(positions)} platser")

    rec.update(namn=cands[0]["namn"], candidates=positions, ambiguous=ambiguous)
    done()
    return rec


def median_min(values, decimals=2):
    if not values:
        return "–"
    v = sorted(values)
    return f"median {v[len(v) // 2]:.{decimals}f}, min {v[0]:.{decimals}f}, max {v[-1]:.{decimals}f}"


def print_summary(mode, facit, stats, log_path, use_filter=False):
    print(f"\nSammanfattning ({mode}): {stats['reads']} avläsningar. Logg: {log_path}")
    tries = stats["tries"]
    if tries:
        line = f"  Försök efter {WARMUP_S} s uppvärmning: {tries} bildrutor, {stats['hit_frames']} med kod ({stats['hit_frames'] / tries:.0%})"
        if facit:
            line += (f", {stats['right_frames']} med rätt kod ({stats['right_frames'] / tries:.0%}) före filter"
                     f", {stats['right_frames_kept']} ({stats['right_frames_kept'] / tries:.0%}) efter höjdfiltret")
        print(line)
    if facit:
        print(f"  Facit {facit}: {stats['right']} rätt, {stats['wrong']} fel")
        print(f"  px/modul, rätta: {median_min(stats['px_right'])}")
        print(f"  px/modul, fel:   {median_min(stats['px_wrong'])}")
    if stats.get("lens_all"):
        print(f"  Linsposition, alla bildrutor:        {median_min(stats['lens_all'], 0)}")
        if stats.get("lens_hit"):
            print(f"  Linsposition, bildrutor med rätt kod: {median_min(stats['lens_hit'], 0)}")
    span = (stats["t_last"] or 0) - (stats["t_first"] or 0)
    if stats["msgs"] > 1 and span > 0:
        line = f"  Kameran: {(stats['msgs'] - 1) / span:.1f} bildrutor/s mottagna"
        if stats["seq_first"] is not None and stats["seq_last"] is not None:
            line += f", {(stats['seq_last'] - stats['seq_first']) / span:.1f}/s enligt kamerans sekvensnummer"
        print(line + f" (inställt {stats['fps_set']} fps, skannern avkodar högst {stats['scan_max']:.0f}/s)")
    if stats.get("decode_ms"):
        print(f"  Avkodning: median {np.median(stats['decode_ms']):.0f} ms per bild (max {max(stats['decode_ms']):.0f} ms)")
    if stats.get("hand_mode") and stats.get("decode_ms"):
        print(f"  Hand: hittad i {stats['hand_frames']} av {len(stats['decode_ms'])} avkodade bildrutor, "
              f"koden hittad i handrutan {stats['crop_hits']} gånger")
    print(f"  Filter ({'PÅ' if use_filter else 'AV, bara loggat'}):")
    if not stats["filtered"]:
        print("    inga läsningar fångades")
    for reason, f in stats["filtered"].items():
        line = f"    {FILTER_TEXT[reason]}: {f['n']} läsningar"
        if facit:
            line += f" ({f['right']} rätt kod, {f['wrong']} fel kod)"
        print(line)
    if facit:
        print(f"  Efter höjdfiltret (koden godkänd): {stats['kept_right']} rätt, {stats['kept_wrong']} fel")


def diagnose(color, results, n_saved, folder, meta=None):
    """Ljus och skärpa i bilden, och sparar en märkt bild. Returnerar en statusrad."""
    gray = cv2.cvtColor(cv2.resize(color, (960, 540)), cv2.COLOR_BGR2GRAY)
    brightness = float(gray.mean())                              # 0 = svart, 255 = vitt
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())     # lågt = suddigt
    status = (f"📷 ljus {brightness:3.0f}/255 ({'mörkt' if brightness < 60 else 'ok'})  "
              f"skärpa {sharpness:5.0f} ({'suddigt' if sharpness < 50 else 'ok'})  "
              f"{'lins %3d  ' % meta['lins'] if meta and 'lins' in meta else ''}"
              f"{'hand %.2f m  ' % meta['hand_m'] if meta and 'hand_m' in meta else ''}"
              f"koder: {[r.text for r in results] or 'inga'}")

    if n_saved < DIAG_MAX_IMAGES:
        img = color.copy()
        if meta and "hand" in meta:   # blå ruta: det skannern tror är handen med varan (ändring 35)
            h, w = img.shape[:2]
            x0, y0, x1, y1 = meta["hand"]
            cv2.rectangle(img, (int(x0 * w), int(y0 * h)), (int(x1 * w), int(y1 * h)), (255, 128, 0), 6)
        for r in results:
            pts = np.array([[c.x, c.y] for c in (r.position.top_left, r.position.top_right,
                                                 r.position.bottom_right, r.position.bottom_left)], np.int32)
            cv2.polylines(img, [pts], True, (0, 255, 0), 4)
        # OpenCV kan inte rita å/ä/ö
        ascii_status = status.replace("📷 ", "").translate(str.maketrans("åäöÅÄÖ", "aaoAAO"))
        cv2.putText(img, ascii_status, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
        path = os.path.join(folder, f"snap_{n_saved + 1:03d}_{time.strftime('%H%M%S')}.jpg")
        cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        status += f"  → {path}"
    return status


def main():
    ap = argparse.ArgumentParser(description="Position från streckkoder (produkter som landmärken)")
    ap.add_argument("karta", nargs="?", default=DEFAULT_MAP)
    ap.add_argument("--diag", action="store_true", help="spara bilder och visa ljus/skärpa varannan sekund")
    ap.add_argument("--4k", dest="uhd", action="store_true", help="läs i 3840x2160 (längre läsavstånd)")
    ap.add_argument("--fokus", type=int, metavar="N",
                    help="lås linsen på position N (0-255) i stället för autofokus")
    ap.add_argument("--fokusruta", type=float, nargs="?", const=FOCUS_REGION_DEFAULT, metavar="ANDEL",
                    help=f"autofokus bara på en ruta mitt i bilden (andel av bredd och höjd, standard {FOCUS_REGION_DEFAULT})")
    ap.add_argument("--hand", action="store_true",
                    help="handläget (standard): fokus efter handens avstånd, ljus och avkodning på handen med varan")
    ap.add_argument("--utan-hand", dest="utan_hand", action="store_true",
                    help="stäng av handläget: vanlig autofokus och hela bilden")
    ap.add_argument("--facit", metavar="EAN",
                    help="rätt streckkod i testet: loggar varje läsning som rätt/fel och märker felläsningar")
    ap.add_argument("--filter", action="store_true",
                    help="avvisa tunna remsor, ingen position vid orimligt djup (utan flaggan loggas det bara)")
    ap.add_argument("--vagledning", choices=("text", "tal"),
                    help="röstvägledning: text = skriv ut beskeden, tal = läs upp dem (docs/ROSTVAGLEDNING.md)")
    ap.add_argument("--sikte", choices=("huvud", "hand"), default="huvud",
                    help="vägledningens riktningar: huvud = vrid huvudet mot koden, hand = flytta varan")
    ap.add_argument("--lank", type=int, metavar="PORT",
                    help="öppna en länk på 127.0.0.1:PORT för andra program (JSON-rader). 0 = välj ledig port")
    args = ap.parse_args()
    if args.fokus is not None and not 0 <= args.fokus <= 255:
        sys.exit(f"❌ --fokus {args.fokus} är utanför 0-255")
    if args.fokusruta is not None and not 0.1 <= args.fokusruta <= 1.0:
        sys.exit(f"❌ --fokusruta {args.fokusruta} ska ligga mellan 0,1 och 1,0")
    if args.fokusruta is not None and args.fokus is not None:
        sys.exit("❌ --fokus låser linsen och --fokusruta styr autofokus: välj en av dem")
    if args.hand and (args.fokus is not None or args.fokusruta is not None):
        sys.exit("❌ --hand styr fokus själv: använd den utan --fokus och --fokusruta")
    if args.hand and args.utan_hand:
        sys.exit("❌ --hand och --utan-hand: välj en")
    use_hand = not args.utan_hand and args.fokus is None and args.fokusruta is None   # standard (ändring 36)
    if args.lank is not None and not 0 <= args.lank <= 65535:
        sys.exit(f"❌ --lank {args.lank} är ingen giltig port (0-65535)")
    facit = None
    if args.facit:
        facit = normalize_ean(args.facit)
        if not facit:
            sys.exit(f"❌ --facit {args.facit!r} är ingen giltig EAN-13/EAN-8/UPC-A (fel längd eller kontrollsiffra)")
    map_path = args.karta
    products = load_products(map_path)
    n_places = sum(len(v) for v in products.values())
    print(f"Karta: {len(products)} streckkoder på {n_places} platser ({map_path})")

    mode = "4k" if args.uhd else "1080p"
    os.makedirs("logs", exist_ok=True)
    log_path = f"logs/scan_{time.strftime('%Y%m%d_%H%M%S')}_{mode}.jsonl"
    stats = {"reads": 0, "right": 0, "wrong": 0, "px_right": [], "px_wrong": [],
             "tries": 0, "hit_frames": 0, "right_frames": 0, "lens_all": [], "lens_hit": [],
             "filtered": {}, "kept_right": 0, "kept_wrong": 0, "right_frames_kept": 0,
             "msgs": 0, "t_first": None, "t_last": None, "seq_first": None, "seq_last": None,
             "decode_ms": [], "hand_frames": 0, "crop_hits": 0, "hand_mode": use_hand}
    if facit:
        print(f"Facit: {facit}. Felläsningar markeras.")

    scan_interval = UHD_SCAN_INTERVAL_S if args.uhd else SCAN_INTERVAL_S
    stats["fps_set"] = UHD_FPS if args.uhd else CAMERA_FPS
    stats["scan_max"] = 1 / scan_interval
    try:
        session = create_session(products, GUIDANCE_MODES[args.vagledning],
                                 AimConvention.HEAD if args.sikte == "huvud" else AimConvention.HAND, args.lank)
    except OSError as e:   # t.ex. porten är upptagen
        sys.exit(f"❌ Kunde inte öppna länken på port {args.lank}: {e}")
    with dai.Device(build_pipeline(uhd=args.uhd, focus=args.fokus, focus_share=args.fokusruta, hand=use_hand)) as device, open(log_path, "a", encoding="utf-8") as log:
        usb = device.getUsbSpeed()
        print(f"Kamera: {'4K 3840x2160 @ ' + str(UHD_FPS) if args.uhd else '1080p @ ' + str(CAMERA_FPS)} fps, USB {usb.name}")
        if args.fokus is not None:
            print(f"Fokus: manuell, linsposition {args.fokus}")
        elif args.fokusruta is not None:
            print(f"Fokus: autofokus, bara rutan i mitten ({args.fokusruta * 100:.0f} % av bredd och höjd)")
        elif use_hand:
            print("Fokus: efter handens avstånd, ljuset efter handen (det närmaste inom en armlängd); utan hand autofokus")
        else:
            print("Fokus: autofokus")
        print(f"Filter: {'PÅ (avvisar tunna remsor, ingen position vid orimligt djup)' if args.filter else 'AV (loggas och märks bara)'}")
        if args.uhd and usb not in (dai.UsbSpeed.SUPER, dai.UsbSpeed.SUPER_PLUS):
            print("⚠️  4K kräver USB3 (blå port). Med USB2 kan bilden hacka eller utebli.")
        q = device.getOutputQueue(name="out", maxSize=4, blocking=False)
        control_q = device.getInputQueue("control") if use_hand else None
        hand_focus = HandFocus() if use_hand else None
        print(f"Söker efter streckkoder (max ~{1 / scan_interval:.0f}/s). Loggar till {log_path}. Ctrl+C avslutar.")
        last_scan = last_diag = 0.0
        started = time.time()
        n_saved = 0
        diag_dir = os.path.join("logs", "snapshots", os.path.basename(log_path)[:-len(".jsonl")])   # ändring 36
        if args.diag:
            os.makedirs(diag_dir, exist_ok=True)
            print(f"Diagnostik PÅ: bild var {DIAG_INTERVAL_S:.0f}:e sekund till {diag_dir}/ (max {DIAG_MAX_IMAGES})")
        try:
            while True:
                msg = q.get()
                now = time.time()
                # Hur många bildrutor kameran faktiskt levererar (ändring 27), före skannerns egen gräns
                stats["msgs"] += 1
                stats["t_first"] = stats["t_first"] or now
                stats["t_last"] = now
                try:
                    seq = msg["color"].getSequenceNum()
                    stats["seq_first"] = seq if stats["seq_first"] is None else stats["seq_first"]
                    stats["seq_last"] = seq
                except Exception:
                    pass
                # Begränsa ALLA avkodningar, även när ingen kod syns (CPU = ström)
                if now - last_scan < scan_interval:
                    continue
                last_scan = now

                color = msg["color"].getCvFrame()
                meta = frame_meta(msg["color"])
                depth = msg["depth"].getFrame()   # uint16, millimeter
                t_decode = time.perf_counter()
                if hand_focus is not None:
                    region = find_near_region(depth)
                    command = hand_focus.update(now, region)
                    if command is not None:
                        send_focus(control_q, command, color.shape[1], color.shape[0])
                    results, where = decode_frame(color, hand_focus.crop(now))
                    meta["avkodat_i"] = where
                    if region is not None:
                        meta["hand"] = [round(v, 3) for v in (region.x0, region.y0, region.x1, region.y1)]
                        meta["hand_m"] = round(region.depth_m, 3)
                else:
                    results, where = decode_frame(color)
                stats["decode_ms"].append((time.perf_counter() - t_decode) * 1000)
                stats["hand_frames"] += "hand" in meta
                stats["crop_hits"] += where == "ruta"
                recs = [handle_barcode(res, color, depth, products, log, now, mode, facit, stats, meta, args.filter)
                        for res in results]
                session.on_frame(now, recs)   # röstvägledning och länk (ändring 29-31), även utan läsning
                if now - started >= WARMUP_S:
                    stats["right_frames_kept"] += any(r.get("correct") and "tunn" not in r["filter"] for r in recs)
                    stats["tries"] += 1
                    if "lins" in meta:
                        stats["lens_all"].append(meta["lins"])
                        if facit and any(normalize_ean(r.text) == facit for r in results):
                            stats["lens_hit"].append(meta["lins"])
                    stats["hit_frames"] += bool(results)
                    stats["right_frames"] += bool(facit and any(normalize_ean(r.text) == facit for r in results))

                if args.diag and now - last_diag >= DIAG_INTERVAL_S:
                    last_diag = now
                    print(diagnose(color, results, n_saved, diag_dir, meta))
                    n_saved += 1
        except KeyboardInterrupt:
            print("\nAvslutar.")
        finally:
            session.close()
        print_summary(mode, facit, stats, log_path, args.filter)
        if args.vagledning:
            print(f"  {session.basket.summary()}")


if __name__ == "__main__":
    main()
