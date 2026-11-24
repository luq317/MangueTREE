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


def _eixo_anos(fig, anos, horizontal=False, barras=False):
    """Year axis with every year labelled. For columns the axis starts half a year before the
    first one (no empty band at the left) and ends half a year after the last."""
    anos = sorted({int(a) for a in anos})
    if not anos:
        return fig
    pad = 0.6 if barras else 0.4
    eixo = dict(type="linear", tickmode="array", tickvals=anos, ticktext=[str(a) for a in anos],
                range=[anos[-1] + pad, anos[0] - pad] if horizontal else [anos[0] - pad, anos[-1] + pad])
    if horizontal:
        fig.update_yaxes(**eixo)
    else:
        fig.update_xaxes(tickangle=-45 if len(anos) > 12 else 0, **eixo)
    return fig


def _fecha(fig, estilos, titulo):
    """``charts._layout`` plus the legend of the joined plots: it goes in one row at the bottom of
    the figure (never at the right, where it would squeeze the plotting area)."""
    fig = ui._layout(fig, estilos, titulo)
    if any(getattr(tr, "legendgroup", "") == "incompleta" for tr in fig.data):
        m = fig.layout.margin
        fig.update_layout(legend=dict(orientation="h", xref="container", x=0, xanchor="left",
                                      yref="container", y=0, yanchor="bottom"),
                          margin=dict(t=m.t, r=m.r, l=m.l, b=(m.b or 58) + 46))
    return fig


def _incompleta(sub):
    """Boolean array: rows of a joined plot with data of only part of its plots."""
    if "incompleta" not in sub:
        return np.zeros(len(sub), dtype=bool)
    return sub["incompleta"].fillna(False).astype(bool).to_numpy()


def _estilo_pontos(sub, lang, tamanho=6):
    """Marker, text and hover of a series: a joined plot year with part of the plots is drawn
    with an open diamond and an asterisk, and the hover says which plots were used."""
    inc = _incompleta(sub)
    T = i18n.t
    marker_symbol = np.where(inc, "diamond-open", "circle")
    texto = np.where(inc, "*", "")
    hover = None
    if "membros" in sub:
        hover = [T("colon.chart.hover_plots", lang, plots=m) if i else ""
                 for m, i in zip(sub["membros"], inc)]
    return inc, dict(size=tamanho, symbol=list(marker_symbol)), list(texto), hover


def _legenda_incompleta(fig, lang, tem):
    """Legend entry that explains the asterisk (only when some point has it)."""
    if tem:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers+text", text=["*"],
                                 legendgroup="incompleta",
                                 name=i18n.t("colon.chart.incomplete_legend", lang),
                                 marker=dict(size=8, symbol="diamond-open", color="#5F726A"),
                                 showlegend=True))
        fig.update_layout(showlegend=True)


def fig_curva_densidade(dens, estilos, lang=None, escala_log=False, tipo="line"):
    """Density of juveniles (ind/ha) of each plot over the years. ``dens`` is the table
    of ``densidade_jovens`` (without the species split). ``tipo``: line, markers, bar or hbar
    (there is one value per plot and year, so no standard deviation)."""
    lang = ui._lang(lang)
    T = i18n.t
    cores = estilos["paleta"]
    horizontal = tipo == "hbar"
    fig = go.Figure()
    for i, (nome, sub) in enumerate(dens.groupby("parcela", sort=True)):
        sub = sub.sort_values("ano")
        y = sub["ind_ha"].where(sub["ind_ha"] > 0) if escala_log else sub["ind_ha"]
        cor = cores[i % len(cores)]
        if tipo in ("bar", "hbar"):
            fig.add_trace(go.Bar(x=y if horizontal else sub["ano"], y=sub["ano"] if horizontal else y,
                                 name=str(nome), marker_color=cor,
                                 orientation="h" if horizontal else "v"))
            continue
        inc, marcador, texto, hover = _estilo_pontos(sub, lang)
        marcador["color"] = cor
        fig.add_trace(go.Scatter(x=sub["ano"], y=y, name=str(nome), line=dict(color=cor),
                                 mode="lines+markers+text" if tipo == "line" else "markers+text",
                                 marker=marcador, text=texto, textposition="top center",
                                 hovertext=hover, hoverinfo="x+y+text" if hover else None,
                                 cliponaxis=False))
    tem = bool(_incompleta(dens).any())
    eixo_d = T("colon.chart.density_axis", lang)
    fig.update_layout(barmode="group", xaxis_title=eixo_d if horizontal else T("colon.chart.year", lang),
                      yaxis_title=T("colon.chart.year", lang) if horizontal else eixo_d,
                      showlegend=dens["parcela"].nunique() > 1)
    _legenda_incompleta(fig, lang, tem)
    if escala_log:
        (fig.update_xaxes if horizontal else fig.update_yaxes)(type="log")
    _eixo_anos(fig, dens["ano"], horizontal, tipo in ("bar", "hbar"))
    return _fecha(fig, estilos, T("colon.chart.density_title", lang))


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
    inc = set(sub.loc[_incompleta(sub), "ano"].astype(int)) if len(sub) else set()
    rotulos = [f"{int(a)}*" if int(a) in inc else str(int(a)) for a in anos]
    fig = go.Figure()
    for esp, nome in nomes.items():
        d = sub[sub["especie"] == esp].set_index("ano").reindex(anos)
        fig.add_trace(go.Bar(x=rotulos, y=d[y].fillna(0), name=nome,
                             marker_color=cores[nome]))
    fig.update_layout(barmode="stack", xaxis_title=T("colon.chart.year", lang),
                      yaxis_title=T("colon.chart.relative_axis" if relativa
                                    else "colon.chart.density_axis", lang))
    fig.update_xaxes(type="category", tickangle=-45 if len(anos) > 12 else 0)
    if inc:
        fig.add_annotation(xref="paper", yref="paper", x=0, y=-0.28, showarrow=False,
                           xanchor="left", font=dict(size=11),
                           text="* " + T("colon.chart.incomplete_legend", lang))
    if relativa:
        fig.update_yaxes(range=[0, 100])
    return ui._layout(fig, estilos, T("colon.chart.species_title", lang, plot=parcela))


def fig_altura(est, estilos, lang=None, tipo="line_sd"):
    """Height (cm, or m when so chosen: ``est`` is already converted) of juveniles, per plot
    (and species or class, when the table has those columns). ``est`` is the table of
    ``estatistica_altura``. ``tipo``: line, markers, bar, hbar, line_sd, markers_sd or bar_sd
    (the *_sd types add one standard deviation)."""
    lang = ui._lang(lang)
    T = i18n.t
    cores = estilos["paleta"]
    chave = ["parcela"] + [c for c in ("especie", "classe") if c in est.columns]
    horizontal = tipo == "hbar"
    com_dp = tipo.endswith("_sd") or horizontal
    fig = go.Figure()
    for i, (k, sub) in enumerate(est.groupby(chave, sort=True)):
        sub = sub.sort_values("ano")
        k = k if isinstance(k, tuple) else (k,)
        partes = []
        for c, x in zip(chave, k):
            partes.append(str(x) if c == "parcela" else nome_especie(x) if c == "especie"
                          else T(f"colon.cls.{x}", lang))
        nome = " ".join(partes)
        cor = cores[i % len(cores)]
        dp = sub["dp"].fillna(0)
        # the standard deviation is drawn upwards only (the bar goes from the mean to mean + SD)
        cima = lambda eixo: {eixo: dict(type="data", symmetric=False, array=dp, arrayminus=dp * 0,
                                        visible=True, thickness=1)}
        if tipo in ("bar", "bar_sd", "hbar"):
            if horizontal:
                fig.add_trace(go.Bar(x=sub["media"], y=sub["ano"], name=nome, marker_color=cor,
                                     orientation="h", **cima("error_x")))
            else:
                fig.add_trace(go.Bar(x=sub["ano"], y=sub["media"], name=nome, marker_color=cor,
                                     **(cima("error_y") if tipo == "bar_sd" else {})))
            continue
        inc, marcador, texto, hover = _estilo_pontos(sub, lang)
        marcador["color"] = cor
        fig.add_trace(go.Scatter(
            x=sub["ano"], y=sub["media"], name=nome, marker=marcador, text=texto,
            mode="lines+markers+text" if tipo in ("line", "line_sd") else "markers+text",
            line=dict(color=cor), textposition="top center", hovertext=hover,
            hoverinfo="x+y+text" if hover else None, cliponaxis=False,
            **(cima("error_y") if tipo.endswith("_sd") else {})))
    n_series = len(fig.data)
    eixo_h = T("colon.chart.height_axis", lang, u=ui.altura_unidade())
    fig.update_layout(barmode="group", showlegend=n_series > 1,
                      xaxis_title=eixo_h if horizontal else T("colon.chart.year", lang),
                      yaxis_title=T("colon.chart.year", lang) if horizontal else eixo_h)
    _legenda_incompleta(fig, lang, bool(_incompleta(est).any()))
    _eixo_anos(fig, est["ano"], horizontal, tipo in ("bar", "bar_sd", "hbar"))
    (fig.update_xaxes if horizontal else fig.update_yaxes)(rangemode="tozero")
    return _fecha(fig, estilos, T("colon.chart.height_title", lang))


def fig_cruzamento_linha(cruz, estilos, lang=None, escala_log=False):
    """Density (left axis) and mean height (right axis) of juveniles over the years, one
    pair of lines per plot. ``cruz`` is ``cruzar_altura_densidade`` (heights already in the
    unit shown)."""
    lang = ui._lang(lang)
    T = i18n.t
    cores = estilos["paleta"]
    fig = go.Figure()
    for i, (parc, sub) in enumerate(cruz.groupby("parcela", sort=True)):
        sub = sub.sort_values("ano")
        cor = cores[i % len(cores)]
        _, marcador, texto, hover = _estilo_pontos(sub, lang)
        marcador["color"] = cor
        fig.add_trace(go.Scatter(
            x=sub["ano"], y=sub["ind_ha"], mode="lines+markers+text", name=f"{parc} {T('colon.cross.density_short', lang)}",
            line=dict(color=cor), marker=marcador, text=texto, textposition="top center",
            hovertext=hover, hoverinfo="x+y+text" if hover else None))
        fig.add_trace(go.Scatter(
            x=sub["ano"], y=sub["altura"], mode="lines+markers", yaxis="y2",
            name=f"{parc} {T('colon.cross.height_short', lang)}",
            line=dict(color=cor, dash="dash"), marker=dict(size=6, symbol="square", color=cor),
            error_y=dict(type="data", array=sub["dp"].fillna(0), visible=True, thickness=1)))
    fig.update_layout(
        xaxis_title=T("colon.chart.year", lang),
        yaxis=dict(title=T("colon.chart.density_axis", lang),
                   type="log" if escala_log else "linear"),
        yaxis2=dict(title=T("colon.chart.height_axis", lang, u=ui.altura_unidade()),
                    overlaying="y", side="right", showgrid=False, hoverformat=",.2f"),
        showlegend=True)
    _legenda_incompleta(fig, lang, bool(_incompleta(cruz).any()))
    _anos(fig, cruz["ano"])
    return _fecha(fig, estilos, T("colon.cross.line_title", lang))


def fig_cruzamento_xy(cruz, estilos, lang=None, x="densidade", escala_log=False, reta=True):
    """Mean height against density, one point per plot and year (the year is written by the
    point). ``x`` is "densidade" (density on X, height on Y) or "altura" (the reverse)."""
    lang = ui._lang(lang)
    T = i18n.t
    cores = estilos["paleta"]
    u = ui.altura_unidade()
    eixo_d = T("colon.chart.density_axis", lang)
    eixo_h = T("colon.chart.height_axis", lang, u=u)
    fig = go.Figure()
    for i, (parc, sub) in enumerate(cruz.groupby("parcela", sort=True)):
        sub = sub.sort_values("ano")
        _, marcador, _, hover = _estilo_pontos(sub, lang, tamanho=9)
        marcador["color"] = cores[i % len(cores)]
        xs, ys = (sub["ind_ha"], sub["altura"]) if x == "densidade" else (sub["altura"], sub["ind_ha"])
        anos = [f"{a}*" if inc else str(a) for a, inc in zip(sub["ano"], _incompleta(sub))]
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="markers+text", name=str(parc), marker=marcador, text=anos,
            textposition="top center", hovertext=hover, hoverinfo="x+y+text" if hover else None))
    if reta:                                    # least-squares line of each plot (y = a + b x)
        from manguetree import colonizacao as col
        for i, (parc, sub) in enumerate(cruz.groupby("parcela", sort=True)):
            xs, ys = (sub["ind_ha"], sub["altura"]) if x == "densidade" else (sub["altura"], sub["ind_ha"])
            r = col.regressao_linear(xs, ys)
            if r is not None and not escala_log:
                gx = np.linspace(float(xs.min()), float(xs.max()), 20)
                fig.add_trace(go.Scatter(x=gx, y=r["a"] + r["b"] * gx, mode="lines", showlegend=False,
                                         hoverinfo="skip", line=dict(color=cores[i % len(cores)],
                                                                     width=1.4, dash="dot")))
    fig.update_layout(xaxis_title=eixo_d if x == "densidade" else eixo_h,
                      yaxis_title=eixo_h if x == "densidade" else eixo_d, showlegend=True)
    if escala_log:
        fig.update_xaxes(type="log") if x == "densidade" else fig.update_yaxes(type="log")
    _legenda_incompleta(fig, lang, bool(_incompleta(cruz).any()))
    return _fecha(fig, estilos, T("colon.cross.xy_title", lang))


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
        inc, marcador, texto, hover = _estilo_pontos(sub, lang, 8)
        marcador["color"] = cor[n]
        fig.add_trace(go.Scatter(x=sub["idade"], y=sub["ind_ha"], mode="markers+text",
                                 name=str(n), marker=marcador, text=texto,
                                 textposition="top center", hovertext=hover,
                                 hoverinfo="x+y+text" if hover else None))
    _legenda_incompleta(fig, lang, bool(_incompleta(d).any()))
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


def _teto(v):
    """Round ``v`` up to a round number (1, 2, 2.5, 5 times a power of ten)."""
    import math
    if v <= 0:
        return 1.0
    p = 10.0 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if v <= m * p:
            return m * p
    return 10 * p


def _milhar(v, lang):
    """Whole number with thousands separator of the language (10.000 in pt, 10,000 in en)."""
    txt = f"{v:,.0f}"
    return txt.replace(",", ".") if lang == "pt" else txt


def _eixo_valores(fig, eixo, vmax, vmin, log, lang):
    """Value axis with complete numbers: linear from 0, or log with 1; 10; 100; 1.000..."""
    if log:
        import math
        lo, hi = math.floor(math.log10(max(vmin, 1e-9))), math.ceil(math.log10(max(vmax, 1)))
        lo = min(lo, 0)
        ticks = [10.0 ** k for k in range(lo, hi + 1)]
        upd = dict(type="log", range=[lo, hi], tickmode="array", tickvals=ticks,
                   ticktext=[_milhar(v, lang) if v >= 1 else f"{v:g}".replace(".", ",")
                             for v in ticks], exponentformat="none")
    else:
        topo = _teto(vmax * 1.05)
        upd = dict(type="linear", range=[0, topo], tickformat=",d", exponentformat="none")
    (fig.update_yaxes if eixo == "y" else fig.update_xaxes)(**upd)


def fig_idade(df, regs, estilos, lang=None, tipo="markers", log=False, curva=False):
    """Density (ind/ha) against plot age. Age on X from 0 to 10 years (more only if a plot is
    older), density with complete numbers, linear or log. ``tipo``: markers, line, bar or hbar. ``regs`` {label: fit} and ``curva``: draw the fitted curve y = exp(a) x^b. The plot
    area is square (the page sets the size, see ``TAMANHO_IDADE``)."""
    lang = ui._lang(lang)
    T = i18n.t
    cores = estilos["paleta"]
    d = df[(df["idade"] > 0) & (df["ind_ha"] > 0)].copy()
    horizontal = tipo == "hbar"
    ax_idade, ax_val = ("y", "x") if horizontal else ("x", "y")
    fig = go.Figure()
    nomes = sorted(d["parcela"].unique())
    cor = {n: cores[i % len(cores)] for i, n in enumerate(nomes)}
    for n in nomes:
        sub = d[d["parcela"] == n].sort_values("idade")
        if tipo in ("bar", "hbar"):
            fig.add_trace(go.Bar(x=sub["ind_ha"] if horizontal else sub["idade"],
                                 y=sub["idade"] if horizontal else sub["ind_ha"],
                                 name=str(n), marker_color=cor[n],
                                 orientation="h" if horizontal else "v"))
            continue
        inc, marcador, texto, hover = _estilo_pontos(sub, lang, 8)
        marcador["color"] = cor[n]
        fig.add_trace(go.Scatter(
            x=sub["idade"], y=sub["ind_ha"], name=str(n), marker=marcador, text=texto,
            mode="lines+markers+text" if tipo == "line" else "markers+text",
            line=dict(color=cor[n]), textposition="top center", hovertext=hover,
            hoverinfo="x+y+text" if hover else None, cliponaxis=False))
    tem_inc = bool(_incompleta(d).any())
    if curva and tipo not in ("bar", "hbar"):
        xs = np.linspace(max(float(d["idade"].min()), 0.25) if not d.empty else 0.25,
                         max(float(d["idade"].max()), 1.0) if not d.empty else 1.0, 80)
        for rotulo, r in regs.items():
            if r is None:
                continue
            nm = (T("colon.chart.fit_all", lang) if rotulo == "" else
                  T("colon.chart.fit_plot", lang, plot=rotulo))
            fig.add_trace(go.Scatter(x=xs, y=np.exp(r["a"]) * xs ** r["b"], mode="lines",
                                     name=nm, line=dict(color="#C0504D" if rotulo == "" else
                                                        cor.get(rotulo, "#5F726A"), width=1.8,
                                                        dash="solid" if rotulo == "" else "dash")))
    vmax = float(d["ind_ha"].max()) if not d.empty else 1.0
    vmin = float(d["ind_ha"].min()) if not d.empty else 1.0
    amax = max(10, int(np.ceil(d["idade"].max()))) if not d.empty else 10
    fig.update_layout(barmode="group", showlegend=True,
                      xaxis_title=T("colon.chart.density_axis" if horizontal else "colon.chart.age_axis", lang),
                      yaxis_title=T("colon.chart.age_axis" if horizontal else "colon.chart.density_axis", lang),
                      legend=dict(x=0.015, y=0.985, xanchor="left", yanchor="top",
                                  bgcolor="rgba(255,255,255,0.8)", bordercolor="#D5DDD8",
                                  borderwidth=0.5))
    _eixo_valores(fig, ax_val, vmax, vmin, log, lang)
    (fig.update_yaxes if horizontal else fig.update_xaxes)(
        type="linear", range=[0, amax + 0.5], tickmode="linear", tick0=0,
        dtick=2 if amax <= 10 else 5)
    fig = ui._layout(fig, estilos, T("colon.chart.regression_title", lang))
    fig.update_layout(margin=dict(t=46, r=24, b=96, l=72))
    if tem_inc:                                  # what the open diamond means, under the axis title
        fig.add_annotation(xref="paper", yref="paper", x=0, y=-0.2, xanchor="left", yanchor="top",
                           showarrow=False, font=dict(size=10),
                           text="◇* " + T("colon.chart.incomplete_legend", lang))
    return fig


#: size (px) that makes the plotting area of ``fig_idade`` square with its margins
TAMANHO_IDADE = (514, 560)          # width, height


def alinhar(*figs, topo=70, base=150):
    """Give charts shown side by side the same margins (and no automatic margins), so their
    axes start and end at the same heights."""
    for f in figs:
        f.update_layout(margin=dict(t=topo, b=base, l=72, r=24))
        f.update_xaxes(automargin=False)
        f.update_yaxes(automargin=False)
    return figs


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
    return ui._layout(fig, estilos, T("colon.chart.schema_title", lang))


def cores_contagem(grupos, agrupar, estilos):
    """Default colour of each group of ``fig_contagem`` (cohorts: Viridis, grey for the ones
    without a cohort; species: their own colours; others: the page palette)."""
    from manguetree import colonizacao as col
    import plotly.colors as pcolors
    if agrupar == "coorte":
        n = max(len(grupos) - (col.SEM_COORTE in grupos), 1)
        tons = pcolors.sample_colorscale("Viridis", [i / max(n - 1, 1) for i in range(n)])
        cores = {g: tons[i] for i, g in enumerate(x for x in grupos if x != col.SEM_COORTE)}
        cores[col.SEM_COORTE] = "#B8C2BC"
    elif agrupar == "especie":
        c = ui.species_colors([nome_especie(g) for g in grupos])
        cores = {g: c[nome_especie(g)] for g in grupos}
    else:
        paleta = estilos["paleta"]
        cores = {g: paleta[i % len(paleta)] for i, g in enumerate(grupos)}
    return cores


def nome_grupo(g, agrupar, lang=None):
    """Legend text of a group of ``fig_contagem``."""
    from manguetree import colonizacao as col
    lang = ui._lang(lang)
    T = i18n.t
    return (T("colon.cohort.none", lang) if g == col.SEM_COORTE else
            nome_especie(g) if agrupar == "especie" else
            T(f"colon.cls.{g}", lang) if agrupar == "classe" else str(g))


def hex_cor(c):
    """"#RRGGBB" of a colour given as "#RRGGBB" or "rgb(r, g, b)" (colour pickers need hex)."""
    c = str(c).strip()
    if c.startswith("#"):
        return c if len(c) == 7 else "#" + "".join(ch * 2 for ch in c[1:4])
    r, g, b = [int(float(v)) for v in c[c.index("(") + 1:c.index(")")].split(",")[:3]]
    return f"#{r:02X}{g:02X}{b:02X}"


def gradiente(base, grupos):
    """Light to dark tones of one base colour, one per group, in the order given."""
    base = hex_cor(base)
    r, g, b = (int(base[i:i + 2], 16) for i in (1, 3, 5))
    n = max(len(grupos), 1)
    out = {}
    for i, gr in enumerate(grupos):
        f = 0.35 + 0.65 * (i / (n - 1) if n > 1 else 1.0)       # share of the base colour
        out[gr] = "#%02X%02X%02X" % tuple(int(round(255 - (255 - v) * f)) for v in (r, g, b))
    return out


def grupos_contagem(df, agrupar):
    """Groups of a count table, in the order they are drawn."""
    from manguetree import colonizacao as col
    g = df["grupo"].unique()
    return col.ordem_coortes(g) if agrupar == "coorte" else sorted(g)


def fig_contagem(df, estilos, lang=None, agrupar="coorte", percentual=False, cores_usuario=None):
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
    cores = cores_contagem(grupos, agrupar, estilos)
    if cores_usuario:
        cores = {**cores, **{g: c for g, c in cores_usuario.items() if g in cores}}
    total = d.groupby("ano")["n"].sum()
    fig = go.Figure()
    for g in grupos:
        sub = d[d["grupo"] == g].set_index("ano").reindex(anos)["n"].fillna(0)
        y = (100 * sub / total.reindex(anos)).fillna(0) if percentual else sub
        nome = nome_grupo(g, agrupar, lang)
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
