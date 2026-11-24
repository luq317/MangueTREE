# -*- coding: utf-8 -*-
"""Height unit (m or cm): conversion of results, labels and the pages."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from manguetree import charts as ui
from manguetree import unidades

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "manguetree" / "app"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_conversion_scales_only_height_columns_and_does_not_repeat():
    df = pd.DataFrame({"height": [2.0, np.nan], "dbh": [10.0, 5.0], "height_mean_m": [3.0, 4.0]})
    out = unidades.na_unidade(df, "cm")
    assert out["height"].iloc[0] == 200.0 and out["dbh"].tolist() == [10.0, 5.0]
    assert out["height_mean_m"].tolist() == [300.0, 400.0]
    assert unidades.na_unidade(out, "cm") is out                    # marked: not converted twice
    assert df["height"].iloc[0] == 2.0                              # the original is untouched
    assert unidades.na_unidade(df, "m") is df


def test_conversion_of_results_and_lists():
    res = {"summary": {"height_mean_m": 9.0, "mean_dbh_cm": 10.0, "n_live": 3},
           "data": pd.DataFrame({"height": [1.5]})}
    out = unidades.na_unidade([res], "cm")[0]
    assert out["summary"] == {"height_mean_m": 900.0, "mean_dbh_cm": 10.0, "n_live": 3}
    assert out["data"]["height"].iloc[0] == 150.0 and res["summary"]["height_mean_m"] == 9.0


def test_factors():
    assert unidades.fator_m("cm") == 100.0 and unidades.fator_m("m") == 1.0
    assert unidades.fator_cm("m") == 0.01 and unidades.fator_cm("cm") == 1.0


def _single(unit):
    at = AppTest.from_file(str(APP / "pages" / "1_Single_plot.py"), default_timeout=180).run()
    at.file_uploader[0].set_value(("guaratiba_T2_2009.xlsx",
                                   (ROOT / "data" / "guaratiba_T2_2009.xlsx").read_bytes(), XLSX))
    at.run()
    if unit != "m":
        at.radio(key="unidade_altura").set_value(unit).run()
    return at


def test_single_plot_shows_the_height_in_the_chosen_unit():
    m = {x.label: x.value for x in _single("m").metric}
    at = _single("cm")
    assert not at.exception
    cm = {x.label: x.value for x in at.metric}
    assert "Mean height (m)" in m and "Mean height (cm)" in cm
    assert cm["Canopy height (cm)"] == "1287.00" and m["Canopy height (m)"] == "12.87"
