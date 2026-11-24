# -*- coding: utf-8 -*-
"""Chart types of the yearly series (line, points, columns, horizontal bars, with SD)."""
import pandas as pd
import pytest

from manguetree import charts as ui

ESTILOS = {"paleta": ["#2e8b57", "#2a4d69"]}
DF = pd.DataFrame({"plot": ["A"] * 3 + ["B"] * 3, "year": [2010, 2012, 2014] * 2,
                   "height_mean_m": [3, 4, 5, 2, 3, 4.], "height_sd_m": [.5] * 6,
                   "density_live_ha": [1, 2, 3, 3, 2, 1.]})


@pytest.mark.parametrize("chart", ui.SERIES_CHARTS)
@pytest.mark.parametrize("view", ["plots", "mean"])
def test_every_series_chart_draws(chart, view):
    for y in ("height_mean_m", "density_live_ha"):
        fig = ui.fig_series(DF, ESTILOS, y, view, chart, "pt")
        assert len(fig.data) >= 1


def test_sd_only_for_parameters_that_have_one():
    com = ui.fig_series(DF, ESTILOS, "height_mean_m", "plots", "line_sd", "pt")
    sem = ui.fig_series(DF, ESTILOS, "density_live_ha", "plots", "line_sd", "pt")
    assert com.data[0].error_y.array is not None and list(com.data[0].error_y.array) == [.5] * 3
    assert sem.data[0].error_y.array is None


def test_horizontal_bars_put_the_years_on_the_vertical_axis():
    fig = ui.fig_series(DF, ESTILOS, "density_live_ha", "plots", "hbar", "pt")
    assert fig.data[0].orientation == "h" and list(fig.data[0].y) == ["2010", "2012", "2014"]


def test_species_fixed_order():
    from manguetree import charts as mc
    mix = ["Laguncularia racemosa", "Unidentified", "Avicennia schaueriana", "Rhizophora mangle", "Conocarpus erectus"]
    ordem = mc.ordem_especies(mix)
    assert [e.split()[0] for e in ordem] == ["Rhizophora", "Avicennia", "Laguncularia", "Conocarpus", "Unidentified"]
    assert mc.chave_especie("Rhizophora mangle") < mc.chave_especie("Avicennia schaueriana") < mc.chave_especie("Laguncularia racemosa")


def test_ordena_tracos_only_species():
    import plotly.graph_objects as go
    from manguetree import charts as mc
    fig = go.Figure([go.Bar(name="Avicennia schaueriana", x=[1], y=[1]), go.Bar(name="Rhizophora mangle", x=[1], y=[1])])
    assert [t.name for t in mc._ordena_tracos(fig).data][0].startswith("Rhizophora")
    fig2 = go.Figure([go.Bar(name="B", x=[1], y=[1]), go.Bar(name="A", x=[1], y=[1])])
    assert [t.name for t in mc._ordena_tracos(fig2).data] == ["B", "A"]
