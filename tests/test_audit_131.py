# -*- coding: utf-8 -*-
"""Fixes of the 1.3.1 audit: each test reproduces one problem found with the template
workbook, its realistic variations or the colonization workbooks."""
from pathlib import Path

import pandas as pd
import pytest

from manguetree import colonizacao as col
from test_colonizacao import PAGE, XLSX, _df_with, _workbook

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "manguetree" / "app"


@pytest.fixture
def plot_k(tmp_path):
    return col.le_parcela(_workbook(tmp_path / "Parcela K.xlsx"))


def _run(at):
    next(b for b in at.button if "Run" in b.label).click().run()
    return at


# ---------------------------------------------------------------- C1
def test_two_files_of_the_same_plot_keep_the_first_and_say_so(tmp_path):
    from streamlit.testing.v1 import AppTest
    data = _workbook(tmp_path / "Parcela K.xlsx").read_bytes()
    at = AppTest.from_file(str(PAGE), default_timeout=60).run()
    at.file_uploader[0].set_value([("Parcela K.xlsx", data, XLSX),
                                   ("Parcela K (1).xlsx", data, XLSX)])
    _run(at.run())
    assert not at.exception
    assert any("Parcela K (1).xlsx" in e.value for e in at.error)
    assert _df_with(at, "Plot", "Individuals")["Plot"].tolist() == ["K"]


# ---------------------------------------------------------------- C2
@pytest.mark.parametrize("todos", [False, True])
def test_count_by_year_follows_the_density_version(plot_k, todos):
    dens = col.densidade_jovens([plot_k], incluir_sem_coorte=todos)
    cont = col.contagem_por_ano([plot_k], ["jovem"], agrupar="nenhum", incluir_sem_coorte=todos)
    assert cont.groupby("ano")["n"].sum().to_dict() == dens.set_index("ano")["n"].to_dict()


def test_count_hides_incomplete_years_like_the_density(tmp_path):
    a = col.le_parcela(_workbook(tmp_path / "Parcela K.xlsx"))
    b = col.le_parcela(_workbook(tmp_path / "Parcela L.xlsx", "L"))
    b.blocos = b.blocos[:1]                    # L read only in 2005: 2006 is incomplete
    b._tabela_individuos = None
    unidas = {"K+L": ["K", "L"]}
    cont = col.contagem_por_ano([a, b], ["jovem"], agrupar="nenhum", unidas=unidas,
                                ocultar_incompletas=True)
    dens = col.densidade_jovens([a, b], unidas=unidas, incluir_sem_coorte=True,
                                ocultar_incompletas=True)
    assert sorted(cont["ano"].unique()) == sorted(dens["ano"].unique()) == [2005]


# ---------------------------------------------------------------- A1
def test_pdf_dbh_class_labels_keep_every_digit():
    from manguetree.reports import panel as pn
    assert pn._class_labels("pt") == ["< 2,5", "2,5 a 5", "5 a 7,5", "7,5 a 10", "10 a 12,5", "≥ 12,5"]
    assert pn._class_labels("en") == ["< 2.5", "2.5 to 5", "5 to 7.5", "7.5 to 10", "10 to 12.5", "≥ 12.5"]


# ---------------------------------------------------------------- E1, E2
def _template_upload(page, name, lang="pt"):
    from streamlit.testing.v1 import AppTest
    from manguetree import template
    at = AppTest.from_file(str(APP / "pages" / page), default_timeout=120).run()
    at.file_uploader[0].set_value((name, template.excel_bytes(lang), XLSX))
    return at.run()


@pytest.mark.parametrize("lang", ["pt", "en"])
def test_template_plot_is_named_after_the_file_not_its_sheet(lang):
    at = _template_upload("1_Single_plot.py", "H2_2020.xlsx", lang)
    assert not at.exception
    cap = " ".join(c.value for c in at.caption)
    assert "Plot: H2_2020" in cap and "Plot: Data" not in cap and "Plot: Dados" not in cap
    assert not at.selectbox or all(s.label != "Sheet" for s in at.selectbox)


def test_sheet_names_that_name_no_plot():
    from manguetree import charts as ui
    assert ui.is_help_sheet("Instruções") and ui.is_help_sheet("instrucoes") and ui.is_help_sheet("Instructions")
    for nome in ("Dados", "Data", "Sheet1", "Planilha1", "2009"):
        assert ui.is_generic_sheet(nome)
    for nome in ("H2", "T2 2009", "Parcela K"):
        assert not ui.is_generic_sheet(nome)


def test_temporal_leaves_the_instructions_sheet_out():
    at = _template_upload("3_Temporal.py", "H2.xlsx")
    assert not at.exception
    sel = next(m for m in at.multiselect if m.key and m.key.startswith("sheets_temp_"))
    assert sel.value == ["Dados"]


# ---------------------------------------------------------------- C3 to C7
def _odd_workbook(path, letter="K"):
    """The synthetic workbook with a 700 cm height (row 10, column K), a juvenile without
    species (row 11) and a mistyped cohort (row 13)."""
    import openpyxl
    _workbook(path, letter)
    wb = openpyxl.load_workbook(path)
    ws = wb[letter]
    ws["K10"].value = 700
    ws["H11"].value = None
    ws["E13"].value = 20118
    wb.save(path)
    return path


def test_to_fix_list_points_at_every_odd_cell(tmp_path):
    p = col.le_parcela(_odd_workbook(tmp_path / "Parcela K.xlsx"))
    pend = col.tabela_pendencias(p)
    got = {(r.problema, r.linha, r.coluna, None if pd.isna(r.ano) else int(r.ano))
           for r in pend.itertuples()}
    assert got == {("coorte_posterior", 12, "", 2005), ("coorte_posterior", 12, "", 2006),
                   ("coorte_invalida", 13, "", None), ("altura", 10, "K", 2005),
                   ("sem_especie", 11, "", None)}
    assert pend.loc[pend["problema"] == "altura", "lacre"].tolist() == ["104"]
    # nothing leaves the calculation: the 700 cm height is in the statistics of 2005
    est = col.estatistica_altura([p], incluir_sem_coorte=True)
    assert est.loc[est["ano"] == 2005, "maximo"].iloc[0] == 700
    alt = col.tabela_alertas_altura(p)
    assert alt.set_index("ano")["suspeitas"].to_dict() == {2005: 1, 2006: 0}


def test_blank_and_question_mark_species_are_one_label(tmp_path):
    from manguetree import colonizacao_charts as cc
    p = col.le_parcela(_odd_workbook(tmp_path / "Parcela K.xlsx"))
    dens = col.densidade_jovens([p], incluir_sem_coorte=True, por_especie=True)
    assert set(dens["especie"]) == {"Av", "Lg", col.SEM_ESPECIE}
    assert cc.nome_especie("", "en") == cc.nome_especie("?", "en") == "No species"
    assert cc.nome_especie(" ", "pt") == "Sem espécie"


def test_check_tab_lists_cells_to_fix_and_the_area_used(tmp_path):
    from streamlit.testing.v1 import AppTest
    data = _odd_workbook(tmp_path / "Parcela Z.xlsx", "Z").read_bytes()
    at = AppTest.from_file(str(PAGE), default_timeout=60).run()
    at.file_uploader[0].set_value([("Parcela Z.xlsx", data, XLSX)])
    _run(at.run())
    assert not at.exception
    fix = _df_with(at, "Row", "Column", "Tag", "Problem", "Value")
    assert len(fix) == 5 and "700 cm" in fix["Value"].tolist()
    summary = _df_with(at, "Plot", "Area used (m²)")
    assert summary["Area used (m²)"].tolist() == [60.0]
    assert any("No known area for Z" in w.value for w in at.warning)
    assert any("Area of plot Z unknown" in c.value for c in at.sidebar.caption)
    years = _df_with(at, "Plot", "Years")["Years"].tolist()
    assert years == ["2005 to 2006"]


# ---------------------------------------------------------------- C8
@pytest.mark.parametrize("nome,letra", [("Parcela K.xlsx", "K"), ("Plot K.xlsx", "K"),
                                        ("parcela_K.xlsx", "K"), ("K.xlsx", "K"),
                                        ("K (1).xlsx", "K"), ("Parcela AB.xlsx", "AB"),
                                        ("/tmp/Mono Laiza/Parcela L.xlsx", "L"),
                                        ("dados 2020.xlsx", None)])
def test_plot_letter_from_the_file_name(nome, letra):
    assert col._letra_da_planilha(nome) == letra


def test_reading_errors_and_warnings_are_translated(tmp_path):
    from streamlit.testing.v1 import AppTest
    import openpyxl
    path = _workbook(tmp_path / "dados.xlsx")
    wb = openpyxl.load_workbook(path)
    wb.create_sheet("L")
    wb.save(path)
    at = AppTest.from_file(str(PAGE), default_timeout=60).run()
    at.file_uploader[0].set_value([("dados.xlsx", path.read_bytes(), XLSX)])
    at.run()
    assert not at.exception
    msg = " ".join(e.value for e in at.error)
    assert "could not tell the plot letter" in msg and "Nao" not in msg
    assert col.traduz_rotulo("Coleta 35", "en") == "Collection 35"
    assert col.traduz_rotulo("Coletas 35 a 36", "en") == "Collections 35 to 36"
    assert col.traduz_rotulo("2005", "en") == "2005"


# ---------------------------------------------------------------- C12 to C17
def test_age_chart_keeps_zero_density_on_a_linear_axis():
    import pandas as pd
    from manguetree import colonizacao_charts as cc
    from test_colonizacao import _estilos
    d = pd.DataFrame({"parcela": ["K"] * 3, "ano": [2007, 2008, 2009], "ind_ha": [0.0, 50.0, 80.0],
                      "idade": [1, 2, 3], "membros": ["K"] * 3, "n_parcelas": [1] * 3,
                      "incompleta": [False] * 3})
    lin = cc.fig_idade(d, {}, _estilos(), "en", "markers", log=False)
    log = cc.fig_idade(d, {}, _estilos(), "en", "markers", log=True)
    assert list(lin.data[0].x) == [1, 2, 3] and list(log.data[0].x) == [2, 3]


def test_horizontal_height_bars_draw_the_sd_only_when_asked(plot_k):
    from manguetree import colonizacao_charts as cc
    from test_colonizacao import _estilos
    est = col.estatistica_altura([plot_k], incluir_sem_coorte=True)
    sem = cc.fig_altura(est, _estilos(), "en", "hbar").data[0]
    com = cc.fig_altura(est, _estilos(), "en", "hbar_sd").data[0]
    assert sem.orientation == com.orientation == "h"
    assert not (sem.error_x and sem.error_x.visible) and com.error_x.visible


def test_charts_with_the_same_title_get_different_file_names():
    from streamlit.testing.v1 import AppTest
    script = '''
import plotly.graph_objects as go
import streamlit as st
from manguetree import charts as ui
for k in ("a", "b"):
    ui.show(st, go.Figure(layout=dict(title=dict(text="Densidade"))), k, botoes=False)
st.session_state["nomes_vistos"] = dict(st.session_state["_nomes_graficos"])
'''
    at = AppTest.from_string(script, default_timeout=60).run()
    assert not at.exception
    primeiro = at.session_state["nomes_vistos"]
    assert set(primeiro.values()) == {"a", "b"} and any(n.endswith("Densidade-2") for n in primeiro)
    at.run()                                       # a rerun keeps the same names
    assert at.session_state["nomes_vistos"] == primeiro


def test_page_percent_table_and_plot_filter(tmp_path):
    from streamlit.testing.v1 import AppTest
    ks = [(f"Parcela {l}.xlsx", _workbook(tmp_path / f"Parcela {l}.xlsx", l).read_bytes(), XLSX)
          for l in ("K", "L")]
    at = AppTest.from_file(str(PAGE), default_timeout=60).run()
    at.file_uploader[0].set_value(ks).run()
    _run(at)
    at.checkbox(key="colon_ct_pct").check().run()
    assert not at.exception
    tabelas = [d.value for d in at.dataframe if d.value.index.name == "Year"]
    assert any(len(v.columns) > 1 and v.sum(axis=1).round(6).eq(100).all() for v in tabelas)
    at.multiselect(key="colon_g_pl").set_value(["K"]).run()
    assert not at.exception
    tabelas = [d.value for d in at.dataframe if d.value.index.name == "Year"]
    assert ["K"] in [list(v.columns) for v in tabelas]
    assert not any("L" in list(v.columns) for v in tabelas)


# ---------------------------------------------------------------- E3 to E9
def _resolver(region="BR_S_SE"):
    from manguetree.species import SpeciesResolver, load_genus_defaults, load_species_table
    return SpeciesResolver(load_species_table(), region, load_genus_defaults())


def _template_df(lang="pt"):
    import io
    from manguetree import io as mio, template
    df, _ = mio.load_excel_sheet(io.BytesIO(template.excel_bytes(lang)), 0, "", 100.0)
    return df


@pytest.mark.parametrize("lang", ["pt", "en"])
def test_the_template_raises_no_warning(lang):
    from manguetree.validation import validate
    assert [i.kind for i in validate(_template_df(lang), _resolver())] == []


def test_tree_number_only_on_the_first_stem_is_one_tree_everywhere():
    from manguetree import calc as mc
    from manguetree.validation import validate
    df = _template_df()
    df.loc[2, "tree_id"] = None                     # second stem of tree 2: number left blank
    kinds = [i.kind for i in validate(df, _resolver())]
    assert "stem_count_mismatch" not in kinds and "duplicate_tag" not in kinds
    res = mc.analyze(df, 100.0, _resolver())
    assert res["summary"]["n_stems"] == 5


def test_same_tag_on_two_trees_is_still_flagged():
    from manguetree.validation import validate
    df = _template_df()
    df.loc[3, "tag"] = "1001"                       # tree 3 with the tag of tree 1
    assert [i.kind for i in validate(df, _resolver())].count("duplicate_tag") == 2


def test_blank_species_says_blank():
    from manguetree.validation import validate, describe
    df = _template_df()
    df.loc[0, "species"] = None
    msgs = [describe(i, "pt") for i in validate(df, _resolver()) if i.kind == "unknown_species"]
    assert msgs == ["espécie em branco"]


@pytest.mark.parametrize("texto,valor", [("1.000", 1000.0), ("1.000 m²", 1000.0), ("1,000", 1000.0),
                                         ("1.000,5", 1000.5), ("0,01 ha", 100.0), ("2.5", 2.5),
                                         ("100", 100.0)])
def test_area_text_with_thousands_marks(texto, valor):
    from manguetree import io as mio
    assert mio._area_number(texto) == valor


def test_sampled_area_label_is_read(tmp_path):
    import openpyxl
    from manguetree import io as mio
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Área amostrada (m²)", 250])
    ws.append([])
    ws.append(["Indivíduo", "Espécie", "DAP (cm)", "Condição"])
    ws.append([1, "Rm", 8.4, "v"])
    wb.save(tmp_path / "p.xlsx")
    _, area = mio.load_excel_sheet(str(tmp_path / "p.xlsx"), 0, "", 100.0)
    assert area == 250


def test_missing_column_message_uses_column_names():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(APP / "pages" / "1_Single_plot.py"), default_timeout=60).run()
    at.file_uploader[0].set_value(("p.csv", b"tree_id;species;condition\n1;Rm;v\n", "text/csv")).run()
    msg = " ".join(e.value for e in at.error)
    assert "DBH (cm)" in msg and "Missing columns: dbh" not in msg


# ---------------------------------------------------------------- P1 to P7
def test_pdf_texts_write_the_height_unit():
    from manguetree import i18n
    for lang in ("pt", "en"):
        for k in ("report.read.single", "report.sum.multi", "report.sum.multi_same"):
            txt = i18n.catalog(lang)[k]
            assert "{h} {u}" in txt and "{h} m" not in txt


def test_temporal_prefix_has_the_years_once():
    from manguetree import nomes
    assert nomes.sem_anos("guaratiba_H2_2003_2025") == "guaratiba_H2"
    assert nomes.sem_anos("H2") == "H2" and nomes.sem_anos("2009") == "2009"
    assert nomes.lista_parcelas([nomes.sem_anos("guaratiba_H2_2003_2025")]) == "guaratiba-H2"


def test_long_plot_lists_are_never_cut_in_the_middle():
    from manguetree import nomes
    longas = ["Guaratiba-transecto-A1", "Guaratiba-transecto-A2", "Guaratiba-transecto-B1"]
    assert nomes.lista_parcelas(longas, "pt") == "3-parcelas"
    assert nomes.lista_parcelas(["F2", "H2", "J2"]) == "F2-H2-J2"


def test_multiple_plots_tables_keep_every_plot_sheet():
    from manguetree import exportar
    usados = set()
    nomes = []
    for p in ("Guaratiba transecto A parcela 1", "Guaratiba transecto A parcela 2", "Problemas"):
        n = exportar.nome_unico(p, usados | {"Problemas"})
        usados.add(n)
        nomes.append(n)
    assert len(set(nomes)) == 3 and all(len(n) <= 26 for n in nomes)
    assert nomes[2] == "Problemas (2)"


def test_temporal_pdf_names_the_plots_and_says_mean():
    import shutil
    import subprocess
    import pandas as pd
    from manguetree import report as rep
    serie = pd.DataFrame({"year": [2009, 2015], "density_live_ha": [3000.0, 2800.0],
                          "ba_live_ha": [20.0, 22.0], "mean_dbh_cm": [8.0, 9.0]})
    pdf = rep.temporal_report(serie, None, None, lang="en", figures=[], plots=["H2", "J2"])
    assert pdf[:4] == b"%PDF"
    if shutil.which("pdftotext"):
        txt = subprocess.run(["pdftotext", "-", "-"], input=pdf, capture_output=True).stdout.decode()
        assert "H2, J2" in txt and "mean of the plots" in txt


# ---------------------------------------------------------------- S1: m and cm
def test_temporal_keeps_the_chosen_parameters_when_the_height_unit_changes():
    from streamlit.testing.v1 import AppTest
    data = (ROOT / "data" / "guaratiba_H2_2003_2025.xlsx").read_bytes()
    at = AppTest.from_file(str(APP / "pages" / "3_Temporal.py"), default_timeout=300).run()
    at.file_uploader[0].set_value(("guaratiba_H2_2003_2025.xlsx", data, XLSX)).run()
    next(b for b in at.button if "Run" in b.label).click().run()
    escolha = lambda k: at.session_state[f"_escolha_{k}"]
    antes = escolha("params_sep")
    assert "height_mean_m" in antes
    for u in ("cm", "m", "cm"):
        at.radio(key="unidade_altura").set_value(u).run()
        assert not at.exception, u
        assert escolha("params_sep") == antes
    at.selectbox(key="modo_evol").set_value("dual").run()
    for u in ("m", "cm", "m"):
        at.radio(key="unidade_altura").set_value(u).run()
        assert not at.exception, u
        assert escolha("eixo_dir") == ["height_mean_m"] and escolha("eixo_esq") == ["density_live_ha"]
    at.radio(key="unidade_altura").set_value("cm").run()
    at.sidebar.selectbox[0].set_value("pt").run()          # language changes the labels too
    assert not at.exception and escolha("eixo_dir") == ["height_mean_m"]
