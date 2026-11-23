"""The plot-location map: one figure for the app and the PDF report.

Satellite image behind (see ``basemap``; the plain coordinate plot when the tiles cannot be
downloaded) with a small pin on each plot."""
from __future__ import annotations

import io

import numpy as np

from manguetree import i18n
from manguetree.reports import basemap, formatting as fm, theme

_PIN_PATH = None


def _pin_path():
    """Teardrop pin whose tip is the origin, so the tip sits on the plot's coordinate."""
    global _PIN_PATH
    if _PIN_PATH is None:
        from matplotlib.path import Path
        r, cy = 0.62, 1.55
        a = np.arccos(r / cy)                       # tangent points seen from the tip
        ang = np.linspace(np.pi / 2 - a + np.pi, np.pi / 2 + a - np.pi + 2 * np.pi, 40)
        ang = np.linspace(-(np.pi / 2 - a), np.pi + (np.pi / 2 - a), 40)
        circ = np.column_stack([r * np.cos(ang), cy + r * np.sin(ang)])
        verts = np.vstack([[0, 0], circ, [0, 0]])
        _PIN_PATH = Path(verts, closed=True)
    return _PIN_PATH


def location_figure(coords, lang="pt", cmap=None, figsize=(7.0, 4.4)):
    """Figure with the plots over satellite imagery, or None without coordinates.
    ``coords``: DataFrame lat, lon[, plot]. The figure carries ``_manguetree_sat``."""
    import matplotlib
    import matplotlib.patheffects as pe
    import matplotlib.pyplot as plt
    if coords is None or len(coords) == 0:
        return None
    c = coords.dropna(subset=["lat", "lon"])
    if c.empty:
        return None
    fig, ax = plt.subplots(figsize=figsize)
    has_name = "plot" in c.columns
    nomes = c["plot"].astype(str).values if has_name else [None] * len(c)
    lat, lon = list(c["lat"].astype(float)), list(c["lon"].astype(float))
    bounds = basemap.padded_bounds(lat, lon)
    bg = basemap.background(bounds)
    sat = bg is not None
    if sat:
        ax.imshow(bg[0], extent=bg[1], origin="upper", zorder=0)
        ax.set_xlim(*bounds[2:]); ax.set_ylim(*bounds[:2])
    base = theme.NAVY
    cores = [(cmap or {}).get(str(n_), theme.AMBER if sat else base) for n_ in nomes]
    many = len(c) > 12                               # tree-by-tree coordinates: small dots, no pins
    if many:
        ax.scatter(lon, lat, s=10, color=cores, edgecolor="white", lw=0.4, zorder=3)
    else:
        ax.scatter(lon, lat, s=520, marker=matplotlib.markers.MarkerStyle(_pin_path()), color=cores,
                   edgecolor="white", linewidths=0.9, zorder=3)
        for x_, y_, n_ in zip(lon, lat, nomes):
            if n_:
                ax.annotate(n_, (x_, y_), xytext=(8, 10), textcoords="offset points", fontsize=8.5, fontweight="bold",
                            color="white" if sat else base, zorder=4,
                            path_effects=[pe.withStroke(linewidth=2.2, foreground="#000000AA")] if sat else None)
    ax.set_xlabel(i18n.t("report.map.lon", lang)); ax.set_ylabel(i18n.t("report.map.lat", lang))
    if not sat:
        if len(c) > 1:
            dx = max(max(lon) - min(lon), 1e-4); dy = max(max(lat) - min(lat), 1e-4)
            ax.set_xlim(min(lon) - dx * .15, max(lon) + dx * .15)
            ax.set_ylim(min(lat) - dy * .15, max(lat) + dy * .15)
        ax.grid(color="#E4E8EB", lw=0.6); ax.set_axisbelow(True)
    ax.set_aspect(1 / max(np.cos(np.deg2rad(float(np.mean(lat)))), 0.2), adjustable="box" if sat else "datalim")
    ax.ticklabel_format(useOffset=False, style="plain")
    ax.xaxis.set_major_formatter(fm.mpl_formatter(lang, 3)); ax.yaxis.set_major_formatter(fm.mpl_formatter(lang, 3))
    if sat:
        ax.text(0.995, 0.012, basemap.ATTRIBUTION, transform=ax.transAxes, ha="right", va="bottom", fontsize=6.5,
                color="white", bbox=dict(facecolor="#00000066", edgecolor="none", pad=1.5), zorder=5)
    fig.tight_layout()
    fig._manguetree_sat = sat
    return fig


def location_png(coords, lang="pt", cmap=None, dpi=200):
    """PNG bytes of ``location_figure`` (None without coordinates)."""
    import matplotlib.pyplot as plt
    fig = location_figure(coords, lang, cmap)
    if fig is None:
        return None
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor="white")
    plt.close(fig)
    return buf.getvalue()
