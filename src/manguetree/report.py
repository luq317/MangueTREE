# -*- coding: utf-8 -*-
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
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image,
                                Table, TableStyle, PageBreak, CondPageBreak, KeepTogether)

_VERDE = marca.VERDE
_VERDE_ESC = marca.VERDE_ESCURO


def _cor_especie(esp):
    return mc.species_color(esp)


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



# DejaVu Sans ships with matplotlib and has "²", "³", "≥", "·" and the Portuguese accents.
_FONT, _FONT_BOLD = "DejaVuSans", "DejaVuSans-Bold"


def _register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    if _FONT in pdfmetrics.getRegisteredFontNames():
        return
    fonts = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    pdfmetrics.registerFont(TTFont(_FONT, str(fonts / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(_FONT_BOLD, str(fonts / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFontFamily(_FONT, normal=_FONT, bold=_FONT_BOLD,
                                  italic=_FONT, boldItalic=_FONT_BOLD)


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
        ax.boxplot(dados, tick_labels=nomes)      # matplotlib >= 3.9
    except TypeError:
        ax.boxplot(dados, labels=nomes)
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
# PDF ASSEMBLY
# ---------------------------------------------------------------------------
def _estilos():
    _register_fonts()
    ss = getSampleStyleSheet()
    for st in ss.byName.values():          # DejaVu everywhere (accents, ², ≥)
        if hasattr(st, "fontName"):
            st.fontName = _FONT_BOLD if "Bold" in st.fontName else _FONT
    ss.add(ParagraphStyle("H", parent=ss["Heading2"], textColor=colors.HexColor(_VERDE_ESC),
                          fontSize=13, spaceBefore=10, spaceAfter=4))
    ss.add(ParagraphStyle("Cap", parent=ss["Normal"], fontSize=8,
                          textColor=colors.grey, alignment=1, spaceAfter=8))
    return ss


def _mpl_para_img(fig, largura=15 * cm):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig); buf.seek(0)
    from PIL import Image as PILImage
    w, h = PILImage.open(buf).size
    buf.seek(0)
    return Image(buf, width=largura, height=largura * h / w)


_LARGURA_UTIL = A4[0] - 3.2 * cm  # largura entre margens


_PAD = 3                  # cell padding (pt) on each side
_HDR_SIZE, _CELL_SIZE = 6.5, 7
LANDSCAPE_OVER_COLUMNS = 8   # wider tables get the page in landscape (when they do not fit)


def _cell_text(v, lang):
    """Table cell text: decimal comma in Portuguese, catalog text for missing values."""
    if isinstance(v, (int, np.integer)) and not isinstance(v, bool):
        return str(int(v))
    if v is None or (isinstance(v, (float, np.floating)) and pd.isna(v)):
        return i18n.t("report.na", lang)
    if isinstance(v, (float, np.floating)):
        text = f"{v:.2f}"
        return text.replace(".", ",") if lang == "pt" else text
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


def _tabela_rl(df, ss, lang, width=None):
    lay = table_layout(df, lang, width or _LARGURA_UTIL)
    est_cel = ParagraphStyle("cel", fontName=_FONT, fontSize=lay["cell_size"],
                             leading=lay["cell_size"] + 1.5, alignment=1)
    est_hdr = ParagraphStyle("hdr", fontName=_FONT_BOLD, fontSize=lay["hdr_size"],
                             leading=lay["hdr_size"] + 1.5, alignment=1,
                             textColor=colors.white)
    header = [Paragraph(xml_escape(c), est_hdr) for c in lay["header"]]
    linhas = [[Paragraph(xml_escape(v), est_cel) for v in row] for row in lay["rows"]]
    t = Table([header] + linhas, colWidths=lay["widths"], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(_VERDE)),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9E2DC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7F5")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), _PAD), ("RIGHTPADDING", (0, 0), (-1, -1), _PAD),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
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


def _cabecalho_rodape(lang, seal):
    T = _T(lang)
    logo = ImageReader(_logo_png())
    selo = ImageReader(_selo_png()) if seal else None
    footer = [T("report.footer.generated", version=__version__, url=marca.REPO_URL),
              T("report.footer.cite", citation=marca.CITATION)]

    def _desenha(canvas, doc):
        canvas.saveState()
        w, h = canvas._pagesize
        # header
        canvas.drawImage(logo, 1.6 * cm, h - 2.1 * cm, 1.3 * cm, 1.3 * cm, mask="auto")
        canvas.setFillColor(colors.HexColor(_VERDE_ESC))
        canvas.setFont(_FONT_BOLD, 13)
        canvas.drawString(3.1 * cm, h - 1.35 * cm, f"{marca.APP_NOME}")
        canvas.setFillColor(colors.grey); canvas.setFont(_FONT, 8.5)
        canvas.drawString(3.1 * cm, h - 1.75 * cm, T("report.tagline"))
        canvas.setStrokeColor(colors.HexColor(_VERDE)); canvas.setLineWidth(1.5)
        canvas.line(1.6 * cm, h - 2.25 * cm, w - 1.6 * cm, h - 2.25 * cm)
        # footer: generated-with line, citation (wrapped), page number
        canvas.setStrokeColor(colors.HexColor("#D9E2DC")); canvas.setLineWidth(0.5)
        canvas.line(1.6 * cm, 1.9 * cm, w - 1.6 * cm, 1.9 * cm)
        canvas.setFont(_FONT, 6.8); canvas.setFillColor(colors.grey)
        width = w - 3.2 * cm - (1.8 * cm if seal else 0)
        lines = [x for t in footer for x in _wrap_line(t, _FONT, 6.8, width)]
        for i, linha in enumerate(lines):
            canvas.drawString(1.6 * cm, 1.55 * cm - i * 0.3 * cm, linha)
        if seal:
            canvas.drawImage(selo, w - 3.0 * cm, 0.5 * cm, 1.4 * cm, 1.4 * cm, mask="auto")
        canvas.setFont(_FONT, 7)
        canvas.drawRightString(w - (3.2 if seal else 1.6) * cm, 0.7 * cm,
                               T("report.page", n=canvas.getPageNumber()))
        canvas.restoreState()
    return _desenha


def _gerar(titulo, subtitulo, blocos, lang, seal):
    """blocos: lista de ('h', txt) | ('tab', df) | ('fig', mpl_fig) | ('cap', txt)."""
    T = _T(lang)
    buf = io.BytesIO()
    ss = _estilos()
    # a table wider than the portrait page (and with many columns) puts the page in landscape
    landscape = any(
        t == "tab" and c is not None and not c.empty
        and len(_table_frame(c).columns) > LANDSCAPE_OVER_COLUMNS
        and not table_layout(c, lang, _LARGURA_UTIL)["fits"]
        for t, c in blocos)
    page = (A4[1], A4[0]) if landscape else A4
    width = page[0] - 3.2 * cm
    doc = SimpleDocTemplate(buf, pagesize=page, topMargin=2.7 * cm, bottomMargin=2.4 * cm,
                            leftMargin=1.6 * cm, rightMargin=1.6 * cm,
                            title=f"{marca.APP_NOME}: {titulo}")
    flow = [Paragraph(xml_escape(titulo), ss["Title"])]
    if subtitulo:
        flow.append(Paragraph(xml_escape(subtitulo), ss["Cap"]))
    flow.append(Paragraph(T("report.generated_on",
                            date=datetime.now().strftime("%d/%m/%Y %H:%M" if lang == "pt"
                                                         else "%Y-%m-%d %H:%M")), ss["Cap"]))
    flow.append(Spacer(1, 6))
    i = 0
    while i < len(blocos):
        tipo, conteudo = blocos[i]
        if tipo == "h":
            prox = blocos[i + 1] if i + 1 < len(blocos) else (None, None)
            if prox[0] == "fig" and prox[1] is not None:
                # keep the heading with the first figure (no orphan heading at page end)
                flow.append(KeepTogether([Paragraph(conteudo, ss["H"]),
                                          _mpl_para_img(prox[1]), Spacer(1, 10)]))
                i += 2
                continue
            flow.append(CondPageBreak(3 * cm))
            flow.append(Paragraph(conteudo, ss["H"]))
        elif tipo == "cap":
            flow.append(Paragraph(xml_escape(conteudo), ss["Cap"]))
        elif tipo == "tab":
            if conteudo is not None and not conteudo.empty:
                flow.append(_tabela_rl(conteudo, ss, lang, width)); flow.append(Spacer(1, 8))
        elif tipo == "fig" and conteudo is not None:
            flow.append(_mpl_para_img(conteudo)); flow.append(Spacer(1, 10))
        i += 1
    cr = _cabecalho_rodape(lang, seal)
    doc.build(flow, onFirstPage=cr, onLaterPages=cr)
    buf.seek(0)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# PUBLIC REPORTS
# ---------------------------------------------------------------------------
MAX_LINHAS_VERIFICACAO = 100


def _bloco_verificacao(issues_df, lang):
    """Blocks of the data-check section.

    ``issues_df`` is a frame from ``charts.issues_display_frame`` in ``lang`` (may carry
    an extra sheet/plot/year column); None means validation was not run (no section).
    """
    if issues_df is None:
        return []
    T = _T(lang)
    h = xml_escape(T("report.h.verification"))
    if issues_df.empty:
        return [("h", h), ("cap", T("report.verification.ok"))]
    from manguetree import charts as ui
    sev = issues_df[ui.issue_column_label("severity", lang)]
    n_err = int((sev == ui.severity_label("error", lang)).sum())
    n_warn = int((sev == ui.severity_label("warning", lang)).sum())
    # errors first, so the truncation never hides them (stable sort keeps row order)
    issues_df = issues_df.iloc[
        (sev != ui.severity_label("error", lang)).to_numpy().argsort(kind="stable")]
    b = [("h", h), ("cap", T("report.verification.counts", errors=n_err, warnings=n_warn))]
    if len(issues_df) > MAX_LINHAS_VERIFICACAO:
        b.append(("cap", T("report.verification.truncated", shown=MAX_LINHAS_VERIFICACAO,
                           total=len(issues_df), sheet=T("sheet.issues"))))
    b.append(("tab", issues_df.head(MAX_LINHAS_VERIFICACAO)))
    return b


def single_plot_report(res, lang="en", seal=False):
    from manguetree import charts as ui
    T = _T(lang)
    H = lambda k: xml_escape(T(f"report.h.{k}"))
    b = _bloco_verificacao(ui.issues_display_frame(res.get("issues", []), lang=lang), lang)
    b += [("h", H("summary")), ("tab", ui.resumo_para_df(res, lang)),
          ("cap", T("method.heights_live_only")),
          ("h", H("by_species")), ("tab", ui.tabela_por_especie(res, lang)),
          ("h", H("phyto")), ("tab", ui.for_display(res["importance"], lang=lang)),
          ("h", H("figures")), ("cap", T("report.note.dbh_classes")),
          ("fig", _fig_comp_ba(res, lang, seal)),
          ("fig", _fig_classes(res, "density", lang, seal)),
          ("fig", _fig_classes(res, "basal_area", lang, seal))]
    fig_dist = _fig_distribuicao(res.get("diameter_dist"), lang, seal)
    if fig_dist is not None:
        qm = res.get("diameter_info", {}).get("q_mean")
        b += [("fig", fig_dist),
              ("cap", T("report.cap.q_mean",
                        q=(i18n.fmt_number(round(qm, 2), lang) if qm is not None else "-")))]
    b += [("fig", _fig_ivi(res["importance"], lang, seal)),
          ("fig", _fig_hist(res, lang, seal)),
          ("fig", _fig_alt_dap(res, lang, seal)),
          ("fig", _fig_perfil(res, lang, seal))]
    return _gerar(T("report.title.single"), str(res.get("plot_name") or ""), b, lang, seal)


def multiple_plots_report(resultados, df_param, ivi, df_especies, issues_df=None,
                          lang="en", seal=False):
    from manguetree import charts as ui
    T = _T(lang)
    H = lambda k: xml_escape(T(f"report.h.{k}"))
    b = _bloco_verificacao(issues_df, lang)
    shown = ui.for_display(df_param, lang=lang)
    b += [("h", H("comparison")), ("tab", shown.round(2))]
    for col in mc.metric_columns(df_param):
        b.append(("fig", _fig_barras(shown, ui.label("plot", lang), ui.label(col, lang), seal)))
    b += [("h", H("dbh_distribution")),
          ("fig", _fig_box(resultados, lang, seal)),
          ("h", H("species_contribution")),
          ("fig", _fig_especies_parcelas(df_especies, lang, seal)),
          ("h", H("ivi")), ("tab", ui.for_display(ivi, lang=lang)),
          ("fig", _fig_ivi(ivi, lang, seal))]
    return _gerar(T("report.title.multiple"), T("report.plots_count", n=len(resultados)),
                  b, lang, seal)


def temporal_report(df_serie, df_esp, issues_df=None, lang="en", seal=False):
    from manguetree import charts as ui
    T = _T(lang)
    H = lambda k: xml_escape(T(f"report.h.{k}"))
    b = _bloco_verificacao(issues_df, lang)
    b += [("h", H("series")),
          ("tab", ui.for_display(df_serie, lang=lang).round(2)), ("h", H("evolution"))]
    for col in mc.metric_columns(df_serie):
        b.append(("fig", _fig_serie(df_serie, col, lang, seal)))
    if df_esp is not None and not df_esp.empty:
        b.append(("h", H("evolution_species")))
        for met in ["density_ha", "ba_ha", "mean_dbh_cm", "height_mean_m",
                    "ba_contribution_pct"]:
            if met in df_esp.columns:
                b.append(("fig", _fig_serie_especie(df_esp, met, lang, seal)))
    period = T("report.period", start=int(df_serie["year"].min()),
               end=int(df_serie["year"].max()))
    return _gerar(T("report.title.temporal"), period, b, lang, seal)
