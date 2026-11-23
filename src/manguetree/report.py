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
report.py
=========
Bilingual (English/Portuguese) PDF reports with the MangueTREE header, a citation
footer and all the figures of the analysis. Every text comes from the catalogs.

Figures are drawn with matplotlib (no browser/kaleido needed); the MangueTREE seal is
stamped on them only when ``seal=True``.

Public functions (all return PDF bytes):
    single_plot_report(res, lang="en", seal=False)
    multiple_plots_report(results, df_param, ivi, df_species, issues_df=None, lang="en", seal=False)
    temporal_report(df_series, df_species, issues_df=None, lang="en", seal=False)
"""
import io
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.patheffects
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from manguetree import calc as mc
from manguetree import branding as marca
from manguetree import i18n
from manguetree import __version__

# Estilo "artigo científico" para todas as figuras do relatório.
plt.rcParams.update({
    "figure.dpi": 120,
    "figure.max_open_warning": 0,      # all figures are built before the PDF is assembled
    "font.family": "DejaVu Sans",
    "axes.titlelocation": "left",
    "axes.titlesize": 10,
    "axes.titleweight": "bold",
    "axes.titlepad": 8,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "axes.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": False,
    "legend.fontsize": 8,
    "legend.frameon": False,
})

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image,
                                Table, TableStyle, CondPageBreak, KeepTogether)

_VERDE = marca.VERDE
_VERDE_ESC = marca.VERDE_ESCURO


def _cor_especie(esp):
    from manguetree.reports import theme
    return theme.species_color(esp)


# ---------------------------------------------------------------------------
# SELO E LOGO (matplotlib / reportlab)
# ---------------------------------------------------------------------------
def _texto_arco(ax, txt, cx, cy, r, a0, a1, fontsize, color):
    """Escreve 'txt' curvado ao longo de um arco (graus a0->a1), letras tangentes."""
    angs = np.linspace(a0, a1, len(txt))
    for ch, a in zip(txt, angs):
        rad = np.deg2rad(a)
        ax.text(cx + r * np.cos(rad), cy + r * np.sin(rad), ch,
                rotation=a - 90, ha="center", va="center", rotation_mode="anchor",
                fontsize=fontsize, color=color, fontweight="bold")


def _desenhar_selo(fig, ax, com_texto=True):
    """Selo A: dois anéis, logo centralizado, 'MANGUETREE' curvado no topo."""
    import matplotlib.patches as mp
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.set_aspect("equal"); ax.axis("off")
    ax.add_patch(mp.Circle((50, 50), 47, fill=False, ec=_VERDE_ESC, lw=2.5))
    ax.add_patch(mp.Circle((50, 50), 40, fill=False, ec=_VERDE_ESC, lw=1))
    pos = ax.get_position()
    lado = pos.width * 0.5
    sub = fig.add_axes([pos.x0 + pos.width / 2 - lado / 2,
                        pos.y0 + pos.height / 2 - lado / 2, lado, lado])
    marca.desenhar_logo_mpl(sub)
    if com_texto:
        _texto_arco(ax, marca.SELO_TEXTO.upper(), 50, 50, 43, 145, 35,
                    fontsize=9, color=_VERDE_ESC)
        ax.plot([50], [8], marker="o", ms=2.5, color=_VERDE_ESC)


def _selo_png(px=170, com_texto=True):
    fig = plt.figure(figsize=(px / 100, px / 100), dpi=100)
    ax = fig.add_axes([0.02, 0.02, 0.96, 0.96])
    _desenhar_selo(fig, ax, com_texto=com_texto)
    buf = io.BytesIO(); fig.savefig(buf, format="png", transparent=True, dpi=140)
    plt.close(fig); buf.seek(0)
    return buf


def _logo_png(px=220):
    fig = plt.figure(figsize=(px / 100, px / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    marca.desenhar_logo_mpl(ax)
    buf = io.BytesIO(); fig.savefig(buf, format="png", transparent=True, dpi=140)
    plt.close(fig); buf.seek(0)
    return buf


_SELO_MINI = None


def selo_mini_png_bytes():
    """Selo compacto (anéis + logo, sem texto) para carimbar figuras. Cacheado."""
    global _SELO_MINI
    if _SELO_MINI is None:
        _SELO_MINI = _selo_png(px=150, com_texto=False).getvalue()
    return _SELO_MINI


def _carimbar(fig, seal=False):
    """Stamp the seal (rings + logo) on the figure's lower right corner, if ``seal``."""
    if not seal:
        return fig
    import matplotlib.image as mpimg
    arr = mpimg.imread(io.BytesIO(selo_mini_png_bytes()))
    ax = fig.add_axes([0.90, 0.01, 0.10, 0.10], zorder=10)
    ax.imshow(arr); ax.axis("off")
    return fig



# Liberation Sans (SIL OFL, same metrics as Arial) is bundled in data/fonts: it has the Portuguese
# accents and the signs the reports use (≥ ▲ ▼ − → ■ Δ).
_FONT, _FONT_BOLD = "LiberationSans", "LiberationSans-Bold"
_FONT_IT, _FONT_BI = "LiberationSans-Italic", "LiberationSans-BoldItalic"
_FONTS_DIR = Path(__file__).resolve().parent / "data" / "fonts"


def _register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    if _FONT_BI in pdfmetrics.getRegisteredFontNames():
        return
    for name, arq in ((_FONT, "Regular"), (_FONT_BOLD, "Bold"), (_FONT_IT, "Italic"), (_FONT_BI, "BoldItalic")):
        pdfmetrics.registerFont(TTFont(name, str(_FONTS_DIR / f"LiberationSans-{arq}.ttf")))
    pdfmetrics.registerFontFamily(_FONT, normal=_FONT, bold=_FONT_BOLD, italic=_FONT_IT, boldItalic=_FONT_BI)


_register_fonts()


def _T(lang):
    return lambda key, **p: i18n.t(key, lang, **p)


def _sp(esp, lang):
    """Short species name for figures, with the language's placeholder for unresolved."""
    from manguetree.charts import species_name
    return species_name(mc.species_short(esp), lang)


# ---------------------------------------------------------------------------
# FIGURES: SINGLE PLOT
# ---------------------------------------------------------------------------
def _fig_comp_ba(res, lang, seal):
    from manguetree.charts import condition_label
    d = res["data"]; d = d[d["dbh"] > 0].copy()
    ft = mc._ft(res["summary"]["plot_area_m2"])
    comp = d.groupby(["species_label", "live"])["basal_area_m2"].sum() * ft
    comp = comp[comp > 0.001]
    if comp.empty:
        return None
    labels = [f"{_sp(sp, lang)} ({condition_label('live' if live else 'dead', lang)})"
              for sp, live in comp.index]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.pie(comp.values, labels=labels, autopct="%1.0f%%",
           colors=[_cor_especie(sp) for sp, _ in comp.index],
           textprops={"fontsize": 8})
    ax.set_title(i18n.t("chart.ba_composition", lang), fontweight="bold")
    return _carimbar(fig, seal)


def _fig_classes(res, metric, lang, seal):
    from manguetree.charts import label, dbh_class_label
    df = res["dbh_density"] if metric == "density" else res["dbh_ba"]
    if df is None or df.empty:
        return None
    fig, ax = plt.subplots(figsize=(6, 4))
    bottom = np.zeros(len(df.index))
    for esp in df.columns:
        ax.bar(df.index.map(lambda v: dbh_class_label(v, lang)), df[esp].values,
               bottom=bottom, label=_sp(esp, lang), color=_cor_especie(esp))
        bottom += df[esp].values
    ax.set_ylabel(label("density_ha" if metric == "density" else "ba_ha", lang))
    ax.set_xlabel(label("dbh_class", lang))
    name = i18n.t("metric.density" if metric == "density" else "metric.basal_area", lang)
    ax.set_title(i18n.t("chart.dbh_classes", lang, metric=name), fontweight="bold")
    ax.legend(fontsize=8)
    return _carimbar(fig, seal)


def _fig_ivi(ivi, lang, seal):
    if ivi is None or ivi.empty:
        return None
    from manguetree.charts import label
    comps = [c for c in ["rel_density", "rel_dominance", "rel_frequency"] if c in ivi.columns]
    is_ivi = "ivi" in ivi.columns
    d = ivi.sort_values("ivi" if is_ivi else "rel_dominance")
    fig, ax = plt.subplots(figsize=(6, 4))
    left = np.zeros(len(d))
    cores = {"rel_density": "#4C78A8", "rel_dominance": "#E4A11B", "rel_frequency": "#57B77E"}
    y = np.arange(len(d))
    h = 0.8 if is_ivi else 0.8 / len(comps)
    for k, c in enumerate(comps):
        if is_ivi:                                   # stacked components of the IVI
            ax.barh(y, d[c].values, left=left, label=label(c, lang), color=cores.get(c))
            left += d[c].values
        else:                                        # no frequency: side by side
            ax.barh(y + (k - (len(comps) - 1) / 2) * h, d[c].values, height=h,
                    label=label(c, lang), color=cores.get(c))
    ax.set_yticks(y); ax.set_yticklabels([_sp(e, lang) for e in d["species"]], fontsize=8)
    ax.set_xlabel("%"); ax.legend(fontsize=8)
    ax.set_title(i18n.t("chart.ivi" if is_ivi else "chart.rel_components", lang),
                 fontweight="bold")
    return _carimbar(fig, seal)


def _fig_alt_dap(res, lang, seal):
    from manguetree.charts import label
    d = res["data"]
    d = d[d["live"]].dropna(subset=["height", "dbh"])          # live stems only
    d = d[(d["dbh"] > 0) & (d["height"] > 0)]
    if len(d) < 2:
        return None
    fig, ax = plt.subplots(figsize=(6, 4))
    for esp in d["species_label"].unique():
        s = d[d["species_label"] == esp]
        ax.scatter(s["dbh"], s["height"], s=22, color=_cor_especie(esp),
                   label=_sp(esp, lang), alpha=0.8)
        if len(s) > 1:
            m = np.polyfit(s["dbh"], s["height"], 1)
            xr = np.linspace(s["dbh"].min(), s["dbh"].max(), 30)
            ax.plot(xr, np.poly1d(m)(xr), "--", color=_cor_especie(esp), lw=1.4)
    ax.set_xlabel(label("dbh", lang)); ax.set_ylabel(label("height", lang))
    ax.set_title(i18n.t("chart.height_dbh", lang), fontweight="bold"); ax.legend(fontsize=8)
    return _carimbar(fig, seal)


def _fig_perfil(res, lang, seal):
    from manguetree.charts import label
    d = res["data"]; d = d[d["live"] & (d["height"] > 0) & (d["dbh"] > 0)].sort_values("height")
    if d.empty:
        return None
    fig, ax = plt.subplots(figsize=(6, 4))
    x = np.arange(len(d))
    for esp in d["species_label"].unique():
        mask = (d["species_label"] == esp).values
        ax.scatter(x[mask], d["height"].values[mask],
                   s=np.clip(d["dbh"].values[mask] * 4, 10, 300),
                   color=_cor_especie(esp), alpha=0.7, label=_sp(esp, lang),
                   edgecolors="white", lw=0.5)
    hd = res["summary"].get("canopy_height_m", 0)
    if hd:
        ax.axhline(hd, ls=":", color="gray")
    ax.set_xticks([]); ax.set_ylabel(label("height", lang))
    ax.set_xlabel(i18n.t("chart.trees_by_height", lang))
    ax.set_title(i18n.t("chart.vertical_profile", lang), fontweight="bold")
    ax.legend(fontsize=8)
    return _carimbar(fig, seal)


def _fig_distribuicao(dist_tab, lang, seal):
    from manguetree.charts import label, dbh_class_label
    if dist_tab is None or dist_tab.empty:
        return None
    fig, ax = plt.subplots(figsize=(6, 3.8))
    ax.bar(dist_tab["class_cm"].astype(str).map(lambda v: dbh_class_label(v, lang)),
           dist_tab["density_ha"], color=_VERDE)
    ax.set_xlabel(label("dbh_class", lang)); ax.set_ylabel(label("density_ha", lang))
    ax.set_title(i18n.t("chart.diameter_dist", lang), fontweight="bold")
    plt.setp(ax.get_xticklabels(), rotation=25, ha="right", fontsize=7)
    fig.tight_layout()
    return _carimbar(fig, seal)


def _fig_hist(res, lang, seal):
    from manguetree.charts import label
    d = res["data"]; d = d[d["live"] & (d["dbh"] > 0)]
    if d.empty:
        return None
    fig, ax = plt.subplots(figsize=(6, 4))
    for esp in d["species_label"].unique():
        ax.hist(d[d["species_label"] == esp]["dbh"], bins=15, alpha=0.7,
                color=_cor_especie(esp), label=_sp(esp, lang))
    ax.set_xlabel(label("dbh", lang)); ax.set_ylabel(i18n.t("chart.n_stems", lang))
    ax.set_title(i18n.t("chart.dbh_hist", lang), fontweight="bold"); ax.legend(fontsize=8)
    return _carimbar(fig, seal)


# ---------------------------------------------------------------------------
# FIGURES: MULTIPLE PLOTS / TEMPORAL
# ---------------------------------------------------------------------------
def _fig_barras(df, xcol, ycol, seal):
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.bar(df[xcol].astype(str), df[ycol], color=_VERDE)
    ax.set_ylabel(ycol); ax.set_title(ycol, fontweight="bold")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right", fontsize=8)
    fig.tight_layout()
    return _carimbar(fig, seal)


def _fig_box(resultados, lang, seal):
    from manguetree.charts import label
    dados = [r["data"][r["data"]["live"] & (r["data"]["dbh"] > 0)]["dbh"].values
             for r in resultados]
    nomes = [str(r["plot_name"]) for r in resultados]
    if not any(len(x) for x in dados):
        return None
    fig, ax = plt.subplots(figsize=(6, 3.8))
    try:
        bp = ax.boxplot(dados, tick_labels=nomes, patch_artist=True)      # matplotlib >= 3.9
    except TypeError:
        bp = ax.boxplot(dados, labels=nomes, patch_artist=True)
    from manguetree.reports import theme as _t
    cm = _t.plot_color_map(nomes)
    for patch, n_ in zip(bp["boxes"], nomes):
        patch.set_facecolor(cm[n_] + "8C"); patch.set_edgecolor(_t.AXIS); patch.set_linewidth(_t.AXIS_WIDTH)
    for k in ("whiskers", "caps", "medians"):
        for ln in bp[k]:
            ln.set_color(_t.AXIS); ln.set_linewidth(_t.AXIS_WIDTH)
    ax.set_ylabel(label("dbh", lang))
    ax.set_title(i18n.t("chart.dbh_by_plot", lang), fontweight="bold")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right", fontsize=8)
    fig.tight_layout()
    return _carimbar(fig, seal)


def _fig_especies_parcelas(df_long, lang, seal):
    from manguetree.charts import label
    if df_long is None or df_long.empty:
        return None
    piv = df_long[df_long["condition"] == "live"].pivot_table(
        index="plot", columns="species", values="value", aggfunc="sum", fill_value=0)
    if piv.empty:
        return None
    fig, ax = plt.subplots(figsize=(6, 3.8))
    bottom = np.zeros(len(piv.index))
    for esp in piv.columns:
        ax.bar(piv.index.astype(str), piv[esp].values, bottom=bottom,
               label=_sp(esp, lang), color=_cor_especie(esp))
        bottom += piv[esp].values
    ax.set_ylabel(label("ba_live_ha", lang))
    ax.set_title(i18n.t("chart.species_by_plot", lang), fontweight="bold")
    ax.legend(fontsize=8); plt.setp(ax.get_xticklabels(), rotation=20, ha="right", fontsize=8)
    fig.tight_layout()
    return _carimbar(fig, seal)


def _fig_serie(df_serie, col, lang, seal):
    from manguetree.charts import label
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.plot(df_serie["year"], df_serie[col], marker="o", color=_VERDE)
    ax.set_xlabel(label("year", lang)); ax.set_ylabel(label(col, lang))
    ax.set_title(label(col, lang), fontweight="bold")
    fig.tight_layout()
    return _carimbar(fig, seal)


def _fig_serie_especie(df_esp, metrica, lang, seal):
    if df_esp is None or df_esp.empty:
        return None
    from manguetree.charts import label
    fig, ax = plt.subplots(figsize=(6, 3.6))
    for esp in df_esp["species"].unique():
        s = df_esp[df_esp["species"] == esp].sort_values("year")
        ax.plot(s["year"], s[metrica], marker="o", color=_cor_especie(esp),
                label=_sp(esp, lang))
    ax.set_xlabel(label("year", lang)); ax.set_ylabel(label(metrica, lang))
    ax.set_title(i18n.t("chart.by_species", lang, metric=label(metrica, lang)),
                 fontweight="bold")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return _carimbar(fig, seal)


# ---------------------------------------------------------------------------
# PANELS (matplotlib): letters inside the titles, room between the panels
# ---------------------------------------------------------------------------
from manguetree.reports.theme import PLOT_COLORS as _PALETA


def _panel_letters(n):
    return [f"({chr(97 + i)})" for i in range(n)]


def _paineis(df, colunas, x, kind, lang, seal, por_figura=4, cmap=None):
    """Figures of up to four panels (a), (b)... one per column of ``df``.

    ``kind`` "bar" (x: plot names) or "line" (x: years)."""
    from manguetree.charts import label
    figs = []
    for ini in range(0, len(colunas), por_figura):
        grupo = colunas[ini:ini + por_figura]
        n = len(grupo)
        ncol = 1 if n == 1 else 2
        nrow = (n + ncol - 1) // ncol
        fig, axs = plt.subplots(nrow, ncol, figsize=(7.4, 2.05 * nrow + 0.3), squeeze=False)
        for k, (ax, col, letra) in enumerate(zip(axs.ravel(), grupo, _panel_letters(n))):
            vals = pd.to_numeric(df[col], errors="coerce").values
            if kind == "bar":
                xs = df[x].astype(str).values
                cores = [(cmap or {}).get(str(n_), _PALETA[i % len(_PALETA)]) for i, n_ in enumerate(xs)]
                bars = ax.bar(xs, vals, color=cores, width=0.55)
                if len(xs) <= 8:
                    for b, v in zip(bars, vals):
                        if np.isfinite(v):
                            ax.text(b.get_x() + b.get_width() / 2, v, _cell_text(float(v), lang) if abs(v) < 100 else f"{v:,.0f}".replace(",", "."),
                                    ha="center", va="bottom", fontsize=6.8, color="#4A5560")
                    ax.set_ylim(0, np.nanmax(vals) * 1.2 if np.isfinite(vals).any() and np.nanmax(vals) > 0 else 1)
                if len(xs) > 5:
                    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
            else:
                ax.plot(df[x].values, vals, marker="o", ms=3.5, lw=1.5, color=_PALETA[0])
                ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True, nbins=6))
            ax.set_title(f"{letra} {label(col, lang)}", fontsize=8.6, fontweight="bold", loc="left", pad=7)
            ax.grid(axis="y", color="#E4E8EB", lw=0.6); ax.set_axisbelow(True)
            ax.tick_params(labelsize=7.5)
        for ax in axs.ravel()[n:]:
            ax.axis("off")
        fig.subplots_adjust(left=0.08, right=0.98, top=0.93, bottom=0.12 if kind == "line" else 0.14,
                            wspace=0.30, hspace=0.85)
        figs.append(_carimbar(fig, seal))
    return figs


def _fig_mapa(coords, lang, seal, cmap=None):
    """The same location figure as the app (satellite image and pins)."""
    from manguetree.reports import maps
    fig = maps.location_figure(coords, lang, cmap)
    return None if fig is None else _carimbar(fig, seal)


# ---------------------------------------------------------------------------
# THE APP'S OWN CHARTS (Plotly -> PNG), with a fallback when no browser is found
# ---------------------------------------------------------------------------
import functools
import os
import re


@functools.lru_cache(maxsize=1)
def plotly_images_available():
    """True when Plotly can export PNG here (needs Chrome or Chromium; see kaleido)."""
    if os.environ.get("MANGUETREE_NO_PLOTLY_IMAGES"):
        return False
    try:
        import plotly.graph_objects as go
        go.Figure(go.Bar(x=[1], y=[1])).to_image(format="png", width=80, height=60)
        return True
    except Exception:
        return False


def _texto_simples(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(html or ""))).strip()


# slot of each app chart in the page (spec section 3.1), by the key the page gave it
_SLOT_EXACT = {"1_1": "full_compact", "1_2": "square_center", "1_3": "half_pair", "1_4": "half_pair",
               "1_5": "full_standard", "1_6": "full_standard", "1_7": "full_standard",
               "2_1": "square_center", "2_2": "full_standard", "2_3": "full_standard",
               "2_4": "full_compact", "3_2": "full_standard", "3_6": "half_pair", "3_7": "half_pair",
               "fig_esp_lado": "multi_facet", "colon_schema": "full_compact"}
_SLOT_PREFIX = (("evol_", "half_pair"), ("mort_", "full_standard"), ("fig_esp", "full_standard"),
                ("colon_", "full_standard"))


def _slot_da_chave(key):
    key = str(key or "")
    if key in _SLOT_EXACT:
        return _SLOT_EXACT[key]
    for pre, slot in _SLOT_PREFIX:
        if key.startswith(pre):
            return slot
    return "full_standard"


def _assinatura_dados(fig_json):
    """Names and values of the traces: two charts with the same signature show the same data."""
    import json
    try:
        d = json.loads(fig_json)["data"]
        return json.dumps([(t.get("name"), t.get("type"), t.get("x"), t.get("y")) for t in d], default=str)
    except Exception:
        return fig_json


def _sem_duplicados(figures, colunas_painel=(), tem_painel_mortalidade=False):
    """Drops charts that repeat another one of the report: a plain line of a parameter that a
    panel (a, b, c, d) already draws, the mortality lines when the mortality panel exists, and
    any chart whose traces equal one already kept (live and dead basal area by species shown in
    two tabs)."""
    out, vistos = [], set()
    for f in figures or []:
        key = str(f.get("key", ""))
        try:
            import json
            tipos = {t.get("type") for t in json.loads(f["json"])["data"]}
        except Exception:
            tipos = set()
        so_linhas = tipos <= {"scatter"}
        if key.startswith("evol_") and so_linhas and key[5:] in colunas_painel:
            continue
        if key in ("3_6", "3_7") and so_linhas and tem_painel_mortalidade:
            continue
        sig = _assinatura_dados(f["json"])
        if sig in vistos:
            continue
        vistos.add(sig); out.append(f)
    return out


def _render_plotly(figures, lang="pt", plot_colors=None):
    """[{"section", "title", "png", "slot", "w_mm", "h_mm"}] for the saved charts (those that
    fail are skipped). The chart goes through ``prepare_plotly_for_pdf``: slot size, legend on
    top, decimal mark of the language and the fixed species palette; the title leaves the
    picture and becomes the caption."""
    import plotly.io as pio
    from manguetree.reports import plotly_adapter as pa, theme
    out = []
    for f in figures or []:
        try:
            fig = pio.from_json(f["json"])
            titulo = _texto_simples(getattr(fig.layout.title, "text", ""))
            slot = _slot_da_chave(f.get("key"))
            n_rows = max(1, len({getattr(t, "yaxis", None) for t in fig.data})) if slot == "multi_facet" else 1
            prep = pa.prepare_plotly_for_pdf(fig, slot, lang, n_rows, plot_colors=plot_colors)
            png = prep.to_image(format="png", width=prep.layout.width, height=prep.layout.height,
                                scale=theme.PDF_SCALE)
            w_mm, h_mm = theme.slot_mm(slot, n_rows)
            out.append({"section": f.get("section") or "", "title": titulo, "png": png, "slot": slot,
                        "w_mm": w_mm, "h_mm": h_mm})
        except Exception:
            continue
    return out


def _blocos_figuras(imgs, titulo_padrao):
    """Blocks of the charts, grouped under the tab they came from; two half-width charts in a
    row become one pair block."""
    b, atual, i = [], None, 0
    while i < len(imgs):
        im = imgs[i]
        sec = im["section"] or titulo_padrao
        if sec != atual:
            b.append(("h", xml_escape(sec))); atual = sec
        nxt = imgs[i + 1] if i + 1 < len(imgs) else None
        if (im["slot"] == "half_pair" and nxt is not None and nxt["slot"] == "half_pair"
                and (nxt["section"] or titulo_padrao) == sec):
            b.append(("pair", im, nxt)); i += 2
        else:
            b.append(("img", im["png"], im["w_mm"], im["h_mm"], im["title"], im["slot"])); i += 1
    return b


# ---------------------------------------------------------------------------
# PDF ASSEMBLY
# ---------------------------------------------------------------------------
_SERIF, _SERIF_BOLD, _SERIF_IT = _FONT, _FONT_BOLD, _FONT_IT
from manguetree.reports import theme as _th
_NAVY = _th.NAVY
_GREY = _th.INK_2
_MARGEM = _th.MARGIN_SIDE_MM * mm


def _register_serif():
    _register_fonts()


def _estilos():
    _register_fonts(); _register_serif()
    ss = getSampleStyleSheet()
    for st in ss.byName.values():
        if hasattr(st, "fontName"):
            st.fontName = _FONT_BOLD if "Bold" in st.fontName else _FONT
    ss.add(ParagraphStyle("Titulo", fontName=_SERIF_BOLD, fontSize=_th.SIZE_H1, leading=25,
                          textColor=colors.HexColor(_NAVY)))
    ss.add(ParagraphStyle("Sub", fontName=_SERIF, fontSize=_th.SIZE_SMALL, leading=13,
                          textColor=colors.HexColor(_GREY)))
    ss.add(ParagraphStyle("H", fontName=_SERIF_BOLD, fontSize=_th.SIZE_H2, leading=17,
                          textColor=colors.HexColor(_NAVY), keepWithNext=1))
    ss.add(ParagraphStyle("Kicker", fontName=_FONT_BOLD, fontSize=8.5, leading=11, charSpace=1.1,
                          textColor=colors.HexColor(_th.TEAL)))
    ss.add(ParagraphStyle("H1", fontName=_FONT_BOLD, fontSize=_th.SIZE_H1, leading=24,
                          textColor=colors.HexColor(_th.NAVY)))
    ss.add(ParagraphStyle("Meta", fontName=_FONT, fontSize=_th.SIZE_SMALL - 0.5, leading=12.5,
                          textColor=colors.HexColor(_th.INK_2)))
    ss.add(ParagraphStyle("KpiL", fontName=_FONT_BOLD, fontSize=7.8, leading=10, charSpace=0.7,
                          textColor=colors.HexColor(_th.INK_2)))
    ss.add(ParagraphStyle("KpiV", fontName=_FONT, fontSize=17, leading=21, textColor=colors.HexColor(_th.NAVY)))
    ss.add(ParagraphStyle("KpiS", fontName=_FONT, fontSize=8, leading=10.2, textColor=colors.HexColor(_th.INK_2)))
    ss.add(ParagraphStyle("CalloutT", fontName=_FONT_BOLD, fontSize=8.6, leading=11, charSpace=1.0,
                          textColor=colors.HexColor(_th.NAVY)))
    ss.add(ParagraphStyle("Callout", fontName=_FONT, fontSize=10, leading=14.6,
                          textColor=colors.HexColor(_th.INK)))
    ss.add(ParagraphStyle("Ref", fontName=_FONT, fontSize=9, leading=12.5, leftIndent=14, firstLineIndent=-14,
                          textColor=colors.HexColor(_th.INK)))
    ss.add(ParagraphStyle("Corpo", fontName=_SERIF, fontSize=9.6, leading=14.4,
                          alignment=4, textColor=colors.HexColor(_th.INK)))
    ss.add(ParagraphStyle("Cap", fontName=_SERIF, fontSize=_th.SIZE_FOOT, leading=11.2,
                          textColor=colors.HexColor(_GREY), spaceBefore=3, spaceAfter=10))
    ss.add(ParagraphStyle("CapTab", fontName=_SERIF, fontSize=_th.SIZE_FOOT, leading=11.2,
                          textColor=colors.HexColor(_GREY), spaceAfter=3))
    return ss


def _mpl_para_img(fig, largura=15 * cm):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig); buf.seek(0)
    from PIL import Image as PILImage
    w, h = PILImage.open(buf).size
    buf.seek(0)
    return Image(buf, width=largura, height=largura * h / w)


def _junta_titulo(flow, pend):
    """Puts the heading at flow[pend] and the chart just added in one block."""
    if pend is not None and pend == len(flow) - 2:
        fig = flow.pop(); head = flow.pop()
        flow.append(KeepTogether([head] + list(fig._content)))     # flat: nested blocks wrap badly


def _png_slot(png, largura, altura):
    """Picture at the exact size of its slot (mm), centred."""
    im = Image(io.BytesIO(png), width=largura, height=altura)
    im.hAlign = "CENTER"
    return im


def _png_para_img(png, largura, altura_max=7.0 * cm):
    """Picture at the text width, never taller than ``altura_max`` (three charts per page)."""
    from PIL import Image as PILImage
    w, h = PILImage.open(io.BytesIO(png)).size
    alt = largura * h / w
    if alt > altura_max:
        largura, alt = largura * altura_max / alt, altura_max
    im = Image(io.BytesIO(png), width=largura, height=alt)
    im.hAlign = "CENTER"
    return im


_LARGURA_UTIL = A4[0] - 2 * _MARGEM   # width between the margins of the portrait page


_PAD = 3                  # cell padding (pt) on each side
_HDR_SIZE, _CELL_SIZE = 7.5, 8
LANDSCAPE_OVER_COLUMNS = 8   # wider tables get the page in landscape (when they do not fit)


def _cell_text(v, lang):
    """Table cell text: decimal comma in Portuguese, thousands separator, catalog text for
    missing values. Years (1900 to 2100) are never given a separator."""
    from manguetree.reports.formatting import fmt_br
    if isinstance(v, (int, np.integer)) and not isinstance(v, bool):
        v = int(v)
        return str(v) if (abs(v) < 1000 or 1900 <= v <= 2100) else fmt_br(v, 0, lang)
    if v is None or (isinstance(v, (float, np.floating)) and pd.isna(v)):
        return i18n.t("report.na", lang)
    if isinstance(v, (float, np.floating)):
        return fmt_br(v, 2, lang)
    return str(v)


def _table_frame(df):
    df = df.copy()
    if df.index.name or not isinstance(df.index, pd.RangeIndex):
        df = df.reset_index()
    return df


def table_layout(df, lang, width, max_col=12):
    """Column widths (pt) of a PDF table: proportional to the longest word of each header
    and the longest cell word, so no word is ever split. Returns a dict with ``header``,
    ``rows`` (text), ``widths``, ``fits`` (False when even the minimum needs more than
    ``width``) and the font sizes used."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    df = _table_frame(df).iloc[:, :max_col]
    header = [str(c) for c in df.columns]
    # per-row tuples of object values keep each column's dtype (ints stay ints)
    rows = [[_cell_text(v, lang) for v in row]
            for row in df.astype(object).itertuples(index=False, name=None)]
    hs, cs = _HDR_SIZE, _CELL_SIZE
    while True:
        need = []
        for j, h in enumerate(header):
            w = max((stringWidth(x, _FONT_BOLD, hs) for x in h.split()), default=0)
            for r in rows:
                w = max([w] + [stringWidth(x, _FONT, cs) for x in r[j].split()])
            need.append(w + 2 * _PAD + 2)
        if sum(need) <= width or cs <= 5.5:
            break
        hs, cs = hs - 0.5, cs - 0.5
    extra = max(width - sum(need), 0)
    widths = [n + extra * n / sum(need) for n in need]
    return {"header": header, "rows": rows, "widths": widths, "fits": sum(need) <= width,
            "hdr_size": hs, "cell_size": cs}


_NUM = re.compile(r"^[-−+]?[\d.,]+( ?%)?$")


def _tabela_rl(df, ss, lang, width=None, bars=None, species_first=False, bold_last_row=False, bold_cols=(),
               bold_first=True):
    """Table in the report style: navy header with white bold text, thin row rules, numbers
    right-aligned, first column bold. ``bars``: [(header, values, vmax, colors)] adds columns
    of proportional bars; ``species_first``: first column is a species name (colour square,
    bold italic)."""
    from manguetree.reports import theme as th
    bars = bars or []
    w_bar = 0.26 * (width or _LARGURA_UTIL)
    lay = table_layout(df, lang, (width or _LARGURA_UTIL) - w_bar * len(bars))
    cs, hs = lay["cell_size"], lay["hdr_size"]
    n = len(lay["header"])
    num_col = [bool(lay["rows"]) and
               sum(bool(_NUM.match(r[j].strip())) or r[j] in ("-", "") for r in lay["rows"]) >= 0.7 * len(lay["rows"])
               for j in range(n)]
    nome = lambda j: 0 if j == 0 else (2 if num_col[j] else 0)
    cel = lambda j, bold=False: ParagraphStyle(
        f"c{j}{bold}", fontName=_FONT_BOLD if bold else _FONT, fontSize=cs, leading=cs + 2.6,
        alignment=nome(j), textColor=colors.HexColor(th.INK))
    hdr = lambda j: ParagraphStyle(f"h{j}", fontName=_FONT_BOLD, fontSize=hs, leading=hs + 2.4,
                                   alignment=nome(j), textColor=colors.white)
    header = [Paragraph(xml_escape(c), hdr(j)) for j, c in enumerate(lay["header"])]
    header += [Paragraph(xml_escape(b[0]), hdr(0)) for b in bars]
    rows = []
    for i, row in enumerate(lay["rows"]):
        last = bold_last_row and i == len(lay["rows"]) - 1
        cells = []
        for j, v in enumerate(row):
            txt = xml_escape(v)
            if j == 0 and species_first:
                cor = th.species_color(v)
                txt = f'<font color="{cor}">■</font> <b><i>{txt}</i></b>'
            elif (j == 0 and bold_first) or last:
                txt = f"<b>{txt}</b>"
            cells.append(Paragraph(f"<b>{txt}</b>" if (j in bold_cols and not txt.startswith("<b>")) else txt, cel(j)))
        for hb, vals, vmax, cols in bars:
            from manguetree.reports.panel import _bar
            c = cols[i] if isinstance(cols, (list, tuple)) else cols
            cells.append(_bar(float(vals[i]), vmax, w_bar - 6, c, height=8, label="", font=_FONT))
        rows.append(cells)
    widths = lay["widths"] + [w_bar] * len(bars)
    t = Table([header] + rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(th.NAVY)),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, colors.HexColor(th.GRID)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, 0), 6), ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 5), ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
    ] + ([("BACKGROUND", (0, -1), (-1, -1), colors.HexColor(th.CALLOUT_BG))] if bold_last_row else [])))
    return t


def _wrap_line(text, font, size, width):
    """Greedy word wrap of ``text`` to ``width`` points."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    lines, cur = [], ""
    for word in text.split(" "):
        trial = f"{cur} {word}".strip()
        if cur and stringWidth(trial, font, size) > width:
            lines.append(cur); cur = word
        else:
            cur = trial
    return lines + [cur]


def _canvas_numerado(lang, seal):
    """Canvas that writes "page X of Y" once the page count is known."""
    from reportlab.pdfgen import canvas as _cv
    T = _T(lang)

    class _Numerado(_cv.Canvas):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._estados = []

        def showPage(self):
            self._estados.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._estados)
            for est in self._estados:
                self.__dict__.update(est)
                self.setFont(_FONT, 8)
                self.setFillColor(colors.HexColor(_th.INK_2))
                self.drawRightString(self._pagesize[0] - (3.6 * cm if seal else _MARGEM), 0.95 * cm,
                                     T("report.page_of", n=self._pageNumber, total=total))
                super().showPage()
            super().save()
    return _Numerado


def _cabecalho_rodape(lang, seal, titulo=""):
    T = _T(lang)
    selo = ImageReader(_selo_png()) if seal else None
    left = T("report.footer.short", version=__version__, title=titulo)

    def _desenha(canvas, doc):
        canvas.saveState()
        w, h = canvas._pagesize
        canvas.setStrokeColor(colors.HexColor(_th.RULE)); canvas.setLineWidth(0.5)
        canvas.line(_MARGEM, 1.45 * cm, w - _MARGEM, 1.45 * cm)
        canvas.setFont(_FONT, 8); canvas.setFillColor(colors.HexColor(_th.INK_2))
        canvas.drawString(_MARGEM, 0.95 * cm, left)
        if seal:
            canvas.drawImage(selo, w - 3.4 * cm, 0.3 * cm, 1.3 * cm, 1.3 * cm, mask="auto")
        canvas.restoreState()
    return _desenha


def _capa(titulo, subtitulo, kpis, resumo, lang, ss, width, kicker=None, meta=None, leitura=None):
    """First block of page 1: navy top bar, kicker with the logo, title, meta line, grid of key
    numbers (with change and sub-lines) and the "reading of the results" callout."""
    T = _T(lang)
    th = _th
    data = datetime.now().strftime("%d/%m/%Y %H:%M" if lang == "pt" else "%Y-%m-%d %H:%M")
    logo = Image(_logo_png(), width=0.9 * cm, height=0.9 * cm)         # transparent background
    kick = Paragraph(xml_escape((kicker or f"{marca.APP_NOME} · {T('report.tagline')}").upper()), ss["Kicker"])
    topo = Table([[kick, logo]], colWidths=[width - 1.2 * cm, 1.2 * cm])
    topo.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 3.2, colors.HexColor(th.NAVY)),
                              ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 7),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    sub = meta or " · ".join(x for x in (subtitulo, T("report.generated_on", date=data)) if x)
    flow = [topo, Spacer(1, 3), Paragraph(xml_escape(titulo), ss["H1"]), Spacer(1, 2),
            Paragraph(xml_escape(sub), ss["Meta"]), Spacer(1, 8)]
    reg = Table([[""]], colWidths=[width], rowHeights=[1])
    reg.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.HexColor(th.RULE))]))
    flow += [reg, Spacer(1, 9)]
    if kpis:
        labels, values = [], []
        for k in kpis:
            label, value = k[0], k[1]
            unit = k[2] if len(k) > 2 else ""
            sub1 = k[3] if len(k) > 3 else ""
            labels.append(Paragraph(xml_escape(str(label).upper()), ss["KpiL"]))
            body = f'<font size="17"><b>{xml_escape(str(value))}</b></font>'
            if unit:
                body += f' <font size="9" color="{th.INK_2}"><b>{xml_escape(str(unit))}</b></font>'
            cell = [Paragraph(body, ss["KpiV"])]
            if sub1:
                cell.append(Paragraph(sub1, ss["KpiS"]))
            values.append(cell)
        kt = Table([labels, values], colWidths=[width / len(kpis)] * len(kpis))
        kt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(th.RULE)),
            ("LINEAFTER", (0, 0), (-2, -1), 0.5, colors.HexColor(th.RULE)),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor(th.RULE)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, 0), 5), ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
            ("TOPPADDING", (0, 1), (-1, 1), 6), ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]))
        flow += [kt, Spacer(1, 10)]
    if resumo:
        cal = Table([[Paragraph(xml_escape((leitura or T("report.reading")).upper()), ss["CalloutT"])],
                     [Paragraph(resumo, ss["Callout"])]], colWidths=[width])
        cal.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(th.CALLOUT_BG)),
                                 ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(th.TEAL)),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 11), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                                 ("TOPPADDING", (0, 0), (0, 0), 9), ("BOTTOMPADDING", (0, 0), (0, 0), 2),
                                 ("TOPPADDING", (0, 1), (0, 1), 0), ("BOTTOMPADDING", (0, 1), (0, 1), 10)]))
        flow += [cal, Spacer(1, 6)]
    return flow


def _titulo_secao(texto, ss, width):
    """Section heading: bold navy text over a thin rule (kept with what follows)."""
    t = Table([[Paragraph(texto, ss["H"])]], colWidths=[width])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor(_th.GRID)),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    t.keepWithNext = 1
    t.spaceBefore = 12
    t.spaceAfter = 7
    return t


def _gerar(titulo, subtitulo, blocos, lang, seal, kpis=None, resumo=None, kicker=None, meta=None,
           rodape=None, leitura=None):
    """blocos: list of ('h', text) | ('tab', df[, caption]) | ('fig', mpl_fig[, caption])
    | ('img', png, w_px, h_px[, caption]) | ('cap', text) | ('par', text).

    Headings are numbered, figures and captioned tables too; the cover (identity, title,
    key numbers, summary) opens the first page and the text flows on from there."""
    T = _T(lang)
    buf = io.BytesIO()
    ss = _estilos()
    page = A4                                  # always portrait
    width = page[0] - 2 * _MARGEM
    doc = SimpleDocTemplate(buf, pagesize=page, topMargin=_th.MARGIN_TOP_MM * mm, bottomMargin=2.3 * cm,
                            leftMargin=_MARGEM, rightMargin=_MARGEM,
                            title=f"{marca.APP_NOME}: {titulo}", author=marca.APP_NOME)
    flow = _capa(titulo, subtitulo, kpis, resumo, lang, ss, width, kicker=kicker, meta=meta, leitura=leitura)
    n_h = n_fig = n_tab = 0
    pend = None
    fig_word, tab_word = T("report.figure"), T("report.table")

    def _legenda(n, palavra, texto):
        t_ = f"<b>{xml_escape(palavra)} {n}.</b>" + (f" {xml_escape(texto)}" if texto else "")
        return Paragraph(t_, ss["Cap"])

    for b in blocos:
        tipo = b[0]
        if tipo not in ("h", "fig", "img", "pair", "flow", "sp"):
            pend = None
        if tipo == "h":
            n_h += 1
            flow.append(CondPageBreak(4.5 * cm))
            flow.append(_titulo_secao(f"{n_h}. {b[1]}", ss, width))
            pend = len(flow) - 1            # a chart right after it travels with the heading
        elif tipo == "par":
            flow.append(Paragraph(b[1], ss["Corpo"])); flow.append(Spacer(1, 5))
        elif tipo == "cap":
            flow.append(Paragraph(xml_escape(b[1]), ss["Cap"]))
        elif tipo == "tab":
            if b[1] is not None and not b[1].empty:
                tabela = _tabela_rl(b[1], ss, lang, width, **(b[3] if len(b) > 3 else {}))
                if len(b) > 2 and b[2]:
                    n_tab += 1
                    cap = Paragraph(f"<b>{xml_escape(tab_word)} {n_tab}.</b> {xml_escape(b[2])}", ss["CapTab"])
                    if len(b[1]) < 12:
                        flow.append(KeepTogether([cap, tabela]))
                    else:
                        flow += [cap, tabela]
                else:
                    flow.append(tabela)
                flow.append(Spacer(1, 9))
        elif tipo == "fig" and b[1] is not None:
            fig = b[1]
            texto = b[2] if len(b) > 2 else None
            if texto is None and len(fig.axes) == 1:            # the title becomes the caption
                texto = fig.axes[0].get_title(loc="left") or fig.axes[0].get_title()
                fig.axes[0].set_title("")
            n_fig += 1
            flow.append(KeepTogether([_mpl_para_img(fig, width * (0.92 if len(fig.axes) > 1 else 0.78)),
                                      _legenda(n_fig, fig_word, texto)]))
            _junta_titulo(flow, pend); pend = None
        elif tipo == "sp":
            flow.append(Spacer(1, b[1]))
        elif tipo == "flow":
            fl = b[1](width)
            flow += fl
            if pend is not None and pend == len(flow) - len(fl) - 1 and len(fl) == 1 and isinstance(fl[0], KeepTogether):
                last = flow.pop(); head = flow.pop()
                flow.append(KeepTogether([head] + list(last._content)))
            pend = None
            flow.append(Spacer(1, 6))
        elif tipo == "pair":
            n_fig += 2
            cel = [[_png_slot(b[1]["png"], b[1]["w_mm"] * mm, b[1]["h_mm"] * mm),
                    _png_slot(b[2]["png"], b[2]["w_mm"] * mm, b[2]["h_mm"] * mm)],
                   [_legenda(n_fig - 1, fig_word, b[1]["title"]), _legenda(n_fig, fig_word, b[2]["title"])]]
            par = Table(cel, colWidths=[width / 2] * 2)
            par.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                     ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
            flow.append(KeepTogether([par]))
            _junta_titulo(flow, pend); pend = None
        elif tipo == "img":
            n_fig += 1
            slot = b[5] if len(b) > 5 else None
            if slot:                                  # a chart of the app: the slot's size in mm
                im_ = _png_slot(b[1], b[2] * mm, b[3] * mm)
            else:
                im_ = _png_para_img(b[1], width, 6.6 * cm if len(b) > 4 and b[4] == T("report.cap.dashboard") else 7.0 * cm)
            flow.append(KeepTogether([im_, _legenda(n_fig, fig_word, b[4] if len(b) > 4 else "")]))
            _junta_titulo(flow, pend); pend = None
    flow.append(_titulo_secao(xml_escape(T("report.refs")), ss, width))
    for k, ref in enumerate((T("report.ref.estrada"), T("report.ref.jimenez"), marca.CITATION), 1):
        flow.append(Paragraph(f"{k}. {xml_escape(ref)}", ss["Ref"]))
    cr = _cabecalho_rodape(lang, seal, rodape or titulo)
    doc.build(flow, onFirstPage=cr, onLaterPages=cr, canvasmaker=_canvas_numerado(lang, seal))
    buf.seek(0)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# PUBLIC REPORTS
# ---------------------------------------------------------------------------
def _bloco_verificacao(issues_df, lang):
    """Blocks of the data-check section: counts plus one row per problem category (with a
    short example); the line-by-line list stays in the Excel export.

    ``issues_df`` is a frame from ``charts.issues_display_frame`` in ``lang`` (may carry
    an extra sheet/plot/year column); None means validation was not run (no section).
    """
    from manguetree.reports import formatting as fm
    if issues_df is None:
        return []
    T = _T(lang)
    h = xml_escape(T("report.h.verification"))
    if issues_df.empty:
        return [("h", h), ("cap", T("report.verification.ok"))]
    n_err, n_warn, tabela = fm.group_issues(issues_df, lang)
    return [("h", h),
            ("cap", T("report.verification.summary", errors=n_err, warnings=n_warn,
                      sheet=T("sheet.issues"))),
            ("tab", tabela)]


def _num(v, lang, dec=1):
    """Number text: thousands dot and decimal comma in Portuguese, the usual way in English."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "-"
    if not np.isfinite(v):
        return "-"
    text = f"{v:,.{dec}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".") if lang == "pt" else text


def _imagens_do_app(figures, titulo_padrao, lang="pt", plot_colors=None):
    """Blocks with the app's own charts, or None when they cannot be drawn here."""
    if not figures or not plotly_images_available():
        return None
    imgs = _render_plotly(figures, lang, plot_colors)
    return _blocos_figuras(imgs, titulo_padrao) if imgs else None


def _fig_map_block(coords, lang, seal, cmap=None):
    f = _fig_mapa(coords, lang, seal, cmap)
    if f is None:
        return []
    return [("fig", f, i18n.t("report.cap.map_sat" if getattr(f, "_manguetree_sat", False) else "report.cap.map", lang))]


def _classes_dap(res, lang):
    """Table of live stems by DBH class: class, N, share and the bar."""
    from manguetree.reports import panel as pn, formatting as fm
    T = _T(lang)
    d = res["data"]
    live = d[d["dbh"].notna() & (d["dbh"] > 0) & d["live"]]
    cnt = np.histogram(live["dbh"], bins=[-np.inf] + list(pn.EDGES) + [np.inf])[0]
    tot = max(int(cnt.sum()), 1)
    labs = pn._class_labels(lang)
    mx = int(cnt.argmax()) if cnt.size else -1
    rows = [{T("report.panel.col_class"): lab + (f" ({T('report.panel.mode')})" if i == mx else ""),
             T("report.panel.col_stems"): int(n), T("report.panel.col_share"): f"{fm.fmt_br(100 * n / tot, 1, lang)}%"}
            for i, (lab, n) in enumerate(zip(labs, cnt))]
    return pd.DataFrame(rows), cnt, mx


def _painel_especies(res, lang):
    """Species contribution and live x dead balance, with the plot mortality as last row."""
    from manguetree.reports import formatting as fm, theme as th
    T = _T(lang)
    s = res["summary"]
    sp = mc.species_parameters(res).sort_values("ba_total_ha", ascending=False)
    tot_ba = float(sp["ba_total_ha"].sum()) or 1.0
    rows = [{T("report.panel.col_sp"): (T("labels.unidentified") if r["species"] == mc.UNIDENTIFIED_LABEL else str(r["species"])),
             "DeR (%)": fm.fmt_br(r["rel_density"], 2, lang),
             T("report.panel.ba_live"): fm.fmt_br(r["ba_live_ha"], 2, lang),
             T("report.panel.ba_dead"): fm.fmt_br(r["ba_dead_ha"], 2, lang)} for _, r in sp.iterrows()]
    vals = [float(v) / tot_ba * 100 for v in sp["ba_total_ha"]]
    cols = [th.species_color(x) for x in sp["species"]]
    rows.append({T("report.panel.col_sp"): T("report.panel.mort_row"),
                 "DeR (%)": f"{fm.fmt_br(s['mortality_stems_pct'], 2, lang)}% {T('report.panel.tr_abbr')}",
                 T("report.panel.ba_live"): "-",
                 T("report.panel.ba_dead"): f"{fm.fmt_br(s['ba_dead_ha'], 2, lang)} ({fm.fmt_br(s['mortality_ba_pct'], 1, lang)}%)"})
    vals.append(float(s["mortality_ba_pct"])); cols.append(th.AMBER)
    return pd.DataFrame(rows), vals, cols, list(sp["species"])


def _estrutural_2col(res, lang):
    """Complete structural summary in two columns of parameter | value."""
    from manguetree import charts as ui
    from manguetree.reports import formatting as fm
    T = _T(lang)
    s = res["summary"]; ic = res.get("complexity", {})
    f2 = lambda v: fm.fmt_br(v, 2, lang)
    left = [(T("report.struct.l.stems"), fm.fmt_br(s["n_live"], 0, lang)),
            (T("report.struct.l.individuals"), fm.fmt_br(s["n_live_trees"], 0, lang)),
            (T("report.struct.l.spt"), f2(s["stems_per_tree"])),
            (ui.label("density_live_ha", lang), f2(s["density_live_ha"])),
            (ui.label("density_dead_ha", lang), f2(s["density_dead_ha"])),
            (ui.label("density_total_ha", lang), f2(s["density_total_ha"])),
            (ui.label("ba_live_ha", lang), f2(s["ba_live_ha"])),
            (ui.label("ba_dead_ha", lang), f2(s["ba_dead_ha"])),
            (ui.label("ba_total_ha", lang), f2(s["ba_total_ha"]))]
    right = [(T("report.struct.dbh_live"), f2(s["mean_dbh_cm"])),
             (ui.label("height_mean_m", lang), f2(s["height_mean_m"])),
             (ui.label("height_sd_m", lang), f2(s["height_sd_m"])),
             (T("report.struct.height_minmax"), f"{f2(s['height_min_m'])} / {f2(s['height_max_m'])}"),
             (ui.label("canopy_height_m", lang), f2(s["canopy_height_m"])),
             (ui.label("mortality_stems_pct", lang), f2(s["mortality_stems_pct"])),
             (ui.label("mortality_ba_pct", lang), f2(s["mortality_ba_pct"])),
             (T("report.struct.ic25"), f2(ic.get("dbh_gt_2.5", {}).get("ci"))),
             (T("report.struct.ic10"), f2(ic.get("dbh_gt_10", {}).get("ci")))]
    V = T("report.struct.value")
    df = pd.DataFrame({T("report.struct.left"): [a for a, _ in left], V: [b for _, b in left],
                       T("report.struct.right"): [a for a, _ in right], V + " ": [b for _, b in right]})
    return df


def _leitura_single(res, lang):
    from manguetree.reports import formatting as fm
    T = _T(lang)
    s = res["summary"]; ic = res.get("complexity", {}).get("dbh_gt_2.5", {}).get("ci")
    f1 = lambda v: fm.fmt_br(v, 1, lang)
    f2 = lambda v: fm.fmt_br(v, 2, lang)
    txt = xml_escape(T("report.read.single", plot=str(res.get("plot_name") or ""), area=fm.fmt_br(s["plot_area_m2"], 0, lang),
                       dens=fm.fmt_br(s["density_live_ha"], 0, lang), ba=f2(s["ba_live_ha"]), ba_tot=f2(s["ba_total_ha"]),
                       n_sp=int(s["n_species_live"]), dbh=f2(s["mean_dbh_cm"]), h=f2(s["height_mean_m"]),
                       can=f2(s["canopy_height_m"]), ic=f2(ic)))
    sp = mc.species_parameters(res)
    live = sp[sp["n_live"] > 0]
    if len(live):
        d_top = live.sort_values("rel_density").iloc[-1]; b_top = live.sort_values("rel_dominance").iloc[-1]
        sty = lambda n: xml_escape(str(n))
        if d_top["species"] == b_top["species"]:
            txt += T("report.read.lead_same", sp=sty(d_top["species"]), d_pct=f1(d_top["rel_density"]), b_pct=f1(b_top["rel_dominance"]))
        else:
            txt += T("report.read.lead_diff", d_sp=sty(d_top["species"]), d_pct=f1(d_top["rel_density"]),
                     b_sp=sty(b_top["species"]), b_pct=f1(b_top["rel_dominance"]))
        if float(s["mortality_stems_pct"]) > 0 and sp["n_dead"].max() > 0:
            dead_sp = sp.sort_values("n_dead").iloc[-1]["species"]
            txt += T("report.read.mort", ms=f1(s["mortality_stems_pct"]), mb=f1(s["mortality_ba_pct"]), dead_sp=xml_escape(mc.species_short(dead_sp)))
    return txt


def single_plot_report(res, lang="en", seal=False, figures=None, panel_png=None, coords=None):
    """``figures``: the app's charts as saved by ``charts.show`` (used when Plotly can draw
    them; otherwise the charts are redrawn here)."""
    from manguetree import charts as ui
    from manguetree.reports import formatting as fm, theme as th
    T = _T(lang)
    H = lambda k: xml_escape(T(f"report.h.{k}"))
    s = res["summary"]
    plot = str(res.get("plot_name") or "")
    # 1. summary panel in vertical format
    tc, cnt, mx = _classes_dap(res, lang)
    tsp, vals, cols, _sp_list = _painel_especies(res, lang)
    b = [("h", H("panel_title")),
         ("tab", tc, None, dict(bold_first=False, bars=[(T("report.panel.col_freq"), [float(c) for c in cnt], max(float(cnt.max()), 1.0), th.NAVY)])),
         ("sp", 6),
         ("tab", tsp, None, dict(species_first=True, bars=[(T("report.panel.col_abshare"), vals, 100.0, cols)]))]
    # 2. structural summary
    b += [("h", H("structural_full")), ("tab", _estrutural_2col(res, lang), None, dict(bold_cols=(1, 3), bold_first=False)),
          ("cap", T("method.heights_live_only"))]
    # 3. species and phytosociology
    imp = ui.for_display(res["importance"], lang=lang)
    imp_df = res["importance"]
    dor = [float(v) for v in imp_df["rel_dominance"]]
    b += [("h", H("species_phyto")), ("tab", ui.tabela_por_especie(res, lang), None, dict(species_first=True)),
          ("sp", 8),
          ("tab", imp.drop(columns=[c for c in imp.columns if "(troncos/ha)" in c or "m²/ha" in c]), None,
           dict(species_first=True, bars=[(T("report.panel.dor_col"), dor, 100.0, [th.species_color(x) for x in imp_df["species"]])])),
          ("cap", T("report.note.single_ivi"))]
    # 4. charts
    app = _imagens_do_app(figures, H("structural_charts"), lang)
    if app:
        b += app
    else:
        b += [("h", H("structural_charts")), ("cap", T("report.note.dbh_classes")),
              ("fig", _fig_comp_ba(res, lang, seal)),
              ("fig", _fig_classes(res, "density", lang, seal)),
              ("fig", _fig_classes(res, "basal_area", lang, seal))]
        fig_dist = _fig_distribuicao(res.get("diameter_dist"), lang, seal)
        if fig_dist is not None:
            qm = res.get("diameter_info", {}).get("q_mean")
            b += [("fig", fig_dist),
                  ("cap", T("report.cap.q_mean", q=(i18n.fmt_number(round(qm, 2), lang) if qm is not None else "-")))]
        b += [("fig", _fig_ivi(res["importance"], lang, seal)), ("fig", _fig_hist(res, lang, seal)),
              ("fig", _fig_alt_dap(res, lang, seal)), ("fig", _fig_perfil(res, lang, seal))]
    mapa = _fig_map_block(coords, lang, seal)
    if mapa:
        b += [("h", H("map"))] + mapa
    b += _bloco_verificacao(ui.issues_display_frame(res.get("issues", []), lang=lang), lang)
    f2 = lambda v: fm.fmt_br(v, 2, lang)
    kpis = [(T("report.kpi.dbh"), f2(s["mean_dbh_cm"]), "cm",
             T("report.kpi.sub.stems_tree", stems=fm.fmt_br(s["n_live"], 0, lang), spt=f2(s["stems_per_tree"]))),
            (T("report.kpi.height_canopy"), f"{f2(s['height_mean_m'])} ± {f2(s['height_sd_m'])}", "m",
             T("report.kpi.sub.canopy", canopy=f2(s["canopy_height_m"]), max=f2(s["height_max_m"]))),
            (T("report.kpi.density_live"), fm.fmt_br(s["density_live_ha"], 0, lang), "tr/ha" if lang == "pt" else "st./ha",
             T("report.kpi.sub.mort", m=fm.fmt_br(s["mortality_stems_pct"], 1, lang))),
            (T("report.kpi.ba_total"), f2(s["ba_total_ha"]), "m²/ha",
             T("report.kpi.sub.ba", live=f2(s["ba_live_ha"]), dead=f2(s["ba_dead_ha"])))]
    data = datetime.now().strftime("%d/%m/%Y %H:%M" if lang == "pt" else "%Y-%m-%d %H:%M")
    meta = T("report.meta.single", area=fm.fmt_br(s["plot_area_m2"], 0, lang), species=int(s["n_species_live"]),
             stems=fm.fmt_br(s["n_live"], 0, lang), ind=fm.fmt_br(s["n_live_trees"], 0, lang), date=data)
    return _gerar(T("report.title.single_plot", plot=plot), plot, b, lang, seal, kpis=kpis,
                  resumo=_leitura_single(res, lang), kicker=f"{marca.APP_NOME} · {T('report.kicker.single')}",
                  meta=meta, rodape=T("report.title.single"))


def _resumo_multi(df_param, ivi, lang):
    T = _T(lang)
    d = df_param.set_index("plot")
    def ext(c):
        return d[c].astype(float).idxmin(), d[c].astype(float).min(), d[c].astype(float).idxmax(), d[c].astype(float).max()
    lo, lov, hi, hiv = ext("density_live_ha")
    ba_p = d["ba_live_ha"].astype(float).idxmax(); h_p = d["height_mean_m"].astype(float).idxmax()
    m_p = d["mortality_stems_pct"].astype(float).idxmax()
    if ba_p == h_p:                  # the same plot leads two indicators: one sentence
        txt = xml_escape(T("report.sum.multi_same", lo_plot=lo, lo=_num(lov, lang, 0), hi_plot=hi,
                           hi=_num(hiv, lang, 0), plot=ba_p, ba=_num(d.loc[ba_p, "ba_live_ha"], lang),
                           h=_num(d.loc[h_p, "height_mean_m"], lang), m_plot=m_p,
                           m=_num(d.loc[m_p, "mortality_stems_pct"], lang)))
        if ivi is not None and not ivi.empty and "ivi" in ivi.columns:
            top = ivi.sort_values("ivi").iloc[-1]
            txt += " " + T("report.sum.single_top", species=f"<i>{xml_escape(str(top['species']))}</i>",
                           ivi=_num(top["ivi"], lang))
        return txt
    txt = xml_escape(T("report.sum.multi", lo_plot=lo, lo=_num(lov, lang, 0), hi_plot=hi, hi=_num(hiv, lang, 0),
                       ba_plot=ba_p, ba=_num(d.loc[ba_p, "ba_live_ha"], lang), h_plot=h_p,
                       h=_num(d.loc[h_p, "height_mean_m"], lang),
                       m_plot=m_p, m=_num(d.loc[m_p, "mortality_stems_pct"], lang)))
    if ivi is not None and not ivi.empty and "ivi" in ivi.columns:
        top = ivi.sort_values("ivi").iloc[-1]
        txt += " " + T("report.sum.single_top", species=f"<i>{xml_escape(str(top['species']))}</i>",
                       ivi=_num(top["ivi"], lang))
    return txt


def _issues_por_parcela(resultados):
    """{plot: (errors, warnings)} from the ``issues`` kept in each plot's result."""
    out = {}
    for r in resultados:
        iss = r.get("issues") or []
        out[str(r.get("plot_name") or "")] = (sum(1 for i in iss if getattr(i, "severity", "") == "error"),
                                              sum(1 for i in iss if getattr(i, "severity", "") == "warning"))
    return out


def _tabela_indicadores(df_param, lang):
    """Indicators by plot (compact): area, mean DBH, mean height, live density, live basal area
    and a basal-area bar."""
    from manguetree import charts as ui
    from manguetree.reports import formatting as fm
    cols = [c for c in ("plot_area_m2", "mean_dbh_cm", "height_mean_m", "density_live_ha", "ba_live_ha")
            if c in df_param.columns]
    d = pd.DataFrame({ui.label("plot", lang): df_param["plot"].astype(str).values})
    for c in cols:
        v = df_param[c].astype(float)
        d[ui.label(c, lang)] = [fm.fmt_br(x, 0 if c in ("plot_area_m2", "density_live_ha") else 1, lang) for x in v]
    ba = df_param["ba_live_ha"].astype(float).values if "ba_live_ha" in df_param.columns else None
    return d, ba


def _tabela_ivi(ivi, lang):
    from manguetree import charts as ui
    from manguetree.reports import formatting as fm
    d = pd.DataFrame({ui.label("species", lang): ivi["species"].astype(str).values})
    for c in ("rel_frequency", "rel_density", "rel_dominance", "ivi"):
        if c in ivi.columns:
            d[ui.label(c, lang)] = [fm.fmt_br(float(x), 1, lang) for x in ivi[c]]
    return d


def _matriz_complementar(resultados, df_param, lang):
    from manguetree import charts as ui
    from manguetree.reports import formatting as fm
    T = _T(lang)
    ip = _issues_por_parcela(resultados)
    cols = [c for c in ("canopy_height_m", "mortality_stems_pct", "mortality_ba_pct", "complexity_2_5") if c in df_param.columns]
    d = pd.DataFrame({ui.label("plot", lang): df_param["plot"].astype(str).values})
    for c in cols:
        d[ui.label(c, lang)] = [fm.fmt_br(float(x), 1 if c == "canopy_height_m" else 2, lang) for x in df_param[c]]
    d[T("report.col.errors_warnings")] = [f"{ip.get(str(p), (0, 0))[0]} / {ip.get(str(p), (0, 0))[1]}" for p in df_param["plot"]]
    return d


def multiple_plots_report(resultados, df_param, ivi, df_especies, issues_df=None,
                          lang="en", seal=False, figures=None, coords=None):
    from manguetree import charts as ui
    from manguetree.reports import formatting as fm, theme as th
    T = _T(lang)
    H = lambda k: xml_escape(T(f"report.h.{k}"))
    cmap = th.plot_color_map(df_param["plot"]) if "plot" in df_param.columns else {}
    b = []
    try:
        tab, ba = _tabela_indicadores(df_param, lang)
        bars = ([(T("report.col.ba_bar"), [float(x) for x in ba], max(float(ba.max()), 1e-9), th.NAVY)]
                if ba is not None else [])
        b += [("h", H("indicators_by_plot")), ("tab", tab, None, dict(bars=bars)),
              ("cap", T("report.note.indicators"))]
    except Exception:
        shown = ui.for_display(df_param, lang=lang)
        b += [("h", H("comparison")), ("tab", shown.round(2))]
    if ivi is not None and not ivi.empty and "ivi" in ivi.columns:
        iv = ivi.sort_values("ivi", ascending=False).reset_index(drop=True)
        b += [("h", H("ivi_set")),
              ("tab", _tabela_ivi(iv, lang), None,
               dict(species_first=True, bars=[(T("report.col.ivi_bar", max=fm.fmt_br(float(iv["ivi"].max()), 0, lang)),
                                                [float(x) for x in iv["ivi"]], float(iv["ivi"].max()),
                                                [th.species_color(x) for x in iv["species"]])]))]
    cols = [c for c in mc.metric_columns(df_param) if str(c).isidentifier()]
    if cols:
        b.append(("h", H("overview")))
        for k, f in enumerate(_paineis(df_param, cols, "plot", "bar", lang, seal, cmap=cmap)):
            b.append(("fig", f, T("report.cap.panels", first=ui.label(cols[k * 4], lang), n=min(4, len(cols) - k * 4))))
    app = _imagens_do_app(figures, H("figures"), lang, plot_colors=cmap)
    if app:
        b += app
    else:
        b += [("h", H("dbh_distribution")), ("fig", _fig_box(resultados, lang, seal)),
              ("h", H("species_contribution")), ("fig", _fig_especies_parcelas(df_especies, lang, seal)),
              ("h", H("ivi")), ("fig", _fig_ivi(ivi, lang, seal))]
    try:
        b += [("h", H("complementary")), ("tab", _matriz_complementar(resultados, df_param, lang)),
              ("cap", T("report.note.complementary"))]
    except Exception:
        pass
    mapa = _fig_map_block(coords, lang, seal, cmap)
    if mapa:
        b += [("h", H("map"))] + mapa
    b += _bloco_verificacao(issues_df, lang)
    nomes = [str(p) for p in df_param["plot"]] if "plot" in df_param.columns else []
    has_area = "plot_area_m2" in df_param.columns
    areas = ", ".join(fm.fmt_br(float(a), 0, lang) for a in df_param["plot_area_m2"]) if has_area else ""
    area_tot = fm.fmt_br(df_param["plot_area_m2"].astype(float).sum(), 0, lang) if has_area else "-"
    try:
        especies = [str(x) for x in ivi.sort_values("ivi", ascending=False)["species"]] if ivi is not None else []
        kpis = [(T("report.kpi.plots"), str(len(resultados)), "", xml_escape(", ".join(nomes))),
                (T("report.kpi.area"), area_tot, "m²", xml_escape(areas + " m²") if has_area else ""),
                (T("report.kpi.live_stems"), fm.fmt_br(df_param["n_live"].astype(float).sum(), 0, lang) if "n_live" in df_param.columns else "-", "",
                 T("report.kpi.sub.sum_plots")),
                (T("report.kpi.richness"), str(len(especies)), T("report.unit.species"),
                 "<i>" + xml_escape(", ".join(mc.species_short(x) if hasattr(mc, "species_short") else x for x in especies[:3])) + "</i>")]
    except Exception:
        kpis = []
    try:
        resumo = _resumo_multi(df_param, ivi, lang)
    except Exception:
        resumo = None
    data = datetime.now().strftime("%d/%m/%Y %H:%M" if lang == "pt" else "%Y-%m-%d %H:%M")
    meta = T("report.meta.multi", plots=", ".join(nomes), area=area_tot, date=data) if nomes else None
    return _gerar(T("report.title.multiple"), T("report.plots_count", n=len(resultados)), b, lang, seal, kpis=kpis,
                  resumo=resumo, kicker=f"{marca.APP_NOME} · {T('report.kicker.multi')}", meta=meta,
                  rodape=T("report.title.multiple"), leitura=T("report.reading"))


def _delta_html(v0, v1, lang, dec=2, unit="", pct=True, invert=False):
    """Coloured change line: ▲/▼ absolute (and %) from first to last survey."""
    from manguetree.reports import formatting as fm
    d = v1 - v0
    up = d >= 0
    good = (not up) if invert else up
    col = "#15803D" if good else "#B91C1C"
    arrow = "▲" if up else "▼"
    s = f"{arrow} {'+' if up else '−'}{fm.fmt_br(abs(d), dec, lang)}{(' ' + unit) if unit else ''}"
    if pct and v0:
        s += f" ({'+' if up else '−'}{fm.fmt_br(abs(d / v0 * 100), 1, lang)}%)"
    return f'<font color="{col}"><b>{s}</b></font>'


def _tabela_serie(s, lang):
    """Series table: one row per survey plus a bold last row with the change (t0 to tn);
    columns that never change (e.g. species count) are left out."""
    from manguetree import charts as ui
    from manguetree.reports import formatting as fm
    cols = [c for c in mc.metric_columns(s) if str(c).isidentifier() and c in s.columns
            and s[c].astype(float).nunique() > 1]
    dec = lambda c: 0 if ("density" in c or c.startswith("n_")) else 2
    out = {ui.label("year", lang): [str(int(y)) for y in s["year"]]}
    for c in cols:
        v = s[c].astype(float)
        out[ui.label(c, lang)] = [fm.fmt_br(x, dec(c), lang) for x in v]
    d = pd.DataFrame(out)
    last = {ui.label("year", lang): f"Δ {int(s['year'].iloc[0]) % 100:02d}–{int(s['year'].iloc[-1]) % 100:02d}"}
    for c in cols:
        x = float(s[c].iloc[-1]) - float(s[c].iloc[0])
        last[ui.label(c, lang)] = ("+" if x > 0 else ("−" if x < 0 else "")) + fm.fmt_br(abs(x), dec(c), lang)
    return pd.concat([d, pd.DataFrame([last])], ignore_index=True)


def temporal_report(df_serie, df_esp, issues_df=None, lang="en", seal=False, figures=None):
    from manguetree import charts as ui
    from manguetree.reports import formatting as fm
    T = _T(lang)
    H = lambda k: xml_escape(T(f"report.h.{k}"))
    s = df_serie.sort_values("year").reset_index(drop=True)
    cols = [c for c in mc.metric_columns(df_serie)]
    b = [("h", H("series_summary")), ("cap", T("report.note.series")),
         ("tab", _tabela_serie(s, lang), None, dict(bold_last_row=True))]
    figures = _sem_duplicados(figures, set(cols), "mortality_stems_pct" in cols)
    cols = [c for c in cols if c in s.columns and pd.to_numeric(s[c], errors="coerce").nunique() > 1]
    app = _imagens_do_app(figures, H("figures"), lang)
    if cols:
        b.append(("h", H("overview_series")))
        for k, f in enumerate(_paineis(s, cols, "year", "line", lang, seal)):
            b.append(("fig", f, T("report.cap.panels", first=ui.label(cols[k * 4], lang), n=min(4, len(cols) - k * 4))))
    if app:
        b += app
    elif df_esp is not None and not df_esp.empty:
        b.append(("h", H("evolution_species")))
        for met in ["density_ha", "ba_ha", "mean_dbh_cm", "height_mean_m", "ba_contribution_pct"]:
            if met in df_esp.columns:
                b.append(("fig", _fig_serie_especie(df_esp, met, lang, seal)))
    b += _bloco_verificacao(issues_df, lang)
    y0, y1 = int(s["year"].iloc[0]), int(s["year"].iloc[-1])
    span = max(y1 - y0, 1)
    def val(c, i):
        return float(s[c].iloc[i]) if c in s.columns else None
    def kpi(c, label, dec, unit, fmt=None):
        v0, v1 = val(c, 0), val(c, -1)
        if v0 is None:
            return None
        rate = (v1 - v0) / span
        sub = (_delta_html(v0, v1, lang, dec, unit) + "<br/>" +
               T("report.kpi.sub.temporal", y0=y0, v0=fm.fmt_br(v0, dec, lang), rate=("+" if rate >= 0 else "−") + fm.fmt_br(abs(rate), dec, lang)))
        return (f"{label} ({y1})", fm.fmt_br(v1, dec, lang), unit, sub)
    kpis = [k for k in (kpi("mean_dbh_cm", T("report.kpi.dbh"), 2, "cm"),
                        kpi("canopy_height_m", T("report.kpi.canopy"), 2, "m"),
                        kpi("density_live_ha", T("report.kpi.density_live"), 0, "tr/ha" if lang == "pt" else "st./ha"),
                        kpi("ba_live_ha", T("report.kpi.ba_live"), 2, "m²/ha")) if k]
    def first_last(c):
        return (_num(s[c].iloc[0], lang, 0 if "density" in c else 1), _num(s[c].iloc[-1], lang, 0 if "density" in c else 1)) if c in s.columns else ("-", "-")
    d0, d1 = first_last("density_live_ha"); b0, b1 = first_last("ba_live_ha"); m0, m1 = first_last("mean_dbh_cm")
    mort = _num(s["mortality_stems_pct"].iloc[-1], lang) if "mortality_stems_pct" in s.columns else "-"
    resumo = xml_escape(T("report.sum.temporal", y0=y0, y1=y1, n=len(s), d0=d0, d1=d1, b0=b0, b1=b1,
                          m0=m0, m1=m1, mort=mort))
    data = datetime.now().strftime("%d/%m/%Y %H:%M" if lang == "pt" else "%Y-%m-%d %H:%M")
    meta = T("report.meta.temporal", y0=y0, y1=y1, n=len(s), span=span, date=data)
    return _gerar(T("report.title.temporal"), T("report.period", start=y0, end=y1), b, lang, seal,
                  kpis=kpis, resumo=resumo, kicker=f"{marca.APP_NOME} · {T('report.kicker.temporal')}", meta=meta,
                  rodape=T("report.title.temporal"), leitura=T("report.reading.temporal"))


def colonization_report(resumos, dens, lang="en", seal=False, figures=None):
    """Colonization dynamics report. ``resumos``: ``colonizacao.resumo`` of each plot;
    ``dens``: juvenile density table (columns parcela, ano, ind_ha, n)."""
    T = _T(lang)
    H = lambda k: xml_escape(T(f"report.h.{k}"))
    tab = pd.DataFrame({
        T("report.col.plot"): [r["parcela"] for r in resumos],
        T("report.col.file"): [r["arquivo"] for r in resumos],
        T("report.col.individuals"): [r["individuos"] for r in resumos],
        T("report.col.collections"): [r["blocos"] for r in resumos],
        T("report.col.years"): [f"{r['anos'][0]} - {r['anos'][1]}" if r["anos"] else "-" for r in resumos]})
    b = [("h", H("colonization_read")), ("tab", tab)]
    figures = _sem_duplicados([f for f in (figures or []) if f.get("key") != "colon_schema_obs"])
    app = _imagens_do_app(figures, H("figures"), lang)
    if app:
        b += app
    n_ind = int(sum(r["individuos"] for r in resumos))
    n_col = int(sum(r["blocos"] for r in resumos))
    anos = [a for r in resumos if r["anos"] for a in r["anos"]]
    kpis, resumo = [], None
    try:
        d = dens["ind_ha"].astype(float)
        kpis = [(T("report.kpi.col_plots"), str(len(resumos))), (T("report.kpi.col_collections"), str(n_col)),
                (T("report.kpi.col_individuals"), _num(n_ind, lang, 0)),
                (T("report.kpi.col_density"), _num(d.mean(), lang, 0))]
        resumo = xml_escape(T("report.sum.colonization", plots=len(resumos), collections=n_col,
                              individuals=_num(n_ind, lang, 0), y0=min(anos) if anos else "-",
                              y1=max(anos) if anos else "-", density=_num(d.mean(), lang, 0),
                              dmin=_num(d.min(), lang, 0), dmax=_num(d.max(), lang, 0)))
    except Exception:
        pass
    return _gerar(T("report.title.colonization"), T("report.plots_count", n=len(resumos)), b, lang, seal,
                  kpis=kpis, resumo=resumo, kicker=f"{marca.APP_NOME} · {T('report.kicker.colonization')}",
                  rodape=T("report.title.colonization"))
