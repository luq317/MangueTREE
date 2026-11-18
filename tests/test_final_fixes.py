"""Regression tests for the final whole-branch review of stage A."""
import io as _stdio
from pathlib import Path

import openpyxl
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from manguetree import calc, charts as ui, io as mio, report as rep
from manguetree.species import SpeciesResolver, load_genus_defaults, load_species_table
from manguetree.validation import normalise_condition, validate

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "manguetree" / "app"
G = 0.00007854


def _res(region="BR_S_SE", table=None):
    return SpeciesResolver(load_species_table() if table is None else table, region,
                           load_genus_defaults())


RES = _res()


def _kinds(issues):
    return [i.kind for i in issues]


def _xlsx(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(list(r))
    buf = _stdio.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


HEAD = ["tree_id", "n_stems", "species", "dbh_cm", "height_m", "condition"]


# ---------------------------------------------------------------- C1
def test_c1_text_dbh_is_reported_not_silently_dropped():
    csv = "tree_id;species;dbh;condition\n1;Rh;10;v\n2;Rh;1o,5;v\n"
    df = mio.load_csv(_stdio.StringIO(csv))
    iss = [i for i in validate(df, RES) if i.kind == "non_numeric_value"]
    assert len(iss) == 1 and iss[0].severity == "error" and iss[0].source_row == 3
    assert "1o,5" in iss[0].detail and iss[0].action == "excluded"
    assert calc.analyze(df, 100.0, RES)["summary"]["n_stems"] == 1


def test_c1_text_height_is_reported():
    csv = "tree_id;species;dbh;height;condition\n1;Rh;10;6,x;v\n"
    df = mio.load_csv(_stdio.StringIO(csv))
    iss = [i for i in validate(df, RES) if i.kind == "non_numeric_value"]
    assert len(iss) == 1 and iss[0].action == "height excluded" and "6,x" in iss[0].detail


def test_c1_stem_count_ignores_placeholder_rows():
    df = pd.DataFrame({"tree_id": [1, 1, 1], "n_stems": [1, 1, 1],
                       "species": ["Rh", "Rh", None], "dbh": [5.0, None, None],
                       "condition": ["v", "v", None], "source_row": [2, 3, 4]})
    # rows: DBH, condition only, nothing -> 2 stems recorded, but declared 1
    got = [i for i in validate(df, RES) if i.kind == "stem_count_mismatch"]
    assert len(got) == 1 and "2 rows" in got[0].detail
    df2 = df.iloc[[0, 2]]
    assert not [i for i in validate(df2, RES) if i.kind == "stem_count_mismatch"]


def _csv_page(tmp_path, text):
    f = tmp_path / "plot.csv"
    f.write_text(text, encoding="utf-8")
    at = AppTest.from_file(str(APP / "pages" / "1_Single_plot.py"),
                           default_timeout=120).run()
    up = next(u for u in at.sidebar.file_uploader if u.key == "upload_unico")
    up.set_value(("plot.csv", f.read_bytes(), "text/csv"))
    return at.run()


def test_c1_upload_shows_no_dbh_and_text_dbh_issues(tmp_path):
    at = _csv_page(tmp_path, "Indivíduo;Espécie;DAP;Condição\n1;Rm;10;v\n2;Rm;;v\n"
                             "3;Rm;1o,5;v\n")
    assert not at.exception
    shown = " ".join(str(df.value.to_dict("list")) for df in at.dataframe)
    assert ui.issue_kind_label("condition_without_dbh", "en") in shown
    assert ui.issue_kind_label("non_numeric_value", "en") in shown
    assert "1o,5" in shown


# ---------------------------------------------------------------- C2
def test_c2_pooled_density_uses_sum_of_areas():
    results = []
    for sheet in ("F2", "H2", "J2"):
        df, area = mio.load_excel_sheet(ROOT / "data" / "guaratiba_T2_2009.xlsx", sheet)
        results.append(calc.analyze(df, area, RES, plot_name=sheet))
    tab = calc.pooled_importance(results)
    areas = [r["summary"]["plot_area_m2"] for r in results]
    n_ident = sum(int(r["data"][r["data"]["live"] & r["data"]["scientific_name"].notna()
                          & (r["data"]["dbh"] > 0)].shape[0]) for r in results)
    assert tab["density_ha"].sum() == pytest.approx(n_ident * 10000.0 / sum(areas))
    assert tab["n_stems"].sum() == n_ident
    ba = sum(r["data"].loc[r["data"]["live"] & r["data"]["scientific_name"].notna()
                           & (r["data"]["dbh"] > 0), "basal_area_m2"].sum()
             for r in results)
    assert tab["ba_ha"].sum() == pytest.approx(ba * 10000.0 / sum(areas))
    assert tab["ivi"].sum() == pytest.approx(300.0)


# ---------------------------------------------------------------- C3
def test_c3_non_positive_heights_are_not_used():
    df = pd.DataFrame({"tree_id": [1, 2, 3, 4], "species": ["Rh"] * 4,
                       "dbh": [5, 6, 7, 8], "height": [4.0, 0.0, -3.0, 6.0],
                       "condition": ["v"] * 4})
    s = calc.analyze(df, 100.0, RES)["summary"]
    assert s["height_mean_m"] == 5.0 and s["height_min_m"] == 4.0
    assert s["canopy_height_m"] == 5.0


def test_c3_height_validation_actions():
    df = pd.DataFrame({"tree_id": [1, 2], "species": ["Rh", "Rh"], "dbh": [0.0, 5.0],
                       "height": [3.0, -2.0], "condition": ["v", "v"],
                       "source_row": [2, 3]})
    bad = [i for i in validate(df, RES) if i.kind == "implausible_value"]
    acts = {i.source_row: i.action for i in bad}
    assert acts == {2: "excluded", 3: "height excluded"}


# ------------------------------------------------- I9 rule + science pins
def test_i9_every_issue_action_matches_behaviour():
    df = pd.DataFrame({
        "tree_id": [1, 2, 3, 4, 5, 6],
        "species": ["Rh"] * 6,
        "dbh": [10.0, 5.0, 7.0, 0.0, 8.0, 9.0],
        "height": [5.0, 4.0, None, 3.0, -1.0, 6.0],
        "condition": ["v", "m", "x", "v", "v", "m"],
        "source_row": [2, 3, 4, 5, 6, 7]})
    r = calc.analyze(df, 100.0, RES)
    s, iss = r["summary"], r["issues"]
    by = {(i.kind, i.source_row): i for i in iss}
    # "excluded": unknown condition (row 4) and DBH 0 (row 5) are not counted
    assert by[("unknown_condition", 4)].action == "excluded"
    assert by[("implausible_value", 5)].action == "excluded"
    assert s["n_stems"] == 4 and s["n_live"] == 2 and s["n_dead"] == 2
    # "height excluded" (row 6, -1) and "height ignored" (dead rows) stay out of heights
    assert by[("implausible_value", 6)].action == "height excluded"
    assert by[("dead_with_height", 7)].action == "height ignored"
    assert s["height_mean_m"] == 5.0 and s["height_max_m"] == 5.0


def _pin_plot():
    return pd.DataFrame({
        "tree_id": list(range(1, 11)),
        "species": ["Rh", "Rh", "As", "As", "Lg", "Rh", "As", "Rh", "Rh", "As"],
        "dbh": [1, 3, 5, 8, 11, 12, 15, 20, 4, 6],
        "height": [2, 3, 4, 5, 6, 7, 8, 9, None, None],
        "condition": ["v"] * 8 + ["m", "m"],
        "unit": ["u1", "u1", "u2", "u2", "u1", "u2", "u1", "u1", "u2", "u2"]})


def test_i9_frequency_pins():
    d = calc.prepare(_pin_plot(), RES)
    t = calc.importance_value(d, 100.0, unit_col="unit").set_index("species")
    # live stems: Rh in u1,u2 ; As in u1,u2 ; Lg in u1 only (2 units in total)
    assert t.loc["Rhizophora mangle", "abs_frequency"] == pytest.approx(100.0)
    assert t.loc["Avicennia schaueriana", "abs_frequency"] == pytest.approx(100.0)
    assert t.loc["Laguncularia racemosa", "abs_frequency"] == pytest.approx(50.0)
    # relative: 100/250, 100/250, 50/250
    assert t.loc["Rhizophora mangle", "rel_frequency"] == pytest.approx(40.0)
    assert t.loc["Avicennia schaueriana", "rel_frequency"] == pytest.approx(40.0)
    assert t.loc["Laguncularia racemosa", "rel_frequency"] == pytest.approx(20.0)


def test_i9_mortality_pins():
    s = calc.structural_summary(calc.prepare(_pin_plot(), RES), 100.0)
    assert s["mortality_stems_pct"] == pytest.approx(20.0)           # 2 dead / 10 stems
    ba_live = G * (1 + 9 + 25 + 64 + 121 + 144 + 225 + 400)           # 989
    ba_dead = G * (16 + 36)                                            # 52
    assert s["mortality_ba_pct"] == pytest.approx(100 * 52 / 1041)
    assert s["mortality_ba_pct"] == pytest.approx(100 * ba_dead / (ba_live + ba_dead))


def test_i9_dbh_class_labels_use_ge_for_closed_left_classes():
    df = pd.DataFrame({"tree_id": [1, 2], "species": ["Rh", "Rh"], "dbh": [2.5, 10.0],
                       "height": [3, 5], "condition": ["v", "v"]})
    dens, _ = calc.dbh_classes(calc.prepare(df, RES), 100.0)
    assert dens.loc["≥ 10"].sum() == pytest.approx(100.0)
    assert "> 10" not in dens.index


def test_dbh_class_cuts_must_increase():
    d = calc.prepare(_pin_plot(), RES)
    for bad in ((10.0, 10.0), (10.0, 2.5)):
        with pytest.raises(ValueError, match="increas"):
            calc.dbh_classes(d, 100.0, limits=bad)


# ---------------------------------------------------------------- I2 area
def test_i2_text_area_and_portuguese_label():
    rows = [["Área (m²)", "225,0"], [], HEAD, [1, 1, "As", 10.0, 6.0, "v"]]
    df, area = mio.load_excel_sheet(_xlsx(rows), 0)
    assert area == 225.0 and df.attrs["area_source"] == "label"
    rows = [["Parcela (m2):", 80], HEAD, [1, 1, "As", 10.0, 6.0, "v"]]
    df, area = mio.load_excel_sheet(_xlsx(rows), 0)
    assert area == 80.0 and df.attrs["area_source"] == "label"


def test_i2_cell_ref_text_area():
    rows = [["x", "y"], ["a", "b"], ["c", "d"], ["Parcela", "150,5"], HEAD,
            [1, 1, "As", 10.0, 6.0, "v"]]
    df, area = mio.load_excel_sheet(_xlsx(rows), 0, cell_ref="B4")
    assert area == 150.5 and df.attrs["area_source"] == "cell"


def test_i2_fallback_is_flagged():
    rows = [HEAD, [1, 1, "As", 10.0, 6.0, "v"]]
    df, area = mio.load_excel_sheet(_xlsx(rows), 0, area_fallback=100.0)
    assert area == 100.0 and df.attrs["area_source"] == "fallback"
    hits = [i for i in validate(df, RES) if i.kind == "area_fallback"]
    assert len(hits) == 1 and hits[0].severity == "warning" and "100" in hits[0].detail
    assert "area_fallback" in _kinds(calc.analyze(df, area, RES)["issues"])
    rows = [["plot_area_m2", 80], HEAD, [1, 1, "As", 10.0, 6.0, "v"]]
    df, _ = mio.load_excel_sheet(_xlsx(rows), 0)
    assert "area_fallback" not in _kinds(validate(df, RES))


# ---------------------------------------------------------------- I3
def test_i3_unresolved_species_are_in_class_tables_and_not_in_richness():
    north = _res("BR_N_NE")
    df = pd.DataFrame({"tree_id": [1, 2, 3], "species": ["Pe", "Rh", "Lg"],
                       "dbh": [5.0, 6.0, 7.0], "height": [3, 4, 5],
                       "condition": ["v"] * 3})
    r = calc.analyze(df, 100.0, north)
    dens, ba = r["dbh_density"], r["dbh_ba"]
    assert dens.to_numpy().sum() == pytest.approx(r["summary"]["density_live_ha"])
    assert ba.to_numpy().sum() == pytest.approx(r["summary"]["ba_live_ha"])
    assert "Unidentified" in dens.columns
    assert r["summary"]["n_species_live"] == 1
    assert list(r["importance"]["species"]) == ["Laguncularia racemosa"]
    te = ui.tabela_por_especie(r, "pt")
    assert "Não identificada" in te["Espécie"].tolist()
    assert "Unidentified" in ui.tabela_por_especie(r, "en")["Species"].tolist()
    assert te["Densidade viva (troncos/ha)"].sum() == pytest.approx(r["summary"]["density_live_ha"])
    long = ui.dados_especies_parcelas([r], "densidade")
    assert long.loc[long["condition"] == "live", "value"].sum() == pytest.approx(
        r["summary"]["density_live_ha"])


def test_i3_validation_action_text():
    df = pd.DataFrame({"tree_id": [1], "species": ["xx"], "dbh": [5.0],
                       "condition": ["v"], "source_row": [2]})
    act = [i.action for i in validate(df, RES) if i.kind == "unknown_species"]
    assert act == ["counted in totals; excluded from species richness and importance values"]


# ---------------------------------------------------------------- I4
def _two_species_res(height_dead=True):
    df = pd.DataFrame({"tree_id": [1, 2, 3, 4], "species": ["Rhizophora mangle",
                       "Rhizophora racemosa", "Rhizophora mangle", "Rhizophora mangle"],
                       "dbh": [5.0, 6.0, 7.0, 8.0], "height": [4.0, 5.0, 9.0, 0.0],
                       "condition": ["v", "v", "m", "v"]})
    return calc.analyze(df, 100.0, _res("BR_N_NE"))


def test_i4_height_dbh_charts_ignore_dead_and_non_positive():
    r = _two_species_res()
    fig, _ = ui.fig_altura_dap(r, {"paleta": ["#000"]})
    n_pts = sum(len(t.x) for t in fig.data if t.mode in (None, "markers"))
    assert n_pts == 2                      # dead (h=9) and h=0 are out
    f = rep._fig_alt_dap(r, "en", False)
    pts = sum(len(c.get_offsets()) for c in f.axes[0].collections)
    assert pts == 2


# ---------------------------------------------------------------- I5
def test_i5_species_of_one_genus_get_different_colors_and_labels():
    assert calc.species_color("Rhizophora mangle") != calc.species_color("Rhizophora racemosa")
    assert calc.species_short("Rhizophora mangle") == "R. mangle"
    r = _two_species_res()
    f = rep._fig_classes(r, "density", "en", False)
    labels = [t.get_text() for t in f.axes[0].get_legend().get_texts()]
    assert "R. mangle" in labels and "R. racemosa" in labels
    cm = ui.cor_por_especie(["Rhizophora mangle", "Rhizophora racemosa"])
    assert len(set(cm.values())) == 2
    pie = rep._fig_comp_ba(r, "en", False)
    texts = [t.get_text() for t in pie.axes[0].texts]
    assert any("R. mangle" in t for t in texts) and any("R. racemosa" in t for t in texts)


# ---------------------------------------------------------------- I6
def test_i6_user_alias_overrides_genus_default():
    tbl = load_species_table()
    tbl.loc[tbl["code"] == "Ag", "aliases"] += "|av"
    for region in ("BR_N_NE", "BR_S_SE"):
        res = SpeciesResolver(tbl, region, load_genus_defaults()).resolve("Av")
        assert res.code == "Ag" and res.status == "ok"
    # built-in behaviour untouched
    assert _res("BR_S_SE").resolve("As").code == "As"
    assert _res("BR_N_NE").resolve("Av").code == "As"


# ---------------------------------------------------------------- I7
def test_i7_cp1252_csv(tmp_path):
    p = tmp_path / "f.csv"
    p.write_bytes("Espécie;DAP;Condição;Indivíduo\nRh;10,5;v;1\n".encode("cp1252"))
    df = mio.load_csv(str(p))
    assert df["dbh"].tolist() == [10.5] and mio.has_required_columns(df)
    p.write_bytes("﻿Espécie;DAP;Condição;Indivíduo\nRh;10,5;v;1\n".encode("utf-8"))
    assert mio.has_required_columns(mio.load_csv(str(p)))
    assert mio.has_required_columns(mio.load_csv(_stdio.BytesIO(
        "Espécie;DAP;Condição;Indivíduo\nRh;10,5;v;1\n".encode("cp1252"))))


# ---------------------------------------------------------------- minors
def test_lone_alt_med_header_warns():
    rows = [["Indivíduo", "Espécie", "DAP", "Alt. med.", "Condição"], [1, "As", 10, 1.6, "v"]]
    df, _ = mio.load_excel_sheet(_xlsx(rows), 0)
    assert df["height"].tolist() == [1.6]
    assert "ambiguous_height_column" in _kinds(validate(df, RES))
    rows = [["Indivíduo", "Espécie", "DAP", "Alt. med.", "Alt. Corr.", "Condição"],
            [1, "As", 10, 1.6, 7.0, "v"]]
    df, _ = mio.load_excel_sheet(_xlsx(rows), 0)
    assert "ambiguous_height_column" not in _kinds(validate(df, RES))


@pytest.mark.parametrize("code, want", [("V.", "live"), ("m.", "dead"), ("v ", "live"),
                                        ("M.", "dead"), ("x.", None)])
def test_condition_codes_with_punctuation(code, want):
    assert normalise_condition(code) == want


def test_conocarpus_co_abbreviation():
    for region in ("BR_S_SE", "BR_N_NE", "CARIBBEAN_ATLANTIC", "EASTERN_PACIFIC"):
        assert _res(region).resolve("Co").code == "Ce"


def test_author_and_sp_suffixes():
    r = _res("BR_N_NE")
    assert r.resolve("Rhizophora mangle L.").code == "Rm"
    assert r.resolve("Avicennia germinans (L.) L.").code == "Ag"
    assert r.resolve("Laguncularia sp.").code == "Lg"
    assert r.resolve("Rhizophora spp.").status == "ambiguous"
    assert _res("BR_S_SE").resolve("Rhizophora sp").code == "Rm"


def test_unit_count_uses_units_with_any_live_stem():
    df = pd.DataFrame({"tree_id": [1, 2, 3], "species": ["Lg", "xx", "xx"],
                       "dbh": [5, 6, 7], "height": [3, 4, 5], "condition": ["v"] * 3,
                       "unit": ["u1", "u2", "u2"]})
    t = calc.importance_value(calc.prepare(df, RES), 100.0, unit_col="unit")
    assert t.loc[0, "abs_frequency"] == pytest.approx(50.0)   # u2 counts as a unit


def test_dead_choice_flags_dead_with_height():
    df = pd.DataFrame({"tree_id": [1], "species": ["Rh"], "dbh": [5.0], "height": [4.0],
                       "condition": [None], "source_row": [2]})
    assert "dead_with_height" not in _kinds(validate(df, RES))
    assert "dead_with_height" in _kinds(validate(df, RES, missing_condition="dead"))
    assert "dead_with_height" in _kinds(calc.analyze(df, 100.0, RES,
                                                     missing_condition="dead")["issues"])


def test_prepared_data_display_hides_raw_columns():
    df = mio.load_csv(_stdio.StringIO("tree_id;species;dbh;condition\n1;Rh;1o;v\n"))
    shown = ui.for_display(calc.prepare(df, RES), data_table=True)
    assert not [c for c in shown.columns if str(c).startswith("_")]


def test_data_readme_exists():
    t = (ROOT / "data" / "README.md").read_text(encoding="utf-8")
    assert "Guaratiba" in t and "(manuscript under review)" in t and "NEMA" in t


# ---------------------------------------------------------------- pages
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _temporal_upload(sheet_names):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name in sheet_names:
        ws = wb.create_sheet(name)
        for r in [["plot_area_m2", 100], HEAD, [1, 1, "As", 10.0, 6.0, "v"]]:
            ws.append(r)
    buf = _stdio.BytesIO()
    wb.save(buf)
    at = AppTest.from_file(str(APP / "pages" / "3_Temporal.py"), default_timeout=120).run()
    at.file_uploader[0].set_value(("t.xlsx", buf.getvalue(), XLSX_MIME))
    return at.run()


def test_temporal_warns_on_duplicate_year():
    """Reported once, after the analysis, by the duplicate_year issue (sheets analysed)."""
    at = _temporal_upload(["a 2010", "b 2010", "2012"])
    assert not at.exception
    next(b for b in at.button if "Run" in b.label).click()
    at.run()
    assert not at.exception
    kinds = [i.kind for v in at.session_state["temp_issues"].values() for i in v]
    assert kinds.count("duplicate_year") == 2
    assert not any("2010" in w.value for w in at.warning)      # no pre-analysis warning


def test_temporal_asks_for_year_when_sheet_has_none():
    at = _temporal_upload(["levantamento", "2012"])
    assert not at.exception
    assert any("detect the year" in w.value for w in at.warning)


def test_single_plot_equal_class_cuts_show_error_not_crash(tmp_path):
    f = tmp_path / "p.csv"
    f.write_text("Indivíduo;Espécie;DAP;Condição\n1;Rm;10;v\n", encoding="utf-8")
    at = AppTest.from_file(str(APP / "pages" / "1_Single_plot.py"), default_timeout=60).run()
    up = next(u for u in at.sidebar.file_uploader if u.key == "upload_unico")
    up.set_value(("p.csv", f.read_bytes(), "text/csv"))
    at.run()
    for n in at.sidebar.number_input:
        if n.label == "Cutoff 1":
            n.set_value(10.0)
    at.run()
    assert not at.exception
    assert any("must be different" in e.value for e in at.sidebar.error)
