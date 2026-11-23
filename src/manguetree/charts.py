# -*- coding: utf-8 -*-
"""
charts.py
=========
Gráficos (Plotly, qualidade de publicação) e exportações (Excel/CSV)
compartilhados pelas páginas do MangueTREE.
"""

from pathlib import Path
import hashlib
import io
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.colors as pcolors

from manguetree import calc as mc
from manguetree import i18n
from manguetree import branding as marca
from manguetree.species import (REGIONS, SpeciesResolver, load_genus_defaults,
                                load_species_table)
from manguetree.validation import describe, describe_action, issues_to_frame

# Config de exportação em alta resolução para todos os gráficos Plotly.
# O botão "câmera" da barra do Plotly passa a exportar em escala 3x (publicação).
PLOT_CONFIG = {
    "toImageButtonOptions": {"format": "png", "scale": 4},
    "displaylogo": False,
    "modeBarButtonsToAdd": ["toImage"],
}

_SELO_URI = None


def _selo_uri():
    """Data-URI do selo (mini) para carimbar gráficos Plotly. Vazio se indisponível."""
    global _SELO_URI
    if _SELO_URI is None:
        try:
            import base64
            from manguetree import report as _rep
            _SELO_URI = "data:image/png;base64," + \
                base64.b64encode(_rep.selo_mini_png_bytes()).decode()
        except Exception:
            _SELO_URI = ""
    return _SELO_URI

# Palette code -> colours; the display name is the catalog entry ``palette.<code>``.
PALETAS = {
    # "manguetree": each species keeps its own colour (genus hue); the other palettes
    # also recolour the species, in the order of their scientific names
    "manguetree": ["#2E8B57", "#1F4D3A", "#4C78A8", "#7B5230", "#9FD3B2", "#8C9A94", "#C9A27E"],
    "lab": ["#1F3A5F", "#2A9D8F", "#B8C4CC", "#5F7A94", "#8FD1C7", "#E4E9EE"],
    "greens": ["#1B5E20", "#43A047", "#A5D6A7", "#2E7D32", "#81C784", "#C8E6C9"],
    "default": pcolors.qualitative.Plotly,
    "pastel": pcolors.qualitative.Pastel,
    "bold": pcolors.qualitative.Bold,
    "d3": pcolors.qualitative.D3,
    "set2": pcolors.qualitative.Set2,
    "dark2": pcolors.qualitative.Dark2,
    "viridis": pcolors.sequential.Viridis,
}


def palette_label(code, lang=None):
    return i18n.t(f"palette.{code}", lang or i18n.get_lang())


# --- Identidade visual -------------------------------------------------------
LOGO_SVG = marca.LOGO_SVG

_CSS = """
<style>
:root { --mt-green:#2E8B57; --mt-ink:#1A2B22; }
[data-testid="stMetric"]{
  background:#F4F7F5; border:1px solid #E2E8E4; border-radius:12px;
  padding:12px 16px;
}
[data-testid="stMetricLabel"] p{ color:#4A5A52; font-weight:600; }
[data-testid="stSidebar"]{ background:#F7FAF8; }
.stTabs [data-baseweb="tab-list"]{ gap:4px; }
.mt-header{ display:flex; align-items:center; gap:14px; margin:2px 0 6px 0; }
.mt-header h1{ font-size:1.7rem; line-height:1.1; margin:0; color:var(--mt-ink); }
.mt-header .mt-sub{ color:#6B7A72; font-size:0.95rem; margin-top:2px; }
.mt-divider{ height:3px; background:linear-gradient(90deg,#2E8B57,#57B77E 60%,#F7FAF8);
  border:none; border-radius:2px; margin:2px 0 14px 0; }
</style>
"""


def topo(titulo, subtitulo=""):
    """Injeta o estilo base e desenha o cabeçalho com o logo do MangueTREE."""
    import streamlit as st
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        f'<div class="mt-header">{LOGO_SVG}'
        f'<div><h1>{titulo}</h1><div class="mt-sub">{subtitulo}</div></div></div>'
        '<hr class="mt-divider"/>', unsafe_allow_html=True)


def _layout(fig, estilos, titulo=None):
    """Estilo 'artigo científico': título menor à esquerda, eixos finos, fonte menor.
    The MangueTREE seal is added only when ``estilos["seal"]`` is true."""
    tam_t = estilos.get("tamanho_titulo", 14)
    tam_e = estilos.get("tamanho_eixos", 12)
    fig.update_layout(
        template="plotly_white",
        font=dict(family="sans-serif", size=11, color=marca.TINTA),
        title=dict(text=titulo, x=0.0, xanchor="left", font=dict(size=tam_t)),
        plot_bgcolor="white", paper_bgcolor="white",
        legend_title_text="", margin=dict(t=46, r=24, b=58, l=62),
        separators=",." if _lang() == "pt" else ".,",              # decimal, thousands
    )
    if estilos.get("bar_width"):
        fig.update_layout(bargap=1 - float(estilos["bar_width"]))
    if estilos.get("height") and not fig.layout.height:
        fig.update_layout(height=int(estilos["height"]))
    eixo = dict(showline=True, linewidth=0.8, linecolor="#5F726A", zeroline=False,
                ticks="outside", tickcolor="#5F726A", ticklen=4,
                tickfont=dict(size=10), title_font=dict(size=tam_e),
                exponentformat="none", separatethousands=True)     # 10.000, never 10k
    fig.update_xaxes(showgrid=False, **eixo)
    fig.update_yaxes(showgrid=False, **eixo)
    from manguetree.reports.plotly_adapter import outline_boxes
    outline_boxes(fig, "#5F726A", 0.8)          # box / violin: thin outline like the axes
    # the seal (opt-in, sidebar checkbox) is placed by add_seal once the final size and
    # margins are known, in the lower right corner outside the plotting area
    fig.update_layout(meta={"mt_seal": bool(estilos.get("seal"))})
    return fig


def add_seal(fig):
    """MangueTREE seal in the lower right corner, below the chart (outside the axes)."""
    meta = fig.layout.meta or {}
    if not (isinstance(meta, dict) and meta.get("mt_seal")):
        return fig
    h = fig.layout.height or 450
    m = fig.layout.margin
    mt, mb = (m.t if m.t is not None else 46), (m.b if m.b is not None else 58)
    extra = 38
    fig.update_layout(height=h + extra, margin=dict(b=mb + extra))
    plot_h = max(h + extra - mt - mb - extra, 50)
    y = -(mb + extra - 4) / plot_h          # paper units: just above the bottom edge
    uri = _selo_uri()
    if uri:
        fig.add_layout_image(dict(source=uri, xref="paper", yref="paper", x=1.0, y=y,
                                  sizex=0.09, sizey=30 / plot_h, xanchor="right", yanchor="bottom",
                                  layer="above", opacity=0.9))
    else:
        fig.add_annotation(text=marca.SELO_TEXTO, xref="paper", yref="paper", x=1.0, y=y,
                           showarrow=False, xanchor="right", yanchor="bottom",
                           font=dict(size=9, color="#9AA7A0"))
    return fig


PALETTE_STATE = "_palette"      # session key with the palette chosen on the current page


def use_palette(name):
    """Remember the page's palette (species charts read it through species_colors)."""
    import streamlit as st
    st.session_state[PALETTE_STATE] = name


def species_colors(especies):
    """Species -> colour. Palette "manguetree" (default): genus hue, own tone per species;
    any other palette: its colours in the order of the scientific names."""
    try:
        import streamlit as st
        nome = st.session_state.get(PALETTE_STATE, "manguetree")
    except Exception:
        nome = "manguetree"
    especies = list(dict.fromkeys(especies))
    if nome not in PALETAS or nome == "manguetree":
        return {e: mc.species_color(e) for e in especies}
    cores = PALETAS[nome]
    ordem = sorted(especies, key=lambda s: (s == mc.UNIDENTIFIED_LABEL, str(s)))
    return {sp: cores[i % len(cores)] for i, sp in enumerate(ordem)}


def cor_por_especie(especies):
    """Mapa espécie->cor (segue a paleta escolhida; ver species_colors)."""
    return species_colors(especies)


# Column labels live in the catalogs as ``labels.<internal column>``; the prepared data
# table has two columns that read differently (``labels.data.<column>``).
_DATA_COLUMNS = ("species", "n_stems")
_SPECIES_STATUS = ("ok", "genus_default", "ambiguous", "unknown")


def _lang(lang=None):
    return lang or i18n.get_lang()


def label(col, lang=None, data_table=False):
    """Display label of an internal column name in ``lang`` (default: current)."""
    if data_table and col in _DATA_COLUMNS:
        return i18n.t(f"labels.data.{col}", _lang(lang))
    if " [" in str(col) and str(col).endswith("]"):     # "<parameter> [<DBH class>]"
        base, cls = str(col).split(" [", 1)
        if base.isidentifier():
            return f"{label(base, lang)} [{cls[:-1]} cm]"
    if not str(col).isidentifier():      # already a display name (e.g. species contribution)
        return str(col)
    return i18n.t(f"labels.{col}", _lang(lang))


def species_name(name, lang=None):
    """Species label for display: scientific names stay as they are; the placeholder
    for unresolved species follows the language."""
    if name == mc.UNIDENTIFIED_LABEL:
        return i18n.t("species.unidentified", _lang(lang))
    return name


def condition_label(cond, lang=None):
    """'live'/'dead'/'both' (internal codes) -> display text."""
    return i18n.t(f"cond.{cond}", _lang(lang))


def _num(value, decimals, lang):
    text = f"{value:.{decimals}f}"
    return text.replace(".", ",") if lang == "pt" else text


num = _num      # public alias: number text with the decimal separator of ``lang``


COUNT_COLUMNS = ("plot_area_m2", "n_species_live",
                 "n_dead_no_dbh", "n_live_no_dbh", "n_live", "n_dead", "n_stems", "n_live_trees",
                 "live_trees_start", "live_trees_end", "survivors", "deaths", "recruits")


def integer_counts(df):
    """Copy of ``df`` whose count/area columns are integers when every value is integral
    (a mean over repeated years or a concat of floats would show 3.00 and 80.00)."""
    out = df.copy()
    for c in COUNT_COLUMNS:
        if c in out.columns and out[c].notna().all() and (out[c] == out[c].round()).all():
            out[c] = out[c].round().astype(int)
    return out


def format_by_dtype(df, decimals=2):
    """``Styler.format`` mapping: integer columns without decimals, others with ``decimals``."""
    return {c: ("{:d}" if pd.api.types.is_integer_dtype(df[c]) else f"{{:.{decimals}f}}")
            for c in df.columns if pd.api.types.is_numeric_dtype(df[c])}


def sheet_names(uploaded):
    """Sheet names of an uploaded workbook, read once per uploaded file (not at every
    rerun of the page)."""
    import streamlit as st

    @st.cache_data(show_spinner=False, max_entries=8)
    def _names(file_id, _data):
        return pd.ExcelFile(io.BytesIO(_data)).sheet_names

    return list(_names(getattr(uploaded, "file_id", uploaded.name), uploaded.getvalue()))


def for_display(df, data_table=False, lang=None, text_ids=True):
    """Copy of a calc output with column (and index) labels in ``lang``.

    ``text_ids`` (data table only) shows tree ids as text, which Arrow needs for mixed
    int/text ids; the Excel export keeps them as they are."""
    if df is None:
        return df
    lang = _lang(lang)
    out = df
    if data_table:      # hidden helper columns (raw unreadable text) are not shown
        out = out[[c for c in out.columns if not str(c).startswith("_")]]
    names = {c: (species_name(c, lang) if c == mc.UNIDENTIFIED_LABEL
                 else label(c, lang, data_table))
             for c in out.columns
             if c == mc.UNIDENTIFIED_LABEL or i18n.catalog(i18n.DEFAULT).get(f"labels.{c}")
             or (" [" in str(c) and str(c).endswith("]"))}
    out = out.rename(columns=names)
    for col in ("species", "species_label"):
        if col in df.columns:
            out[names[col]] = out[names[col]].map(lambda v: species_name(v, lang))
    if data_table:
        # mixed int/text tree ids break Arrow serialisation; condition and species
        # status codes are shown in the interface language
        for bcol in ("live", "true_mangrove"):      # booleans in the interface language
            if bcol in df.columns:
                bn = names.get(bcol, bcol)
                out[bn] = out[bn].map(lambda v: i18n.t("common.yes" if v else "common.no", lang)
                                      if isinstance(v, (bool, np.bool_)) else v).astype(object)
        for idcol in ("tree_id", "tag"):
            if text_ids and idcol in df.columns:
                out[names.get(idcol, idcol)] = out[names.get(idcol, idcol)].map(
                    lambda v: v if pd.isna(v) else str(v)).astype(object)
        if "condition" in df.columns:
            cn = names.get("condition", "condition")
            out[cn] = out[cn].map(lambda v: condition_label(v, lang)
                                  if v in ("live", "dead") else v)
        if "species_status" in df.columns:
            sn = names.get("species_status", "species_status")
            out[sn] = out[sn].map(lambda v: i18n.t(f"status.{v}", lang)
                                  if v in _SPECIES_STATUS else v)
    if out.index.name == "dbh_class":
        out.index = out.index.map(lambda v: dbh_class_label(v, lang))
    if out.index.name and i18n.catalog(i18n.DEFAULT).get(f"labels.{out.index.name}"):
        out.index = out.index.rename(label(out.index.name, lang))
    return out


def dbh_class_label(text, lang=None):
    """DBH class label ("2.5–10") with the decimal separator of ``lang``."""
    return str(text).replace(".", ",") if _lang(lang) == "pt" else str(text)


def _cmap(species, lang):
    """Display name -> colour (colours follow the scientific name, not the language)."""
    cores = species_colors(species)
    return {species_name(e, lang): cores[e] for e in species}


# ---------------------------------------------------------------------------
# GRÁFICOS
# ---------------------------------------------------------------------------
def fig_composicao_ba(res, estilos, tipo="pie", lang=None):
    """Contribuição de cada espécie/condição para a área basal total."""
    lang = _lang(lang)
    d = res["data"]
    val = d[d["dbh"].notna() & (d["dbh"] > 0)].copy()
    cond = val["live"].map(lambda v: condition_label("live" if v else "dead", lang))
    comp_col = i18n.t("chart.component", lang)
    ba_col = label("ba_ha", lang)
    val[comp_col] = val["species_label"].map(lambda v: species_name(v, lang)) \
        + " (" + cond + ")"
    comp = (val.groupby(comp_col)["basal_area_m2"].sum()
               * mc._ft(res["summary"]["plot_area_m2"]))
    comp = comp[comp > 0.001].reset_index()
    comp.columns = [comp_col, ba_col]
    if comp.empty:
        return None
    if tipo == "treemap":
        fig = px.treemap(comp, path=[px.Constant(i18n.t("chart.ba_total", lang)), comp_col],
                         values=ba_col, color_discrete_sequence=estilos["paleta"])
        fig.update_traces(textinfo="label+value+percent root")
    else:
        fig = px.pie(comp, values=ba_col, names=comp_col,
                     hole=0.4, color_discrete_sequence=estilos["paleta"])
        fig.update_traces(textposition="inside", textinfo="percent+label")
    return _layout(fig, estilos, i18n.t("chart.ba_composition", lang))


def fig_ivi(tab, estilos, lang=None):
    """Barras horizontais por espécie: componentes empilhados do IVI ou, sem frequência, densidade e dominância relativas lado a lado."""
    if tab is None or tab.empty:
        return None
    lang = _lang(lang)
    comps = [c for c in ["rel_density", "rel_dominance", "rel_frequency"]
             if c in tab.columns]
    is_ivi = "ivi" in tab.columns
    total_col = label("ivi" if is_ivi else "rel_dominance", lang)
    tab = for_display(tab, lang=lang)
    comps = [label(c, lang) for c in comps]
    sp, comp_name = label("species", lang), i18n.t("chart.component", lang)
    axis_title = i18n.t("chart.axis.ivi" if is_ivi else "chart.axis.relative", lang)
    dfm = tab.melt(id_vars=[sp], value_vars=comps, var_name=comp_name, value_name="value")
    ordem = tab.sort_values(total_col)[sp].tolist()
    fig = px.bar(dfm, y=sp, x="value", color=comp_name, orientation="h",
                 color_discrete_sequence=estilos["paleta"],
                 category_orders={sp: ordem}, labels={"value": axis_title})
    titulo = i18n.t("chart.ivi" if is_ivi else "chart.rel_components", lang)
    fig.update_layout(barmode="stack" if is_ivi else "group", xaxis_title=axis_title)
    return _layout(fig, estilos, titulo)


def fig_phyto_100(tab, estilos, lang=None):
    """Each relative value (DeR%, DoR%, FR%) as one 100% column split by species."""
    if tab is None or tab.empty:
        return None
    lang = _lang(lang)
    comps = [c for c in ["rel_density", "rel_dominance", "rel_frequency"] if c in tab.columns]
    cmap = species_colors(tab["species"].unique())
    fig = go.Figure()
    for _, row in tab.sort_values(comps[-1], ascending=False).iterrows():
        vals = [row[c] for c in comps]
        fig.add_trace(go.Bar(x=[label(c, lang) for c in comps], y=vals, name=species_name(row["species"], lang),
                             marker_color=cmap[row["species"]],
                             text=[num(v, 1, lang) for v in vals], textposition="inside"))
    fig.update_layout(barmode="stack", yaxis_title="%")
    fig.update_yaxes(range=[0, 100], ticksuffix="%")
    return _layout(fig, estilos, i18n.t("chart.phyto_100", lang))


def fig_classes_dap(dens_cl, domi_cl, estilos, metrica="density", lang=None, pct=False):
    """Distribuição por classes de DAP (barras empilhadas por espécie); ``pct=True``:
    cada classe soma 100% (contribuição de cada espécie na classe)."""
    lang = _lang(lang)
    df = dens_cl if metrica == "density" else domi_cl
    if df is None or df.empty:
        return None
    if pct:
        tot = df.sum(axis=1).replace(0, np.nan)
        df = df.div(tot, axis=0).mul(100).fillna(0)
    sp, val = label("species", lang), "value"
    dfp = df.reset_index().melt(id_vars="dbh_class", var_name=sp, value_name=val)
    dfp[sp] = dfp[sp].map(lambda v: species_name(v, lang))
    dfp["dbh_class"] = dfp["dbh_class"].astype(str).map(lambda v: dbh_class_label(v, lang))
    cmap = _cmap(df.columns, lang)
    cls = label("dbh_class", lang)
    fig = px.bar(dfp, x="dbh_class", y=val, color=sp, color_discrete_map=cmap,
                 barmode="stack", labels={"dbh_class": cls, val: label("value", lang)})
    ylab = label("density_ha" if metrica == "density" else "ba_ha", lang)
    if pct:
        ylab = i18n.t("temporal.chart.stack100", lang) + " · " + ylab
        fig.update_yaxes(range=[0, 100], ticksuffix="%")
    fig.update_layout(xaxis_title=cls, yaxis_title=ylab)
    name = i18n.t("metric.density" if metrica == "density" else "metric.basal_area", lang)
    return _layout(fig, estilos, i18n.t("chart.dbh_classes", lang, metric=name))


def fig_distribuicao_diametrica(dist_tab, estilos, lang=None):
    """Distribuição por classes diamétricas regulares."""
    if dist_tab is None or dist_tab.empty:
        return None
    lang = _lang(lang)
    fig = px.bar(dist_tab, x="class_cm", y="density_ha",
                 color_discrete_sequence=[mc.GENUS_COLORS["Rhizophora"]],
                 labels={"class_cm": label("dbh_class", lang),
                         "density_ha": label("density_ha", lang)})
    fig.update_traces(marker_line_width=0)
    fig.update_layout(xaxis_title=label("dbh_class", lang),
                      yaxis_title=label("density_ha", lang))
    return _layout(fig, estilos, i18n.t("chart.diameter_dist", lang))


def fig_hist_dap(res, estilos, lang=None):
    lang = _lang(lang)
    d = res["data"]
    dd = d[d["live"] & d["dbh"].notna() & (d["dbh"] > 0)].copy()
    if dd.empty:
        return None
    sp = label("species", lang)
    dd[sp] = dd["species_label"].map(lambda v: species_name(v, lang))
    cmap = _cmap(dd["species_label"].unique(), lang)
    fig = px.histogram(dd, x="dbh", color=sp, barmode="stack",
                       color_discrete_map=cmap, nbins=25, labels={"dbh": label("dbh", lang),
                                         "count": i18n.t("chart.count", lang)})
    # plotly names the histogram's y value "count" in the hover text
    fig.for_each_trace(lambda tr: tr.update(hovertemplate=tr.hovertemplate.replace(
        "count=", i18n.t("chart.count", lang) + "=")))
    fig.update_layout(xaxis_title=label("dbh", lang),
                      yaxis_title=i18n.t("chart.n_stems", lang), bargap=0.1)
    return _layout(fig, estilos, i18n.t("chart.dbh_hist", lang))


def fig_altura_dap(res, estilos, lang=None, species=None):
    """Dispersão altura x DAP com regressão linear por espécie. ``species``: lista de
    espécies (nomes científicos) a mostrar; None = todas."""
    lang = _lang(lang)
    d = res["data"]
    dd = d[d["live"]].dropna(subset=["height", "dbh"])     # live stems only
    dd = dd[(dd["dbh"] > 0) & (dd["height"] > 0)].copy()
    if species is not None:
        dd = dd[dd["species_label"].isin(species)]
    if len(dd) < 2:
        return None, []
    sp = label("species", lang)
    dd[sp] = dd["species_label"].map(lambda v: species_name(v, lang))
    cmap = _cmap(dd["species_label"].unique(), lang)
    fig = px.scatter(dd, x="dbh", y="height", color=sp, color_discrete_map=cmap,
                     labels={"dbh": label("dbh", lang), "height": label("height", lang)})
    detalhes = []
    for esp in dd[sp].unique():
        sub = dd[dd[sp] == esp]
        if len(sub) > 1:
            m = np.polyfit(sub["dbh"], sub["height"], 1)
            xr = np.linspace(sub["dbh"].min(), sub["dbh"].max(), 50)
            yr = np.poly1d(m)(xr)
            r2 = np.corrcoef(sub["height"], np.poly1d(m)(sub["dbh"]))[0, 1] ** 2
            fig.add_trace(go.Scatter(x=xr, y=yr, mode="lines",
                          name=i18n.t("chart.regression", lang, species=esp),
                          line=dict(color=cmap.get(esp, "#555"), dash="dash")))
            detalhes.append({sp: esp,
                             i18n.t("chart.equation", lang):
                                 f"y = {_num(m[0], 2, lang)}x + {_num(m[1], 2, lang)}",
                             "R²": _num(r2, 3, lang)})
    fig.update_layout(xaxis_title=label("dbh", lang), yaxis_title=label("height", lang))
    return _layout(fig, estilos, i18n.t("chart.height_dbh", lang)), detalhes


PROFILE_KINDS = ("bubbles", "stems", "strata", "violin")


def fig_perfil_vertical(res, estilos, lang=None, kind="bubbles", strata_width=1.0):
    """
    Perfil/estrutura vertical do bosque (troncos vivos com altura). ``kind``:
    "stems"   cada tronco como uma haste vertical, ordenada pela altura;
    "strata"  número de troncos por classe de altura, empilhado por espécie;
    "violin"  distribuição das alturas de cada espécie;
    "bubbles" cada tronco como um círculo na sua altura, tamanho proporcional ao DAP.
    """
    lang = _lang(lang)
    d = res["data"]
    dd = d[d["live"] & (d["height"] > 0) & d["dbh"].notna() & (d["dbh"] > 0)].copy()
    if dd.empty:
        return None
    if kind != "bubbles":
        return _perfil_alt(res, dd, estilos, lang, kind, strata_width)
    dd = dd.sort_values("height")
    dd["x"] = np.arange(len(dd))
    cmap = _cmap(dd["species_label"].unique(), lang)
    fig = go.Figure()
    hover = (i18n.t("chart.hover_height", lang) + "<br>" + i18n.t("chart.hover_dbh", lang))
    for raw in dd["species_label"].unique():
        esp = species_name(raw, lang)
        sub = dd[dd["species_label"] == raw]
        fig.add_trace(go.Scatter(
            x=sub["x"], y=sub["height"], mode="markers", name=esp,
            marker=dict(size=np.clip(sub["dbh"], 3, 40),
                        color=cmap.get(esp, "#555"),
                        line=dict(width=0.5, color="white"), sizemode="diameter"),
            customdata=np.stack([sub["dbh"]], axis=-1),
            hovertemplate=hover + "<extra>" + esp + "</extra>"))
    # linha do dossel médio
    hd = res["summary"].get("canopy_height_m", 0)
    if hd:
        fig.add_hline(y=hd, line_dash="dot", line_color="gray",
                      annotation_text=i18n.t("chart.canopy_mean", lang,
                                             h=_num(hd, 1, lang)))
    fig.update_layout(xaxis_title=i18n.t("chart.trees_by_height", lang),
                      yaxis_title=label("height", lang),
                      xaxis_showticklabels=False)
    # size legend: reference circles of 5, 10 and 20 cm DBH in the lower right corner,
    # which is always empty (the trees are sorted by height)
    n = len(dd)
    ref = [5, 10, 20]
    ytop = float(dd["height"].min()) + 0.12 * float(dd["height"].max() - dd["height"].min() or 1)
    xs = [n * 0.80 + i * max(n * 0.06, 2) for i in range(len(ref))]
    fig.add_trace(go.Scatter(x=xs, y=[ytop] * len(ref), mode="markers+text",
                             marker=dict(size=ref, sizemode="diameter", color="rgba(0,0,0,0)",
                                         line=dict(color="#5F726A", width=1.2)),
                             text=[f"{v} cm" for v in ref], textposition="bottom center",
                             textfont=dict(size=9, color="#5F726A"), hoverinfo="skip",
                             showlegend=False))
    fig.add_annotation(x=xs[len(xs) // 2], y=ytop, yshift=26, text=i18n.t("chart.bubble_is_dbh", lang),
                       showarrow=False, font=dict(size=10, color="#5F726A"))
    fig.update_xaxes(range=[-2, max(n, xs[-1]) + 3])
    return _layout(fig, estilos, i18n.t("chart.vertical_profile", lang))


def _perfil_alt(res, dd, estilos, lang, kind, strata_width):
    cmap = _cmap(dd["species_label"].unique(), lang)
    fig = go.Figure()
    hd = res["summary"].get("canopy_height_m", 0)
    if kind == "stems":
        dd = dd.sort_values("height").reset_index(drop=True)
        dd["x"] = np.arange(len(dd))
        for raw in dd["species_label"].unique():
            esp = species_name(raw, lang)
            sub = dd[dd["species_label"] == raw]
            xs, ys = [], []
            for x, h in zip(sub["x"], sub["height"]):
                xs += [x, x, None]
                ys += [0, h, None]
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name=esp,
                                     line=dict(color=cmap.get(esp, "#555"), width=3)))
        fig.update_layout(xaxis_title=i18n.t("chart.trees_by_height", lang),
                          yaxis_title=label("height", lang), xaxis_showticklabels=False)
    elif kind == "strata":
        w = float(strata_width)
        top = np.ceil(dd["height"].max() / w) * w
        bins = np.arange(0, top + w, w)
        dd["_c"] = pd.cut(dd["height"], bins=bins, right=False)
        for raw in dd["species_label"].unique():
            esp = species_name(raw, lang)
            cnt = dd[dd["species_label"] == raw].groupby("_c", observed=False).size()
            fig.add_trace(go.Bar(y=[f"{_num(iv.left, 1, lang)} a {_num(iv.right, 1, lang)}" for iv in cnt.index],
                                 x=cnt.values, orientation="h", name=esp,
                                 marker_color=cmap.get(esp, "#555")))
        fig.update_layout(barmode="stack", xaxis_title=i18n.t("chart.n_stems", lang),
                          yaxis_title=i18n.t("chart.height_class", lang))
        return _layout(fig, estilos, i18n.t("chart.vertical_profile", lang))
    else:  # violin: only species with at least two heights
        for raw in dd["species_label"].unique():
            esp = species_name(raw, lang)
            sub = dd[dd["species_label"] == raw]
            if sub["height"].notna().sum() < 2:
                continue
            fig.add_trace(go.Violin(x=[esp] * len(sub), y=sub["height"], name=esp, box_visible=True,
                                    meanline_visible=True, line_color=cmap.get(esp, "#555"),
                                    points="all", pointpos=0, jitter=0.3, marker_size=3))
        fig.update_layout(yaxis_title=label("height", lang), showlegend=False)
    if hd:
        fig.add_hline(y=hd, line_dash="dot", line_color="gray",
                      annotation_text=i18n.t("chart.canopy_mean", lang, h=_num(hd, 1, lang)))
    return _layout(fig, estilos, i18n.t("chart.vertical_profile", lang))


# ---------------------------------------------------------------------------
# COMPARATIVO / TEMPORAL (múltiplas parcelas)
# Tables keep internal (language independent) column names: plot, year, density_live_ha,
# ... ; ``for_display`` / ``label`` give the text in the current language.
# ---------------------------------------------------------------------------
NON_METRIC_COLUMNS = mc.NON_METRIC_COLUMNS
metric_columns = mc.metric_columns


def fig_dbh_height_plots(df_param, estilos, lang=None):
    """Each plot as a point: mean DBH (x) against mean height (y), with ±SD of height."""
    lang = _lang(lang)
    fig = go.Figure()
    cores = estilos["paleta"]
    for i, (_, row) in enumerate(df_param.iterrows()):
        fig.add_trace(go.Scatter(
            x=[row["mean_dbh_cm"]], y=[row["height_mean_m"]], mode="markers+text",
            text=[str(row["plot"])], textposition="top center", name=str(row["plot"]),
            marker=dict(size=13, color=cores[i % len(cores)]),
            error_y=dict(type="data", array=[row.get("height_sd_m", 0) or 0], visible="height_sd_m" in row)))
    fig.update_layout(showlegend=False, xaxis_title=label("mean_dbh_cm", lang),
                      yaxis_title=label("height_mean_m", lang))
    return _layout(fig, estilos, i18n.t("chart.dbh_height_plots", lang))


def fig_jimenez(df, estilos, lang=None, text="plot", group=None, log=False):
    """Live stem density (y) against mean DBH (x) of each plot (or plot and year), over the
    theoretical curve of Jimenez et al. (1985). ``df`` needs mean_dbh_cm and density_live_ha;
    ``text`` is the label column and ``group`` the column that sets the colour (default: text)."""
    lang = _lang(lang)
    d = df[(df["mean_dbh_cm"] > 0) & (df["density_live_ha"] > 0)]
    if d.empty:
        return None
    group = group or text
    lo, hi = float(d["mean_dbh_cm"].min()), float(d["mean_dbh_cm"].max())
    x0 = max(1.0, lo * 0.7)
    x1 = max(hi * 1.15, x0 + 1)
    xs = np.geomspace(x0, x1, 120) if log else np.linspace(x0, x1, 120)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=mc.jimenez_density_ha(xs), mode="lines", name=i18n.t("chart.jimenez_curve", lang),
                             line=dict(color="#5F726A", width=1.6), hoverinfo="skip"))
    cores = estilos["paleta"]
    for i, (g, sub) in enumerate(d.groupby(group, sort=False)):
        fig.add_trace(go.Scatter(
            x=sub["mean_dbh_cm"], y=sub["density_live_ha"], mode="markers+text",
            text=sub[text].astype(str), textposition="top center", name=str(g),
            marker=dict(size=11, color=cores[i % len(cores)])))
    fig.update_layout(xaxis_title=label("mean_dbh_cm", lang), yaxis_title=label("density_live_ha", lang))
    if log:
        fig.update_xaxes(type="log")
        fig.update_yaxes(type="log")
    return _layout(fig, estilos, i18n.t("chart.jimenez", lang))


def show_jimenez(container, df, estilos, key, lang=None, text="plot", group=None):
    """Subheader, log option, chart and note of the Jimenez et al. (1985) comparison."""
    import streamlit as st
    T = i18n.t
    container.subheader(T("chart.jimenez_title", lang))
    log = container.checkbox(T("chart.jimenez_log", lang), value=False, key=f"jim_log_{key}")
    fig = fig_jimenez(df, estilos, lang, text, group, log)
    if fig is None:
        container.info(T("chart.jimenez_nodata", lang))
        return
    show(container, fig, key, estilos)
    container.caption(T("chart.jimenez_note", lang))


PER_STEM = {"mean_dbh_cm": "dbh", "height_mean_m": "height"}


def fig_plot_distribution(resultados, estilos, param, kind="box", lang=None):
    """Distribution of DBH or height of the live stems of each plot (box or violin)."""
    lang = _lang(lang)
    col = PER_STEM[param]
    frames = []
    for r in resultados:
        d = r["data"]
        dd = d[d["live"] & (d["dbh"] > 0)][[col]].dropna()
        dd = dd[dd[col] > 0]
        dd["plot"] = r["plot_name"]
        frames.append(dd)
    cons = pd.concat(frames, ignore_index=True)
    f = px.violin if kind == "violin" else px.box
    extra = dict(box=True, points=False) if kind == "violin" else {}
    fig = f(cons, x="plot", y=col, color="plot", color_discrete_sequence=estilos["paleta"],
            labels={"plot": label("plot", lang), col: label(col, lang)}, **extra)
    # one shape per plot, centred on its name (no side-by-side offset)
    fig.update_layout(showlegend=False, yaxis_title=label(col, lang),
                      violinmode="overlay", boxmode="overlay")
    return _layout(fig, estilos, label(col, lang))


def fig_free_compare(df_param, estilos, mode, a, b=None, lang=None, kind="bar", resultados=None,
                     second_style="lines+markers"):
    if mode == "single" and kind in ("box", "violin") and a in PER_STEM and resultados:
        return fig_plot_distribution(resultados, estilos, a, kind, lang)
    if mode == "single" and kind == "line":
        lang = _lang(lang)
        fig = go.Figure(go.Scatter(x=df_param["plot"], y=df_param[a], mode="lines+markers",
                                   line=dict(color=estilos["paleta"][0])))
        fig.update_layout(xaxis_title=label("plot", lang), yaxis_title=label(a, lang))
        return _layout(fig, estilos, label(a, lang))
    return _fig_free_compare(df_param, estilos, mode, a, b, lang, second_style)


def _fig_free_compare(df_param, estilos, mode, a, b=None, lang=None, second_style="lines+markers"):
    """Free comparison of the plots: ``mode`` "single" (bars of ``a``), "dual" (bars of
    ``a`` on the left axis, line of ``b`` on the right) or "xy" (``a`` against ``b``)."""
    from plotly.subplots import make_subplots
    lang = _lang(lang)
    cores = estilos["paleta"]
    if mode == "xy" and b:
        fig = go.Figure(go.Scatter(x=df_param[a], y=df_param[b], mode="markers+text",
                                   text=df_param["plot"].astype(str), textposition="top center",
                                   marker=dict(size=12, color=cores[0])))
        fig.update_layout(xaxis_title=label(a, lang), yaxis_title=label(b, lang))
        return _layout(fig, estilos, f"{label(a, lang)} × {label(b, lang)}")
    if mode == "dual" and b:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=df_param["plot"], y=df_param[a], name=label(a, lang),
                             marker_color=cores[0]), secondary_y=False)
        fig.add_trace(go.Scatter(x=df_param["plot"], y=df_param[b], name=label(b, lang),
                                 mode=second_style, line=dict(color="#4C78A8", width=2.5),
                                 marker=dict(size=11, symbol="diamond", color="#4C78A8")),
                      secondary_y=True)
        fig.update_yaxes(title_text=label(a, lang), secondary_y=False)
        fig.update_yaxes(title_text=label(b, lang), secondary_y=True, rangemode="tozero")
        fig.update_xaxes(title_text=label("plot", lang))
        return _layout(fig, estilos, f"{label(a, lang)} · {label(b, lang)}")
    return fig_comparativo_barras(df_param, estilos, a, label(a, lang), lang)


def fig_species_plots_stacked(df_long, estilos, ylabel, chart="stack", show_values=False, lang=None):
    """Species per plot in one column: live solid, dead hatched; ``chart="stack100"``
    shows every part as % of the plot's total."""
    if df_long is None or df_long.empty:
        return None
    lang = _lang(lang)
    df = df_long.groupby(["plot", "species", "condition"], as_index=False)["value"].sum()
    tot = df.groupby("plot")["value"].transform("sum")
    df["_v"] = np.where(tot > 0, 100 * df["value"] / tot, 0.0) if chart == "stack100" else df["value"]
    plots = list(dict.fromkeys(df_long["plot"]))
    cores = species_colors(df["species"].unique())
    fig = go.Figure()
    for cond, pattern in (("live", ""), ("dead", "/")):
        for sp in sorted(df["species"].unique(), key=str):
            sub = df[(df["species"] == sp) & (df["condition"] == cond)].set_index("plot").reindex(plots)
            if sub["_v"].fillna(0).sum() == 0:
                continue
            cor = cores[sp]
            vals = sub["_v"].fillna(0)
            fig.add_trace(go.Bar(
                x=plots, y=vals, name=f"{species_name(sp, lang)} · {i18n.t('condition.' + cond, lang)}",
                legendrank=10 * sorted(df["species"].unique(), key=str).index(sp) + (0 if cond == "live" else 1),
                text=[num(v, 0 if chart == "stack100" else 2, lang) if v else "" for v in vals]
                if show_values else None, textposition="inside",
                marker=dict(color=cor if cond == "live" else "white", line=dict(color=cor, width=1.2),
                            pattern=dict(shape=pattern, fgcolor=cor, size=6, solidity=0.35))))
    fig.update_layout(barmode="stack", xaxis_title=label("plot", lang),
                      yaxis_title=(i18n.t("temporal.chart.stack100", lang) + " · " + ylabel)
                      if chart == "stack100" else ylabel)
    if chart == "stack100":
        fig.update_yaxes(range=[0, 100], ticksuffix="%")
    fig = _layout(fig, estilos, i18n.t("chart.species_by_plot", lang))
    n_sp = df["species"].nunique()
    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.18, x=0, xanchor="left",
                                  entrywidth=0.5, entrywidthmode="fraction", font=dict(size=10),
                                  traceorder="normal"),
                      margin=dict(b=40 + 22 * n_sp), height=380 + 22 * n_sp)
    return fig


def fig_comparativo_barras(df_param, estilos, y, titulo, lang=None):
    lang = _lang(lang)
    fig = px.bar(df_param, x="plot", y=y, color="plot",
                 color_discrete_sequence=estilos["paleta"],
                 labels={"plot": label("plot", lang), y: label(y, lang)})
    fig.update_layout(showlegend=False)
    return _layout(fig, estilos, titulo)


def fig_box_dap(lista_res, estilos, lang=None):
    lang = _lang(lang)
    frames = []
    for r in lista_res:
        dd = r["data"][r["data"]["live"] & (r["data"]["dbh"] > 0)][["dbh"]].copy()
        dd["plot"] = r["plot_name"]
        frames.append(dd)
    if not frames:
        return None
    cons = pd.concat(frames, ignore_index=True)
    fig = px.box(cons, x="plot", y="dbh", color="plot",
                 color_discrete_sequence=estilos["paleta"],
                 labels={"plot": label("plot", lang), "dbh": label("dbh", lang)})
    fig.update_layout(showlegend=False, yaxis_title=label("dbh", lang))
    return _layout(fig, estilos, i18n.t("chart.dbh_by_plot", lang))


def fig_radar(df_param, estilos, metricas, lang=None):
    """Radar comparando parcelas em várias métricas (normalizadas 0-1)."""
    lang = _lang(lang)
    dfn = df_param.copy()
    for m in metricas:
        mx = dfn[m].max()
        dfn[m] = dfn[m] / mx if mx else 0
    nomes = [label(m, lang) for m in metricas]
    fig = go.Figure()
    for _, row in dfn.iterrows():
        fig.add_trace(go.Scatterpolar(r=[row[m] for m in metricas] + [row[metricas[0]]],
                                      theta=nomes + [nomes[0]],
                                      fill="toself", name=str(row["plot"])))
    # the polar domain leaves room around the plot for the (long) axis labels
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1], showticklabels=False),
                                 domain=dict(x=[0.24, 0.76], y=[0.08, 0.88])))
    return _layout(fig, estilos, i18n.t("chart.radar", lang))


def fig_temporal(df_serie, estilos, y, titulo=None, lang=None):
    lang = _lang(lang)
    fig = px.line(df_serie, x="year", y=y, markers=True,
                  color_discrete_sequence=estilos["paleta"],
                  labels={"year": label("year", lang), y: label(y, lang)})
    return _layout(fig, estilos, titulo or label(y, lang))


def fig_temporal_multi(df_serie, estilos, series_esq, series_dir, lang=None):
    """
    Série temporal com DOIS eixos y independentes:
    'series_esq' (lista) no eixo esquerdo, 'series_dir' (lista) no direito.
    """
    from plotly.subplots import make_subplots
    lang = _lang(lang)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    cores = estilos["paleta"]
    i = 0
    for col in series_esq:
        fig.add_trace(go.Scatter(x=df_serie["year"], y=df_serie[col], name=label(col, lang),
                                 mode="lines+markers",
                                 line=dict(color=cores[i % len(cores)])),
                      secondary_y=False)
        i += 1
    for col in series_dir:
        fig.add_trace(go.Scatter(x=df_serie["year"], y=df_serie[col],
                                 name=i18n.t("chart.right_axis", lang, name=label(col, lang)),
                                 mode="lines+markers",
                                 line=dict(color=cores[i % len(cores)], dash="dot")),
                      secondary_y=True)
        i += 1
    fig.update_xaxes(title_text=label("year", lang))
    fig.update_yaxes(title_text=" · ".join(label(c, lang) for c in series_esq),
                     secondary_y=False)
    fig.update_yaxes(title_text=" · ".join(label(c, lang) for c in series_dir),
                     secondary_y=True)
    return _layout(fig, estilos, i18n.t("chart.temporal_dual", lang))


def serie_por_especie(resultados):
    """
    Série temporal POR ESPÉCIE (troncos vivos). Espera resultados com res['year'].
    Colunas (nomes internos): year, species, density_ha, ba_ha, mean_dbh_cm,
    height_mean_m, ba_contribution_pct.
    """
    linhas = []
    for res in resultados:
        ano = res.get("year")
        d = res["data"]
        d = d[d["live"] & d["dbh"].notna() & (d["dbh"] > 0)]
        ft = mc._ft(res["summary"]["plot_area_m2"])
        ba_total = d["basal_area_m2"].sum() * ft
        for esp, sub in d.groupby("species_label"):
            dens = len(sub) * ft
            ba = sub["basal_area_m2"].sum() * ft
            dap_q = float(np.sqrt((ba * 12732.39) / dens)) if dens > 0 else 0.0
            alt = sub["height"].dropna()
            linhas.append({
                "year": ano, "species": esp, "_sheet": res.get("plot_name"),
                "density_ha": dens,
                "ba_ha": ba,
                "mean_dbh_cm": dap_q,
                "height_mean_m": float(alt.mean()) if not alt.empty else np.nan,
                "ba_contribution_pct": (ba / ba_total * 100) if ba_total else 0.0,
            })
    out = pd.DataFrame(linhas)
    if out.empty:
        return out
    # Sheets that share a year are averaged, as the main series is. A species that is
    # absent from one of those sheets counts as zero there (not as missing), so the
    # mean is over all the sheets of the year; DBH and height stay undefined.
    extra = []
    for ano, g in out.groupby("year"):
        sheets = list(dict.fromkeys(g["_sheet"]))
        if len(sheets) < 2:
            continue
        have = set(zip(g["_sheet"], g["species"]))
        for esp in g["species"].unique():
            for sh in sheets:
                if (sh, esp) not in have:
                    extra.append({"year": ano, "species": esp, "_sheet": sh,
                                  "density_ha": 0.0, "ba_ha": 0.0, "mean_dbh_cm": np.nan,
                                  "height_mean_m": np.nan, "ba_contribution_pct": 0.0})
    if extra:
        out = pd.concat([out, pd.DataFrame(extra)], ignore_index=True)
    return (out.drop(columns="_sheet").groupby(["year", "species"], as_index=False, sort=True)
            .mean(numeric_only=True))


def fig_serie_especie(df_esp, estilos, metrica_col, tipo="line", lang=None):
    """Evolução de uma métrica por espécie ao longo dos anos (linha ou área empilhada)."""
    if df_esp is None or df_esp.empty:
        return None
    lang = _lang(lang)
    df = df_esp.sort_values("year").copy()
    sp = label("species", lang)
    df[sp] = df["species"].map(lambda v: species_name(v, lang))
    cmap = _cmap(df_esp["species"].unique(), lang)
    labs = {"year": label("year", lang), metrica_col: label(metrica_col, lang)}
    if tipo == "area":
        fig = px.area(df, x="year", y=metrica_col, color=sp, color_discrete_map=cmap,
                      labels=labs)
    else:
        fig = px.line(df, x="year", y=metrica_col, color=sp, markers=True,
                      color_discrete_map=cmap, labels=labs)
    fig.update_layout(yaxis_title=label(metrica_col, lang), xaxis_title=label("year", lang))
    return _layout(fig, estilos,
                   i18n.t("chart.by_species", lang, metric=label(metrica_col, lang)))


def dados_especies_parcelas(resultados, metrica="area"):
    """
    DataFrame longo: contribuição de cada espécie (viva/morta) por parcela.
    metrica: 'area' (m²/ha) ou 'densidade' (troncos/ha). Colunas internas: plot,
    species, condition ('live'/'dead'), value.
    """
    linhas = []
    for res in resultados:
        d = res["data"]
        d = d[d["dbh"].notna() & (d["dbh"] > 0)]
        ft = mc._ft(res["summary"]["plot_area_m2"])
        for (esp, viva), sub in d.groupby(["species_label", "live"]):
            valor = sub["basal_area_m2"].sum() * ft if metrica == "area" else len(sub) * ft
            linhas.append({"plot": res["plot_name"], "species": esp,
                           "condition": "live" if viva else "dead", "value": valor})
    return pd.DataFrame(linhas, columns=["plot", "species", "condition", "value"])


def fig_especies_parcelas(df_long, estilos, ylabel, condicao="both", lang=None):
    """Barras empilhadas: contribuição por espécie e parcela (hachura = morta)."""
    if df_long is None or df_long.empty:
        return None
    lang = _lang(lang)
    df = df_long.copy()
    if condicao != "both":
        df = df[df["condition"] == condicao]
    if df.empty:
        return None
    sp, cond, plot = label("species", lang), label("condition", lang), label("plot", lang)
    df[sp] = df["species"].map(lambda v: species_name(v, lang))
    df[cond] = df["condition"].map(lambda v: condition_label(v, lang))
    cmap = _cmap(df_long["species"].unique(), lang)
    kwargs = dict(x="plot", y="value", color=sp, color_discrete_map=cmap, barmode="stack",
                  labels={"plot": plot, "value": ylabel})
    if condicao == "both":
        kwargs["pattern_shape"] = cond
        kwargs["pattern_shape_map"] = {condition_label("live", lang): "",
                                       condition_label("dead", lang): "/"}
    fig = px.bar(df, **kwargs)
    fig.update_layout(yaxis_title=ylabel, xaxis_title=plot)
    return _layout(fig, estilos, i18n.t("chart.species_by_plot", lang))


# ---------------------------------------------------------------------------
# EXPORTAÇÕES
# ---------------------------------------------------------------------------
_SUMMARY_KEYS = ("n_live", "n_live_trees", "density_live_ha", "density_dead_ha",
                 "density_total_ha", "ba_live_ha", "ba_dead_ha", "ba_total_ha", "mean_dbh_cm",
                 "height_mean_m", "height_sd_m", "height_min_m", "height_max_m",
                 "canopy_height_m",
                 "mortality_stems_pct", "mortality_ba_pct", "n_species_live",
                 "stems_per_tree")


def resumo_para_df(res, lang=None):
    lang = _lang(lang)
    r = res["summary"]
    # integers stay integers (counts); the value column holds mixed types on purpose
    linhas = [{label("parameter", lang): label(k, lang),
               label("value", lang): (int(r[k]) if isinstance(r[k], (int, np.integer))
                                      else round(r[k], 3))}
              for k in _SUMMARY_KEYS if k in r]
    for key, lab in (("dbh_gt_2.5", "complexity_2_5"), ("dbh_gt_10", "complexity_10")):
        if key in res.get("complexity", {}):
            linhas.append({label("parameter", lang): label(lab, lang),
                           label("value", lang): round(res["complexity"][key]["ci"], 3)})
    pcol, vcol = label("parameter", lang), label("value", lang)
    # build the value column as object, or pandas would turn the counts into floats
    return pd.DataFrame({pcol: [x[pcol] for x in linhas],
                         vcol: pd.Series([x[vcol] for x in linhas], dtype=object)})


def tabela_por_especie(res, lang=None):
    """Densidade e área basal viva/morta POR ESPÉCIE (para exportações)."""
    lang = _lang(lang)
    d = res["data"]
    d = d[d["dbh"].notna() & (d["dbh"] > 0)]
    ft = mc._ft(res["summary"]["plot_area_m2"])
    L = lambda k: label(k, lang)
    linhas = []
    for esp, sub in d.groupby("species_label"):
        v = sub[sub["live"]]
        m = sub[~sub["live"]]
        dv = len(v) * ft
        linhas.append({
            L("species"): species_name(esp, lang),
            L("n_live_stems"): int(len(v)),
            L("n_dead_stems"): int(len(m)),
            L("density_live_ha"): dv,
            L("density_dead_ha"): len(m) * ft,
            L("ba_live_ha"): v["basal_area_m2"].sum() * ft,
            L("ba_dead_ha"): m["basal_area_m2"].sum() * ft,
            L("mean_dbh_live_cm"): mc.quadratic_mean_dbh(v["basal_area_m2"].sum() * ft, dv),
        })
    tab = pd.DataFrame(linhas)
    if not tab.empty:
        tab = tab.sort_values(L("ba_live_ha"), ascending=False).reset_index(drop=True)
    return tab


def species_shares(res, base="density"):
    """Contribution (%) of each species to the live and the dead total of ``base``
    ("density" or "ba"). Returns {(species_label, "live"|"dead"): percent}."""
    d = res["data"]
    d = d[d["dbh"].notna() & (d["dbh"] > 0)]
    out = {}
    for cond, part in (("live", d[d["live"]]), ("dead", d[~d["live"]])):
        val = (part.groupby("species_label").size() if base == "density"
               else part.groupby("species_label")["basal_area_m2"].sum())
        tot = float(val.sum())
        for sp, v in val.items():
            out[(sp, cond)] = 100.0 * float(v) / tot if tot > 0 else 0.0
    return out


def share_column(species, cond, base, lang=None):
    """Column name of a species contribution, e.g. "% dens. viva - A. schaueriana"."""
    return i18n.t(f"labels.share_{base}_{cond}", _lang(lang), species=species_name(species, lang))


def validation_banner(issues_by_unit, lang=None):
    """One line above the tabs; the full data check is in its own tab."""
    import streamlit as st
    lang = _lang(lang)
    all_issues = [i for v in issues_by_unit.values() for i in v]
    n_err, n_warn = issues_counts(all_issues)
    if not all_issues:
        st.caption(i18n.t("panel.banner_ok", lang))
    else:
        icon_note(st, "verificacao", i18n.t("panel.banner", lang, errors=n_err, warnings=n_warn))


def to_excel_bytes(res, lang=None):
    """Gera um .xlsx com as tabelas calculadas (layout inspirado na planilha base)."""
    lang = _lang(lang)
    S = lambda k: i18n.t(f"sheet.{k}", lang)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xls:
        resumo_para_df(res, lang).to_excel(xls, sheet_name=S("summary"), index=False)
        te = tabela_por_especie(res, lang)
        if te is not None and not te.empty:
            te.round(3).to_excel(xls, sheet_name=S("by_species"), index=False)
        if res["importance"] is not None and not res["importance"].empty:
            for_display(res["importance"], lang=lang).round(3).to_excel(
                xls, sheet_name=S("ivi"), index=False)
        if res["dbh_density"] is not None and not res["dbh_density"].empty:
            for_display(res["dbh_density"], lang=lang).round(2).to_excel(
                xls, sheet_name=S("density_classes"))
        if res["dbh_ba"] is not None and not res["dbh_ba"].empty:
            for_display(res["dbh_ba"], lang=lang).round(4).to_excel(
                xls, sheet_name=S("dominance_classes"))
        for_display(res["data"], data_table=True, lang=lang, text_ids=False).to_excel(
            xls, sheet_name=S("data"), index=False)
        issues_frame_by_unit({"": res.get("issues", [])}, lang=lang).to_excel(
            xls, sheet_name=S("issues"), index=False)
    buf.seek(0)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# REGIÃO, TABELA DE ESPÉCIES E VERIFICAÇÃO DOS DADOS (interface)
# Every text comes from the catalogs (validation.*, issue.*, panel.*).
# ---------------------------------------------------------------------------
ISSUE_COLUMNS = ("kind", "severity", "source_row", "tree_id", "detail", "action")
MISSING_CONDITION_CHOICES = ("exclude", "live", "dead")
SPECIES_REQUIRED_COLUMNS = ["code", "scientific_name", "genus", "aliases",
                            "regions", "true_mangrove"]


def issue_kind_label(kind, lang=None):
    return i18n.t(f"validation.kind.{kind}", _lang(lang))


def severity_label(severity, lang=None):
    return i18n.t(f"validation.severity.{severity}", _lang(lang))


def issue_column_label(col, lang=None):
    return i18n.t(f"issue.col.{col}", _lang(lang))


def _issue_text(issue, lang, describe_fn, plain):
    """Catalog text of an issue in ``lang``. An issue built by hand (no ``params``)
    whose catalog text has unfilled placeholders keeps its own ``plain`` text."""
    text = describe_fn(issue, lang)
    if text.startswith("validation.") or ("{" in text and not issue.params):
        return plain
    return text


def issues_display_frame(issues, unit_col=None, unit_label=None, lang=None):
    """Issues as a table with labels in ``lang``.

    ``unit_label`` is a column name (or a tuple of names) for the sheet/plot/year the
    issues belong to; ``unit_col`` is the matching value (or tuple of values).
    """
    lang = _lang(lang)
    f = issues_to_frame(issues).copy()
    f["kind"] = f["kind"].map(lambda k: issue_kind_label(k, lang))
    f["severity"] = f["severity"].map(lambda k: severity_label(k, lang))
    if issues:
        f["detail"] = [_issue_text(i, lang, describe, i.detail) for i in issues]
        f["action"] = [_issue_text(i, lang, describe_action, i.action) if i.action else ""
                       for i in issues]
    f = f.astype(object).where(f.notna(), "")
    f = f.rename(columns={c: issue_column_label(c, lang) for c in ISSUE_COLUMNS})
    if unit_label is not None:
        labels = (unit_label,) if isinstance(unit_label, str) else tuple(unit_label)
        values = unit_col if isinstance(unit_col, tuple) else (unit_col,)
        for pos, (lab, val) in enumerate(zip(labels, values)):
            f.insert(pos, lab, val)
    return f


def issues_frame_by_unit(issues_by_unit, unit_label=None, lang=None):
    """All issues in one display table, the single format used by the panel and by
    every Excel/PDF export. ``unit_label`` (a name or a tuple of names, matching
    the keys of ``issues_by_unit``) adds the sheet/plot/year column(s)."""
    frames = [issues_display_frame(v, name, unit_label, lang)
              for name, v in issues_by_unit.items() if v]
    if not frames:
        empty = issues_display_frame([], lang=lang)
        if unit_label is not None:
            labels = (unit_label,) if isinstance(unit_label, str) else tuple(unit_label)
            for pos, lab in enumerate(labels):
                empty.insert(pos, lab, [])
        return empty
    return pd.concat(frames, ignore_index=True)


def issues_counts(issues):
    """(n_errors, n_warnings)."""
    return (sum(i.severity == "error" for i in issues),
            sum(i.severity == "warning" for i in issues))


def validation_panel(issues_by_unit, unit_label=None, key="missing_cond", lang=None):
    """Render the data-check panel and return ``missing_condition``.

    ``issues_by_unit`` maps a sheet/plot/year name to its list of ``Issue``; with
    ``unit_label`` set, the table gets that extra column. The radio for stems with
    DBH but no condition appears only when such an issue exists.
    """
    import streamlit as st
    lang = _lang(lang)
    T = lambda k: i18n.t(k, lang)
    st.subheader(T("panel.title"))
    all_issues = [i for v in issues_by_unit.values() for i in v]
    n_err, n_warn = issues_counts(all_issues)
    c1, c2 = st.columns(2)
    c1.metric(T("panel.errors"), n_err)
    c2.metric(T("panel.warnings"), n_warn)
    choice = "exclude"
    if not all_issues:
        st.success(T("panel.ok"))
        return choice
    shown = issues_frame_by_unit(issues_by_unit, unit_label, lang)
    shown = shown.apply(lambda c: c.map(str) if c.dtype == object else c)   # ids: numbers and text mixed
    st.dataframe(shown, width="stretch", hide_index=True)
    if any(i.kind == "dbh_without_condition" for i in all_issues):
        choice = st.radio(T("panel.radio"), list(MISSING_CONDITION_CHOICES),
                          format_func=lambda c: T(f"panel.missing.{c}"), horizontal=True,
                          key=key)
    return choice


SEAL_KEY = "show_seal"
_SEAL_CHOICE_KEY = "_show_seal"     # plain copy that survives page changes (like the language)


def seal_checkbox(container):
    """The "show seal" checkbox; the choice follows the user across pages."""
    import streamlit as st
    ss = st.session_state
    if SEAL_KEY not in ss:
        ss[SEAL_KEY] = bool(ss.get(_SEAL_CHOICE_KEY, False))
    value = container.checkbox(i18n.t("sidebar.show_seal"), key=SEAL_KEY)
    ss[_SEAL_CHOICE_KEY] = value
    return value


PAGE_ICON = str(Path(__file__).parent / "app" / "assets" / "logo.png")
NAV_PAGES = (("Home.py", "nav.home"), ("pages/1_Single_plot.py", "nav.single"),
             ("pages/2_Multiple_plots.py", "nav.multiple"), ("pages/3_Temporal.py", "nav.temporal"),
             ("pages/5_Colonizacao.py", "nav.colonizacao"), ("pages/4_About.py", "nav.about"))


def colonizacao_enabled():
    """The colonization page is a preview: it only shows up when the environment variable
    MANGUETREE_COLONIZACAO is 1/true or the app secret ``colonizacao`` is true (Streamlit
    Cloud: App settings, Secrets). Without either, the menu entry is hidden."""
    import os
    if str(os.environ.get("MANGUETREE_COLONIZACAO", "")).strip().lower() in ("1", "true", "yes", "sim"):
        return True
    try:
        import streamlit as st
        return str(st.secrets.get("colonizacao", "")).strip().lower() in ("1", "true", "yes", "sim")
    except Exception:
        return False


def sidebar_nav(container, tab_icons=(), subtab_icons=()):
    """Page menu with translated names and the MangueTREE icons (icons.css). Streamlit's
    automatic menu (built from the file names) is turned off in .streamlit/config.toml
    (showSidebarNavigation). ``tab_icons``: icon names of the page's tabs, in order."""
    import streamlit as st
    from manguetree import icons
    st.html(icons.css(tab_icons, subtab_icons))
    reset_report_figs()                       # the charts of this run feed the PDF report
    for page, key in NAV_PAGES:
        if "Colonizacao" in page and not colonizacao_enabled():
            continue
        try:
            container.page_link(page, label=i18n.t(key))
        except Exception:        # outside a multipage run (unit tests of a single page)
            pass
    container.divider()


def icon_heading(container, icon, text, level=2):
    """Heading with a MangueTREE icon (replaces st.header/subheader with emoji)."""
    from manguetree import icons
    container.markdown(f'<h{level} style="display:flex;align-items:center">{icons.img(icon, 22 if level <= 2 else 18, "0")}'
                       f'{text}</h{level}>', unsafe_allow_html=True)


def icon_note(container, icon, text):
    """Info box with a MangueTREE icon (replaces st.info with a pointing emoji)."""
    from manguetree import icons
    import re
    html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    container.markdown(
        f'<div style="display:flex;gap:10px;align-items:center;background:#EEF6F1;border-radius:8px;'
        f'padding:14px 16px;color:#1F4D3A">{icons.img(icon, 22, "0")}<span>{html}</span></div>',
        unsafe_allow_html=True)


def quit_button(container):
    """"Quit MangueTREE" button for the desktop build (launcher sets MANGUETREE_DESKTOP):
    stops the local server, so the app needs no console window to close."""
    import os
    import time
    if os.environ.get("MANGUETREE_DESKTOP") != "1":
        return
    if container.button(i18n.t("sidebar.quit"), key="quit_app"):
        container.info(i18n.t("sidebar.quit_done"))
        time.sleep(1.0)       # let the browser receive the message
        os._exit(0)


def _table_signature(table):
    return hashlib.md5(table.to_csv(index=False).encode("utf-8")).hexdigest()


def sidebar_species_settings(container):
    """Region selector + editable species table; returns a ``SpeciesResolver``.

    The editor input is ``st.session_state["species_base"]`` and the edited table is
    kept in ``["species_table"]``; both survive reruns and are shared by the pages;
    ``st.session_state["settings_sig"]`` holds (region, table hash) for cache keys.
    """
    import streamlit as st
    ss = st.session_state
    if "species_base" not in ss:       # input of the editor; never overwritten by edits
        ss["species_base"] = load_species_table()
    genus_defaults = load_genus_defaults()
    lang = i18n.get_lang()
    T = lambda k, **p: i18n.t(k, lang, **p)   # bound: AppTest calls format_func outside a run
    region = container.selectbox(T("sidebar.region"), list(REGIONS), index=0,
                                 key="region_code",
                                 format_func=lambda c: T(f"region.{c}"),
                                 help=T("sidebar.region_help"))
    with container.expander(T("sidebar.species_table")):
        up = st.file_uploader(T("sidebar.species_upload"), type=["csv"],
                              key="species_csv")
        if up is not None and ss.get("species_csv_name") != (up.name, up.size):
            try:
                new = pd.read_csv(up, dtype=str, keep_default_na=False)
                missing = [c for c in SPECIES_REQUIRED_COLUMNS if c not in new.columns]
                if missing:
                    st.error(T("sidebar.species_missing_columns", columns=", ".join(missing)))
                else:
                    ss["species_base"] = new
                    ss["species_csv_name"] = (up.name, up.size)
                    ss.pop("species_editor", None)
            except Exception as e:
                st.error(T("sidebar.species_read_error", error=str(e)))
        st.caption(T("sidebar.species_aliases_note"))
        edited = st.data_editor(ss["species_base"], num_rows="dynamic",
                                key="species_editor", width="stretch",
                                hide_index=True)
        if st.button(T("sidebar.species_reset"), key="species_reset"):
            ss["species_base"] = load_species_table()
            ss.pop("species_editor", None)
            st.rerun()
    table = edited.fillna("").astype(str)
    table = table[table["code"].str.strip() != ""].reset_index(drop=True)
    ss["species_table"] = table
    try:
        resolver = SpeciesResolver(table, region, genus_defaults)
    except Exception as e:
        container.error(T("sidebar.species_invalid", error=str(e)))
        table = load_species_table()
        resolver = SpeciesResolver(table, region, genus_defaults)
    ss["settings_sig"] = (region, _table_signature(table))
    coll = resolver.alias_collisions()
    if coll:
        container.warning(T("sidebar.alias_collisions") + " "
                          + "; ".join(T("sidebar.alias_collision_item", alias=a, new=c,
                                        old=o) for a, c, o in coll))
    return resolver


def settings_signature():
    """(region, species-table hash) of the current sidebar settings."""
    import streamlit as st
    return st.session_state.get("settings_sig")


# ---------------------------------------------------------------------------
# TEMPORAL v1.1.0: every parameter, several plots, stacked columns
# ---------------------------------------------------------------------------
def _year_axis(fig, df, gaps=False):
    """Years on the x axis. ``gaps=False`` (lab convention): one column after the other,
    with no empty space for years without a survey; ``gaps=True``: a time scale."""
    years = sorted(df["year"].dropna().unique())
    if gaps:
        fig.update_xaxes(type="linear", tickmode="array", tickvals=years,
                         ticktext=[str(int(y)) for y in years])
    else:
        fig.update_xaxes(type="category", categoryorder="array",
                         categoryarray=[str(int(y)) for y in years])
        for tr in fig.data:
            if getattr(tr, "x", None) is not None and not getattr(tr, "fill", None):
                tr.x = [str(int(float(v))) for v in tr.x]
    fig.update_xaxes(tickangle=-45 if len(years) > 12 else 0)
    return fig


def fig_series(df, estilos, y, view="plots", chart="line", lang=None, gaps=False):
    """One parameter over the years. With several plots: one trace per plot
    (``view="plots"``) or the mean with a band / error bars of one SD (``view="mean"``)."""
    lang = _lang(lang)
    cores = estilos["paleta"]
    fig = go.Figure()
    plots = list(dict.fromkeys(df["plot"])) if "plot" in df.columns else [None]
    if view == "mean" and len(plots) > 1:
        g = df.groupby("year")[y].agg(["mean", "std", "count"]).reset_index().fillna({"std": 0})
        if chart == "bar":
            fig.add_trace(go.Bar(x=g["year"], y=g["mean"], marker_color=cores[0],
                                 error_y=dict(type="data", array=g["std"], visible=True),
                                 name=i18n.t("temporal.view.mean", lang)))
        else:
            band = pd.concat([g["year"], g["year"][::-1]])
            fig.add_trace(go.Scatter(x=band, y=pd.concat([g["mean"] + g["std"], (g["mean"] - g["std"])[::-1]]),
                                     fill="toself", fillcolor="rgba(46,139,87,0.15)", line=dict(width=0),
                                     hoverinfo="skip", showlegend=False))
            fig.add_trace(go.Scatter(x=g["year"], y=g["mean"], mode="lines+markers",
                                     line=dict(color=cores[0]), name=i18n.t("temporal.view.mean", lang)))
    else:
        for i, p in enumerate(plots):
            sub = df if p is None else df[df["plot"] == p]
            sub = sub.sort_values("year")
            nome = str(p) if p is not None else label(y, lang)
            if chart == "bar":
                fig.add_trace(go.Bar(x=sub["year"], y=sub[y], name=nome, marker_color=cores[i % len(cores)]))
            else:
                fig.add_trace(go.Scatter(x=sub["year"], y=sub[y], mode="lines+markers", name=nome,
                                         line=dict(color=cores[i % len(cores)])))
        fig.update_layout(barmode="group", showlegend=len(plots) > 1)
    fig.update_layout(xaxis_title=label("year", lang), yaxis_title=label(y, lang))
    # the mean ± SD band needs a numeric axis
    return _year_axis(_layout(fig, estilos, label(y, lang)), df,
                      gaps=gaps or (view == "mean" and chart == "line" and len(plots) > 1))


def palette_species_colors(species, estilos):
    """Species -> colour, following the palette chosen in the sidebar."""
    return species_colors(species)


LIVE_DEAD_METRICS = {"live_dead_density": ("density_live_ha", "density_dead_ha", "density_total_ha"),
                     "live_dead_ba": ("ba_live_ha", "ba_dead_ha", "ba_total_ha")}


def fig_species_live_dead(df_esp, estilos, metric, chart="stack", show_values=False, lang=None,
                          gaps=False):
    """Live (solid) and dead (hatched) of each species in the same column, stacked;
    ``chart="stack100"`` shows each part as % of the year's total."""
    if df_esp is None or df_esp.empty:
        return None
    lang = _lang(lang)
    viva, morta, total = LIVE_DEAD_METRICS[metric]
    df = df_esp.sort_values("year").copy()
    tot = df.groupby("year")[total].transform("sum")
    order = df.groupby("species")[total].mean().sort_values(ascending=False).index.tolist()
    cores = palette_species_colors(df["species"].unique(), estilos)
    fig = go.Figure()
    for cond, col, pattern in (("live", viva, ""), ("dead", morta, "/")):
        for sp in order:
            sub = df[df["species"] == sp]
            vals = (100 * sub[col] / tot[sub.index]).where(tot[sub.index] > 0, 0.0) \
                if chart == "stack100" else sub[col]
            cor = cores[sp]
            txt = [num(v, 0 if chart == "stack100" else 2, lang) for v in vals] if show_values else None
            fig.add_trace(go.Bar(
                x=sub["year"], y=vals, text=txt, textposition="inside",
                legendrank=10 * order.index(sp) + (0 if cond == "live" else 1),
                name=f"{species_name(sp, lang)} · {i18n.t('condition.' + cond, lang)}",
                marker=dict(color=cor if cond == "live" else "white", line=dict(color=cor, width=1.2),
                            pattern=dict(shape=pattern, fgcolor=cor, size=6, solidity=0.35))))
    fig.update_layout(barmode="stack", xaxis_title=label("year", lang),
                      yaxis_title=label(total, lang) if chart != "stack100"
                      else i18n.t("temporal.chart.stack100", lang) + " · " + label(total, lang))
    if chart == "stack100":
        fig.update_yaxes(range=[0, 100], ticksuffix="%")
    fig = _layout(fig, estilos, i18n.t(f"temporal.metric.{metric}", lang))
    # fixed frame, so two of these side by side have the same size; legend: one row per
    # species, live in the first column and dead in the second
    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.26, x=0, xanchor="left",
                                  entrywidth=0.5, entrywidthmode="fraction", font=dict(size=10),
                                  traceorder="normal"),
                      margin=dict(t=46, r=24, b=40 + 22 * len(order), l=80), height=380 + 22 * len(order))
    fig.update_yaxes(automargin=False)
    return _year_axis(fig, df, gaps)


def fig_species_series(df_esp, estilos, metric, chart="line", show_values=False, lang=None,
                       gaps=False):
    """A per-species parameter over the years: lines, grouped columns, stacked
    columns or 100% stacked columns (each year's column adds up to 100%)."""
    if df_esp is None or df_esp.empty:
        return None
    if metric in LIVE_DEAD_METRICS:
        return fig_species_live_dead(df_esp, estilos, metric, "stack100" if chart == "stack100"
                                     else "stack", show_values, lang, gaps)
    lang = _lang(lang)
    df = df_esp.sort_values("year").copy()
    order = (df.groupby("species")[metric].mean().sort_values(ascending=False).index.tolist())
    fig = go.Figure()
    if chart == "stack100":
        tot = df.groupby("year")[metric].transform("sum")
        df["_v"] = np.where(tot > 0, 100 * df[metric] / tot, 0.0)
    else:
        df["_v"] = df[metric]
    cores = palette_species_colors(df["species"].unique(), estilos)
    for sp in order:
        sub = df[df["species"] == sp]
        nome = species_name(sp, lang)
        cor = cores[sp]
        if chart == "line":
            fig.add_trace(go.Scatter(x=sub["year"], y=sub["_v"], mode="lines+markers", name=nome,
                                     line=dict(color=cor)))
        else:
            txt = [num(v, 0 if chart == "stack100" else 2, lang) for v in sub["_v"]] if show_values else None
            fig.add_trace(go.Bar(x=sub["year"], y=sub["_v"], name=nome, marker_color=cor,
                                 text=txt, textposition="inside" if chart != "bar" else "outside",
                                 insidetextanchor="middle"))
    fig.update_layout(barmode={"bar": "group", "stack": "stack", "stack100": "stack"}.get(chart, "group"),
                      legend=dict(orientation="h", yanchor="top", y=-0.22, x=0.5, xanchor="center"),
                      xaxis_title=label("year", lang),
                      yaxis_title=(i18n.t("temporal.chart.stack100", lang) + " · " + label(metric, lang))
                      if chart == "stack100" else label(metric, lang))
    if chart == "stack100":
        fig.update_yaxes(range=[0, 100], ticksuffix="%")
    fig = _layout(fig, estilos, i18n.t("chart.by_species", lang, metric=label(metric, lang)))
    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.22, x=0.5, xanchor="center"),
                      margin=dict(b=110))
    return _year_axis(fig, df, gaps)


def fig_species_by_plot_panels(df_esp, estilos, metric, chart="stack", show_values=False, lang=None,
                               gaps=False):
    """Several plots side by side (one panel per plot, same y scale) for a per-species
    parameter over the years."""
    from plotly.subplots import make_subplots
    lang = _lang(lang)
    plots = list(dict.fromkeys(df_esp["plot"]))
    ncol = min(len(plots), 3)
    nrow = int(np.ceil(len(plots) / ncol))
    fig = make_subplots(rows=nrow, cols=ncol, subplot_titles=[str(p) for p in plots],
                        shared_yaxes=True, horizontal_spacing=0.04, vertical_spacing=0.14)
    for i, p in enumerate(plots):
        sub = fig_species_series(df_esp[df_esp["plot"] == p], estilos, metric, chart, show_values, lang, gaps)
        if sub is None:
            continue
        for tr in sub.data:
            tr.showlegend = i == 0
            fig.add_trace(tr, row=i // ncol + 1, col=i % ncol + 1)
        fig.update_xaxes(type="category" if not gaps else "linear", row=i // ncol + 1, col=i % ncol + 1,
                         tickangle=-45)
    fig.update_layout(barmode="stack" if chart != "bar" else "group",
                      height=330 * nrow + 120,
                      legend=dict(orientation="h", yanchor="top", y=-0.12, x=0, xanchor="left",
                                  entrywidth=0.5, entrywidthmode="fraction", font=dict(size=10),
                                  traceorder="normal"))
    if chart == "stack100":
        fig.update_yaxes(range=[0, 100], ticksuffix="%")
    title = (i18n.t(f"temporal.metric.{metric}", lang) if metric in LIVE_DEAD_METRICS
             else i18n.t("chart.by_species", lang, metric=label(metric, lang)))
    return _layout(fig, estilos, title)


def fig_one_species_plots(df_esp, estilos, species, metric, lang=None, gaps=False, show_values=False):
    """One species, every plot side by side in each year (live solid, dead hatched when
    ``metric`` is a live + dead option)."""
    lang = _lang(lang)
    df = df_esp[df_esp["species"] == species].sort_values("year")
    if df.empty:
        return None
    plots = list(dict.fromkeys(df_esp["plot"]))
    # plots need clearly different colours (the default palette is all greens)
    cores = estilos["paleta"] if len(set(estilos["paleta"][:len(plots)])) == len(plots) and \
        estilos["paleta"] is not PALETAS["manguetree"] else ["#2E8B57", "#4C78A8", "#E3A21A", "#7B5230", "#8C9A94", "#1F4D3A"]
    fig = go.Figure()
    partes = ((LIVE_DEAD_METRICS[metric][0], "live", ""), (LIVE_DEAD_METRICS[metric][1], "dead", "/")) \
        if metric in LIVE_DEAD_METRICS else ((metric, None, ""),)
    for i, p in enumerate(plots):
        sub = df[df["plot"] == p]
        cor = cores[i % len(cores)]
        for j, (col, cond, pattern) in enumerate(partes):
            nome = f"{p} · {i18n.t('condition.' + cond, lang)}" if cond else str(p)
            fig.add_trace(go.Bar(
                x=sub["year"], y=sub[col], name=nome, offsetgroup=str(p), legendrank=10 * i + j,
                text=[num(v, 2, lang) for v in sub[col]] if show_values else None, textposition="inside",
                marker=dict(color=cor if cond != "dead" else "white", line=dict(color=cor, width=1.2),
                            pattern=dict(shape=pattern, fgcolor=cor, size=6, solidity=0.35))))
    ylab = label(LIVE_DEAD_METRICS[metric][2], lang) if metric in LIVE_DEAD_METRICS else label(metric, lang)
    fig.update_layout(barmode="stack", xaxis_title=label("year", lang), yaxis_title=ylab)
    fig = _layout(fig, estilos, f"{species_name(species, lang)} · {label(metric, lang)}")
    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.22, x=0, xanchor="left",
                                  entrywidth=0.5, entrywidthmode="fraction", font=dict(size=10),
                                  traceorder="normal"), margin=dict(b=120))
    return _year_axis(fig, df, gaps)


def fig_plot_difference(df_esp, estilos, plot_a, plot_b, metric, lang=None, gaps=False):
    """Difference ``plot_b - plot_a`` of a per-species parameter in each year (bars above
    zero: plot_b has more). For the live + dead options the total is compared."""
    lang = _lang(lang)
    col = LIVE_DEAD_METRICS[metric][2] if metric in LIVE_DEAD_METRICS else metric
    a = df_esp[df_esp["plot"] == plot_a].pivot_table(index="year", columns="species", values=col, aggfunc="mean")
    b = df_esp[df_esp["plot"] == plot_b].pivot_table(index="year", columns="species", values=col, aggfunc="mean")
    years = sorted(set(a.index) & set(b.index))
    if not years:
        return None
    sps = sorted(set(a.columns) | set(b.columns), key=str)
    a = a.reindex(index=years, columns=sps).fillna(0)
    b = b.reindex(index=years, columns=sps).fillna(0)
    cores = species_colors(sps)
    fig = go.Figure()
    for sp in sps:
        fig.add_trace(go.Bar(x=years, y=(b[sp] - a[sp]), name=species_name(sp, lang), marker_color=cores[sp]))
    fig.add_hline(y=0, line_color="#5F726A", line_width=1.2)
    fig.update_layout(barmode="group", xaxis_title=label("year", lang),
                      yaxis_title=i18n.t("temporal.diff_axis", lang, metric=label(col, lang)))
    fig = _layout(fig, estilos, i18n.t("temporal.diff_title", lang, a=plot_a, b=plot_b, metric=label(col, lang)))
    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.22, x=0, xanchor="left",
                                  font=dict(size=10)), margin=dict(b=110))
    return _year_axis(fig, pd.DataFrame({"year": years}), gaps)


# ---------------------------------------------------------------------------
# v1.1.0: chart style for the page, per-chart fine tuning, batch PNG export
# ---------------------------------------------------------------------------
def style_controls(container, page, paleta_nome, show_seal):
    """Sidebar sliders that set the look of every chart of the page; returns ``estilos``."""
    T = i18n.t
    with container.expander(T("style.more"), expanded=False):
        tt = st_slider(T("sidebar.title_font"), 10, 24, 14, f"tit_{page}")
        ta = st_slider(T("sidebar.axis_font"), 8, 20, 11, f"eix_{page}")
        bg = st_slider(T("style.bar_width"), 10, 100, 80, f"bar_{page}", T("style.bar_width_help"))
        hh = st_slider(T("style.height"), 300, 900, 450, f"alt_{page}", step=10)
        import streamlit as st
        full = st.checkbox(T("style.full_width"), value=True, key=f"full_{page}",
                           help=T("style.full_width_help"))
        ww = None if full else st_slider(T("style.width"), 300, 1600, 800, f"larg_{page}", step=10)
    return {"paleta": PALETAS[paleta_nome], "tamanho_titulo": tt, "tamanho_eixos": ta,
            "seal": show_seal, "bar_width": bg / 100.0, "height": hh, "width": ww}


def st_slider(label_, lo, hi, default, key, help_=None, step=1):
    import streamlit as st
    return st.slider(label_, lo, hi, default, key=key, help=help_, step=step)


# ---------------------------------------------------------------------------
# Charts of the page, kept as they are on screen for the PDF report
# ---------------------------------------------------------------------------
def reset_report_figs():
    import streamlit as st
    st.session_state["_rep_figs"] = {}
    st.session_state["_rep_sec"] = ""


def report_section(label):
    """Name of the section (the tab) that the next charts belong to in the PDF."""
    import streamlit as st
    st.session_state["_rep_sec"] = str(label)


def _register_fig(key, fig):
    import streamlit as st
    figs = st.session_state.setdefault("_rep_figs", {})
    figs[key] = {"key": key, "section": st.session_state.get("_rep_sec", ""), "json": fig.to_json()}


def report_figures():
    """Charts drawn in the current run, in page order: [{"key", "section", "json"}]."""
    import streamlit as st
    return list(st.session_state.get("_rep_figs", {}).values())


def figures_signature():
    import hashlib
    h = hashlib.sha1()
    for f in report_figures():
        h.update(f["key"].encode()); h.update(f["json"].encode())
    return h.hexdigest()


def pdf_block(container, name, build, file_name, sig, lang=None):
    """"Prepare PDF" button + download. ``build(figures)`` returns the PDF bytes; it runs
    only on click, with the charts as they are on screen. A PDF made before the charts or
    the settings changed is flagged as out of date."""
    import streamlit as st
    T = i18n.t
    k = f"pdfx_{name}"
    full = (sig, figures_signature())
    if container.button(T("export.pdf_prepare"), key=f"{k}_btn"):
        with st.spinner(T("export.preparing_pdf_all")):
            try:
                st.session_state[k] = (full, build(report_figures()))
            except Exception as e:
                st.session_state.pop(k, None)
                st.warning(T("export.pdf_unavailable", error=str(e)))
    cur = st.session_state.get(k)
    if cur and cur[0] == full:
        container.download_button(T("export.pdf"), data=cur[1], file_name=file_name,
                                  mime="application/pdf", type="primary", key=f"{k}_dl")
    elif cur:
        container.caption(T("export.pdf_stale"))
    else:
        container.caption(T("export.pdf_figures_note"))


def show(container, fig, key, estilos=None):
    """Draw ``fig`` with a small "Ajustar" menu above it (bar width, y limits, height of
    this chart only). The page-wide defaults come from ``estilos``."""
    import streamlit as st
    if fig is None:
        return
    T = i18n.t
    estilos = estilos or {}
    has_bars = any(getattr(tr, "type", "") == "bar" for tr in fig.data)
    with container.popover(T("chart.adjust"), icon=":material/tune:"):
        ca, cb = st.columns(2)
        h = ca.number_input(T("style.height"), 200, 1600, int(estilos.get("height") or fig.layout.height or 450),
                            step=10, key=f"adjh_{key}")
        full = cb.checkbox(T("style.full_width"), value=estilos.get("width") is None, key=f"adjfull_{key}")
        w = None if full else cb.number_input(T("style.width"), 300, 2400, int(estilos.get("width") or 800),
                                              step=10, key=f"adjw_{key}")
        bw = st.slider(T("style.bar_width"), 10, 100, int(100 * estilos.get("bar_width", 0.8)),
                       key=f"adjb_{key}") if has_bars else None
        c1, c2 = st.columns(2)
        ymin = c1.text_input(T("style.ymin"), "", key=f"adjy0_{key}")
        ymax = c2.text_input(T("style.ymax"), "", key=f"adjy1_{key}")
        novos = {}
        if st.checkbox(T("style.edit_texts"), value=False, key=f"adjtxt_{key}"):
            st.caption(T("style.edit_texts_hint"))
            atual_t = getattr(fig.layout.title, "text", None) or ""
            atual_x = getattr(fig.layout.xaxis.title, "text", None) or ""
            atual_y = getattr(fig.layout.yaxis.title, "text", None) or ""
            novos["title"] = st.text_input(T("style.chart_title"), "", placeholder=atual_t,
                                           key=f"adjtit_{key}")
            if atual_x:
                novos["x"] = st.text_input(T("style.x_title"), "", placeholder=atual_x,
                                           key=f"adjxt_{key}")
            if atual_y:
                novos["y"] = st.text_input(T("style.y_title"), "", placeholder=atual_y,
                                           key=f"adjyt_{key}")
            for i, tr in enumerate(fig.data[:15]):
                if getattr(tr, "name", None) and tr.showlegend is not False and \
                        getattr(tr, "type", "") in ("scatter", "bar", "box", "violin", "histogram"):
                    novos[("trace", i)] = st.text_input(
                        T("style.legend_name", name=tr.name), "", placeholder=str(tr.name),
                        key=f"adjln_{key}_{i}")
    fig.update_layout(height=h)
    for chave_, txt in novos.items():           # empty box keeps the original text
        if not txt.strip():
            continue
        if chave_ == "title":
            fig.update_layout(title_text=txt)
        elif chave_ == "x":
            fig.update_layout(xaxis_title_text=txt)
        elif chave_ == "y":
            fig.update_layout(yaxis_title_text=txt)
        else:
            fig.data[chave_[1]].name = txt
    if w:                                   # fixed width: same size on screen and in the PNG
        fig.update_layout(width=int(w), autosize=False)
    if bw is not None:
        fig.update_layout(bargap=1 - bw / 100.0)

    def _f(txt):
        try:
            return float(str(txt).replace(",", "."))
        except ValueError:
            return None
    lo, hi = _f(ymin), _f(ymax)
    if lo is not None or hi is not None:          # None keeps that end automatic
        fig.update_layout(yaxis_range=[lo, hi], yaxis_autorange=None)
    add_seal(fig)
    _register_fig(key, fig)
    container.plotly_chart(fig, width=int(w) if w else "stretch", config=PLOT_CONFIG, key=f"fig_{key}")


_ZIP_JS = r"""
const CRC=(()=>{let t=[];for(let n=0;n<256;n++){let c=n;for(let k=0;k<8;k++)c=c&1?0xEDB88320^(c>>>1):c>>>1;t[n]=c>>>0}return t})();
function crc32(b){let c=0xFFFFFFFF;for(let i=0;i<b.length;i++)c=CRC[(c^b[i])&255]^(c>>>8);return (c^0xFFFFFFFF)>>>0}
function zip(files){const enc=new TextEncoder();let parts=[],central=[],off=0;
 for(const f of files){const name=enc.encode(f.name),d=f.data,crc=crc32(d);
  const h=new DataView(new ArrayBuffer(30));h.setUint32(0,0x04034b50,true);h.setUint16(4,20,true);h.setUint32(14,crc,true);
  h.setUint32(18,d.length,true);h.setUint32(22,d.length,true);h.setUint16(26,name.length,true);
  parts.push(new Uint8Array(h.buffer),name,d);
  const c=new DataView(new ArrayBuffer(46));c.setUint32(0,0x02014b50,true);c.setUint16(4,20,true);c.setUint16(6,20,true);
  c.setUint32(16,crc,true);c.setUint32(20,d.length,true);c.setUint32(24,d.length,true);c.setUint16(28,name.length,true);c.setUint32(42,off,true);
  central.push(new Uint8Array(c.buffer),name);off+=30+name.length+d.length}
 const size=central.reduce((s,a)=>s+a.length,0);const e=new DataView(new ArrayBuffer(22));e.setUint32(0,0x06054b50,true);
 e.setUint16(8,files.length,true);e.setUint16(10,files.length,true);e.setUint32(12,size,true);e.setUint32(16,off,true);
 return new Blob([...parts,...central,new Uint8Array(e.buffer)],{type:'application/zip'})}
async function png(gd,scale){const w=gd._fullLayout.width,h=gd._fullLayout.height;const cv=document.createElement('canvas');
 cv.width=Math.round(w*scale);cv.height=Math.round(h*scale);const ctx=cv.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,cv.width,cv.height);
 for(const svg of gd.querySelectorAll('svg.main-svg')){const s=svg.cloneNode(true);s.setAttribute('xmlns','http://www.w3.org/2000/svg');
  s.setAttribute('width',w);s.setAttribute('height',h);const img=new Image();
  img.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(new XMLSerializer().serializeToString(s));await img.decode();
  ctx.drawImage(img,0,0,cv.width,cv.height)}
 return new Uint8Array(await (await new Promise(r=>cv.toBlob(r,'image/png'))).arrayBuffer())}
document.getElementById('go').onclick=async()=>{const st=document.getElementById('st');
 const doc=window.parent.document;let panel=[...doc.querySelectorAll('[role="tabpanel"]')].find(p=>p.offsetParent!==null&&!p.hidden)||doc;
 const plots=[...panel.querySelectorAll('.js-plotly-plot')].filter(g=>g.offsetParent!==null&&g._fullLayout);
 if(!plots.length){st.textContent=MSG_NONE;return}
 st.textContent=MSG_WORK;const files=[];let i=1;
 for(const gd of plots){let t=(gd._fullLayout.title&&gd._fullLayout.title.text)||('figura_'+i);
  t=t.replace(/<[^>]+>/g,'').normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/[^A-Za-z0-9]+/g,'_').replace(/^_|_$/g,'').slice(0,60);
  files.push({name:String(i).padStart(2,'0')+'_'+t+'.png',data:await png(gd,SCALE)});i++}
 const a=document.createElement('a');a.href=URL.createObjectURL(zip(files));a.download=ZIPNAME;document.body.appendChild(a);a.click();
 st.textContent=MSG_DONE.replace('{n}',files.length)};
"""


def batch_png_button(container, dpi, zip_name="MangueTREE_figuras.zip"):
    """Button that saves every chart of the open tab as PNG (at ``dpi``) in one ZIP.
    The charts are drawn in the browser, so no extra program is needed."""
    import json
    T = i18n.t
    js = (_ZIP_JS.replace("SCALE", str(dpi / 96.0)).replace("ZIPNAME", json.dumps(zip_name))
          .replace("MSG_NONE", json.dumps(T("export.batch_none"))).replace("MSG_WORK", json.dumps(T("export.batch_work")))
          .replace("MSG_DONE", json.dumps(T("export.batch_done"))))
    html = (f'<body style="margin:0;font-family:Source Sans Pro,Arial,sans-serif">'
            f'<button id="go" style="width:100%;padding:8px 10px;border-radius:8px;border:1px solid #2E8B57;'
            f'background:#fff;color:#1F4D3A;font-weight:600;cursor:pointer">{T("export.batch_button")}</button>'
            f'<div id="st" style="font-size:12px;color:#5F726A;margin-top:4px"></div><script>{js}</script></body>')
    container.iframe(html, height=70)          # st.iframe: runs the script, reaches the page



def location_deck(coords, mode="dark"):
    """Interactive map (pydeck) of the plots: small pins-as-dots coloured per plot, plot name on
    hover and as a label. ``mode``: "dark" (dark base map) or "satellite" (Esri imagery)."""
    import pydeck as pdk
    from manguetree.reports import basemap, theme
    c = coords.dropna(subset=["lat", "lon"]).copy()
    c["lat"] = c["lat"].astype(float); c["lon"] = c["lon"].astype(float)
    names = c["plot"].astype(str) if "plot" in c.columns else pd.Series([""] * len(c), index=c.index)
    cmap = theme.plot_color_map(names) if "plot" in c.columns else {}
    rgb = lambda h: [int(h[i:i + 2], 16) for i in (1, 3, 5)]
    c["name"] = names
    c["color"] = [rgb(cmap.get(n, theme.AMBER)) + [235] for n in names]
    bounds = basemap.padded_bounds(list(c["lat"]), list(c["lon"]))
    zoom = min(basemap.choose_zoom(bounds, max_side=3), 17)
    view = pdk.ViewState(latitude=float(c["lat"].mean()), longitude=float(c["lon"].mean()), zoom=zoom)
    layers = []
    many = len(c) > 12
    # sizes in metres with a pixel clamp: pydeck would turn a "pixels" string into an expression
    layers.append(pdk.Layer("ScatterplotLayer", data=c, get_position="[lon, lat]", get_fill_color="color",
                            get_line_color=[255, 255, 255], stroked=True, line_width_min_pixels=1.2,
                            get_radius=1, radius_min_pixels=3 if many else 6, radius_max_pixels=3 if many else 7,
                            pickable=True))
    if not many:
        layers.append(pdk.Layer("TextLayer", data=c, get_position="[lon, lat]", get_text="name", get_size=13,
                                get_color=[255, 255, 255], get_pixel_offset=[0, -16],
                                font_weight=700,
                                font_settings={"sdf": True}, outline_width=3, outline_color=[0, 0, 0, 200]))
    return pdk.Deck(layers=layers, initial_view_state=view,
                    map_style=_satellite_style_url() if mode == "satellite" else "dark",
                    tooltip={"text": "{name}"} if "plot" in c.columns else None)


def _satellite_style_url():
    """The satellite style as a data URL (Streamlit takes the map style only as text)."""
    import json
    import urllib.parse
    return "data:application/json;charset=utf-8," + urllib.parse.quote(json.dumps(SATELLITE_STYLE))


# MapLibre style with the Esri World Imagery tiles (no key needed)
SATELLITE_STYLE = {
    "version": 8,
    "sources": {"esri": {"type": "raster", "tileSize": 256, "maxzoom": 19,
                         "tiles": ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
                         "attribution": "Esri, Maxar, Earthstar Geographics"}},
    "layers": [{"id": "esri", "type": "raster", "source": "esri"}],
}


def location_map(st, coords, lang=None):
    """Plot-location map of the app: interactive (zoom and pan), dark base map or satellite."""
    from manguetree import i18n as _i
    lang = _lang(lang)
    modes = {"dark": _i.t("map.mode_dark", lang), "satellite": _i.t("map.mode_satellite", lang)}
    mode = st.radio(_i.t("map.mode", lang), list(modes), format_func=modes.get, horizontal=True, key="map_mode")
    st.pydeck_chart(location_deck(coords, mode), height=520)
