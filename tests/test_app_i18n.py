"""Bilingual interface: every page runs in both languages, English mode shows no
Portuguese labels, and switching language keeps the results."""
import re
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from manguetree import i18n

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "manguetree" / "app"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# page file, example data file (None: no upload), label of the run button (None: none)
PAGES = [
    ("Home.py", None, None),
    ("pages/1_Single_plot.py", "guaratiba_T2_2009.xlsx", None),
    ("pages/2_Multiple_plots.py", "guaratiba_T2_2009.xlsx", "multi.run"),
    ("pages/3_Temporal.py", "guaratiba_H2_2003_2025.xlsx", "temporal.run"),
    ("pages/4_About.py", None, None),
]
PORTUGUESE_WORDS = ("Parcela", "Espécie", "Densidade", "Área basal", "Altura média",
                    "Verificação")


def _page(path, data_file, run_key, lang, timeout=300):
    at = AppTest.from_file(str(APP / path), default_timeout=timeout)
    at.session_state["lang"] = lang
    at.run()
    if data_file:
        content = (ROOT / "data" / data_file).read_bytes()
        at.file_uploader[0].set_value((data_file, content, XLSX_MIME))
        at.run()
    if run_key:
        next(b for b in at.button if b.label == i18n.t(run_key, lang)).click().run()
    return at


def _texts(at):
    """Visible text of the page: headings, metric labels, table headers, widget labels."""
    out = [e.value for e in at.subheader] + [e.value for e in at.header]
    out += [m.label for m in at.metric]
    for df in at.dataframe:
        out += [str(c) for c in df.value.columns]
        if df.value.index.name:
            out.append(str(df.value.index.name))
    for table in at.table:
        out += [str(c) for c in table.value.columns]
    out += [w.label for w in list(at.selectbox) + list(at.radio) + list(at.multiselect)
            + list(at.number_input) + list(at.button) + list(at.tabs)]
    return out


@pytest.mark.parametrize("lang", ["en", "pt"])
@pytest.mark.parametrize("page,data_file,run_key", PAGES, ids=lambda v: str(v))
def test_pages_run_in_both_languages(page, data_file, run_key, lang):
    at = _page(page, data_file, run_key, lang)
    assert not at.exception
    assert at.session_state["lang"] == lang
    assert i18n.MISSING == set()


def test_english_mode_has_no_portuguese_labels():
    at = _page("pages/1_Single_plot.py", "guaratiba_T2_2009.xlsx", None, "en")
    assert not at.exception
    text = " | ".join(_texts(at))
    assert text
    for word in PORTUGUESE_WORDS:
        assert word not in text, word
    # and the English labels are there
    assert "Live density (stems/ha)" in {m.label for m in at.metric}


def test_portuguese_mode_shows_portuguese_labels():
    at = _page("pages/1_Single_plot.py", "guaratiba_T2_2009.xlsx", None, "pt")
    assert "Densidade viva (troncos/ha)" in {m.label for m in at.metric}
    assert "Verificação dos dados" in [s.value for s in at.subheader]


def test_language_switch_keeps_results():
    at = _page("pages/1_Single_plot.py", "guaratiba_T2_2009.xlsx", None, "en")
    en = {m.label: m.value for m in at.metric}
    keys_en = {k: i18n.t(k, "en") for k in ("labels.density_live_ha", "labels.ba_live_ha",
                                           "labels.mean_dbh_cm")}
    at.sidebar.selectbox(key="lang").select("pt").run()
    assert not at.exception and at.session_state["lang"] == "pt"
    pt = {m.label: m.value for m in at.metric}
    assert pt                                         # results still on the page
    for k, en_label in keys_en.items():
        assert pt[i18n.t(k, "pt")].replace(",", ".") == en[en_label]    # same numbers, decimal comma


@pytest.mark.parametrize("page,data_file,run_key,state_key",
                         [("pages/2_Multiple_plots.py", "guaratiba_T2_2009.xlsx",
                           "multi.run", "multi_resultados"),
                          ("pages/3_Temporal.py", "guaratiba_H2_2003_2025.xlsx",
                           "temporal.run", "temp_serie")])
def test_language_switch_keeps_results_stored_in_session(page, data_file, run_key,
                                                         state_key):
    at = _page(page, data_file, run_key, "en")
    before = at.session_state[state_key]
    at.sidebar.selectbox(key="lang").select("pt").run()
    assert not at.exception
    after = at.session_state[state_key]
    if isinstance(before, pd.DataFrame):
        pd.testing.assert_frame_equal(before, after)
    else:
        assert len(before) == len(after) and after
    assert not at.info or all("Execut" not in i.value for i in at.info)   # not reset


def test_language_choice_survives_page_switch():
    """Widget ids include the page, so the selector keeps its value with
    persist_state="session": choose pt on Home, then move to other pages."""
    at = AppTest.from_file(str(APP / "Home.py"), default_timeout=120).run()
    at.sidebar.selectbox(key="lang").select("pt").run()
    assert not at.exception and at.session_state["lang"] == "pt"
    for page, pt_title in (("pages/4_About.py", "Sobre o MangueTREE"),
                           ("pages/1_Single_plot.py", "Análise de parcela única"),
                           ("pages/3_Temporal.py", "Análise temporal de parcela"),
                           ("Home.py", "Bem-vindo ao MangueTREE")):
        at.switch_page(page).run()
        assert not at.exception, page
        assert at.session_state["lang"] == "pt", page
        assert at.sidebar.selectbox(key="lang").value == "pt", page
        assert pt_title in " ".join(m.value for m in at.markdown), page
    # and back to English
    at.sidebar.selectbox(key="lang").select("en").run()
    at.switch_page("pages/4_About.py").run()
    assert at.session_state["lang"] == "en"


def test_sheet_selection_survives_language_switch():
    """Deselect a sheet, switch language: selection kept and results still shown."""
    import io
    import openpyxl
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    head = ["tree_id", "n_stems", "species", "dbh_cm", "height_m", "condition"]
    for name in ("2009", "2010", "Notes"):
        ws = wb.create_sheet(name)
        for r in [["plot_area_m2", 100], head, [1, 1, "Rm", 10.0, 6.0, "v"],
                  [2, 1, "Rm", 8.0, 5.0, "m"]]:
            ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    at = AppTest.from_file(str(APP / "pages" / "3_Temporal.py"), default_timeout=120)
    at.run()
    at.file_uploader[0].set_value(("t.xlsx", buf.getvalue(), XLSX_MIME)).run()
    ms = next(m for m in at.sidebar.multiselect if m.key.startswith("sheets_temp_"))
    ms.set_value(["2009", "2010"]).run()
    next(b for b in at.button if b.label == i18n.t("temporal.run", "en")).click().run()
    assert not at.exception and at.session_state["temp_serie"] is not None
    n_before = len(at.session_state["temp_serie"])
    at.sidebar.selectbox(key="lang").select("pt").run()
    assert not at.exception
    ms = next(m for m in at.sidebar.multiselect if m.key.startswith("sheets_temp_"))
    assert ms.value == ["2009", "2010"]
    assert len(at.session_state["temp_serie"]) == n_before
    assert any("anos analisados" in s.value for s in at.success)


def test_dbh_class_labels_neutral_in_calc_comma_only_in_portuguese():
    from manguetree import calc, charts as ui
    from manguetree.species import SpeciesResolver, load_genus_defaults, load_species_table
    df = pd.DataFrame({"tree_id": [1, 2, 3], "species": ["Rm"] * 3, "dbh": [1.0, 5.0, 12.0],
                       "height": [2.0, 4.0, 6.0], "condition": ["v"] * 3})
    res = calc.analyze(df, 100.0, SpeciesResolver(load_species_table(), "BR_S_SE",
                                                  load_genus_defaults()))
    assert list(res["dbh_density"].index.astype(str)) == ["< 2.5", "2.5–10", "≥ 10"]
    assert list(ui.for_display(res["dbh_density"], lang="en").index) == ["< 2.5", "2.5–10", "≥ 10"]
    assert list(ui.for_display(res["dbh_density"], lang="pt").index) == ["< 2,5", "2,5–10", "≥ 10"]
    fig = ui.fig_classes_dap(res["dbh_density"], res["dbh_ba"], {"paleta": ["#000"]}, "density", "en")
    assert "2.5–10" in set(fig.data[0].x)


def test_palette_names_follow_language():
    at = AppTest.from_file(str(APP / "pages" / "1_Single_plot.py"), default_timeout=60)
    at.run()
    box = next(s for s in at.sidebar.selectbox if s.key == "pal_unica")
    assert "High contrast" in box.options and "Contraste" not in box.options
    at.sidebar.selectbox(key="lang").select("pt").run()
    box = next(s for s in at.sidebar.selectbox if s.key == "pal_unica")
    assert "Alto contraste" in box.options


def test_portuguese_headers_same_numbers_in_english(tmp_path):
    df = pd.DataFrame({"Indivíduo": [1, 2, 3, 4], "Nº tr's": [1, 1, 1, 1],
                       "Espécie": ["Rm", "Rm", "Lr", "Lr"], "DAP": [5.0, 6.0, 7.0, 8.0],
                       "Alt. Corr.": [3.0, 4.0, 5.0, 6.0], "Condição": ["v", "v", "v", "m"]})
    f = tmp_path / "plot.csv"
    df.to_csv(f, sep=";", index=False)
    got = {}
    for lang in ("en", "pt"):
        at = AppTest.from_file(str(APP / "pages" / "1_Single_plot.py"), default_timeout=120)
        at.session_state["lang"] = lang
        at.run()
        up = next(u for u in at.sidebar.file_uploader if u.key == "upload_unico")
        up.set_value(("plot.csv", f.read_bytes(), "text/csv"))
        at.run()
        assert not at.exception
        got[lang] = {m.label: m.value for m in at.metric}[
            i18n.t("labels.density_live_ha", lang)]
    assert got["en"] == got["pt"] == "300"


def test_no_em_dash_in_user_facing_code_strings():
    bad = []
    for py in list((APP).rglob("*.py")) + [ROOT / "src/manguetree/charts.py",
                                           ROOT / "src/manguetree/branding.py"]:
        for n, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if "—" in line and not line.lstrip().startswith("#"):
                bad.append(f"{py.name}:{n}")
    assert bad == []


def test_branding_citation_and_about():
    from manguetree import branding, __version__
    assert branding.CITATION == ("Pereira LS, Motta LL, Matta TC, Chaves FO, Soares MLG (2026). MangueTREE "
                                 f"v{__version__}. https://github.com/luq317/MangueTREE")
    assert branding.REPO_URL == "https://github.com/luq317/MangueTREE"
    for lang in ("en", "pt"):
        at = AppTest.from_file(str(APP / "pages" / "4_About.py"), default_timeout=60)
        at.session_state["lang"] = lang
        at.run()
        body = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.code)
        for needle in ("Tatiane Costa da Matta", "Filipe de Oliveira Chaves", "Mário Luiz Gomes Soares", "MIT",
                       "pereira.lucas_1@posgraduacao.uerj.br", branding.CITATION,
                       branding.REPO_URL):
            assert needle in body, (lang, needle)


def test_home_species_codes_come_from_the_species_table():
    from manguetree.species import load_species_table
    at = AppTest.from_file(str(APP / "Home.py"), default_timeout=60).run()
    shown = set()
    for table in at.table:
        if i18n.t("home.col.code", "en") in table.value.columns:
            shown = set(table.value[i18n.t("home.col.code", "en")])
    assert shown == set(load_species_table()["code"])


def test_temporal_has_no_pre_analysis_duplicate_year_warning():
    """Repeated years are reported once, after the analysis, by the duplicate_year issue."""
    src = (APP / "pages" / "3_Temporal.py").read_text(encoding="utf-8")
    assert "anos_repetidos" not in src


def test_sidebar_inputs_survive_language_switch():
    """Widgets whose label is translated carry explicit keys, so a language switch
    does not reset what the user typed (Streamlit derives unkeyed widget ids from the label)."""
    at = AppTest.from_file(str(APP / "pages" / "1_Single_plot.py"), default_timeout=60).run()
    next(n for n in at.sidebar.number_input if n.key == "cut1_unica").set_value(3.0).run()
    at.sidebar.selectbox(key="lang").select("pt").run()
    assert not at.exception
    assert next(n for n in at.sidebar.number_input if n.key == "cut1_unica").value == 3.0
