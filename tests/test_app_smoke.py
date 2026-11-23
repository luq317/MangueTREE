import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]

APP = ROOT / "src" / "manguetree" / "app"
PAGES = [APP / "Home.py"] + sorted((APP / "pages").glob("*.py"))


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.stem)
def test_page_runs_without_exception(page):
    at = AppTest.from_file(str(page), default_timeout=60).run()
    assert not at.exception


def test_no_biomass_left():
    pattern = re.compile(r"biomass|carbono|carbon|mangue_biomassa", re.I)
    hits = []
    for py in ROOT.rglob("*.py"):
        rel = py.relative_to(ROOT)
        if set(rel.parts) & {"tests", ".git", "build", "dist",
                             "venv", ".venv", "__pycache__"}:
            continue
        for n, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                hits.append(f"{rel}:{n}")
    assert hits == []


XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _upload(page, data_file, timeout=180):
    at = AppTest.from_file(str(APP / "pages" / page), default_timeout=timeout).run()
    content = (ROOT / "data" / data_file).read_bytes()
    at.file_uploader[0].set_value((data_file, content, XLSX_MIME))
    return at.run()


def _run_button(at):
    return next(b for b in at.button if "Run" in b.label)


def test_single_plot_with_example_data():
    at = _upload("1_Single_plot.py", "guaratiba_T2_2009.xlsx")
    assert not at.exception
    assert not at.error and not at.warning
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Live density (stems/ha)"] == "2978"   # F2 2009, lab: 2977.8


def test_multiple_plots_with_example_data():
    at = _upload("2_Multiple_plots.py", "guaratiba_T2_2009.xlsx")
    _run_button(at).click().run()
    assert not at.exception
    assert not at.warning                       # includes the PDF report
    assert "3 plot(s) processed" in at.success[0].value


def test_temporal_with_example_data():
    at = _upload("3_Temporal.py", "guaratiba_H2_2003_2025.xlsx", timeout=300)
    _run_button(at).click().run()
    assert not at.exception
    assert not at.error and not at.warning
    assert "15 years analysed" in at.success[0].value


def test_single_plot_shows_validation_panel():
    at = _upload("1_Single_plot.py", "guaratiba_T2_2009.xlsx")
    assert not at.exception
    titles = [s.value for s in at.subheader]
    assert "Data check" in titles


def test_region_selector_present():
    from manguetree.species import REGIONS
    at = _upload("1_Single_plot.py", "guaratiba_T2_2009.xlsx")
    boxes = [s for s in at.sidebar.selectbox if s.label == "Region"]
    assert len(boxes) == 1
    assert set(boxes[0].options) == set(REGIONS.values())
    assert boxes[0].value == "BR_S_SE"


def test_region_change_changes_resolver():
    from manguetree.species import REGIONS
    at = _upload("1_Single_plot.py", "guaratiba_T2_2009.xlsx")
    box = [s for s in at.sidebar.selectbox if s.label == "Region"][0]
    box.select("EASTERN_PACIFIC").run()
    assert not at.exception


def test_issues_sheet_in_excel_export():
    import io
    import pandas as pd
    from manguetree import calc as mc, charts as ui, io as mio
    from manguetree.species import SpeciesResolver, load_genus_defaults, load_species_table
    df, area = mio.load_excel_sheet(str(ROOT / "data" / "guaratiba_T2_2009.xlsx"),
                                    "F2", "", 100.0)
    res = mc.analyze(df.dropna(subset=["dbh"]), area,
                     SpeciesResolver(load_species_table(), "BR_S_SE", load_genus_defaults()))
    xl = pd.ExcelFile(io.BytesIO(ui.to_excel_bytes(res)))
    assert "Issues" in xl.sheet_names
    iss = xl.parse("Issues")
    assert list(iss.columns) == ["Problem", "Severity", "Row", "Tree",
                                 "Detail", "Action taken"]
    assert len(iss) == 1
    row = iss.iloc[0]
    assert row["Problem"] == ui.issue_kind_label("stem_count_mismatch", "en")
    assert row["Severity"] == "Warning" and row["Row"] == 98


def test_report_has_validation_section():
    from manguetree import report as rep
    pdf = rep.single_plot_report(_f2_result())
    assert pdf[:4] == b"%PDF"


def _f2_result():
    from manguetree import calc as mc, io as mio
    from manguetree.species import SpeciesResolver, load_genus_defaults, load_species_table
    df, area = mio.load_excel_sheet(str(ROOT / "data" / "guaratiba_T2_2009.xlsx"),
                                    "F2", "", 100.0)
    return mc.analyze(df.dropna(subset=["dbh"]), area,
                      SpeciesResolver(load_species_table(), "BR_S_SE", load_genus_defaults()))


def test_multiple_plots_validation_panel_has_sheet_column():
    at = _upload("2_Multiple_plots.py", "guaratiba_T2_2009.xlsx")
    _run_button(at).click().run()
    assert "Data check" in [s.value for s in at.subheader]


def test_temporal_validation_panel():
    at = _upload("3_Temporal.py", "guaratiba_H2_2003_2025.xlsx", timeout=300)
    _run_button(at).click().run()
    assert "Data check" in [s.value for s in at.subheader]


def test_missing_condition_radio_changes_density(tmp_path):
    import pandas as pd
    df = pd.DataFrame({"Indivíduo": [1, 2, 3], "Espécie": ["Rm"] * 3,
                       "DAP": [5.0, 6.0, 7.0], "Condição": ["V", "V", None]})
    f = tmp_path / "plot.csv"
    df.to_csv(f, sep=";", index=False)
    at = AppTest.from_file(str(APP / "pages" / "1_Single_plot.py"),
                           default_timeout=120).run()
    up = next(u for u in at.sidebar.file_uploader if u.key == "upload_unico")
    up.set_value(("plot.csv", f.read_bytes(), "text/csv"))
    at.run()
    assert not at.exception
    dens = lambda: {m.label: m.value for m in at.metric}["Live density (stems/ha)"]
    assert dens() == "200"                       # excluded: 2 live stems per 100 m2 (ha scale 100x)
    at.radio(key="mc_unica").set_value("live").run()
    assert dens() == "300"


def test_species_csv_missing_columns_shows_error():
    at = AppTest.from_file(str(APP / "pages" / "1_Single_plot.py"),
                           default_timeout=60).run()
    up = next(u for u in at.sidebar.file_uploader if u.key == "species_csv")
    up.set_value(("bad.csv", b"code,genus\nXX,Foo\n", "text/csv")).run()
    assert any("columns" in e.value for e in at.sidebar.error)


def _pdf_text(pdf):
    import shutil
    import subprocess
    if shutil.which("pdftotext") is None:
        pytest.skip("pdftotext not available")
    p = Path(__file__).parent / "_tmp_report.pdf"
    p.write_bytes(pdf)
    try:
        return subprocess.run(["pdftotext", str(p), "-"], capture_output=True,
                              text=True).stdout
    finally:
        p.unlink()


def test_report_verification_section_text():
    from manguetree import report as rep
    txt = _pdf_text(rep.single_plot_report(_f2_result(), lang="pt"))
    assert "Verificação dos dados" in txt
    assert "0 erros e 1 avisos" in txt


def test_report_escapes_markup_in_issue_text():
    from manguetree import report as rep
    from manguetree.validation import Issue
    res = _f2_result()
    res = dict(res, issues=[Issue("unknown_condition", "error", 7, 1,
                                  "condition '<5' and 'V&M' <b>x", "")])
    pdf = rep.single_plot_report(res)          # must not raise
    assert pdf[:4] == b"%PDF"
    txt = _pdf_text(pdf)
    assert "<5" in txt and "V&M" in txt


def test_report_check_is_grouped_by_category_errors_first():
    from manguetree import charts as ui, report as rep
    from manguetree.validation import Issue
    iss = [Issue("duplicate_tag", "warning", n, n, "w", "") for n in range(150)]
    iss.append(Issue("unknown_species", "error", 999, 1, "last-error-marker", ""))
    frame = ui.issues_display_frame(iss, lang="pt")
    blocks = rep._bloco_verificacao(frame, "pt")
    tab = next(c for t, c in blocks if t == "tab")
    assert len(tab) == 2                                   # one row per category, not 151
    assert tab.iloc[0]["Gravidade"] == "Erro"              # errors first
    assert int(tab["Ocorrências (N)"].sum()) == 151
    cap = " ".join(c for t, c in blocks if t == "cap")
    assert "1 erros" in cap and "150 avisos" in cap and "Problemas" in cap


def test_issues_sheet_header_same_in_single_and_multiple():
    import io
    import pandas as pd
    from manguetree import charts as ui
    res = _f2_result()
    single = ui.issues_frame_by_unit({"": res["issues"]}, lang="en")
    multi = ui.issues_frame_by_unit({"F2": res["issues"]}, "Aba", "en")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xls:
        multi.to_excel(xls, sheet_name="Issues", index=False)
    mhead = list(pd.read_excel(io.BytesIO(buf.getvalue()), sheet_name="Issues").columns)
    shead = list(pd.ExcelFile(io.BytesIO(ui.to_excel_bytes(res, "en"))).parse("Issues").columns)
    assert mhead[0] == "Aba" and mhead[1:] == shead == list(single.columns)


def test_temporal_issue_table_keeps_sheet_and_year():
    from manguetree import charts as ui
    res = _f2_result()
    f = ui.issues_frame_by_unit({(2009, "F2a"): res["issues"], (2009, "F2b"): res["issues"]},
                                ("Ano", "Aba"))
    assert list(f.columns[:2]) == ["Ano", "Aba"]
    assert sorted(f["Aba"]) == ["F2a", "F2b"] and set(f["Ano"]) == {2009}


def test_settings_signature_changes_with_species_edit():
    at = AppTest.from_file(str(APP / "pages" / "1_Single_plot.py"),
                           default_timeout=60).run()
    before = at.session_state["settings_sig"]
    table = at.session_state["species_base"].copy()
    table.loc[0, "aliases"] = table.loc[0, "aliases"] + "|zzz"
    at.session_state["species_base"] = table
    at.run()
    assert at.session_state["settings_sig"] != before
    assert at.session_state["settings_sig"][0] == before[0]
