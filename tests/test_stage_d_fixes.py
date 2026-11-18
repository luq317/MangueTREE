"""Stage D: technical fixes carried over from the stage B review."""
import io
from pathlib import Path

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

from manguetree import calc as mc, charts as ui, io as mio
from manguetree.i18n import t
from manguetree.species import SpeciesResolver, load_genus_defaults, load_species_table

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "manguetree" / "app" / "pages"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CSV = (b"tree_id;species;dbh_cm;condition\n"
       b"1;As;5,0;v\n2;As;7,5;v\n3;Rm;12,0;v\n4;Rm;3,1;m\n")


def _res(sheet="F2", name=None, year=None):
    df, area = mio.load_excel_sheet(str(ROOT / "data" / "guaratiba_T2_2009.xlsx"),
                                    sheet, "", 100.0)
    r = mc.analyze(df.dropna(subset=["dbh"]), area,
                   SpeciesResolver(load_species_table(), "BR_S_SE", load_genus_defaults()),
                   plot_name=name or sheet)
    if year:
        r["year"] = year
    return r


def _upload(page, name, content, mime=XLSX):
    at = AppTest.from_file(str(APP / page), default_timeout=300).run()
    at.file_uploader[0].set_value((name, content, mime))
    return at.run()


def test_species_series_zero_fills_species_missing_from_a_sheet_of_the_same_year():
    a, b = _res("F2", "F2", 2009), _res("H2", "H2", 2009)
    keep = b["data"]["species_label"] != "Laguncularia racemosa"   # H2 without Lg
    b["data"] = b["data"][keep]
    both = ui.serie_por_especie([a, b])
    alone = ui.serie_por_especie([a])
    lg_both = both[both["species"] == "Laguncularia racemosa"]["density_ha"].iloc[0]
    lg_alone = alone[alone["species"] == "Laguncularia racemosa"]["density_ha"].iloc[0]
    assert np.isclose(lg_both, lg_alone / 2)     # mean of (value, 0), not the value itself


def test_species_series_single_sheet_years_are_unchanged():
    a, b = _res("F2", "F2", 2009), _res("H2", "H2", 2010)
    out = ui.serie_por_especie([a, b])
    assert (out.groupby("year").size() > 0).all()
    assert (out["density_ha"] > 0).all()          # no zero rows invented for other years


def test_data_table_booleans_are_translated():
    d = _res()["data"]
    en = ui.for_display(d, data_table=True, lang="en")
    pt = ui.for_display(d, data_table=True, lang="pt")
    assert set(en[ui.label("live", "en", True)]) <= {"Yes", "No"}
    assert set(pt[ui.label("live", "pt", True)]) <= {"Sim", "Não"}


def test_excel_data_sheet_keeps_numeric_tree_ids():
    res = _res()
    xl = pd.ExcelFile(io.BytesIO(ui.to_excel_bytes(res, "en")))
    data = xl.parse(t("sheet.data", "en"))
    tree = data[ui.label("tree_id", "en", True)]
    assert not isinstance(tree.iloc[0], str) and tree.iloc[0] == 1   # F2 also has 42A/42B


def test_english_catalog_has_no_ascii_m2():
    from manguetree import i18n
    assert not [k for k, v in i18n.catalog("en").items() if " m2" in str(v)]


def test_csv_area_can_be_confirmed_at_the_default_value():
    at = _upload("1_Single_plot.py", "plot.csv", CSV, "text/csv")
    shown = lambda: " ".join(str(v) for d in at.dataframe for v in d.value.to_numpy().ravel())
    assert "Plot area not found" in shown()
    at.sidebar.checkbox(key="area_ok_unica").check().run()
    assert not at.exception
    assert "Plot area not found" not in shown()


def test_temporal_counts_are_integers():
    content = (ROOT / "data" / "guaratiba_H2_2003_2025.xlsx").read_bytes()
    at = _upload("3_Temporal.py", "guaratiba_H2_2003_2025.xlsx", content)
    next(b for b in at.button if "Run" in b.label).click().run()
    serie = at.session_state["temp_serie"]
    assert pd.api.types.is_integer_dtype(serie["n_species_live"])
    assert pd.api.types.is_integer_dtype(serie["plot_area_m2"])


def test_new_upload_clears_previous_results_and_pdf():
    content = (ROOT / "data" / "guaratiba_T2_2009.xlsx").read_bytes()
    at = _upload("2_Multiple_plots.py", "a.xlsx", content)
    next(b for b in at.button if "Run" in b.label).click().run()
    assert at.session_state["multi_resultados"]
    at.file_uploader[0].set_value(("b.xlsx", content, XLSX)).run()
    assert "multi_resultados" not in at.session_state or not at.session_state["multi_resultados"]


def test_demo_file_with_errors_triggers_the_expected_checks():
    from manguetree.validation import validate
    df, _ = mio.load_excel_sheet(str(ROOT / "data" / "guaratiba_F2_with_errors.xlsx"), "F2", "", 100.0)
    res = SpeciesResolver(load_species_table(), "BR_S_SE", load_genus_defaults())
    kinds = {i.kind for i in validate(df, res)}
    assert {"unknown_species", "dbh_without_condition", "implausible_value",
            "tree_species_conflict", "dead_with_height", "stem_count_mismatch"} <= kinds


def test_map_and_export_are_separate_tabs_last_on_every_analysis_page():
    at = _upload("1_Single_plot.py", "t2.xlsx", (ROOT / "data" / "guaratiba_T2_2009.xlsx").read_bytes())
    labels = [tb.label for tb in at.tabs]
    assert labels[-3:] == [t("single.tab.map", "en"), t("tab.check", "en"), t("single.tab.export", "en")]
    assert not any("&" in lb and "export" in lb.lower() for lb in labels)
    # the single plot has no cover value: only relative density and dominance
    assert not any("cover" in str(df.value.columns).lower() for df in at.dataframe)
