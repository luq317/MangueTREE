# -*- coding: utf-8 -*-
"""
colonizacao_charts.py
=====================
Charts of the colonization dynamics page (Plotly, same look as the other pages):

* density curve of juveniles per plot over the years (linear or log scale);
* contribution of the species (relative density, or density) per year, one plot;
* mean height of juveniles with one standard deviation;
* density against the age of the plots, with the log-linear fit;
* schematic of stem density over stand development (Jimenez et al. 1985, Fig. 2).

All functions take the tables of ``manguetree.colonizacao`` and the ``estilos`` dict of
``charts.style_controls``; text comes from the catalogs (keys ``colon.chart.*``).
"""
import numpy as np
import plotly.graph_objects as go

from manguetree import charts as ui
from manguetree import i18n

#: species codes used in the NEMA workbooks -> scientific names
ESPECIES = {"Av": "Avicennia schaueriana", "Lg": "Laguncularia racemosa",
            "Rh": "Rhizophora mangle"}


def nome_especie(codigo):
    """Scientific name of a workbook species code (other labels are returned unchanged)."""
    return ESPECIES.get(str(codigo).strip().capitalize(), str(codigo) or "?")


def _anos(fig, anos):
    anos = sorted({int(a) for a in anos})
    fig.update_xaxes(type="linear", tickmode="array", tickvals=anos,
                     ticktext=[str(a) for a in anos],
                     tickangle=-45 if len(anos) > 12 else 0)
    return fig


def fig_curva_densidade(dens, estilos, lang=None, escala_log=False):
    """Density of juveniles (ind/ha) of each plot over the years. ``dens`` is the table
    of ``densidade_jovens`` (without the species split)."""
    lang = ui._lang(lang)
    T = i18n.t
    cores = estilos["paleta"]
    fig = go.Figure()
    for i, (nome, sub) in enumerate(dens.groupby("parcela", sort=True)):
        sub = sub.sort_values("ano")
        y = sub["ind_ha"].where(sub["ind_ha"] > 0) if escala_log else sub["ind_ha"]
        fig.add_trace(go.Scatter(x=sub["ano"], y=y, mode="lines+markers", name=str(nome),
                                 line=dict(color=cores[i % len(cores)]),
                                 marker=dict(size=6)))
    fig.update_layout(xaxis_title=T("colon.chart.year", lang),
                      yaxis_title=T("colon.chart.density_axis", lang),
                      showlegend=dens["parcela"].nunique() > 1)
    if escala_log:
        fig.update_yaxes(type="log")
    _anos(fig, dens["ano"])
    return ui._layout(fig, estilos, T("colon.chart.density_title", lang))


def fig_composicao(rel, estilos, parcela, relativa=True, lang=None):
    """Species of one plot per year, as stacked columns: relative density (%) or density
    (ind/ha). ``rel`` is the table of ``densidade_relativa``."""
    lang = ui._lang(lang)
    T = i18n.t
    sub = rel[rel["parcela"] == parcela]
    y = "relativa" if relativa else "ind_ha"
    nomes = {e: nome_especie(e) for e in sub["especie"].unique()}
    cores = ui.species_colors(list(nomes.values()))
    anos = sorted(sub["ano"].unique())
    fig = go.Figure()
    for esp, nome in nomes.items():
        d = sub[sub["especie"] == esp].set_index("ano").reindex(anos)
        fig.add_trace(go.Bar(x=[str(int(a)) for a in anos], y=d[y].fillna(0), name=nome,
                             marker_color=cores[nome]))
    fig.update_layout(barmode="stack", xaxis_title=T("colon.chart.year", lang),
                      yaxis_title=T("colon.chart.relative_axis" if relativa
                                    else "colon.chart.density_axis", lang))
    fig.update_xaxes(type="category", tickangle=-45 if len(anos) > 12 else 0)
    if relativa:
        fig.update_yaxes(range=[0, 100])
    return ui._layout(fig, estilos, T("colon.chart.species_title", lang, plot=parcela))


def fig_altura(est, estilos, lang=None):
    """Mean height (cm) of juveniles with one SD, per plot (and species, when the table
    has the ``especie`` column). ``est`` is the table of ``estatistica_altura``."""
    lang = ui._lang(lang)
    T = i18n.t
    cores = estilos["paleta"]
    chave = ["parcela"] + [c for c in ("especie", "classe") if c in est.columns]
    fig = go.Figure()
    for i, (k, sub) in enumerate(est.groupby(chave, sort=True)):
        sub = sub.sort_values("ano")
        k = k if isinstance(k, tuple) else (k,)
        partes = []
        for c, x in zip(chave, k):
            partes.append(str(x) if c == "parcela" else nome_especie(x) if c == "especie"
                          else T(f"colon.cls.{x}", lang))
        nome = " ".join(partes)
        fig.add_trace(go.Scatter(
            x=sub["ano"], y=sub["media"], mode="lines+markers", name=nome,
            line=dict(color=cores[i % len(cores)]), marker=dict(size=6),
            error_y=dict(type="data", array=sub["dp"].fillna(0), visible=True, thickness=1)))
    fig.update_layout(xaxis_title=T("colon.chart.year", lang),
                      yaxis_title=T("colon.chart.height_axis", lang),
                      showlegend=len(fig.data) > 1)
    _anos(fig, est["ano"])
    return ui._layout(fig, estilos, T("colon.chart.height_title", lang))


def fig_regressao(df, regs, estilos, lang=None):
    """Density (ind/ha) against plot age, both on log axes, with the fitted lines. ``df`` is
    ``densidade_jovens`` plus ``idade`` (``com_idade``); ``regs`` is {label: result of
    ``regressao_log_linear``}, one line per entry (label "" is the fit of all plots)."""
    lang = ui._lang(lang)
    T = i18n.t
    cores = estilos["paleta"]
    d = df[(df["idade"] > 0) & (df["ind_ha"] > 0)]
    fig = go.Figure()
    nomes = sorted(d["parcela"].unique())
    cor = {n: cores[i % len(cores)] for i, n in enumerate(nomes)}
    for n in nomes:
        sub = d[d["parcela"] == n].sort_values("idade")
        fig.add_trace(go.Scatter(x=sub["idade"], y=sub["ind_ha"], mode="markers", name=str(n),
                                 marker=dict(size=8, color=cor[n])))
    xs = np.geomspace(max(d["idade"].min(), 0.5), d["idade"].max(), 60) if not d.empty else []
    for rotulo, r in regs.items():
        if r is None:
            continue
        nome = (T("colon.chart.fit_all", lang) if rotulo == "" else
                T("colon.chart.fit_plot", lang, plot=rotulo))
        fig.add_trace(go.Scatter(x=xs, y=np.exp(r["a"]) * xs ** r["b"], mode="lines", name=nome,
                                 line=dict(color=cor.get(rotulo, "#5F726A"), width=1.6,
                                           dash="solid" if rotulo else "dash")))
    fig.update_xaxes(type="log", title=T("colon.chart.age_axis", lang))
    fig.update_yaxes(type="log", title=T("colon.chart.density_axis", lang))
    return ui._layout(fig, estilos, T("colon.chart.regression_title", lang))


def fig_esquema(estilos, lang=None):
    """Schematic of stem density over stand development (Jimenez et al. 1985, Fig. 2):
    colonization, early development, maturity and senescence. Qualitative only."""
    from manguetree import colonizacao as col
    lang = ui._lang(lang)
    T = i18n.t
    x, y, fases = col.curva_esquematica()
    cores = estilos["paleta"]
    fig = go.Figure()
    for i, (nome, (a, b)) in enumerate(fases.items()):
        fig.add_vrect(x0=a, x1=b, fillcolor="#EEF3F0" if i % 2 == 0 else "#FFFFFF",
                      line_width=0, layer="below",
                      annotation_text=T(f"colon.chart.phase_{nome}", lang),
                      annotation_position="top", annotation_font_size=10)
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(color=cores[0], width=2.2),
                             hoverinfo="skip", showlegend=False))
    fig.update_layout(xaxis_title=T("colon.chart.schema_x", lang),
                      yaxis_title=T("colon.chart.schema_y", lang), showlegend=False)
    fig.update_xaxes(showticklabels=False, ticks="", range=[0, 0.95])
    fig.update_yaxes(showticklabels=False, ticks="", range=[0, 1.15])
    fig.update_layout(margin=dict(t=70))
    return ui._layout(fig, estilos, T("colon.chart.schema_title", lang))


def fig_contagem(df, estilos, lang=None, agrupar="coorte", percentual=False):
    """Individuos por ano, em colunas empilhadas pelo grupo (coorte, especie, codigo ou
    classe). ``df`` e a tabela de ``contagem_por_ano`` de uma parcela (ou das somadas)."""
    from manguetree import colonizacao as col
    import plotly.colors as pcolors
    lang = ui._lang(lang)
    T = i18n.t
    d = df.groupby(["ano", "grupo"], as_index=False)["n"].sum()
    anos = sorted(d["ano"].unique())
    grupos = (col.ordem_coortes(d["grupo"]) if agrupar == "coorte"
              else sorted(d["grupo"].unique()))
    if agrupar == "coorte":
        n = max(len(grupos) - (col.SEM_COORTE in grupos), 1)
        tons = pcolors.sample_colorscale("Viridis", [i / max(n - 1, 1) for i in range(n)])
        cores = {g: tons[i] for i, g in enumerate(x for x in grupos if x != col.SEM_COORTE)}
        cores[col.SEM_COORTE] = "#B8C2BC"
    elif agrupar == "especie":
        cores = ui.species_colors([nome_especie(g) for g in grupos])
        cores = {g: cores[nome_especie(g)] for g in grupos}
    else:
        paleta = estilos["paleta"]
        cores = {g: paleta[i % len(paleta)] for i, g in enumerate(grupos)}
    total = d.groupby("ano")["n"].sum()
    fig = go.Figure()
    for g in grupos:
        sub = d[d["grupo"] == g].set_index("ano").reindex(anos)["n"].fillna(0)
        y = (100 * sub / total.reindex(anos)).fillna(0) if percentual else sub
        nome = (T("colon.cohort.none", lang) if g == col.SEM_COORTE else
                nome_especie(g) if agrupar == "especie" else
                T(f"colon.cls.{g}", lang) if agrupar == "classe" else str(g))
        fig.add_trace(go.Bar(x=[str(int(a)) for a in anos], y=y, name=nome,
                             marker_color=cores[g]))
    fig.update_layout(barmode="stack", xaxis_title=T("colon.chart.year", lang),
                      yaxis_title=T("colon.chart.percent_axis" if percentual
                                    else "colon.chart.count_axis", lang),
                      showlegend=agrupar != "nenhum")
    fig.update_xaxes(type="category", tickangle=-45 if len(anos) > 12 else 0)
    if percentual:
        fig.update_yaxes(range=[0, 100])
    return ui._layout(fig, estilos, T("colon.chart.count_title", lang))
