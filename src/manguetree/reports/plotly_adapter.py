# -*- coding: utf-8 -*-
"""Prepares the app's Plotly charts for the A4 portrait PDF without touching the screen copy."""
from __future__ import annotations

import copy

from manguetree.reports import theme, formatting

DEFAULT_APP_HEIGHT = 450          # height the app gives a chart before the "Adjust" menu
FONT = "Arial, Liberation Sans, Helvetica, sans-serif"


def _height_factor(fig):
    """Height chosen in the Adjust menu, as a factor of the default chart height."""
    h0 = fig.layout.height
    if not h0 or h0 == DEFAULT_APP_HEIGHT:
        return 1.0
    return max(0.6, min(1.6, h0 / DEFAULT_APP_HEIGHT))


def slot_size_px(fig, slot, n_rows=1):
    """(width, height) in px at 1x. A height the user changed scales the slot height inside
    the safe limits (60 to 135 mm)."""
    w, h = theme.slot_px(slot, n_rows)
    f = _height_factor(fig)
    if f != 1.0 and slot != "multi_facet":
        mm = max(theme.MIN_H_MM, min(theme.MAX_H_MM, theme.slot_mm(slot)[1] * f))
        h = int(round(mm * w / theme.slot_mm(slot)[0]))
    return w, h


def _recolor_species(fig):
    """Species traces take the fixed palette (by trace name); other traces are kept."""
    import plotly.graph_objects as go
    for tr in fig.data:
        if isinstance(tr, go.Pie) and tr.labels is not None:        # pie / donut: by label
            tr.marker.colors = [theme.species_color(l) for l in tr.labels]
            continue
        name = getattr(tr, "name", None)
        if not name or not isinstance(tr, (go.Bar, go.Scatter)):
            continue
        base = theme._base_name(name)
        if base not in theme.SPECIES_COLORS and base not in theme.SPECIES_FIXED_EXTRA:
            continue
        c = theme.species_color(base)
        dead = "morta" in str(name).lower() or "dead" in str(name).lower()
        if isinstance(tr, go.Bar):
            if dead:
                tr.marker.color = theme.DEAD_FILL
                tr.marker.line = dict(color=c, width=1)
                tr.marker.pattern = dict(shape=theme.DEAD_HATCH, fgcolor=c)
            else:
                tr.marker.color = c
        else:
            tr.line.color = c
            if tr.marker is not None:
                tr.marker.color = c


def outline_boxes(fig, color=None, width=None):
    """Box and violin shapes keep their fill colour but get a thin outline in the axis colour
    (whiskers and median too), so they look like the axes around them."""
    import plotly.graph_objects as go
    color = color or theme.AXIS
    width = width or theme.AXIS_WIDTH
    for tr in fig.data:
        if not isinstance(tr, (go.Box, go.Violin)):
            continue
        base = None
        for cand in (getattr(tr.marker, "color", None), getattr(tr.line, "color", None)):
            if isinstance(cand, str) and cand.startswith("#"):
                base = cand
                break
        if base is None and isinstance(tr.fillcolor, str):
            base = None
        if base is not None:
            tr.fillcolor = _rgba(base, 0.55)
            if isinstance(tr, go.Box) or tr.marker is not None:
                tr.marker.color = base
        tr.line.color = color
        tr.line.width = width


def _rgba(hex_, a):
    h = hex_.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def _recolor_plots(fig, cmap):
    """Traces named after a plot (and bars whose categories are plots) take that plot's
    colour, so one plot has one colour across the whole report."""
    import plotly.graph_objects as go
    n_bar = sum(isinstance(t, go.Bar) for t in fig.data)
    for tr in fig.data:
        name = str(getattr(tr, "name", "") or "")
        c = cmap.get(name)
        if c is not None:
            if isinstance(tr, go.Bar):
                tr.marker.color = c
            elif isinstance(tr, (go.Box, go.Violin)):
                tr.line.color = c
                tr.marker.color = c
            elif isinstance(tr, go.Scatterpolar):
                tr.line.color = c
                tr.fillcolor = _rgba(c, 0.18)
                tr.marker.color = c
            elif isinstance(tr, go.Scatter):
                if tr.line is not None and tr.mode and "lines" in tr.mode:
                    tr.line.color = c
                if tr.marker is not None:
                    tr.marker.color = c
            continue
        if isinstance(tr, go.Bar) and n_bar == 1 and tr.x is not None and len(tr.x) and all(str(x) in cmap for x in tr.x):
            tr.marker.color = [cmap[str(x)] for x in tr.x]
        elif isinstance(tr, go.Scatter) and tr.text is not None and tr.marker is not None and len(tr.text) \
                and all(str(x) in cmap for x in tr.text):
            tr.marker.color = [cmap[str(x)] for x in tr.text]


def prepare_plotly_for_pdf(fig, slot="full_standard", lang="pt", n_rows=1, recolor=True, plot_colors=None):
    """Copy of ``fig`` sized for ``slot``. Keeps what the user set on screen (edited texts,
    y range, bar width, log scale, chart kind); changes only size, margins, legend position,
    fonts and the decimal mark."""
    f = copy.deepcopy(fig)
    w, h = slot_size_px(fig, slot, n_rows)
    has_legend = f.layout.showlegend is not False and (
        sum(1 for t in f.data if getattr(t, "name", None)) > 1 or
        any(type(t).__name__ == "Pie" for t in f.data))
    f.update_layout(
        width=w, height=h, title=None, paper_bgcolor="white", plot_bgcolor="white",
        separators=formatting.plotly_separators(lang),
        font=dict(family=FONT, size=9, color=theme.INK),
        margin=dict(l=8, r=8, t=(34 if has_legend else 14), b=8),
    )
    if has_legend:
        f.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="center", x=0.5,
                                    font=dict(size=8), title=None))
    for ax in ("xaxis", "yaxis"):
        try:
            getattr(f.layout, ax).update(automargin=True, gridcolor=theme.GRID, linecolor=theme.AXIS, linewidth=theme.AXIS_WIDTH,
                                         zerolinecolor=theme.RULE)
        except Exception:
            pass
    for tr in f.data:
        if type(tr).__name__ == "Pie":
            tr.update(textposition="auto", insidetextorientation="horizontal")
    f.update_layout(uniformtext=dict(minsize=7, mode="hide"))
    if recolor:
        _recolor_species(f)
    if plot_colors:
        _recolor_plots(f, plot_colors)
    outline_boxes(f)
    return f


def to_png(fig, slot="full_standard", lang="pt", n_rows=1):
    """PNG bytes (about 300 dpi) of the prepared chart, plus its slot size in mm."""
    f = prepare_plotly_for_pdf(fig, slot, lang, n_rows)
    png = f.to_image(format="png", width=f.layout.width, height=f.layout.height, scale=theme.PDF_SCALE)
    return png, theme.slot_mm(slot, n_rows)
