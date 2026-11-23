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


def test_live_dead_chart_hatches_the_dead_part():
    df = pd.DataFrame({"year": [2003, 2004], "species": ["A", "A"],
                       "density_live_ha": [30.0, 20.0], "density_dead_ha": [10.0, 5.0],
                       "density_total_ha": [40.0, 25.0]})
    fig = ui.fig_species_series(df, {"paleta": ["#000"]}, "live_dead_density", "stack")
    shapes = [tr.marker.pattern.shape for tr in fig.data]
    assert shapes == ["", "/"]
    assert list(fig.data[0].x) == ["2003", "2004"]          # no gaps by default


def test_dynamics_tab_is_gone():
    src = (APP / "pages" / "3_Temporal.py").read_text(encoding="utf-8")
    assert "dynamics" not in src


def test_palette_recolours_species():
    from streamlit.testing.v1 import AppTest as _AT  # noqa: F401
    import streamlit as st
    st.session_state[ui.PALETTE_STATE] = "lab"
    try:
        cores = ui.species_colors(["Rhizophora mangle", "Avicennia schaueriana"])
        assert cores["Avicennia schaueriana"] == ui.PALETAS["lab"][0]
    finally:
        st.session_state[ui.PALETTE_STATE] = "manguetree"
    assert ui.species_colors(["Rhizophora mangle"])["Rhizophora mangle"] == mc.species_color("Rhizophora mangle")


def test_pdf_data_check_comes_last(monkeypatch):
    from manguetree import report as rep
    seen = {}
    monkeypatch.setattr(rep, "_gerar", lambda title, sub, blocks, lang, seal, **kw: blocks)
    df, a = mio.load_excel_sheet(str(ROOT / "data" / "guaratiba_F2_with_errors.xlsx"), "F2", "", 100.0)
    blocks = rep.single_plot_report(mc.analyze(df, a, RES), lang="en")
    heads = [b[1] for b in blocks if b[0] == "h"]
    assert heads[-1] == rep.xml_escape(rep._T("en")("report.h.verification"))
    assert heads[0] != heads[-1]


def test_one_species_and_difference_charts():
    df = pd.DataFrame({"plot": ["A", "A", "B", "B"], "year": [2003, 2004, 2003, 2004],
                       "species": ["Rhizophora mangle"] * 4,
                       "ba_live_ha": [5.0, 6.0, 4.0, 7.0], "ba_dead_ha": [1.0, 0.5, 0.2, 0.0],
                       "ba_total_ha": [6.0, 6.5, 4.2, 7.0]})
    est = {"paleta": ["#000", "#111"]}
    f = ui.fig_one_species_plots(df, est, "Rhizophora mangle", "live_dead_ba", "pt")
    assert len(f.data) == 4 and f.data[1].marker.pattern.shape == "/"
    d = ui.fig_plot_difference(df, est, "A", "B", "live_dead_ba", "pt")
    assert [round(v, 2) for v in d.data[0].y] == [-1.8, 0.5]
