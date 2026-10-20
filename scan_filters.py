# ===================== NY FIL AV CLAUDE (2026-10-20) =====================
# Gränser och regler för filtren i barcode_scanner.py (ändring 20-22), flyttade hit så att
# analyze_scans.py kan använda samma regler utan kameran (depthai, zxing, OpenCV).
# Bara standardbiblioteket. Ändra gränserna här, så gäller de i både skanner och analys.
# =========================================================================
"""
scan_filters.py - Filter mot felläsningar och felaktigt djup för streckkodsskannern.

"tunn":          läsningen kommer från en tunn remsa av koden. Koden går inte att lita på.
"orimligt djup": djupet stämmer inte med kodens storlek i bilden. Koden kan vara rätt,
                 men avståndet (och därmed positionen) går inte att lita på.
"""
import math

MODULES = 95                # EAN-13 och UPC-A: 95 moduler (grundstreck) mellan första och sista strecket
MIN_HEIGHT_RATIO = 0.15     # höjd/bredd under detta = tunn remsa. Stoppade 60 av 62 fel 17-20/10.
                            # KÄND RISK: hela men korta koder (höjd/bredd ~0,1) avvisas också.
DEPTH_K = {"1080p": 0.52, "4k": 1.0}   # djup (m) * px/modul, uppmätt på tomatpurén (modul ~0,35 mm)
DEPTH_FACTOR = 3            # djupet får skilja högst så många gånger från det kodens storlek säger
FILTER_TEXT = {"tunn": "tunn remsa av koden", "orimligt djup": "orimligt djup"}


def size_from_corners(tl, tr, br, bl):
    """(bredd, höjd) i pixlar, mätt längs kodens kanter så att även roterade koder mäts rätt."""
    width = (math.dist(tl, tr) + math.dist(bl, br)) / 2
    height = (math.dist(tl, bl) + math.dist(tr, br)) / 2
    return width, height


def is_thin(height_ratio):
    return height_ratio < MIN_HEIGHT_RATIO


def expected_depth(px_per_modul, mode):
    """Avståndet (m) som kodens storlek i bilden motsvarar, för en kod lik tomatpurén."""
    return DEPTH_K[mode] / px_per_modul if px_per_modul and mode in DEPTH_K else None


def depth_plausible(d, expected):
    return expected is None or expected / DEPTH_FACTOR <= d <= expected * DEPTH_FACTOR
