# -*- coding: utf-8 -*-
# MangueTREE: structural analysis of mangrove forest plots.
# Copyright (c) 2026 Lucas Silva Pereira, Laiza Lacerda Motta, Tatiane Costa da Matta,
# Filipe de Oliveira Chaves, Mário Luiz Gomes Soares.
#
# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along with this
# program. If not, see <https://www.gnu.org/licenses/>.
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
        img = plt.imread(str(LOGO))[..., :3]
        alpha = (img.min(axis=2) < 0.97).astype(float)            # white background -> transparent
        ax_l.imshow(np.dstack([img, alpha]))
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
    x0, y0 = r[0] + 0.33, r[1] + 0.27
    fig.text(x0 + 0.15, y0 + 0.03, T("condition.live"), fontsize=9, color=th["muted"], ha="right")
    fig.text(x0 + 0.21, y0 + 0.03, T("condition.dead"), fontsize=9, color=th["muted"], ha="right")
    for i, sp in enumerate(species):
        yy = y0 - 0.045 * i
        cor = colors.get(sp, "#888")
        fig.patches.append(Rectangle((x0 - 0.018, yy - 0.006), 0.011, 0.018, transform=fig.transFigure,
                                     facecolor=cor, edgecolor="none"))
        fig.text(x0, yy, name(sp), fontsize=9.5, style="italic", color=th["ink"])
        for j, cond in enumerate(("live", "dead")):
            val = float(sp_par.loc[sp_par["species"] == sp, f"ba_{cond}_ha"].iloc[0])
            fig.text(x0 + 0.15 + 0.06 * j, yy, _fmt(val, 2, lang), fontsize=10, color=th["ink"],
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


# ---------------------------------------------------------------------------
# Interactive version for the page (HTML + SVG; hover shows the values)
# ---------------------------------------------------------------------------
_LOGO_SVG = Path(__file__).parent / "app" / "assets" / "logo_manguetree.svg"


def _esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def panel_html(res, theme="light", lang=None, colors=None, subtitle=""):
    """The summary panel as HTML cards with SVG figures (sharp at any size; hovering a
    bar, slice or point shows its value). Same content as ``summary_panel``."""
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
    F = lambda x, dec: _fmt(x, dec, lang)
    row = lambda sp, col: float(sp_par.loc[sp_par["species"] == sp, col].iloc[0])
    logo = _LOGO_SVG.read_text(encoding="utf-8") if _LOGO_SVG.exists() else ""
    logo = logo.replace("<svg ", '<svg width="40" height="40" ', 1)

    def card(label, value, unit, sub, body, span=1):
        return (f'<div class="c" style="grid-column:span {span}"><div class="k">{_esc(label)}</div>'
                f'<div class="v">{value}<small>{_esc(unit)}</small></div>'
                f'<div class="s">{_esc(sub)}</div>{body}</div>')

    # DBH classes
    live = v[v["live"]]
    edges = [2.5, 5, 7.5, 10, 12.5]
    cnt = np.histogram(live["dbh"], bins=[-np.inf] + edges + [np.inf])[0]
    labs = [f"< {F(2.5, 1)}"] + [f"{F(a, 1)} a {F(b, 1)}" if lang == "pt" else f"{a:g}–{b:g}"
                                  for a, b in zip(edges, edges[1:])] + [f"≥ {F(12.5, 1)}"]
    labs = [lb.replace(",0", "").replace(".0", "") for lb in labs]
    W, H, mxc = 330, 120, max(int(cnt.max()) if cnt.size else 1, 1)
    bw = W / len(cnt)
    bars = ""
    for i, c in enumerate(cnt):
        h = 78 * c / mxc
        cor = (th["ink"] if theme == "light" else th["accent"]) if i == int(cnt.argmax()) else th["faint"]
        bars += (f'<g class="tip" data-tip="{labs[i]} cm: {int(c)}"><rect x="{i*bw+5:.1f}" y="{92-h:.1f}" '
                 f'width="{bw-10:.1f}" height="{h:.1f}" rx="4" fill="{cor}"/>'
                 f'<text x="{i*bw+bw/2:.1f}" y="{86-h:.1f}" class="n">{int(c)}</text>'
                 f'<text x="{i*bw+bw/2:.1f}" y="108" class="a">{labs[i]}</text></g>')
    dbh_svg = (f'<svg viewBox="0 0 {W} 132" width="100%">{bars}'
               f'<text x="{W/2}" y="129" class="a">{_esc(T("dashboard.dbh_axis"))}</text></svg>')

    # height
    hmax = max(s.get("height_max_m") or 0, s.get("canopy_height_m") or 0, 1) * 1.1
    X = lambda val: 8 + 314 * val / hmax
    m_, sd, cn = s["height_mean_m"] or 0, s["height_sd_m"] or 0, s["canopy_height_m"] or 0
    tv = np.linspace(0, np.floor(hmax), 4).round()
    ticks = "".join(f'<text x="{X(t_):.1f}" y="104" class="a" text-anchor="{"start" if i == 0 else "end" if i == len(tv) - 1 else "middle"}"'
                    f' style="text-anchor:{"start" if i == 0 else "end" if i == len(tv) - 1 else "middle"}">{t_:g} m</text>'
                    for i, t_ in enumerate(tv))
    h_svg = (f'<svg viewBox="0 0 330 110" width="100%">'
             f'<line x1="{X(0)}" x2="{X(hmax)}" y1="60" y2="60" stroke="{th["track"]}" stroke-width="14" stroke-linecap="round"/>'
             f'<g class="tip" data-tip="{_esc(T("dashboard.height_sub", canopy=F(cn, 2)))} · {F(m_, 2)} ± {F(sd, 2)} m">'
             f'<line x1="{X(max(m_-sd, 0)):.1f}" x2="{X(m_+sd):.1f}" y1="60" y2="60" stroke="{th["accent"]}" stroke-width="14" stroke-linecap="round"/>'
             f'<circle cx="{X(m_):.1f}" cy="60" r="9" fill="{th["ink"]}" stroke="{th["card"]}" stroke-width="3"/></g>'
             f'<line x1="{X(cn):.1f}" x2="{X(cn):.1f}" y1="38" y2="82" stroke="{th["ink"]}" stroke-width="2" stroke-dasharray="4 3"/>'
             f'<text x="{X(cn):.1f}" y="32" class="a">{_esc(T("dashboard.canopy"))} {F(cn, 2)} m</text>{ticks}</svg>')

    # live density by species
    seg, x0 = "", 0.0
    for sp in species:
        sh = row(sp, "share_density_live_pct")
        if sh <= 0:
            continue
        w = 330 * sh / 100
        txt = f'<text x="{x0+8:.1f}" y="31" class="w">{F(sh, 0)}%</text>' if sh >= 8 else ""
        seg += (f'<g class="tip" data-tip="{_esc(name(sp))}: {F(sh, 1)}% · {F(row(sp, "density_live_ha"), 0)} '
                f'{_esc(T("dashboard.stems_ha"))}"><rect x="{x0:.1f}" y="10" width="{max(w-3, 1):.1f}" '
                f'height="34" rx="6" fill="{colors.get(sp, "#888")}"/>{txt}</g>')
        x0 += w
    leg = "".join(f'<span><i style="background:{colors.get(sp, "#888")}"></i><em>{_esc(name(sp))}</em></span>'
                  for sp in species)
    dens_body = f'<svg viewBox="0 0 330 54" width="100%">{seg}</svg><div class="leg">{leg}</div>'

    # basal area donut: live solid, dead hatched
    tot = float(sp_par["ba_total_ha"].sum()) or 1.0
    defs = "".join(f'<pattern id="h{i}" width="6" height="6" patternUnits="userSpaceOnUse" '
                   f'patternTransform="rotate(45)"><rect width="6" height="6" fill="{th["card"]}"/>'
                   f'<line x1="0" y1="0" x2="0" y2="6" stroke="{colors.get(sp, "#888")}" stroke-width="3"/></pattern>'
                   for i, sp in enumerate(species))
    cx, cy, R, r0 = 150, 120, 88, 54
    ang, arcs = -np.pi / 2, ""
    for cond in ("live", "dead"):
        for i, sp in enumerate(species):
            val = row(sp, f"ba_{cond}_ha")
            if val <= 0:
                continue
            fr = val / tot
            a1 = ang + 2 * np.pi * fr
            big = 1 if fr > 0.5 else 0
            p = (f"M{cx+R*np.cos(ang):.2f} {cy+R*np.sin(ang):.2f} A{R} {R} 0 {big} 1 {cx+R*np.cos(a1):.2f} {cy+R*np.sin(a1):.2f} "
                 f"L{cx+r0*np.cos(a1):.2f} {cy+r0*np.sin(a1):.2f} A{r0} {r0} 0 {big} 0 {cx+r0*np.cos(ang):.2f} {cy+r0*np.sin(ang):.2f}Z")
            fill = colors.get(sp, "#888") if cond == "live" else f"url(#h{i})"
            lab = ""
            if fr >= 0.03:
                mid = (ang + a1) / 2
                lx, ly = cx + (R + 18) * np.cos(mid), cy + (R + 18) * np.sin(mid)
                anchor = "start" if np.cos(mid) >= 0 else "end"
                lab = (f'<line x1="{cx+(R+4)*np.cos(mid):.1f}" y1="{cy+(R+4)*np.sin(mid):.1f}" x2="{lx:.1f}" '
                       f'y2="{ly:.1f}" stroke="{th["muted"]}"/><text x="{lx+(4 if anchor=="start" else -4):.1f}" '
                       f'y="{ly+4:.1f}" class="n" style="text-anchor:{anchor}">{F(100*fr, 0)}%</text>')
            arcs += (f'<g class="tip" data-tip="{_esc(name(sp))} · {_esc(T("condition." + cond))}: {F(val, 2)} m²/ha '
                     f'({F(100*fr, 1)}%)"><path d="{p}" fill="{fill}" stroke="{colors.get(sp, "#888") if cond=="dead" else th["card"]}" '
                     f'stroke-width="1.5"/></g>{lab}')
            ang = a1
    tab_rows = "".join(
        f'<tr><td><i style="background:{colors.get(sp, "#888")}"></i><em>{_esc(name(sp))}</em></td>'
        f'<td>{F(row(sp, "ba_live_ha"), 2)}</td><td>{F(row(sp, "ba_dead_ha"), 2)}</td></tr>' for sp in species)
    ba_body = (f'<div class="ba"><svg viewBox="0 0 300 240" width="300"><defs>{defs}</defs>{arcs}'
               f'<text x="{cx}" y="{cy}" class="big">{F(s["ba_total_ha"], 2)}</text>'
               f'<text x="{cx}" y="{cy+18}" class="a">m²/ha</text></svg>'
               f'<table><tr><th></th><th>{_esc(T("condition.live"))}</th><th>{_esc(T("condition.dead"))}</th></tr>{tab_rows}'
               f'<tr><td colspan="3" class="hn"><i class="hatch"></i>{_esc(T("dashboard.hatch_note"))}</td></tr></table></div>')

    # mortality + Holdridge
    lv = 100 - (s["mortality_ba_pct"] or 0)
    cx_ = res["complexity"]
    mort_body = (f'<svg viewBox="0 0 330 46" width="100%"><defs><pattern id="hm" width="6" height="6" '
                 f'patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="{th["card"]}"/>'
                 f'<line x1="0" y1="0" x2="0" y2="6" stroke="{th["ink"]}" stroke-width="3"/></pattern></defs>'
                 f'<g class="tip" data-tip="{_esc(T("condition.live"))}: {F(lv, 1)}%"><rect x="0" y="6" width="{330*lv/100:.1f}" height="28" rx="6" fill="{th["ink"] if theme == "light" else th["accent"]}"/></g>'
                 f'<g class="tip" data-tip="{_esc(T("condition.dead"))}: {F(100-lv, 1)}%"><rect x="{330*lv/100:.1f}" y="6" width="{330*(100-lv)/100:.1f}" height="28" rx="6" fill="url(#hm)" stroke="{th["ink"]}"/></g>'
                 f'<text x="10" y="25" class="w">{F(lv, 0)}%</text></svg>'
                 f'<div class="s">{_esc(T("dashboard.ba_live_dead"))}</div><hr>'
                 f'<div class="k">{_esc(T("dashboard.holdridge"))}</div>'
                 f'<div class="v" style="font-size:26px">{F(cx_["dbh_gt_2.5"]["ci"], 2)}<small>{_esc(T("dashboard.dbh_gt", v=F(2.5, 1)))}</small></div>'
                 f'<div class="s">{_esc(T("dashboard.holdridge_10", v=F(cx_["dbh_gt_10"]["ci"], 2)))}</div>')

    cards = (card(T("labels.mean_dbh_cm").split(" (")[0], F(s["mean_dbh_cm"], 2), "cm", T("dashboard.dbh_classes"), dbh_svg)
             + card(T("dashboard.height"), F(m_, 2), f"± {F(sd, 2)} m", T("dashboard.height_sub", canopy=F(cn, 2)), h_svg)
             + card(T("labels.density_live_ha").split(" (")[0], F(s["density_live_ha"], 0), T("dashboard.stems_ha"),
                    T("dashboard.share_species"), dens_body)
             + card(T("labels.ba_total_ha").split(" (")[0], F(s["ba_total_ha"], 2), "m²/ha",
                    T("dashboard.ba_sub", live=F(s["ba_live_ha"], 2), dead=F(s["ba_dead_ha"], 2)), ba_body, 2)
             + card(T("dashboard.mortality"), F(s["mortality_stems_pct"], 1), T("dashboard.pct_stems"),
                    T("dashboard.mort_ba", v=F(s["mortality_ba_pct"], 1)), mort_body))
    css = f"""
    .mtp{{background:{th["bg"]};color:{th["ink"]};font-family:"Source Sans Pro","Inter",Arial,sans-serif;padding:26px 28px;border-radius:16px}}
    .mtp .hd{{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}}
    .mtp h2{{margin:0;font-size:26px;color:{th["ink"]}}} .mtp .sub{{color:{th["muted"]};font-size:14px;margin-top:4px}}
    .mtp .brand{{display:flex;align-items:center;gap:8px;font-weight:700;font-size:16px}}
    .mtp .g{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}}
    .mtp .c{{background:{th["card"]};border-radius:14px;padding:18px 22px;box-shadow:0 1px 2px rgba(20,40,70,.06)}}
    .mtp .k{{font-size:11px;letter-spacing:1.2px;text-transform:uppercase;color:{th["muted"]};font-weight:700}}
    .mtp .v{{font-size:32px;font-weight:700;margin:4px 0 2px}} .mtp .v small{{font-size:14px;color:{th["muted"]};font-weight:500;margin-left:5px}}
    .mtp .s{{font-size:12.5px;color:{th["muted"]};margin-bottom:6px}}
    .mtp svg text{{font-family:inherit}} .mtp .n{{font-size:12px;font-weight:700;fill:{th["ink"]};text-anchor:middle}}
    .mtp .a{{font-size:10.5px;fill:{th["muted"]};text-anchor:middle}} .mtp .w{{font-size:12.5px;font-weight:700;fill:#fff}}
    .mtp .big{{font-size:20px;font-weight:700;fill:{th["ink"]};text-anchor:middle}}
    .mtp .leg{{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12px;margin-top:6px}} .mtp i{{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px}}
    .mtp .ba{{display:flex;align-items:center;gap:20px;flex-wrap:wrap}} .mtp table{{border-collapse:collapse;font-size:13px}}
    .mtp th{{color:{th["muted"]};font-weight:500;text-align:right;padding:0 0 6px 18px}} .mtp td{{padding:5px 0 5px 18px;text-align:right;font-weight:700}}
    .mtp td:first-child{{text-align:left;padding-left:0;font-weight:400}} .mtp td.hn{{text-align:left;color:{th["muted"]};font-weight:400;font-size:11.5px;padding-top:10px}}
    .mtp .hatch{{background:repeating-linear-gradient(45deg,{th["muted"]} 0 2px,transparent 2px 5px);border:1px solid {th["muted"]}}}
    .mtp hr{{border:0;border-top:1px solid {th["track"]};margin:12px 0}}
    .mtp .tip{{cursor:pointer;transition:opacity .15s}} .mtp svg:has(.tip:hover) .tip:not(:hover){{opacity:.45}}
    #mttip{{position:fixed;pointer-events:none;background:{th["ink"]};color:{th["card"]};padding:6px 10px;border-radius:8px;
           font-family:"Source Sans Pro","Inter",Arial,sans-serif;font-size:12.5px;font-weight:600;display:none;z-index:9;box-shadow:0 4px 12px rgba(0,0,0,.2);white-space:nowrap}}
    @media (max-width:900px){{.mtp .g{{grid-template-columns:1fr}} .mtp .c{{grid-column:span 1!important}}}}
    """
    return (f'<style>{css}</style><div class="mtp"><div class="hd"><div><h2>{_esc(res.get("plot_name") or "")}</h2>'
            f'<div class="sub">{_esc(subtitle)}</div></div><div class="brand">{logo}MangueTREE</div></div>'
            f'<div class="g">{cards}</div></div><div id="mttip"></div>'
            '<script>const tt=document.getElementById("mttip");'
            'document.querySelectorAll(".tip").forEach(g=>{'
            'g.addEventListener("mousemove",e=>{tt.textContent=g.dataset.tip;tt.style.display="block";'
            'tt.style.left=Math.min(e.clientX+14,window.innerWidth-tt.offsetWidth-8)+"px";tt.style.top=(e.clientY+14)+"px";});'
            'g.addEventListener("mouseleave",()=>{tt.style.display="none";});});</script>')
