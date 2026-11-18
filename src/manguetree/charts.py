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
    eixo = dict(showline=True, linewidth=0.8, linecolor="#5F726A", zeroline=False,
                ticks="outside", tickcolor="#5F726A", ticklen=4,
                tickfont=dict(size=10), title_font=dict(size=tam_e),
                exponentformat="none", separatethousands=True)     # 10.000, never 10k
    fig.update_xaxes(showgrid=False, **eixo)
    fig.update_yaxes(showgrid=False, **eixo)
    if not estilos.get("seal"):         # the seal is opt-in (sidebar checkbox)
        return fig
    uri = _selo_uri()
    if uri:
        fig.add_layout_image(dict(source=uri, xref="paper", yref="paper",
                             x=1.0, y=-0.02, sizex=0.11, sizey=0.11,
                             xanchor="right", yanchor="top", layer="above", opacity=0.95))
    else:
        fig.add_annotation(text=marca.SELO_TEXTO, xref="paper", yref="paper",
                           x=1.0, y=-0.18, showarrow=False, xanchor="right",
                           font=dict(size=9, color="#9AA7A0"))
    return fig


def cor_por_especie(especies):
    """Mapa espécie->cor: matiz do gênero, tom próprio por espécie."""
    return {e: mc.species_color(e) for e in especies}


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


COUNT_COLUMNS = ("plot_area_m2", "n_species_live")


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
            for c in df.columns}


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
             if c == mc.UNIDENTIFIED_LABEL or i18n.catalog(i18n.DEFAULT).get(f"labels.{c}")}
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
        if text_ids and "tree_id" in df.columns:
            out[names.get("tree_id", "tree_id")] = out[names.get("tree_id", "tree_id")].map(
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
    return {species_name(e, lang): mc.species_color(e) for e in species}


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


def fig_classes_dap(dens_cl, domi_cl, estilos, metrica="density", lang=None):
    """Distribuição por classes de DAP (barras empilhadas por espécie)."""
    lang = _lang(lang)
    df = dens_cl if metrica == "density" else domi_cl
    if df is None or df.empty:
        return None
    sp, val = label("species", lang), "value"
    dfp = df.reset_index().melt(id_vars="dbh_class", var_name=sp, value_name=val)
    dfp[sp] = dfp[sp].map(lambda v: species_name(v, lang))
    dfp["dbh_class"] = dfp["dbh_class"].astype(str).map(lambda v: dbh_class_label(v, lang))
    cmap = _cmap(df.columns, lang)
    cls = label("dbh_class", lang)
    fig = px.bar(dfp, x="dbh_class", y=val, color=sp, color_discrete_map=cmap,
                 barmode="stack", labels={"dbh_class": cls, val: label("value", lang)})
    ylab = label("density_ha" if metrica == "density" else "ba_ha", lang)
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


def fig_altura_dap(res, estilos, lang=None):
    """Dispersão altura x DAP com regressão linear por espécie."""
    lang = _lang(lang)
    d = res["data"]
    dd = d[d["live"]].dropna(subset=["height", "dbh"])     # live stems only
    dd = dd[(dd["dbh"] > 0) & (dd["height"] > 0)].copy()
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


def fig_perfil_vertical(res, estilos, lang=None):
    """
    Perfil/estrutura vertical do bosque: cada árvore viva como marcador
    posicionado por altura, tamanho ~ DAP, cor por gênero. Dá a silhueta do dossel.
    """
    lang = _lang(lang)
    d = res["data"]
    dd = d[d["live"] & (d["height"] > 0) & d["dbh"].notna() & (d["dbh"] > 0)].copy()
    if dd.empty:
        return None
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
    return _layout(fig, estilos, i18n.t("chart.vertical_profile", lang))


# ---------------------------------------------------------------------------
# COMPARATIVO / TEMPORAL (múltiplas parcelas)
# Tables keep internal (language independent) column names: plot, year, density_live_ha,
# ... ; ``for_display`` / ``label`` give the text in the current language.
# ---------------------------------------------------------------------------
NON_METRIC_COLUMNS = mc.NON_METRIC_COLUMNS
metric_columns = mc.metric_columns


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
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1]),
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
    st.dataframe(issues_frame_by_unit(issues_by_unit, unit_label, lang),
                 width="stretch", hide_index=True)
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
             ("pages/4_About.py", "nav.about"))


def sidebar_nav(container, tab_icons=()):
    """Page menu with translated names and the MangueTREE icons (icons.css). Streamlit's
    automatic menu (built from the file names) is turned off in .streamlit/config.toml
    (showSidebarNavigation). ``tab_icons``: icon names of the page's tabs, in order."""
    import streamlit as st
    from manguetree import icons
    st.html(icons.css(tab_icons))
    for page, key in NAV_PAGES:
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
