# -*- coding: utf-8 -*-
"""Final whole-branch review of stage B: regression tests for each finding."""
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from manguetree import calc as mc, charts, io as mio, report
from manguetree.species import SpeciesResolver, load_genus_defaults, load_species_table

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def _resolver():
    return SpeciesResolver(load_species_table(), "BR_S_SE", load_genus_defaults())


def _analyze(path, sheet, **kw):
    df, area = mio.load_excel_sheet(str(path), sheet, "", 100.0)
    return mc.analyze(df.dropna(subset=["dbh"]), area, _resolver(), plot_name=sheet, **kw)


def _pdf_text(pdf, tmp_path):
    if shutil.which("pdftotext") is None:
        pytest.skip("pdftotext not available")
    p = tmp_path / "r.pdf"
    p.write_bytes(pdf)
    return subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True,
                          text=True).stdout


# ---- 1. PDF tables keep integers as integers ----
def test_temporal_pdf_prints_years_as_ints(tmp_path):
    serie = pd.DataFrame({"year": [2003, 2004, 2005], "n_stems": [67, 70, 71],
                          "density_live_ha": [1.5, 2.25, 3.0]})
    txt = _pdf_text(report.temporal_report(serie, None, lang="en"), tmp_path)
    assert "2003" in txt and "2003.00" not in txt
    assert "67.00" not in txt


def test_single_pdf_prints_stem_counts_as_ints(tmp_path):
    res = _analyze(DATA / "guaratiba_T2_2009.xlsx", "F2")
    txt = _pdf_text(report.single_plot_report(res, lang="en"), tmp_path)
    n_live = res["summary"]["n_live"]
    assert f" {n_live} " in txt or f" {n_live}\n" in txt
    assert f"{n_live}.00" not in txt


# ---- 2. single-plot page: sheet selector ----
from streamlit.testing.v1 import AppTest

APP = ROOT / "src" / "manguetree" / "app"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _single(name, content, mime=XLSX_MIME, lang="en"):
    at = AppTest.from_file(str(APP / "pages" / "1_Single_plot.py"), default_timeout=180)
    at.session_state["lang"] = lang
    at.run()
    at.file_uploader[0].set_value((name, content, mime))
    return at.run()


def test_single_plot_sheet_selector_reads_chosen_sheet():
    content = (DATA / "guaratiba_T2_2009.xlsx").read_bytes()
    at = _single("guaratiba_T2_2009.xlsx", content)
    box = next(s for s in at.sidebar.selectbox if s.label == "Sheet (plot)")
    assert set(box.options) >= {"F2", "H2"}
    box.select("H2").run()
    assert not at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Live density (stems/ha)"] == "7125"
    assert any("H2" in c.value for c in at.caption)


# ---- 3. pooled_importance without plot names ----
def test_pooled_importance_without_plot_names():
    path = DATA / "guaratiba_T2_2009.xlsx"
    results = [_analyze(path, s) for s in ("F2", "H2")]
    for r in results:
        r["plot_name"] = None
    tab = mc.pooled_importance(results)
    assert not tab.empty
    assert tab["ivi"].sum() == pytest.approx(300.0)
    assert mc.pooled_importance([]).empty


# ---- 4. CSV: the area warning stays until the user sets the area ----
CSV = (b"tree_id;species;dbh_cm;condition\n"
       b"1;As;5,0;v\n2;As;7,5;v\n3;Rm;12,0;v\n4;Rm;3,1;m\n")


def _issue_kinds(at):
    out = []
    for df in at.dataframe:
        out += [str(v) for v in df.value.to_numpy().ravel()]
    return out


def test_csv_default_area_raises_area_warning_until_changed():
    at = _single("plot.csv", CSV, "text/csv")
    assert not at.exception
    assert any("Plot area not found" in v for v in _issue_kinds(at))
    at.sidebar.number_input(key="area_unica").set_value(250.0).run()
    assert not at.exception
    assert not any("Plot area not found" in v for v in _issue_kinds(at))
    assert any("250" in s.value for s in at.success)


def test_load_csv_marks_area_as_fallback():
    import io as _io
    df = mio.load_csv(_io.BytesIO(CSV))
    assert df.attrs["area_source"] == "fallback"


# ---- 5. labels ----
def test_species_label_in_portuguese():
    from manguetree.i18n import t
    assert t("labels.n_species_live", "pt") == "Nº de espécies (vivas)"


def test_ivi_chart_axis_titles():
    res = _analyze(DATA / "guaratiba_T2_2009.xlsx", "F2")
    est = {"paleta": charts.PALETAS[next(iter(charts.PALETAS))], "tamanho_titulo": 14,
           "tamanho_eixos": 11, "seal": False}
    fig = charts.fig_ivi(res["importance"], est, "pt")
    assert fig.layout.xaxis.title.text == "Valor relativo (%)"
    assert fig.layout.barmode == "group"
    fig = charts.fig_ivi(mc.pooled_importance([res, _analyze(DATA / "guaratiba_T2_2009.xlsx", "H2")]),
                         est, "en")
    assert fig.layout.xaxis.title.text == "Importance value"


# ---- 7. quit button only in the desktop build ----
def _home(monkeypatch, desktop):
    if desktop:
        monkeypatch.setenv("MANGUETREE_DESKTOP", "1")
    else:
        monkeypatch.delenv("MANGUETREE_DESKTOP", raising=False)
    return AppTest.from_file(str(APP / "Home.py"), default_timeout=60).run()


def test_quit_button_only_when_desktop(monkeypatch):
    assert not any(b.label == "Quit MangueTREE" for b in _home(monkeypatch, False).sidebar.button)
    at = _home(monkeypatch, True)
    assert not at.exception
    assert any(b.label == "Quit MangueTREE" for b in at.sidebar.button)


def test_launcher_sets_desktop_flag():
    src = (ROOT / "src" / "manguetree" / "launcher.py").read_text(encoding="utf-8")
    assert 'os.environ["MANGUETREE_DESKTOP"] = "1"' in src


# ---- minor 2, 3, 4, 6, 8, 11 ----
def test_portuguese_metrics_use_decimal_comma():
    content = (DATA / "guaratiba_T2_2009.xlsx").read_bytes()
    at = _single("guaratiba_T2_2009.xlsx", content, lang="pt")
    vals = [m.value for m in at.metric]
    assert "26,55" in vals and not any("." in v for v in vals)


def test_data_table_translates_codes_and_stringifies_ids():
    res = _analyze(DATA / "guaratiba_T2_2009.xlsx", "F2")
    d = res["data"].copy()
    d["tree_id"] = d["tree_id"].astype(object)
    d.loc[d.index[0], "tree_id"] = "12a"           # mixed int/text ids
    pt = charts.for_display(d, data_table=True, lang="pt")
    en = charts.for_display(d, data_table=True, lang="en")
    assert set(pt["Condição"]) <= {"Viva", "Morta"}
    assert set(en["Condition"]) <= {"Live", "Dead"}
    assert "genus_default" not in set(pt["Situação da espécie"])
    assert "identified" in set(en["Species status"])
    assert all(isinstance(v, str) for v in pt["Indivíduo"])
    import pyarrow as pa
    pa.Table.from_pandas(pt)                        # must not raise ArrowInvalid


def test_histogram_hover_count_is_translated():
    res = _analyze(DATA / "guaratiba_T2_2009.xlsx", "F2")
    est = {"paleta": charts.PALETAS[next(iter(charts.PALETAS))], "tamanho_titulo": 14,
           "tamanho_eixos": 11, "seal": False}
    fig = charts.fig_hist_dap(res, est, "pt")
    assert "count=" not in fig.data[0].hovertemplate
    assert "Contagem" in fig.data[0].hovertemplate


def test_species_series_averages_duplicate_years():
    base = _analyze(DATA / "guaratiba_T2_2009.xlsx", "F2")
    other = _analyze(DATA / "guaratiba_T2_2009.xlsx", "H2")
    base["year"], other["year"] = 2020, 2020
    both = charts.serie_por_especie([base, other])
    assert not both.duplicated(["year", "species"]).any()
    one = charts.serie_por_especie([base])
    sp = one["species"].iloc[0]
    d1 = one.loc[one.species == sp, "density_ha"].iloc[0]
    d2 = charts.serie_por_especie([other])
    d2 = d2.loc[d2.species == sp, "density_ha"]
    expected = (d1 + d2.iloc[0]) / 2 if len(d2) else d1
    assert both.loc[both.species == sp, "density_ha"].iloc[0] == pytest.approx(expected)


def test_summary_has_total_density_and_height_range():
    res = _analyze(DATA / "guaratiba_T2_2009.xlsx", "F2")
    tab = charts.resumo_para_df(res, "en")
    params = set(tab["Parameter"])
    assert {"Total density (stems/ha)", "Minimum height (m)", "Maximum height (m)"} <= params


def test_single_panel_and_exports_list_the_same_issues():
    content = (DATA / "guaratiba_T2_2009.xlsx").read_bytes()
    at = _single("guaratiba_T2_2009.xlsx", content)
    panel = next(m for m in at.metric if m.label == "Warnings")
    res = _analyze(DATA / "guaratiba_T2_2009.xlsx", "F2")
    assert int(panel.value) == sum(1 for i in res["issues"] if i.severity == "warning")


def test_seal_choice_survives_a_page_change():
    at = AppTest.from_file(str(APP / "pages" / "2_Multiple_plots.py"), default_timeout=120)
    at.run()
    at.file_uploader[0].set_value(("guaratiba_T2_2009.xlsx",
                                   (DATA / "guaratiba_T2_2009.xlsx").read_bytes(), XLSX_MIME))
    at.run()
    at.sidebar.checkbox(key="show_seal").set_value(True).run()
    assert at.session_state["_show_seal"] is True


def test_build_files_are_in_english():
    import re
    pt = re.compile(r"[áéíóúãõçÁÉÍÓÚÃÕÇ]|\b(Pronto|Compacte|Empacotar|Instalar|Anexar)\b")
    files = [ROOT / "MangueTREE.spec", ROOT / "build_windows.bat", ROOT / "build_macos.command",
             ROOT / "src" / "manguetree" / "launcher.py",
             ROOT / ".github" / "workflows" / "build-desktop.yml"]
    for f in files:
        assert not pt.search(f.read_text(encoding="utf-8")), f.name
    assert "setuptools>=77" in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_readme_has_no_broken_image():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    import re
    links = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", re.sub(r"<!--.*?-->", "", text, flags=re.S))
    local = [l for l in links if not l.startswith("http")]
    assert [l for l in local if not (ROOT / l).exists()] == []
