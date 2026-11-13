import io as _io
from pathlib import Path

import openpyxl
import pandas as pd
from streamlit.testing.v1 import AppTest

from manguetree import calc, io as mio, validation
from manguetree.species import SpeciesResolver, load_genus_defaults, load_species_table

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "manguetree" / "app"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
HEADER = ["tree_id", "n_stems", "species", "dbh_cm", "height_m", "condition"]
RES = SpeciesResolver(load_species_table(), "BR_S_SE", load_genus_defaults())


def _workbook(sheets):
    """sheets: name -> list of data rows (header and a plot_area_m2 row are added)."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        ws.append(["plot_area_m2", 100])
        ws.append(HEADER)
        for r in rows:
            ws.append(r)
    buf = _io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


GOOD = [[1, 1, "Rh", 8.0, 5.0, "v"], [2, 1, "As", 12.0, 7.0, "v"],
        [3, 1, "Lg", 4.0, 3.0, "m"]]
EMPTY = [[1, 1, "Rh", None, None, None], [2, 1, "As", None, None, None]]


def _run(page, data, button, timeout=180):
    at = AppTest.from_file(str(APP / "pages" / page), default_timeout=timeout).run()
    at.file_uploader[0].set_value(("t.xlsx", data, XLSX_MIME))
    at.run()
    next(b for b in at.button if button in b.label).click()
    return at.run()


def test_empty_sheet_is_ignored_in_multiple():
    at = _run("2_Multiple_plots.py", _workbook({"F2": GOOD, "H2": GOOD, "V2": EMPTY}),
              "Run")
    assert not at.exception
    assert any("V2" in c.value and "no measured stems" in c.value for c in at.caption)
    assert len(at.session_state["multi_resultados"]) == 2
    tables = [d.value for d in at.dataframe if "Live density (stems/ha)" in d.value.columns]
    assert len(tables[0]) == 2


def test_empty_year_is_ignored_in_temporal():
    at = _run("3_Temporal.py", _workbook({"2009": GOOD, "2010": GOOD, "2011": EMPTY}),
              "Run")
    assert not at.exception
    assert any("2011" in c.value and "no measured stems" in c.value for c in at.caption)
    assert list(at.session_state["temp_serie"]["year"]) == [2009, 2010]


def test_area_label_in_data_rows_is_not_used(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws.append(["plot_area_m2", 80])
    ws.append(HEADER + ["obs"])
    ws.append([1, 1, "Rh", 8.0, 5.0, "v", None])
    ws.append([2, 1, "As", 12.0, 7.0, "v", None])
    ws.append([None, None, None, None, None, None, "área"])
    ws["G5"] = "área"
    ws["H5"] = 4.0
    p = tmp_path / "a.xlsx"
    wb.save(p)
    df, area = mio.load_excel_sheet(str(p), "S", "", 100.0)
    assert area == 80
    assert df.attrs["area_source"] == "label"
    # without a label above the header, a label among the data rows is ignored too
    ws.delete_rows(1)
    wb.save(p)
    df, area = mio.load_excel_sheet(str(p), "S", "", 100.0)
    assert area == 100.0
    assert df.attrs["area_source"] == "fallback"


def test_tree_without_stems():
    df = pd.DataFrame({"tree_id": [1, 1, 2], "n_stems": [2, 2, 1],
                       "species": ["Rh", "Rh", "As"], "dbh": [None, None, 9.0],
                       "height": [None] * 3, "condition": [None, None, "v"],
                       "source_row": [2, 3, 4]})
    issues = validation.validate(df, RES)
    kinds = [(i.kind, i.tree_id) for i in issues]
    assert kinds.count(("tree_without_stems", 1)) == 1
    assert ("stem_count_mismatch", 1) not in kinds
    assert not [i for i in issues if i.kind == "stem_count_mismatch"]


def test_area_not_offered_as_metric():
    from manguetree import charts as ui
    for page, key, col in (("2_Multiple_plots.py", "multi_resultados", None),
                           ("3_Temporal.py", "temp_serie", None)):
        sheets = ({"F2": GOOD, "H2": GOOD} if page.startswith("2")
                  else {"2009": GOOD, "2010": GOOD})
        at = _run(page, _workbook(sheets), "Run")
        assert not at.exception
        offered = []
        for w in list(at.selectbox) + list(at.multiselect):
            offered += list(w.options)
        assert "Live density (stems/ha)" in offered
        assert "Area (m²)" not in offered
    assert "plot_area_m2" in ui.NON_METRIC_COLUMNS


def test_alias_collision_reported():
    t = load_species_table()
    new = {c: "" for c in t.columns}
    new.update(code="ZZ", scientific_name="Zzz zzz", genus="Zzz", aliases="rm",
               regions="BR_S_SE", true_mangrove="true")
    t = pd.concat([t, pd.DataFrame([new])], ignore_index=True)
    r = SpeciesResolver(t, "BR_S_SE", load_genus_defaults())
    assert r.alias_collisions() == [("rm", "ZZ", "Rm")]
    assert r.resolve("rm").code == "ZZ"
    assert RES.alias_collisions() == []


def test_genus_default_override_is_not_a_collision():
    t = load_species_table()
    t.loc[t["code"] == "Ag", "aliases"] += "|av"
    r = SpeciesResolver(t, "BR_N_NE", load_genus_defaults())
    assert r.alias_collisions() == []
    assert r.resolve("Av").code == "Ag"


def test_empty_sheet_sharing_a_year_gives_no_duplicate_year():
    at = _run("3_Temporal.py",
              _workbook({"2009": GOOD, "2010": GOOD, "2010 vazia": EMPTY}), "Run")
    assert not at.exception
    kinds = [i.kind for v in at.session_state["temp_issues"].values() for i in v]
    assert "duplicate_year" not in kinds
    assert any("2010 vazia" in c.value and "no measured stems" in c.value
               for c in at.caption)
