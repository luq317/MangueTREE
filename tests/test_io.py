import io as _stdio
import math
import re

import openpyxl
import pandas as pd

from manguetree import io as mio


def _xlsx_bytes(rows):
    """Build an in-memory .xlsx whose first sheet holds `rows` from cell A1."""
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(list(row))
    buf = _stdio.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_reads_lab_style_header():
    # NEMA lab layout: 6 lines of plot header, column header on row 7, data from row 8
    rows = [
        ["Local :", "Piracão"],
        ["Estação :", "F2"],
        ["Data :", None],
        ["Parcela (m2):", 225],
        ["OBS:", None],
        [None, None, None, None, "Altura (m)"],
        ["Indivíduo", "Nº tr's", "Espécie", "DAP", "Alt. Corr.", "Condição"],
        [1, 1, "As", 14.3, 12.1, "v"],
        [2, 1, "As", "12,6", 15.1, "v"],
        [3, 2, "Rh", 5.0, None, "m"],
    ]
    df, area = mio.load_excel_sheet(_xlsx_bytes(rows), 0, cell_ref="B4")
    assert df is not None
    for col in ["tree_id", "n_stems", "species", "dbh", "height", "condition"]:
        assert col in df.columns
    assert df["source_row"].iloc[0] == 8
    assert df["source_row"].tolist() == [8, 9, 10]
    assert df["dbh"].tolist() == [14.3, 12.6, 5.0]
    assert df["height"].iloc[1] == 15.1
    assert area == 225.0
    assert mio.has_required_columns(df)


def test_reads_plot_area_label():
    rows = [
        ["site", "Guaratiba, Rio de Janeiro, Brazil"],
        ["plot", "H2"],
        ["year", 2009],
        ["plot_area_m2", 80],
        [],
        ["tree_id", "n_stems", "species", "dbh_cm", "height_m", "condition"],
        [1, 1, "As", 10.0, 6.0, "v"],
    ]
    df, area = mio.load_excel_sheet(_xlsx_bytes(rows), 0)
    assert area == 80.0
    assert df["source_row"].iloc[0] == 7
    assert df["dbh"].iloc[0] == 10.0 and df["height"].iloc[0] == 6.0


def test_exact_match_beats_substring():
    csv = ("tree_id;species;dbh_cm;condition;altura;alt med;lon;longitude_gps\n"
           "1;As;10,5;v;7,0;1,6;-43,5;-99\n"
           "2;Rh;4;m;3;1,6;-43,6;-98\n")
    df = mio.load_csv(_stdio.StringIO(csv), delimiter=";")
    assert df["height"].tolist() == [7.0, 3.0]
    assert list(df.columns).count("height") == 1
    assert list(df.columns).count("lon") == 1
    assert df["lon"].tolist() == [-43.5, -43.6]
    assert df["source_row"].tolist() == [2, 3]


def test_to_numeric_handles_comma_and_blank():
    out = mio.to_numeric(pd.Series(["12,6", " ", "3.5", None]))
    assert out.iloc[0] == 12.6
    assert math.isnan(out.iloc[1])
    assert out.iloc[2] == 3.5
    assert math.isnan(out.iloc[3])


def test_full_lab_header_uses_corrected_height():
    # The complete NEMA header has both "Alt. med." (observer eye height) and
    # "Alt. Corr." (tree height); the tree height must win.
    rows = [
        ["Local :", "Piracão"], ["Estação :", "F2"], ["Data :"], ["Parcela (m2):", 225],
        ["OBS:"], [None] * 6 + ["Altura (m)"],
        ["Indivíduo", "Nº tr's", "Observação", "Lacre", "Espécie", "DAP", "Telêmet.",
         "Vara", "Régua", "Alt. med.", "Alt. Corr.", "Condição", "flag"],
        [1, 1, None, 622128, "As", 14.3, 10.5, None, None, 1.6, 12.1, "v", "a3"],
    ]
    df, _ = mio.load_excel_sheet(_xlsx_bytes(rows), 0)
    assert df["height"].tolist() == [12.1]
    assert df["tag"].tolist() == [622128]
    assert df["source_row"].tolist() == [8]


import pytest  # noqa: E402
import zipfile  # noqa: E402


@pytest.mark.parametrize("dbh_header", ["DAP cm", "DAP_cm", "DAP1", "DAP (cm)"])
def test_short_alias_matches_first_header_token(dbh_header):
    rows = [["Indivíduo", "Espécie", dbh_header, "Condição", "longitude_gps", "lon"],
            [1, "As", 10.5, "v", -99.0, -43.5]]
    df, _ = mio.load_excel_sheet(_xlsx_bytes(rows), 0)
    assert df is not None and mio.has_required_columns(df)
    assert df["dbh"].tolist() == [10.5]
    assert df["lon"].tolist() == [-43.5]    # longitude_gps does not become lon


def test_exact_match_is_global_before_partial():
    # "Altura total" would partially match height; the exact "altura" must win
    # even though it comes later in the header.
    csv = ("tree_id;species;dbh;condition;Altura total;altura\n"
           "1;As;10;v;99;7\n")
    df = mio.load_csv(_stdio.StringIO(csv))
    assert df["height"].tolist() == [7.0]


def test_reads_sheet_with_wrong_dimension_metadata():
    rows = [["tree_id", "species", "dbh_cm", "condition"], [1, "As", 10.0, "v"],
            [2, "Rh", 4.0, "m"]]
    src = _xlsx_bytes(rows)
    out = _stdio.BytesIO()
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w") as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                text = data.decode("utf-8")
                wrong = '<dimension ref="A1"/>'
                if re.search(r'<dimension\s+ref="[^"]*"\s*/>', text):
                    text = re.sub(r'<dimension\s+ref="[^"]*"\s*/>', wrong, text, count=1)
                elif "</sheetPr>" in text:
                    text = text.replace("</sheetPr>", "</sheetPr>" + wrong, 1)
                else:
                    text = re.sub(r"(<worksheet\b[^>]*>)", lambda m: m.group(1) + wrong,
                                  text, count=1)
                assert wrong in text                      # the rewrite happened
                data = text.encode("utf-8")
            zout.writestr(item, data)
    out.seek(0)
    df, _ = mio.load_excel_sheet(out, 0)
    assert df is not None and df["dbh"].tolist() == [10.0, 4.0]
