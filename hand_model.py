# ===================== NY FIL AV CLAUDE (2026-11-09) =====================
# Handmodellen (MediaPipe i två steg) som delas av skannern och tools/handmodell.py.
# 1. Handflatemodellen (palm_detection_sh4.blob, 128x128) föreslår var en handflata finns.
# 2. Landmärkesmodellen (hand_landmark_lite_sh4.blob, 224x224) tittar på handrutan och ger ett eget
#    värde för "det här är en hand". Den sorterar bort falsklarm som handflatemodellen ensam ger.
# Mätt med tools/handmodell.py 9/11 (hela bilden, regeln "bekräftad inom 2 s"): med vara i handen
# 83 % (saltburk) och 83 % (ättiksflaska); bordet med varor utan händer 0 % och 0 % (landmärkesvärden
# högst 0,04, gränsen 0,5). Handflatemodellen ensam räknade bordet som hand i 16-55 %.
# Modellerna: MediaPipe (Google, Apache 2.0), omvandlade för OAK-kameran av github.com/geaxgx/depthai_hand_tracker.
# Laddas ner till models/ av tools/handmodell.py (skannern laddar aldrig ner något själv). models/ är i .gitignore.
# Funktionerna här är ren numpy och testas utan kamera; HandModel behöver depthai och OpenCV.
# =========================================================================
"""
hand_model.py - Är det närmaste föremålet en hand? Handflatemodell + landmärkesmodell på kameran.
"""
from __future__ import annotations

import hashlib
import math
import os
import time
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np

MODEL_PATH = "models/palm_detection_sh4.blob"
MODEL_URL = "https://raw.githubusercontent.com/geaxgx/depthai_hand_tracker/main/models/palm_detection_sh4.blob"
MODEL_SHA256 = "4d45ecfddc68d8365fef3cb633d78b916612f25f7a48898f90f8a47d4b151aa5"
INPUT = 128           # modellens bild: 128 x 128
# Steg 2 i MediaPipe (väg B, Elias 9/11): landmärkesmodellen (21 punkter på handen) bekräftar en handflata
# med ett eget värde för "det här är en hand". Lätta versionen, standard i referenskoden.
LM_PATH = "models/hand_landmark_lite_sh4.blob"
LM_URL = "https://raw.githubusercontent.com/geaxgx/depthai_hand_tracker/main/models/hand_landmark_lite_sh4.blob"
LM_SHA256 = "98f2e9642099a572c96e80af944212efec199cdea1995ef391fab0d3a9da45fd"
LM_INPUT = 224        # landmärkesmodellens bild: 224 x 224


@dataclass(frozen=True)
class Palm:
    """En handflata som modellen hittat. Koordinater 0-1 i den bild de gäller (se square_to_frame)."""
    score: float
    x0: float
    y0: float
    x1: float
    y1: float
    kps: Tuple[Tuple[float, float], ...] = ()   # 7 punkter (0 = handleden, 2 = långfingrets knoge)


def palm_anchors(size: int = INPUT) -> np.ndarray:
    """
    Mitten (x, y) på modellens 896 ankarrutor, i samma ordning som modellens utdata. MediaPipe:
    4 lager med steg 8, 16, 16, 16 och 2 rutor per lager och cell (fast storlek 1x1). Lagren med
    samma steg slås ihop: 16x16 celler x 2 + 8x8 celler x 6 = 512 + 384 = 896.
    """
    anchors = []
    for stride, per_cell in ((8, 2), (16, 6)):
        cells = math.ceil(size / stride)
        for y in range(cells):
            for x in range(cells):
                anchors += [((x + 0.5) / cells, (y + 0.5) / cells)] * per_cell
    return np.array(anchors, dtype=np.float32)


def decode_palms(scores: Sequence[float], regressors: Sequence[float], anchors: np.ndarray,
                 threshold: float = 0.5, size: int = INPUT) -> List[Palm]:
    """
    Modellens utdata till rutor (0-1 i den kvadratiska bilden). scores: 896 råvärden (före sigmoid).
    regressors: 896 x 18 (mitt x, mitt y, bredd, höjd i pixlar relativt ankaret, sedan 7 punkter).
    """
    raw = np.clip(np.asarray(scores, dtype=np.float32).reshape(-1), -100, 100)   # som MediaPipe
    prob = 1 / (1 + np.exp(-raw))
    reg = np.asarray(regressors, dtype=np.float32).reshape(len(anchors), -1)
    palms = []
    for i in np.nonzero(prob > threshold)[0]:
        cx = reg[i, 0] / size + anchors[i, 0]
        cy = reg[i, 1] / size + anchors[i, 1]
        w, h = reg[i, 2] / size, reg[i, 3] / size
        if w <= 0 or h <= 0:
            continue
        kps = tuple((float(reg[i, 4 + 2 * k] / size + anchors[i, 0]), float(reg[i, 5 + 2 * k] / size + anchors[i, 1]))
                    for k in range(7))
        palms.append(Palm(float(prob[i]), float(cx - w / 2), float(cy - h / 2), float(cx + w / 2), float(cy + h / 2), kps))
    return palms


def hand_rect(palm: Palm, ox: float, oy: float, side: float, scale: float = 2.6,
              shift_y: float = -0.5) -> List[Tuple[float, float]]:
    """
    Handrutan som landmärkesmodellen ska se, som fyra hörn i kamerabildens pixlar. palm är i den
    kvadratiska modellbilden (0-1); kvadratens övre vänstra hörn ligger på (ox, oy) och sidan är side
    pixlar i kamerabilden. Som MediaPipes palm_detection_detection_to_roi: vriden så att handleden är
    nere och långfingret uppe, flyttad en halv handflata mot fingrarna, scale gånger handflatans
    längsta sida. Hörnen: [nere vänster, uppe vänster, uppe höger, nere höger] i handens riktning.
    """
    (x0, y0), (x2, y2) = palm.kps[0], palm.kps[2]
    rotation = math.pi / 2 - math.atan2(-(y2 - y0), x2 - x0)
    rotation = rotation - 2 * math.pi * math.floor((rotation + math.pi) / (2 * math.pi))
    w, h = (palm.x1 - palm.x0) * side, (palm.y1 - palm.y0) * side
    cx = ox + (palm.x0 + palm.x1) / 2 * side - h * shift_y * math.sin(rotation)
    cy = oy + (palm.y0 + palm.y1) / 2 * side + h * shift_y * math.cos(rotation)
    size = max(w, h) * scale
    b, a = math.cos(rotation) * 0.5, math.sin(rotation) * 0.5
    p0 = (cx - a * size - b * size, cy + b * size - a * size)
    p1 = (cx + a * size - b * size, cy - b * size - a * size)
    return [p0, p1, (2 * cx - p0[0], 2 * cy - p0[1]), (2 * cx - p1[0], 2 * cy - p1[1])]


def iou(a: Palm, b: Palm) -> float:
    ix = max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))
    iy = max(0.0, min(a.y1, b.y1) - max(a.y0, b.y0))
    inter = ix * iy
    union = (a.x1 - a.x0) * (a.y1 - a.y0) + (b.x1 - b.x0) * (b.y1 - b.y0) - inter
    return inter / union if union > 0 else 0.0


def non_max_suppression(palms: List[Palm], overlap: float = 0.3, keep: int = 2) -> List[Palm]:
    """Bästa rutan per hand: rutor som täcker en bättre till mer än overlap tas bort. Högst keep händer."""
    kept: List[Palm] = []
    for p in sorted(palms, key=lambda p: -p.score):
        if all(iou(p, k) <= overlap for k in kept):
            kept.append(p)
        if len(kept) == keep:
            break
    return kept


def square_to_frame(palm: Palm, width: int, height: int) -> Palm:
    """
    Från den kvadratiska modellbilden till kamerabilden (0-1). Kamerabilden (bredare än hög) läggs
    i mitten av kvadraten med svarta kanter över och under, se letterbox().
    """
    pad = (width - height) / 2 / width          # kanten ovanför, som andel av kvadratens sida
    scale = width / height                      # en enhet i kvadraten = så många bildhöjder
    def y(v: float) -> float:
        return min(1.0, max(0.0, (v - pad) * scale))
    return Palm(palm.score, min(1.0, max(0.0, palm.x0)), y(palm.y0), min(1.0, max(0.0, palm.x1)), y(palm.y1))


def letterbox_rows(width: int, height: int, size: int = INPUT) -> Tuple[int, int, int]:
    """(bildens höjd i modellbilden, svart kant över, svart kant under) för en bild width x height."""
    h = round(size * height / width)
    top = (size - h) // 2
    return h, top, size - h - top


def overlaps(region, palm: Palm, margin: float = 0.05, share: float = 0.25) -> bool:
    """
    Ligger handen i den blå rutan (hand_region.NearRegion)? Minst share av handens ruta ska ligga
    inom den blå rutan, utökad med margin (handen kan sticka ut lite bakom varan).
    """
    x0, y0 = region.x0 - margin, region.y0 - margin
    x1, y1 = region.x1 + margin, region.y1 + margin
    ix = max(0.0, min(x1, palm.x1) - max(x0, palm.x0))
    iy = max(0.0, min(y1, palm.y1) - max(y0, palm.y0))
    area = (palm.x1 - palm.x0) * (palm.y1 - palm.y0)
    return area > 0 and ix * iy / area >= share


def shrink_factor(pts: Sequence[Tuple[float, float]], size: int = LM_INPUT) -> int:
    """
    Hur många gånger kamerabilden ska förminskas (med medelvärden) innan handrutan skärs ut, så att
    rutan blir mellan size och 2 x size pixlar. warpAffine tar enstaka pixlar: krymper den en 4K-ruta
    3-5 gånger direkt blir handen kornig (körningen vara1_lm 9/11: riktiga händer median 0,30).
    """
    side = math.dist(pts[1], pts[2])
    return max(1, int(side // size))


class ModelError(Exception):
    """En modell saknas eller är fel fil."""


def ensure_model(path: str = MODEL_PATH, url: str = MODEL_URL, sha256: str = MODEL_SHA256,
                 download: bool = True) -> str:
    """
    Kontrollerar att modellen finns och är rätt fil (sha256). download=True laddar ner den om den
    saknas (tools/handmodell.py); skannern använder download=False och startar utan handmodell.
    """
    if not os.path.exists(path):
        if not download:
            raise ModelError(f"{path} saknas")
        import urllib.request
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        print(f"Laddar ner {os.path.basename(path)} till {path} …")
        urllib.request.urlretrieve(url, path + ".tmp")
        os.replace(path + ".tmp", path)
    with open(path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    if digest != sha256:
        if download:
            os.remove(path)
        raise ModelError(f"{path} är inte den väntade modellen (sha256 {digest[:12]}…)")
    return path


class HandGate:
    """
    Regeln för skannern: det närmaste föremålet räknas som en hand om landmärkesmodellen har
    bekräftat en hand i det någon gång de senaste window sekunderna (den här bildrutan medräknad).
    """

    def __init__(self, window: float = 2.0) -> None:
        self._window = window
        self._last = float("-inf")

    def update(self, t: float, confirmed: bool) -> None:
        if confirmed:
            self._last = t

    def active(self, t: float) -> bool:
        return t - self._last <= self._window


class HandModel:
    """
    Båda modellerna på kamerans processor. add_to() lägger dem i kamerauppsättningen före start,
    attach() kopplar köerna efter start, check() ger landmärkesvärdet (0-1) för den bästa handflatan
    i den blå rutan, 0 om ingen handflata ligger där. Tiden per anrop sparas i ms.
    """

    def __init__(self, palm_path: str = MODEL_PATH, lm_path: str = LM_PATH,
                 palm_threshold: float = 0.5, lm_threshold: float = 0.5) -> None:
        self.palm_path, self.lm_path = palm_path, lm_path
        self.palm_threshold, self.lm_threshold = palm_threshold, lm_threshold
        self.anchors = palm_anchors()
        self.ms: List[float] = []
        self._queues = None

    def add_to(self, pipeline) -> None:
        import depthai as dai
        for blob, name, size in ((self.palm_path, "palm", INPUT), (self.lm_path, "lm", LM_INPUT)):
            nn = pipeline.create(dai.node.NeuralNetwork)
            nn.setBlobPath(blob)
            nn.input.setBlocking(True)
            nn.input.setQueueSize(1)
            xin = pipeline.create(dai.node.XLinkIn)
            xin.setStreamName(f"{name}_in")
            xin.setMaxDataSize(size * size * 3)
            xin.out.link(nn.input)
            xout = pipeline.create(dai.node.XLinkOut)
            xout.setStreamName(f"{name}_out")
            nn.out.link(xout.input)

    def attach(self, device) -> None:
        self._queues = {name: (device.getInputQueue(f"{name}_in"),
                               device.getOutputQueue(f"{name}_out", maxSize=1, blocking=True))
                        for name in ("palm", "lm")}

    def _run(self, name: str, square: np.ndarray):
        import depthai as dai
        q_in, q_out = self._queues[name]
        frame = dai.ImgFrame()
        frame.setType(dai.ImgFrame.Type.BGR888p)
        frame.setWidth(square.shape[1])
        frame.setHeight(square.shape[0])
        frame.setData(square.transpose(2, 0, 1).flatten())
        q_in.send(frame)
        return q_out.get()

    def palms(self, color: np.ndarray) -> List[Tuple[Palm, Palm]]:
        """Handflatorna i hela bilden: (i den kvadratiska modellbilden, i kamerabilden)."""
        import cv2
        h_px, w_px = color.shape[:2]
        h, top, bottom = letterbox_rows(w_px, h_px)
        small = cv2.copyMakeBorder(cv2.resize(color, (INPUT, h), interpolation=cv2.INTER_AREA),
                                   top, bottom, 0, 0, cv2.BORDER_CONSTANT)
        out = self._run("palm", small)
        found = non_max_suppression(decode_palms(out.getLayerFp16("classificators"), out.getLayerFp16("regressors"),
                                                 self.anchors, self.palm_threshold))
        return [(p, square_to_frame(p, w_px, h_px)) for p in found]

    def hand_score(self, color: np.ndarray, palm: Palm, shrunk: dict) -> float:
        """Landmärkesvärdet för handrutan runt palm (i hela bildens kvadrat). shrunk: förminskade bilder."""
        import cv2
        h_px, w_px = color.shape[:2]
        pts = hand_rect(palm, 0, -(w_px - h_px) / 2, w_px)
        k = shrink_factor(pts)
        if k not in shrunk:
            shrunk[k] = color if k == 1 else cv2.resize(color, (w_px // k, h_px // k), interpolation=cv2.INTER_AREA)
        img = shrunk[k]
        sx, sy = img.shape[1] / w_px, img.shape[0] / h_px
        mat = cv2.getAffineTransform(np.float32([(x * sx, y * sy) for x, y in pts[1:]]),
                                     np.float32([(0, 0), (LM_INPUT, 0), (LM_INPUT, LM_INPUT)]))
        out = self._run("lm", cv2.warpAffine(img, mat, (LM_INPUT, LM_INPUT)))
        return float(out.getLayerFp16("Identity_1")[0])

    def check(self, color: np.ndarray, region, max_hands: int = 2) -> float:
        """Det högsta landmärkesvärdet bland handflatorna i den blå rutan (region), 0 om ingen ligger där."""
        t = time.perf_counter()
        inside = [sq for sq, fr in self.palms(color) if overlaps(region, fr)][:max_hands]
        shrunk: dict = {}
        best = max((self.hand_score(color, sq, shrunk) for sq in inside), default=0.0)
        self.ms.append((time.perf_counter() - t) * 1000)
        return best


def load(palm_path: str = MODEL_PATH, lm_path: str = LM_PATH) -> Tuple[Optional[HandModel], str]:
    """Handmodellen om båda filerna finns och är rätt, annars (None, varför). Laddar inte ner något."""
    try:
        ensure_model(palm_path, MODEL_URL, MODEL_SHA256, download=False)
        ensure_model(lm_path, LM_URL, LM_SHA256, download=False)
    except (ModelError, OSError) as e:
        return None, str(e)
    return HandModel(palm_path, lm_path), ""
