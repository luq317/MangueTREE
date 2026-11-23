# -*- coding: utf-8 -*-
"""Design tokens of the PDF reports: colours, fixed species palette, type scale, slots.

Single source for the reportlab layout, the Plotly adapter and the Matplotlib fallback, so
the PDF looks the same with or without Chrome/Chromium."""
from __future__ import annotations

# --- page (mm) --------------------------------------------------------------------------
PAGE_W_MM, PAGE_H_MM = 210.0, 297.0
MARGIN_TOP_MM, MARGIN_SIDE_MM, MARGIN_BOTTOM_MM = 18.0, 18.0, 16.0
CONTENT_W_MM = PAGE_W_MM - 2 * MARGIN_SIDE_MM            # 174 mm
MM_PER_IN = 25.4

# --- colours ----------------------------------------------------------------------------
NAVY = "#1B365D"
TEAL = "#2A8C82"
SAGE = "#6E9476"
AMBER = "#B45309"
INK = "#1E293B"
INK_2 = "#475569"
GRID = "#E2E8F0"
RULE = "#CBD5E1"
CALLOUT_BG = "#F4F8F7"
WHITE = "#FFFFFF"

# --- type (pt) --------------------------------------------------------------------------
SIZE_KICKER, SIZE_H1, SIZE_H2, SIZE_H3 = 9.5, 20, 13.5, 11
SIZE_BODY, SIZE_SMALL, SIZE_FOOT = 10.5, 9.5, 8.5
LEADING_BODY = 1.5

# --- species ----------------------------------------------------------------------------
# fixed stacking and legend order of the three main species
MAIN_SPECIES = ("Avicennia schaueriana", "Rhizophora mangle", "Laguncularia racemosa")
SPECIES_COLORS = {"Avicennia schaueriana": NAVY,
                  "Rhizophora mangle": TEAL,
                  "Laguncularia racemosa": SAGE}
# other species, in the order they are met: fixed sequence, never the main three
COMPLEMENTARY = ("#C9A227", "#8C5E3C", "#7B6FA8", "#D17A5B", "#4C78A8", "#9BB86B")
SPECIES_FIXED_EXTRA = {"Conocarpus erectus": COMPLEMENTARY[0]}
UNKNOWN_COLOR = "#94A3B8"            # unidentified / unknown species
UNKNOWN_NAMES = ("indeterminada", "indeterminate", "unidentified", "unknown", "desconhecida", "")
DEAD_FILL = WHITE                    # dead stems: white fill, outline in the species colour
DEAD_HATCH = "/"

# cohorts (colonization) and many plots: fixed sequences, light to dark within each family
COHORT_COLORS = ("#9BB86B", "#2A8C82", "#1B365D", "#B45309", "#7B6FA8", "#94A3B8")
PLOT_COLORS = (NAVY, TEAL, SAGE, AMBER, "#4C78A8", "#7B6FA8", "#C9A227", "#8C5E3C",
               "#D17A5B", "#9BB86B", "#64748B", "#0F766E")


AXIS = "#5F726A"          # axes, ticks and the outline of box / violin shapes
AXIS_WIDTH = 0.8


def plot_color_map(names):
    """{plot name: colour}: the same colour for a plot in every chart of a report (order of
    ``names``; the sequence repeats only past 12 plots)."""
    out = {}
    for n in names:
        n = str(n)
        if n not in out:
            out[n] = PLOT_COLORS[len(out) % len(PLOT_COLORS)]
    return out


def is_unknown(name) -> bool:
    return str(name or "").strip().lower() in UNKNOWN_NAMES or str(name).lower().startswith("indet")


def _base_name(name) -> str:
    """'Rhizophora mangle (Viva)' / 'R. mangle - morta' -> species part."""
    s = str(name or "").strip()
    for sep in (" (", " - ", " – "):
        if sep in s:
            s = s.split(sep)[0]
    return s


def species_color(name) -> str:
    """Fixed colour of a species. The three main species and Conocarpus keep one colour in
    every report; unknown records are grey; any other species takes the next colour of the
    complementary sequence by a stable hash of its name."""
    base = _base_name(name)
    if base in SPECIES_COLORS:
        return SPECIES_COLORS[base]
    if base in SPECIES_FIXED_EXTRA:
        return SPECIES_FIXED_EXTRA[base]
    if is_unknown(base):
        return UNKNOWN_COLOR
    import hashlib
    k = int(hashlib.md5(base.encode("utf-8")).hexdigest(), 16)
    return COMPLEMENTARY[1 + k % (len(COMPLEMENTARY) - 1)]


def species_colors(names) -> dict:
    """{name: colour} in the order given; the main species come first in stacking order."""
    names = list(dict.fromkeys(names))
    out, used = {}, set()
    for n in names:
        c = species_color(n)
        if c in used and _base_name(n) not in SPECIES_COLORS and not is_unknown(n):
            free = [x for x in COMPLEMENTARY if x not in used]      # keep the extras apart
            c = free[0] if free else c
        out[n] = c; used.add(c)
    return out


def stack_order(names) -> list:
    """Main species first (fixed order), the others alphabetical, unknown last."""
    def key(n):
        b = _base_name(n)
        if b in MAIN_SPECIES:
            return (0, MAIN_SPECIES.index(b), "")
        return (2, 0, "") if is_unknown(b) else (1, 0, b)
    return sorted(dict.fromkeys(names), key=key)


# --- slots (mm), spec section 3.1 -------------------------------------------------------
# name: (width_mm, height_mm)
SLOTS_MM = {
    "panel_2x2": (174.0, 106.0),
    "full_standard": (174.0, 80.0),
    "full_compact": (174.0, 66.0),
    "half_pair": (84.0, 68.0),
    "square_center": (130.0, 108.0),
    "map_box": (174.0, 90.0),
}
MULTI_FACET_ROW_MM = 55.0
MULTI_FACET_MAX_MM = 210.0
MIN_H_MM, MAX_H_MM = 60.0, 135.0
PX_PER_MM = 660.0 / 174.0           # slot pixels at 1x (spec table)
PDF_SCALE = 3                       # about 300 dpi


def slot_mm(slot: str, n_rows: int = 1):
    if slot == "multi_facet":
        return CONTENT_W_MM, min(MULTI_FACET_ROW_MM * max(n_rows, 1), MULTI_FACET_MAX_MM)
    return SLOTS_MM[slot]


SLOTS_PX = {"panel_2x2": (660, 402), "full_standard": (660, 304), "full_compact": (660, 250),
            "half_pair": (320, 258), "square_center": (495, 410), "map_box": (660, 340)}


def slot_px(slot: str, n_rows: int = 1):
    if slot == "multi_facet":
        return 660, min(210 * max(n_rows, 1), 794)           # 210 mm cap
    return SLOTS_PX[slot]


def slot_figsize_in(slot: str, n_rows: int = 1):
    w, h = slot_mm(slot, n_rows)
    return round(w / MM_PER_IN, 2), round(h / MM_PER_IN, 2)
