from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from manguetree import calc as mc
from manguetree import charts as ui
from manguetree import io as mio
from manguetree.species import SpeciesResolver, load_genus_defaults, load_species_table

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "manguetree" / "app"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
H2 = ROOT / "data" / "guaratiba_H2_2003_2025.xlsx"
RES = SpeciesResolver(load_species_table(), "BR_S_SE", load_genus_defaults())


def _two_years():
    out = []
    for y in ("2003", "2004"):
        df, a = mio.load_excel_sheet(str(H2), y, "", 100.0)
        out.append(mc.analyze(df, a, RES))
    return out


def test_plot_parameters_has_everything_the_lab_asked_for():
    p = mc.plot_parameters(_two_years()[0])
    for k in ("mean_dbh_cm", "height_mean_m", "canopy_height_m", "density_live_ha",
              "density_dead_ha", "density_total_ha", "ba_live_ha", "ba_dead_ha", "ba_total_ha",
              "complexity_2_5", "complexity_10", "mortality_ba_pct", "n_dead_no_dbh"):
        assert k in p, k
    assert any(k.startswith("density_live_ha [") for k in p)
    assert ui.label("density_live_ha [2.5–10]", "pt").endswith("[2.5–10 cm]")


def test_species_shares_add_up():
    sp = mc.species_parameters(_two_years()[0])
    assert abs(sp["share_density_live_pct"].sum() - 100) < 1e-9
    assert abs(sp["share_ba_dead_pct"].sum() - 100) < 1e-9


def test_dynamics_rates():
    r0, r1 = _two_years()
    d = mc.dynamics(r0, r1, (2003, 2004))
    assert d["survivors"] + d["deaths"] == d["live_trees_start"]
    assert 0 <= d["mortality_rate_pct_yr"] <= 100


def test_species_stack100_columns_sum_to_100():
    df = pd.DataFrame({"year": [2003, 2003, 2004, 2004], "species": ["A", "B", "A", "B"],
                       "density_live_ha": [30.0, 10.0, 5.0, 15.0]})
    fig = ui.fig_species_series(df, {"paleta": ["#000"]}, "density_live_ha", "stack100")
    tot = [sum(tr.y[i] for tr in fig.data) for i in range(2)]
    assert all(abs(x - 100) < 1e-9 for x in tot)


def test_temporal_page_with_two_plots():
    at = AppTest.from_file(str(APP / "pages" / "3_Temporal.py"), default_timeout=300).run()
    data = H2.read_bytes()
    at.file_uploader[0].set_value([("H2.xlsx", data, XLSX), ("H2b.xlsx", data, XLSX)]).run()
    next(b for b in at.button if "Run" in b.label).click().run()
    assert not at.exception
    serie = at.session_state["temp_serie"]
    assert set(serie["plot"]) == {"H2", "H2b"}
    assert "height_mean_m" in serie.columns
    assert at.session_state["temp_dyn"] is not None
