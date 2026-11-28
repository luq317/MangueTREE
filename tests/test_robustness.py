"""Regression tests for sheets with problems (robustness review, version 1.3.1)."""
import io as _io
from pathlib import Path

import openpyxl
import pandas as pd
from streamlit.testing.v1 import AppTest

from manguetree import calc, io, validation
from manguetree.species import SpeciesResolver, load_genus_defaults, load_species_table

RES = SpeciesResolver(load_species_table(), "BR_S_SE", load_genus_defaults())
APP = Path(__file__).resolve().parents[1] / "src" / "manguetree" / "app"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
HEAD = ["tree_id", "species", "dbh_cm", "height_m", "condition"]
ROWS = [[1, "Rh", 8.4, 6.2, "v"], [2, "Av", 12.1, 7.8, "v"], [3, "Lg", 4.0, 3.9, "m"]]


def _book(rows=ROWS, head=HEAD, top=None, merges=(), widths=None):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "P1"
    for r in (top or []):
        ws.append(r)
    ws.append(head)
    for r in rows:
        ws.append(r)
    for m in merges:
        ws.merge_cells(m)
    buf = _io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _read(buf, **kw):
    df, area = io.load_excel_sheet(buf, "P1", **kw)
    return df, area


def _kinds(df):
    return {i.kind for i in validation.validate(df, RES)}


def test_dbh_in_mm_is_converted_and_flagged():
    df, _ = _read(_book(rows=[[1, "Rh", 84, 6.2, "v"]], head=["tree_id", "species", "DAP (mm)", "height_m", "condition"]))
    assert abs(df["dbh"].iloc[0] - 8.4) < 1e-9
    assert "unit_converted" in _kinds(df)


def test_height_in_cm_is_converted():
    df, _ = _read(_book(rows=[[1, "Rh", 8.4, 620, "v"]], head=["tree_id", "species", "dbh_cm", "Altura (cm)", "condition"]))
    assert abs(df["height"].iloc[0] - 6.2) < 1e-9
    assert "unit_converted" in _kinds(df)


def test_area_in_hectares_is_converted():
    df, area = _read(_book(top=[["Área (ha)", 0.01]]))
    assert abs(area - 100.0) < 1e-6 and df.attrs["area_source"] == "label"
    assert "unit_converted" in _kinds(df)


def test_area_text_and_neighbour_cells():
    assert _read(_book(top=[["Área da parcela", "100 m²"]]))[1] == 100.0
    assert _read(_book(top=[["Área total", None, 225]]))[1] == 225.0
    assert _read(_book(top=[["Área"], [150]]))[1] == 150.0


def test_area_zero_is_reported_as_invalid():
    df, area = _read(_book(top=[["Área", 0]]))
    assert df.attrs["area_source"] == "fallback" and "area_invalid" in _kinds(df)


def test_big_sheet_is_read_in_full_and_truncation_is_reported():
    rows = [[i, "Rh", 5.0, 4.0, "v"] for i in range(1, 6001)]
    df, _ = _read(_book(rows=rows))
    assert len(df) == 6000 and not df.attrs.get("rows_truncated")
    rows = [[i, "Rh", 5.0, 4.0, "v"] for i in range(1, 20101)]
    df, _ = _read(_book(rows=rows))
    assert len(df) == 20000 and "rows_truncated" in _kinds(df)


def test_merged_cells_are_filled_down():
    rows = [[1, "Rh", 8.4, 6.2, "v"], [None, None, 5.0, None, None], [2, "Av", 12.1, 7.8, "v"]]
    df, _ = _read(_book(rows=rows, merges=["A2:A3", "B2:B3", "E2:E3"]))
    assert list(df["condition"][:2]) == ["v", "v"] and list(df["species"][:2]) == ["Rh", "Rh"]
    assert "merged_cells_filled" in _kinds(df)
    r = calc.analyze(df, 100.0, RES)
    assert r["summary"]["n_stems"] == 3


def test_formula_without_stored_value_is_reported():
    rows = [[1, "Rh", "=84/10", 6.2, "v"], [2, "Av", "=121/10", 7.8, "v"]]
    df, _ = _read(_book(rows=rows))
    assert df["dbh"].isna().all() and "formulas_without_value" in _kinds(df)


def test_empty_tree_column_counts_each_stem_as_a_tree():
    df = pd.DataFrame({"tree_id": [None, None, None], "species": ["Rh"] * 3, "dbh": [5.0, 6.0, 7.0],
                       "height": [None] * 3, "condition": ["v"] * 3, "source_row": [2, 3, 4]})
    s = calc.analyze(df, 100.0, RES)["summary"]
    assert s["n_live_trees"] == 3 and s["stems_per_tree"] == 1.0


def test_no_heights_warning():
    df, _ = _read(_book(rows=[[1, "Rh", 8.4, None, "v"]]))
    assert "no_heights" in _kinds(df)


def test_new_header_names_and_csv_delimiter():
    df, _ = _read(_book(head=["Nº", "Espécie", "DAP", "Altura", "Status"]))
    assert io.has_required_columns(df)
    csv = _io.BytesIO("tree_id,species,dbh_cm,height_m,condition\n1,Rh,8.4,6.2,v\n2,Av,12.1,7.8,v\n".encode())
    assert io.has_required_columns(io.load_csv(csv, ";"))


def test_missing_columns_help():
    df = pd.DataFrame({"tree_id": [1], "species": ["Rh"]})
    assert io.missing_columns(df) == ["dbh", "condition"]
    assert "dbh:" in io.accepted_names(["dbh"])


def test_single_page_without_valid_dbh_shows_message_not_traceback():
    buf = _book(rows=[[1, "Rh", None, 6.2, "v"], [2, "Av", None, 7.8, "v"]])
    at = AppTest.from_file(str(APP / "pages" / "1_Single_plot.py"), default_timeout=120).run()
    at.file_uploader[0].set_value(("vazio.xlsx", buf.getvalue(), XLSX_MIME))
    at.run()
    assert not at.exception
    assert any("left for the calculation" in e.value or "ficou para o cálculo" in e.value for e in at.error)


# --- second round (review of 1.3.1) ---------------------------------------------------------

def test_area_in_hectares_without_unit_is_flagged():
    df, area = _read(_book(top=[["Área", 0.01]]))
    assert area == 0.01                                  # used as written, but flagged
    assert "area_implausible" in _kinds(df)
    df, _ = _read(_book(top=[["Área", 400]]))
    assert "area_implausible" not in _kinds(df)


def test_area_unit_in_label_and_value_is_converted_once():
    df, area = _read(_book(top=[["Área (ha)", "0,01 ha"]]))
    assert abs(area - 100.0) < 1e-6
    assert "unit_converted" in _kinds(df) and "area_implausible" not in _kinds(df)
    assert abs(_read(_book(top=[["Área (m²)", "0,02 ha"]]))[1] - 200.0) < 1e-6


def test_tree_number_only_on_first_stem_counts_trees_as_before():
    df = pd.DataFrame({"tree_id": [1, None, None, 2, 3, None], "species": ["Rh"] * 6,
                       "dbh": [5.0, 6.0, 7.0, 8.0, 9.0, 4.0], "height": [None] * 6,
                       "condition": ["v"] * 6, "source_row": range(2, 8)})
    s = calc.analyze(df, 100.0, RES)["summary"]
    assert s["n_live_trees"] == 3 and s["stems_per_tree"] == 2.0


def test_merged_height_and_dbh_are_not_repeated():
    rows = [[1, "Rh", 8.4, 6.2, "v"], [None, None, None, None, None], [2, "Av", 12.1, 7.8, "v"]]
    df, _ = _read(_book(rows=rows, merges=["A2:A3", "B2:B3", "C2:C3", "D2:D3", "E2:E3"]))
    assert list(df["species"][:2]) == ["Rh", "Rh"] and list(df["condition"][:2]) == ["v", "v"]
    assert pd.isna(df["height"].iloc[1]) and pd.isna(df["dbh"].iloc[1])


def test_new_warnings_have_labels_in_both_languages():
    from manguetree import i18n
    kinds = ["unit_converted", "area_invalid", "area_implausible", "rows_truncated",
             "merged_cells_filled", "formulas_without_value", "no_heights"]
    for lang in ("pt", "en"):
        for k in kinds:
            assert f"validation.kind.{k}" in i18n.catalog(lang), (lang, k)
