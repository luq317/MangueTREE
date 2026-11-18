# -*- coding: utf-8 -*-
"""
dashboard.py
============
Summary panel of one plot (Single plot page): the structural parameters as small
figures in cards, saved as one image (PNG) or PDF. Light and dark themes.

Layout (approved by the lab): mean DBH with the DBH classes, height (mean ± SD and
canopy), live density with the share of each species, total basal area (live solid,
dead hatched, by species), mortality (stems and basal area) and the Holdridge index.
"""
import io
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                   # noqa: E402
from matplotlib.patches import FancyBboxPatch, Wedge, Rectangle  # noqa: E402

from manguetree import calc as mc                                 # noqa: E402
from manguetree import i18n                                       # noqa: E402

THEMES = {
    "light": {"bg": "#EEF1F4", "card": "#FFFFFF", "ink": "#1F3A5F", "muted": "#7A8A9C",
              "track": "#E4E9EE", "accent": "#2A9D8F", "faint": "#C9D6E2"},
    "dark": {"bg": "#0F2238", "card": "#16304D", "ink": "#FFFFFF", "muted": "#9FB4C8",
             "track": "#24415F", "accent": "#5FB3D9", "faint": "#3B5A7A"},
}
LOGO = Path(__file__).parent / "app" / "assets" / "logo.png"


def _fmt(v, dec, lang):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "-"
    txt = f"{v:,.{dec}f}"
    if lang == "pt":
        txt = txt.replace(",", "X").replace(".", ",").replace("X", ".")
    return txt


def _card(fig, rect, th):
    x, y, w, h = rect
    fig.patches.append(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.012",
                                      transform=fig.transFigure, facecolor=th["card"],
                                      edgecolor="none", zorder=-10))


def _title(fig, rect, th, label, value, unit, sub=None):
    x, y, w, h = rect
    fig.text(x + 0.018, y + h - 0.035, label.upper(), fontsize=8.5, color=th["muted"],
             fontweight="bold", va="top")
    t = fig.text(x + 0.018, y + h - 0.065, value, fontsize=24, color=th["ink"], fontweight="bold",
                 va="top")
    fig.canvas.draw()
    bb = t.get_window_extent().transformed(fig.transFigure.inverted())
    fig.text(bb.x1 + 0.005, bb.y0 + 0.004, unit, fontsize=10.5, color=th["muted"], va="bottom")
    if sub:
        fig.text(x + 0.018, y + h - 0.135, sub, fontsize=9, color=th["muted"], va="top")


def summary_panel(res, theme="light", lang=None, colors=None, fmt="png", dpi=200, subtitle=""):
    """Bytes of the summary panel (PNG or PDF). ``colors``: species -> colour."""
    lang = lang or i18n.get_lang()
    T = lambda k, **p: i18n.t(k, lang, **p)
    th = THEMES.get(theme, THEMES["light"])
    s = res["summary"]
    d = res["data"]
    v = d[d["dbh"].notna() & (d["dbh"] > 0)]
    sp_par = mc.species_parameters(res)
    species = list(sp_par.sort_values("ba_total_ha", ascending=False)["species"])
    colors = colors or {sp: mc.species_color(sp) for sp in species}
    name = lambda sp: T("labels.unidentified") if sp == mc.UNIDENTIFIED_LABEL else sp

    fig = plt.figure(figsize=(14, 8.6), dpi=dpi, facecolor=th["bg"])
    plt.rcParams["font.family"] = "DejaVu Sans"
    # header
    fig.text(0.035, 0.955, str(res.get("plot_name") or ""), fontsize=24, fontweight="bold",
             color=th["ink"], va="top")
    fig.text(0.035, 0.905, subtitle, fontsize=11, color=th["muted"], va="top")
    if LOGO.exists():
        ax_l = fig.add_axes([0.80, 0.885, 0.045, 0.08])
        ax_l.imshow(plt.imread(str(LOGO)))
        ax_l.axis("off")
        fig.text(0.85, 0.925, "MangueTREE", fontsize=13, fontweight="bold", color=th["ink"], va="center")

    W, G = 0.29, 0.0225
    xs = [0.035, 0.035 + W + G, 0.035 + 2 * (W + G)]
    top = [xs[0], 0.50, W, 0.355]
    # 1. DBH
    r = [xs[0], 0.50, W, 0.355]; _card(fig, r, th)
    _title(fig, r, th, T("labels.mean_dbh_cm").split(" (")[0], _fmt(s["mean_dbh_cm"], 2, lang), "cm",
           T("dashboard.dbh_classes"))
    live = v[v["live"]]
    edges = [2.5, 5, 7.5, 10, 12.5]
    labs = ["< 2,5" if lang == "pt" else "< 2.5"] + \
        [f"{_fmt(a, 1, lang).replace(',0', '').replace('.0', '')} a {_fmt(b, 1, lang).replace(',0', '').replace('.0', '')}"
         if lang == "pt" else f"{a:g}–{b:g}" for a, b in zip(edges, edges[1:])] + [f"≥ {_fmt(edges[-1], 1, lang)}"]
    cnt = np.histogram(live["dbh"], bins=[-np.inf] + edges + [np.inf])[0]
    ax = fig.add_axes([r[0] + 0.02, r[1] + 0.045, r[2] - 0.04, 0.15])
    mx = cnt.argmax() if cnt.size else 0
    ax.bar(range(len(cnt)), cnt, color=[th["ink"] if i == mx else th["faint"] for i in range(len(cnt))],
           width=0.8)
    for i, c in enumerate(cnt):
        ax.text(i, c, str(int(c)), ha="center", va="bottom", fontsize=9, color=th["ink"], fontweight="bold")
    ax.set_xticks(range(len(cnt)), labs, fontsize=7.5, color=th["muted"])
    ax.set_yticks([]); [sp_.set_visible(False) for sp_ in ax.spines.values()]
    ax.set_facecolor(th["card"]); ax.set_ylim(0, max(cnt.max() if cnt.size else 1, 1) * 1.25)
    ax.tick_params(length=0)
    fig.text(r[0] + r[2] / 2, r[1] + 0.012, T("dashboard.dbh_axis"), fontsize=7.5, color=th["muted"], ha="center")

    # 2. Height
    r = [xs[1], 0.50, W, 0.355]; _card(fig, r, th)
    _title(fig, r, th, T("dashboard.height"), _fmt(s["height_mean_m"], 2, lang),
           f"± {_fmt(s['height_sd_m'], 2, lang)} m",
           T("dashboard.height_sub", canopy=_fmt(s["canopy_height_m"], 2, lang)))
    ax = fig.add_axes([r[0] + 0.02, r[1] + 0.05, r[2] - 0.04, 0.13])
    hmax = max(s.get("height_max_m") or 0, s.get("canopy_height_m") or 0, 1) * 1.15
    m_, sd = s["height_mean_m"] or 0, s["height_sd_m"] or 0
    ax.plot([0, hmax], [0, 0], color=th["track"], lw=12, solid_capstyle="round")
    ax.plot([max(m_ - sd, 0), m_ + sd], [0, 0], color=th["accent"], lw=12, solid_capstyle="round")
    ax.scatter([m_], [0], s=160, color=th["ink"], edgecolor=th["card"], linewidth=2.5, zorder=3)
    ax.plot([s["canopy_height_m"]] * 2, [-0.6, 0.6], ls="--", color=th["ink"], lw=1.5)
    ax.text(s["canopy_height_m"], 0.75, T("dashboard.canopy"), fontsize=9, color=th["muted"], ha="center")
    ax.set_ylim(-1, 1.2); ax.set_xlim(-hmax * 0.02, hmax)
    ax.set_yticks([]); [sp_.set_visible(False) for sp_ in ax.spines.values()]
    ax.tick_params(colors=th["muted"], labelsize=8, length=0); ax.set_facecolor(th["card"])
    ax.set_xlabel("m", color=th["muted"], fontsize=8)

    # 3. Live density with species shares
    r = [xs[2], 0.50, W, 0.355]; _card(fig, r, th)
    _title(fig, r, th, T("labels.density_live_ha").split(" (")[0], _fmt(s["density_live_ha"], 0, lang),
           T("dashboard.stems_ha"), T("dashboard.share_species"))
    ax = fig.add_axes([r[0] + 0.02, r[1] + 0.12, r[2] - 0.04, 0.06])
    left = 0
    for sp in species:
        sh = float(sp_par.loc[sp_par["species"] == sp, "share_density_live_pct"].iloc[0])
        if sh <= 0:
            continue
        ax.barh(0, sh, left=left, color=colors.get(sp, "#888"), height=1, edgecolor=th["card"], linewidth=2)
        if sh >= 7:
            ax.text(left + 1.5, 0, f"{_fmt(sh, 0, lang)}%", va="center", fontsize=9.5, color="white",
                    fontweight="bold")
        left += sh
    ax.set_xlim(0, 100); ax.axis("off")
    _legend(fig, [r[0] + 0.02, r[1] + 0.07], species, colors, name, th, r[0] + r[2] - 0.015)

    # 4. Total basal area: live solid + dead hatched
    r = [xs[0], 0.035, W + G + W, 0.43]; _card(fig, r, th)
    _title(fig, r, th, T("labels.ba_total_ha").split(" (")[0], _fmt(s["ba_total_ha"], 2, lang), "m²/ha",
           T("dashboard.ba_sub", live=_fmt(s["ba_live_ha"], 2, lang), dead=_fmt(s["ba_dead_ha"], 2, lang)))
    ax = fig.add_axes([r[0] + 0.06, r[1] + 0.02, 0.24, 0.26])
    ax.set_aspect("equal"); ax.axis("off"); ax.set_xlim(-1.5, 1.5); ax.set_ylim(-1.3, 1.3)
    tot = float(sp_par["ba_total_ha"].sum()) or 1.0
    ang = 90.0
    for cond in ("live", "dead"):
        for sp in species:
            val = float(sp_par.loc[sp_par["species"] == sp, f"ba_{cond}_ha"].iloc[0])
            if val <= 0:
                continue
            frac = val / tot
            a1 = ang - 360 * frac
            cor = colors.get(sp, "#888")
            w_ = Wedge((0, 0), 1, a1, ang, width=0.38, facecolor=cor if cond == "live" else th["card"],
                       edgecolor=cor if cond == "dead" else th["card"],
                       hatch="////" if cond == "dead" else None, linewidth=1.2)
            ax.add_patch(w_)
            if frac >= 0.03:
                mid = np.deg2rad((ang + a1) / 2)
                ax.plot([1.02 * np.cos(mid), 1.15 * np.cos(mid)], [1.02 * np.sin(mid), 1.15 * np.sin(mid)],
                        color=th["muted"], lw=0.8)
                ax.text(1.2 * np.cos(mid), 1.2 * np.sin(mid), f"{_fmt(100 * frac, 0, lang)}%",
                        ha="left" if np.cos(mid) >= 0 else "right", va="center", fontsize=9.5,
                        color=th["ink"], fontweight="bold")
            ang = a1
    ax.text(0, 0.05, _fmt(s["ba_total_ha"], 2, lang), ha="center", va="center", fontsize=13,
            fontweight="bold", color=th["ink"])
    ax.text(0, -0.2, "m²/ha", ha="center", va="center", fontsize=8.5, color=th["muted"])
    # table viva / morta
    x0, y0 = r[0] + 0.36, r[1] + 0.27
    fig.text(x0 + 0.17, y0 + 0.03, T("condition.live"), fontsize=9, color=th["muted"], ha="right")
    fig.text(x0 + 0.24, y0 + 0.03, T("condition.dead"), fontsize=9, color=th["muted"], ha="right")
    for i, sp in enumerate(species):
        yy = y0 - 0.045 * i
        cor = colors.get(sp, "#888")
        fig.patches.append(Rectangle((x0 - 0.018, yy - 0.006), 0.011, 0.018, transform=fig.transFigure,
                                     facecolor=cor, edgecolor="none"))
        fig.text(x0, yy, name(sp), fontsize=9.5, style="italic", color=th["ink"])
        for j, cond in enumerate(("live", "dead")):
            val = float(sp_par.loc[sp_par["species"] == sp, f"ba_{cond}_ha"].iloc[0])
            fig.text(x0 + 0.17 + 0.07 * j, yy, _fmt(val, 2, lang), fontsize=10, color=th["ink"],
                     ha="right", fontweight="bold")
    yy = y0 - 0.045 * len(species) - 0.01
    fig.patches.append(Rectangle((x0 - 0.018, yy - 0.006), 0.011, 0.018, transform=fig.transFigure,
                                 facecolor=th["card"], edgecolor=th["muted"], hatch="////"))
    fig.text(x0, yy, T("dashboard.hatch_note"), fontsize=8.5, color=th["muted"])

    # 5. Mortality + Holdridge (last)
    r = [xs[2], 0.035, W, 0.43]; _card(fig, r, th)
    _title(fig, r, th, T("dashboard.mortality"), _fmt(s["mortality_stems_pct"], 1, lang),
           T("dashboard.pct_stems"), T("dashboard.mort_ba", v=_fmt(s["mortality_ba_pct"], 1, lang)))
    ax = fig.add_axes([r[0] + 0.02, r[1] + 0.205, r[2] - 0.04, 0.035])
    lv = 100 - (s["mortality_ba_pct"] or 0)
    ax.barh(0, lv, color=th["ink"], height=1)
    ax.barh(0, 100 - lv, left=lv, color=th["card"], edgecolor=th["ink"], hatch="////", height=1)
    ax.text(2, 0, f"{_fmt(lv, 0, lang)}%", va="center", color="white" if theme == "light" else th["bg"],
            fontsize=9, fontweight="bold")
    ax.set_xlim(0, 100); ax.axis("off")
    fig.text(r[0] + 0.02, r[1] + 0.175, T("dashboard.ba_live_dead"), fontsize=8, color=th["muted"])
    fig.lines.append(plt.Line2D([r[0] + 0.018, r[0] + r[2] - 0.018], [r[1] + 0.15] * 2,
                                transform=fig.transFigure, color=th["track"], lw=1))
    cx = res["complexity"]
    fig.text(r[0] + 0.018, r[1] + 0.125, T("dashboard.holdridge").upper(), fontsize=8.5,
             color=th["muted"], fontweight="bold", va="top")
    fig.text(r[0] + 0.018, r[1] + 0.09, _fmt(cx["dbh_gt_2.5"]["ci"], 2, lang), fontsize=20,
             color=th["ink"], fontweight="bold", va="top")
    fig.text(r[0] + 0.12, r[1] + 0.075, T("dashboard.dbh_gt", v="2,5" if lang == "pt" else "2.5"),
             fontsize=9, color=th["muted"], va="top")
    fig.text(r[0] + 0.018, r[1] + 0.035,
             T("dashboard.holdridge_10", v=_fmt(cx["dbh_gt_10"]["ci"], 2, lang)), fontsize=9,
             color=th["muted"], va="top")

    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, dpi=dpi, facecolor=th["bg"])
    plt.close(fig)
    return buf.getvalue()


def _legend(fig, pos, species, colors, name, th, xmax=1.0):
    x0, y = pos
    x = x0
    for sp in species:
        if x > x0 and x + 0.012 + 0.0055 * len(name(sp)) > xmax:     # next line
            x, y = x0, y - 0.03
        fig.patches.append(Rectangle((x, y), 0.009, 0.015, transform=fig.transFigure,
                                     facecolor=colors.get(sp, "#888"), edgecolor="none"))
        t = fig.text(x + 0.013, y + 0.002, name(sp), fontsize=8.5, style="italic", color=th["ink"])
        fig.canvas.draw()
        x = t.get_window_extent().transformed(fig.transFigure.inverted()).x1 + 0.015
