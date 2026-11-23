"""Theoretical curve of Jimenez, Lugo & Cintron (1985) and its use in the structure pages."""
import math

import numpy as np
import pandas as pd
import pytest

from manguetree import calc, charts as ui


def _estilos():
    return {"paleta": ui.PALETAS[next(iter(ui.PALETAS))], "tamanho_titulo": 14, "tamanho_eixos": 11,
            "seal": False, "bar_width": 0.8, "height": 450}


def test_constants_match_both_papers():
    # Cavalcanti et al. (2009), eq. 1: ln(y) = 8.92212 - 1.4934 ln(x), y in trees per 0.1 ha
    assert calc.JIMENEZ_LN_A == pytest.approx(8.92212, abs=1e-5)
    assert calc.JIMENEZ_B == 1.4934


def test_density_per_hectare():
    # Cavalcanti et al. (2009), Fig. 3: y = 74960 x^-1.493 in trees per ha
    for x in (2.0, 5.0, 8.38, 12.3):
        assert calc.jimenez_density_ha(x) == pytest.approx(74960 * x ** -1.493, rel=0.01)
    assert calc.jimenez_density_ha(1.0) == pytest.approx(74960)
    assert calc.jimenez_density_ha(10.0) == pytest.approx(10 * math.exp(8.92212 - 1.4934 * math.log(10)), rel=1e-4)


def test_density_array_and_invalid_dbh():
    out = calc.jimenez_density_ha(np.array([1.0, 2.0, 0.0, -3.0]))
    assert out[0] > out[1] > 0
    assert np.isnan(out[2]) and np.isnan(out[3])
    assert math.isnan(calc.jimenez_density_ha(0))


def test_figure_curve_and_points():
    df = pd.DataFrame({"plot": ["A", "B", "C"], "mean_dbh_cm": [4.0, 8.0, 0.0],
                       "density_live_ha": [9000, 2800, 100]})
    f = ui.fig_jimenez(df, _estilos(), "en")
    assert f.data[0].name == "Jiménez et al. (1985)"
    assert [t.name for t in f.data[1:]] == ["A", "B"]          # plot without DBH is left out
    assert list(f.data[0].y) == pytest.approx(list(calc.jimenez_density_ha(np.array(f.data[0].x))))
    assert f.layout.xaxis.type is None
    assert ui.fig_jimenez(df, _estilos(), "en", log=True).layout.yaxis.type == "log"


def test_figure_by_year_groups_by_plot():
    df = pd.DataFrame({"plot": ["A", "A", "B"], "label": ["2005", "2010", "2005"],
                       "mean_dbh_cm": [3.0, 5.0, 4.0], "density_live_ha": [9000, 5000, 7000]})
    f = ui.fig_jimenez(df, _estilos(), "pt", text="label", group="plot")
    assert [t.name for t in f.data[1:]] == ["A", "B"]
    assert list(f.data[1].text) == ["2005", "2010"]


def test_no_points_gives_no_figure():
    df = pd.DataFrame({"plot": ["A"], "mean_dbh_cm": [0.0], "density_live_ha": [0]})
    assert ui.fig_jimenez(df, _estilos(), "en") is None
