# ===================== NY FIL AV CLAUDE (2026-11-06) =====================
# Hittar det som hålls fram mot kameran: det närmaste föremålet inom en armlängd i djupbilden.
# Idé från Elias 6/11: "man visar alltid produkter med handen", så leta efter handen med varan
# i stället för i hela bilden. Varan hamnade ofta i bildens nederkant medan autofokus ställde
# skarpt på bakgrunden i mitten (mosaikerna 6/11). Med rutan kan fokus, ljus och avkodning
# läggas där varan faktiskt är, och rösten kan guida efter den även när ingen kod syns.
# Ren numpy, ingen kamera: testas i tests/test_hand_region.py. Används först av tools/narmast.py.
# 2026-11-06 (steg 2): HandFocus bestämmer när kamerans fokus och ljus ska flyttas till handen och
#   vilken ruta skannern ska läsa först (barcode_scanner.py --hand). tools/narmast.py visade rutan
#   på handen med varan i 8 av 8 bilder.
# 2026-11-07: fokus ställs efter handens AVSTÅND (lens_for_distance), inte med en fokusruta. Provet
#   7/11: med fokusrutan stod linsen på 26-37 (långt bort) trots att handen var på 0,3-0,5 m, och
#   varan var suddig. analyze_scans.py --lins: alla säkra läsningar har skett vid linsläge 66-92.
# =========================================================================
"""
hand_region.py - Rutan runt det närmaste föremålet (handen med varan) i en djupbild.

Djupbilden delas i celler (medianen per cell, så att brus och hål inte stör). Celler mellan
min_mm och max_mm är "nära". Bland dem tas det närmaste skiktet (närmast + band_mm), och av
det den största sammanhängande ytan. Det skiljer handen från t.ex. en bordskant längre bort.
"""
from __future__ import annotations

import warnings
from collections import deque
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class NearRegion:
    """Rutan i normaliserade koordinater: (0,0) = övre vänstra hörnet, (1,1) = nedre högra."""
    x0: float
    y0: float
    x1: float
    y1: float
    depth_m: float      # medianavstånd till ytan
    area: float         # andel av bilden

    @property
    def center(self) -> Tuple[float, float]:
        return (self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2

    @property
    def size(self) -> Tuple[float, float]:
        return self.x1 - self.x0, self.y1 - self.y0

    def expanded(self, margin: float) -> "NearRegion":
        """Större åt alla håll med margin (andel av bilden), men inom bilden."""
        return NearRegion(max(0.0, self.x0 - margin), max(0.0, self.y0 - margin),
                          min(1.0, self.x1 + margin), min(1.0, self.y1 + margin), self.depth_m, self.area)

    def to_pixels(self, width: int, height: int) -> Tuple[int, int, int, int]:
        """(x, y, bredd, höjd) i en bild av given storlek."""
        x, y = int(self.x0 * width), int(self.y0 * height)
        return x, y, max(1, int(self.x1 * width) - x), max(1, int(self.y1 * height) - y)


def cell_medians(depth_mm: np.ndarray, cell: int, min_valid: float = 0.3) -> np.ndarray:
    """Median per cell (mm). NaN där för få pixlar har djup (0 = inget djup)."""
    h, w = depth_mm.shape[:2]
    gh, gw = h // cell, w // cell
    if gh == 0 or gw == 0:
        raise ValueError(f"djupbilden {w}x{h} är mindre än en cell ({cell} px)")
    blocks = depth_mm[:gh * cell, :gw * cell].astype(np.float32)
    blocks = blocks.reshape(gh, cell, gw, cell).transpose(0, 2, 1, 3).reshape(gh, gw, cell * cell)
    blocks[blocks <= 0] = np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)   # celler helt utan djup ger NaN, det är meningen
        med = np.nanmedian(blocks, axis=2)
    valid = np.mean(~np.isnan(blocks), axis=2) >= min_valid
    return np.where(valid, med, np.nan)


def _components(mask: np.ndarray) -> List[List[Tuple[int, int]]]:
    """Sammanhängande ytor (4-grannar) i en boolesk matris."""
    seen = np.zeros_like(mask, dtype=bool)
    parts = []
    for start in zip(*np.nonzero(mask)):
        if seen[start]:
            continue
        seen[start] = True
        part, todo = [], deque([start])
        while todo:
            y, x = todo.popleft()
            part.append((y, x))
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    todo.append((ny, nx))
        parts.append(part)
    return parts


def find_near_region(depth_mm: np.ndarray, min_mm: int = 200, max_mm: int = 800, band_mm: int = 150,
                     cell: int = 20, min_cells: int = 6) -> Optional[NearRegion]:
    """
    Rutan runt det närmaste föremålet inom [min_mm, max_mm], eller None.
    min_mm 200: närmare än ~20 cm finns inget djup. max_mm 800: ungefär en armlängd.
    band_mm 150: hand och vara räknas som samma skikt, en bordskant längre bort inte.
    min_cells 6: mindre ytor är brus.
    """
    med = cell_medians(depth_mm, cell)
    near = (med >= min_mm) & (med <= max_mm)          # NaN ger False
    if not near.any():
        return None
    closest = float(np.percentile(med[near], 5))      # inte minimum: en enda brusig cell ska inte styra
    layer = near & (med <= closest + band_mm)
    parts = [p for p in _components(layer) if len(p) >= min_cells]
    if not parts:
        return None
    part = max(parts, key=len)
    ys, xs = zip(*part)
    gh, gw = med.shape
    return NearRegion(x0=min(xs) / gw, y0=min(ys) / gh, x1=(max(xs) + 1) / gw, y1=(max(ys) + 1) / gh,
                      depth_m=float(np.median([med[p] for p in part])) / 1000, area=len(part) / (gh * gw))


# Linsläge per avstånd: medianer från analyze_scans.py --lins 7/11 (1 614 säkra, rätta läsningar från
# 50 körningar). 0,35-0,50 m är viktat efter antal körningar (2, 6 och 4); över 0,5 m bygger på 1-2
# körningar. Under 0,20 m är djupet opålitligt och räknas inte. Mellan punkterna interpoleras linjärt.
LENS_TABLE = ((0.225, 82), (0.275, 76), (0.325, 76), (0.425, 74), (0.55, 67), (0.675, 66))


def lens_for_distance(distance_m: float) -> int:
    """Linsläget (0-255) där en kod på distance_m meter har lästs säkert, enligt LENS_TABLE."""
    if distance_m <= LENS_TABLE[0][0]:
        return LENS_TABLE[0][1]
    for (d0, l0), (d1, l1) in zip(LENS_TABLE, LENS_TABLE[1:]):
        if distance_m <= d1:
            return int(round(l0 + (l1 - l0) * (distance_m - d0) / (d1 - d0)))
    return LENS_TABLE[-1][1]


@dataclass(frozen=True)
class FocusCommand:
    """Flytta kamerans fokus och ljus till region, eller tillbaka till hela bilden (region None)."""
    region: Optional[NearRegion]


class HandFocus:
    """
    Följer handen mellan bildrutorna. update() säger när kameran ska få en ny fokusruta (bara när
    handen flyttat sig märkbart, och högst var min_interval_s), och när den ska återgå till hela
    bilden (handen borta i lost_after_s). crop() är rutan som skannern läser först.
    """

    def __init__(self, min_interval_s: float = 0.5, move: float = 0.05, grow: float = 0.2,
                 lost_after_s: float = 1.0, margin: float = 0.1, closer: float = 0.03) -> None:
        self._min_interval_s, self._move, self._grow, self._closer = min_interval_s, move, grow, closer
        self._lost_after_s, self._margin = lost_after_s, margin
        self._current: Optional[NearRegion] = None   # senast sedda handen
        self._sent: Optional[NearRegion] = None      # rutan kameran fokuserar på (None = hela bilden)
        self._last_seen = float("-inf")
        self._last_sent = float("-inf")

    def update(self, t: float, region: Optional[NearRegion]) -> Optional[FocusCommand]:
        if region is not None:
            self._current, self._last_seen = region, t
            if self._sent is None or (self._moved(region, self._sent) and t - self._last_sent >= self._min_interval_s):
                self._sent, self._last_sent = region, t
                return FocusCommand(region)
            return None
        if t - self._last_seen > self._lost_after_s:
            self._current = None
            if self._sent is not None:
                self._sent, self._last_sent = None, t
                return FocusCommand(None)
        return None

    def crop(self, t: float) -> Optional[NearRegion]:
        """Handen med marginal, eller None om den inte setts på lost_after_s."""
        if self._current is None or t - self._last_seen > self._lost_after_s:
            return None
        return self._current.expanded(self._margin)

    def _moved(self, new: NearRegion, old: NearRegion) -> bool:
        if abs(new.depth_m - old.depth_m) > self._closer:   # närmare eller längre bort: linsen ska flyttas
            return True
        (nx, ny), (ox, oy) = new.center, old.center
        if abs(nx - ox) > self._move or abs(ny - oy) > self._move:
            return True
        (nw, nh), (ow, oh) = new.size, old.size
        return abs(nw - ow) > self._grow * ow or abs(nh - oh) > self._grow * oh
