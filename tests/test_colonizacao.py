# -*- coding: utf-8 -*-
"""Tests of the colonization dynamics reader (colonizacao.py).

* a small synthetic workbook checks the reading rules (header, blocks, years, codes,
  individuals, cohorts, density, joined plots);
* the NEMA workbooks of the Motta (2026) monograph are private: the validation against
  the "Grafico de densidade dinamica" table runs only when the folder is available
  (set MANGUETREE_COLONIZACAO_DIR or keep the default location next to the repository).
"""
import datetime as dt
import os
from pathlib import Path

import openpyxl
import pytest

from manguetree import colonizacao as col

ROOT = Path(__file__).resolve().parents[1]
FOLDER = Path(os.environ.get(
    "MANGUETREE_COLONIZACAO_DIR",
    ROOT.parent / "Atualização" / "Colonização" / "Planilhas" / "Dinâmica Mono Laiza"))


def _workbook(path, letter="K"):
    """Entry sheet with the 3-row header model (no year in the blocks) and a Contagem
    sheet whose "coluna ref" table gives the year of the second block."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = letter
    fixed = ["Tipo Atual", "lado", "ind", "Coleta", "Coorte", "Tipo de Diâmetro", "Lacre",
             "Espécie"]
    block = ["Tipo", "Altura (cm)", "Diâmetro (cm)", "Observação"]
    ws.append([None] * 9 + ["Coleta 35", None, None, None, None, "Coleta 36"])
    ws.append([None] * 9 + [dt.datetime(2005, 2, 16), None, None, None, None,
                            dt.datetime(2006, 5, 4)])
    ws.append(fixed + [None] + block + [None] + block)
    ws.append(["não preencher esta linha"])

    def row(tipo_atual, lado, ind, coorte, lacre, sp, t1=None, h1=None, t2=None, h2=None):
        r = [tipo_atual, lado, ind, 35, coorte, None, lacre, sp, None]
        r += [t1, h1, None, None, None, t2, h2, None, None]
        ws.append(r)

    # individual 1: two rows with the same ind (a juvenile and an extra trunk)
    row("J", "A", 1, 2004, 101, "Av", "J", 30, "J", 45)
    row("TR", "A", 1, 2004, 102, "Av", "TR", None, "TR", None)
    ws.append([])                                   # blank line
    # individual 2: juvenile in 2005, dead (X) in 2006
    row(None, "A", 2, 2005, 103, "Lg", "J", 20, "X", None)
    ws.append([])
    # one row per individual (no ind number, no blank lines)
    row(None, None, None, 2005, 104, "Av", "J", 25, "J", 35)
    row(None, None, None, "?", 105, "Av", "J", 25, "J", 35)       # no cohort
    row(None, None, None, 2007, 106, "Lg", "J", 25, "J", 35)       # cohort after the year
    row(None, None, None, 2005, 107, "Lg", "J", 25, "N1", None)    # not found in 2006
    row("VERIFICAR", None, None, None, None, None)                 # note, ignored
    row(None, None, None, 2005, 104, "Av")                         # repeated tag
    cont = wb.create_sheet("Contagem")
    cont.append(["contagem"])
    cont.append([])
    cont.append(["Total"])
    cont.append([None, "linhas ref", None, "4:1000", "coorte"])
    cont.append(["coluna ref", "ano", "total", "?", "<1998", 1998])
    cont.append(["O", 2006, 1, 2, 3, 4])               # column O = first column of block 2
    wb.create_sheet("Excluidos").append(["Tipo Atual", "ind", "Lacre"])
    wb.save(path)
    return path


@pytest.fixture
def plot_k(tmp_path):
    return col.le_parcela(_workbook(tmp_path / "Parcela K.xlsx"))


def test_codes_are_normalised_and_classified():
    assert col.normaliza_codigo(" j* ") == "J"
    assert col.normaliza_codigo("-") == ""
    assert col.classifica("J") == "jovem"
    assert col.classifica("N3") == "morto"            # N3 is a typing error for Y
    assert col.classifica("N1") == "incerto" and col.classifica("N2") == "incerto"
    assert col.classifica("XTR") == "tronco_morto"
    assert col.classifica("E") == "excluido"
    assert col.classifica("393") == "desconhecido"
    assert col.classifica("") == "vazio"


def test_blocks_and_years(plot_k):
    assert plot_k.parcela == "K" and plot_k.aba == "K"
    assert len(plot_k.blocos) == 2
    b1, b2 = plot_k.blocos
    assert (b1.ano, b1.origem_ano) == (2005, "data")             # no year, no ref: the date
    assert (b2.ano, b2.origem_ano) == (2006, "coluna ref")       # the ref table wins
    assert b2.data.year == 2006
    assert b1.col_altura_ano is not None


def test_individuals_and_notes(plot_k):
    # ind 1 (two rows), ind 2, 104, 105, 106, 107 and the repeated 104
    assert len(plot_k.individuos) == 7
    assert [len(i.linhas) for i in plot_k.individuos[:2]] == [2, 1]
    assert plot_k.lacres_repetidos == [104]
    assert [t for _, t in plot_k.linhas_anotacao] == ["VERIFICAR"]
    assert plot_k.avisos == []


def test_density_two_versions(plot_k):
    sem = col.densidade_jovens([plot_k], incluir_sem_coorte=False, areas={"K": 60.0})
    com = col.densidade_jovens([plot_k], incluir_sem_coorte=True, areas={"K": 60.0})
    ha = 0.006
    # 2005: ind 1, ind 2, 104, 107 have a valid cohort; 105 has none and 106 is impossible
    assert list(sem["n"]) == [4, 2]
    assert list(com["n"]) == [6, 4]
    assert sem.loc[sem["ano"] == 2005, "ind_ha"].iloc[0] == pytest.approx(4 / ha)
    # 2006: ind 2 is dead (X) and 107 is N1: neither counts as a juvenile
    assert com.loc[com["ano"] == 2006, "n"].iloc[0] == 4


def test_trunks_are_counted_only_in_the_trunk_density(plot_k):
    tr = col.densidade_jovens([plot_k], areas={"K": 60.0}, troncos=True)
    j = col.densidade_jovens([plot_k], areas={"K": 60.0})
    assert tr.loc[tr["ano"] == 2005, "n"].iloc[0] == j.loc[j["ano"] == 2005, "n"].iloc[0] + 1


def test_by_species_and_cohort_table(plot_k):
    esp = col.densidade_jovens([plot_k], areas={"K": 60.0}, por_especie=True)
    assert set(esp["especie"]) == {"Av", "Lg"}
    assert esp.loc[(esp["ano"] == 2005) & (esp["especie"] == "Av"), "n"].iloc[0] == 2
    coh = col.tabela_coortes(plot_k).set_index("ano")
    assert coh.loc[2005, "j_valido"] == 4 and coh.loc[2005, "j_sem_coorte"] == 1
    assert coh.loc[2005, "j_coorte_impossivel"] == 1
    assert coh.loc[2006, "n1"] == 1


def test_joined_plots_sum_counts_and_areas(tmp_path):
    a = col.le_parcela(_workbook(tmp_path / "Parcela A.xlsx", "A"))
    b = col.le_parcela(_workbook(tmp_path / "Parcela B.xlsx", "B"))
    out = col.densidade_jovens([a, b], unidas={"A+B": ["A", "B"]},
                               areas={"A": 25.0, "B": 25.0})
    assert list(out["parcela"].unique()) == ["A+B"]
    assert list(out["n"]) == [8, 4]
    assert out["area_ha"].iloc[0] == pytest.approx(0.005)


def test_year_can_be_corrected(tmp_path):
    p = col.le_parcela(_workbook(tmp_path / "Parcela K.xlsx"), anos_manuais={0: 2003})
    assert (p.blocos[0].ano, p.blocos[0].origem_ano) == (2003, "manual")
    assert p.anos() == [2003, 2006]


def test_plot_letter_comes_from_the_file_name(tmp_path):
    path = _workbook(tmp_path / "planilha qualquer.xlsx")
    with pytest.raises(ValueError):
        col.le_parcela(path)
    assert col.le_parcela(path, parcela="K").parcela == "K"


def test_reference_table_reader(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([None, None, "J", "Densidade de jovens ind/ha"])
    ws.append([None, "Ano", "a", "b"])
    ws.append([None, 1998.0, 3200.0, "-"])
    ws.append([None, 1999.0, 6400.0, 62000.0])
    wb.save(tmp_path / "g.xlsx")
    ref = col.le_tabela_densidade(tmp_path / "g.xlsx")
    assert ref == {("A", 1998): 3200.0, ("A", 1999): 6400.0, ("B", 1999): 62000.0}


def test_height_statistics(plot_k):
    est = col.estatistica_altura([plot_k]).set_index("ano")
    assert est.loc[2005, "n"] == 6 and est.loc[2005, "media"] == pytest.approx(25.0)
    assert est.loc[2005, "dp"] == pytest.approx(10 ** 0.5)          # sample SD
    assert est.loc[2005, "minimo"] == 20 and est.loc[2005, "maximo"] == 30
    assert est.loc[2006, "media"] == pytest.approx(37.5)
    only = col.estatistica_altura([plot_k], incluir_sem_coorte=False).set_index("ano")
    assert only.loc[2005, "n"] == 4                                  # 105 and 106 out
    big = col.estatistica_altura([plot_k], minimo_cm=30).set_index("ano")
    assert big.loc[2005, "n"] == 1 and big.loc[2006, "n"] == 4


def test_joined_height_pools_the_individuals(tmp_path):
    a = col.le_parcela(_workbook(tmp_path / "Parcela A.xlsx", "A"))
    b = col.le_parcela(_workbook(tmp_path / "Parcela B.xlsx", "B"))
    est = col.estatistica_altura([a, b], unidas={"A+B": ["A", "B"]}).set_index("ano")
    assert est.loc[2005, "n"] == 12 and est.loc[2005, "media"] == pytest.approx(25.0)


def test_relative_density(plot_k):
    rel = col.densidade_relativa([plot_k], areas={"K": 60.0}, incluir_sem_coorte=True)
    r = rel.set_index(["ano", "especie"])["relativa"]
    assert r[(2005, "Av")] == pytest.approx(50.0) and r[(2006, "Av")] == pytest.approx(75.0)
    assert rel.groupby("ano")["relativa"].sum().tolist() == pytest.approx([100.0, 100.0])


def _estilos():
    from manguetree import charts as ui
    return {"paleta": ui.PALETAS["lab"], "tamanho_titulo": 14, "tamanho_eixos": 11,
            "seal": False, "bar_width": 0.8, "height": 450, "width": None}


def test_charts(plot_k):
    from manguetree import colonizacao_charts as cc
    est = _estilos()
    dens = col.densidade_jovens([plot_k], areas={"K": 60.0})
    f = cc.fig_curva_densidade(dens, est, "en")
    assert len(f.data) == 1 and list(f.data[0].y) == pytest.approx([4 / 0.006, 2 / 0.006])
    assert cc.fig_curva_densidade(dens, est, "en", escala_log=True).layout.yaxis.type == "log"
    rel = col.densidade_relativa([plot_k], areas={"K": 60.0}, incluir_sem_coorte=True)
    f = cc.fig_composicao(rel, est, "K", True, "en")
    assert [tr.name for tr in f.data] == ["Avicennia schaueriana", "Laguncularia racemosa"]
    assert f.layout.barmode == "stack"
    h = cc.fig_altura(col.estatistica_altura([plot_k]), est, "en")
    assert list(h.data[0].y) == pytest.approx([25.0, 37.5])
    hs = cc.fig_altura(col.estatistica_altura([plot_k], por_especie=True), est, "en")
    assert [t.name for t in hs.data] == ["K Avicennia schaueriana", "K Laguncularia racemosa"]


def test_species_names():
    from manguetree import colonizacao_charts as cc
    assert cc.nome_especie("AV") == "Avicennia schaueriana"
    assert cc.nome_especie("Xx") == "Xx"


def test_codes_can_be_reclassified_by_the_user():
    assert col.classifica("393", {"393": "jovem"}) == "jovem"
    assert col.classifica("J", {"J": "morto"}) == "morto"
    assert col.classifica("J", {"J": "not a class"}) == "jovem"      # invalid class is ignored
    assert col.classifica("X", {"J": "morto"}) == "morto"            # other codes keep the rule


def test_reclassified_code_changes_density_and_tables(tmp_path):
    path = _workbook(tmp_path / "Parcela K.xlsx")
    base = col.le_parcela(path)
    novo = col.le_parcela(path, classes_manuais={"X": "jovem"})
    d0 = col.densidade_jovens([base], areas={"K": 60.0}).set_index("ano")["n"]
    d1 = col.densidade_jovens([novo], areas={"K": 60.0}).set_index("ano")["n"]
    assert d1[2006] == d0[2006] + 1 and d1[2005] == d0[2005]       # dead in 2006 becomes juvenile
    cod = col.tabela_codigos(novo).set_index("codigo")["classe"]
    assert cod["X"] == "jovem" and col.tabela_codigos(base).set_index("codigo")["classe"]["X"] == "morto"
    assert novo.classes_manuais == {"X": "jovem"}


def test_unknown_code_leaves_the_unknown_list_when_reclassified(tmp_path):
    wb = openpyxl.load_workbook(_workbook(tmp_path / "Parcela K.xlsx"))
    ws = wb["K"]
    ws.cell(row=5, column=10).value = "393"
    wb.save(tmp_path / "Parcela K.xlsx")
    assert col.resumo(col.le_parcela(tmp_path / "Parcela K.xlsx"))["codigos_desconhecidos"] == ["393"]
    novo = col.le_parcela(tmp_path / "Parcela K.xlsx", classes_manuais={"393": "morto"})
    assert col.resumo(novo)["codigos_desconhecidos"] == []


def test_clean_table_long_has_one_row_per_individual_and_collection(plot_k):
    longo = col.tabela_limpa([plot_k], "longo")
    assert list(longo.columns) == col.COLUNAS_LONGO
    com_dados = {f"K-{i.grupo + 1}" for i in plot_k.individuos if i.por_bloco}   # rows with no code are left out
    assert set(longo["individuo"]) == com_dados and len(com_dados) == len(plot_k.individuos) - 1
    assert longo.groupby(["individuo", "coleta"]).size().max() == 1
    assert set(longo["ano"].dropna().astype(int)) == {2005, 2006} and longo["usada_na_analise"].all()
    um = longo[(longo["individuo"] == "K-1") & (longo["ano"] == 2005)].iloc[0]
    assert (um["codigo"], um["altura_cm"], um["especie"], um["coorte"]) == ("J", 30, "Av", 2004)
    assert str(um["data"]) == "2005-02-16" and um["lacres"] == "101; 102"
    assert um["troncos_vivos"] == 1 and um["n_jovens"] == 1


def test_clean_table_marks_only_the_last_collection_of_a_year(tmp_path):
    p = col.le_parcela(_workbook(tmp_path / "Parcela K.xlsx"), anos_manuais={0: 2006})
    longo = col.tabela_limpa([p], "longo")
    usada = longo.drop_duplicates("coleta").set_index("coleta")["usada_na_analise"]
    assert usada.tolist() == [False, True]


def test_clean_table_wide_has_one_row_per_individual(plot_k):
    largo = col.tabela_limpa([plot_k], "largo")
    assert len(largo) == len([i for i in plot_k.individuos if i.por_bloco])
    assert {"2005 codigo", "2005 altura_cm", "2006 codigo", "2006 altura_cm"} <= set(largo.columns)
    assert list(largo.columns)[-4:] == ["2005 codigo", "2005 altura_cm", "2006 codigo", "2006 altura_cm"]
    k2 = largo[largo["individuo"] == "K-2"].iloc[0]
    assert (k2["2005 codigo"], k2["2006 codigo"], k2["2005 altura_cm"]) == ("J", "X", 20)
    with pytest.raises(ValueError):
        col.tabela_limpa([plot_k], "outro")


def test_age_and_log_linear_regression():
    import numpy as np
    import pandas as pd
    anos = [2002, 2004, 2008, 2016]
    dens = pd.DataFrame({"parcela": "K", "ano": anos,
                         "ind_ha": [1000.0 * (a - 2000) ** -0.5 for a in anos]})
    dens = pd.concat([dens, pd.DataFrame({"parcela": ["Z"], "ano": [2010], "ind_ha": [5.0]})])
    d = col.com_idade(dens, {"K": 2000, "Z": 0})                 # Z has no start year
    assert d["parcela"].unique().tolist() == ["K"] and d["idade"].tolist() == [2, 4, 8, 16]
    r = col.regressao_log_linear(d)
    assert r["b"] == pytest.approx(-0.5) and r["a"] == pytest.approx(np.log(1000.0))
    assert r["r2"] == pytest.approx(1.0) and r["n"] == 4 and r["ep_b"] == pytest.approx(0.0, abs=1e-9)
    assert col.com_idade(dens, {"K": 2003}).shape[0] == 3           # ages <= 0 are left out
    assert col.regressao_log_linear(d.head(2)) is None              # fewer than three points
    assert col.regressao_log_linear(d.assign(idade=5)) is None      # a single age


def test_regression_ignores_zero_density():
    import pandas as pd
    d = pd.DataFrame({"idade": [1, 2, 4, 8], "ind_ha": [100.0, 0.0, 25.0, 12.5]})
    r = col.regressao_log_linear(d)
    assert r["n"] == 3 and r["b"] == pytest.approx(-1.0)


def test_establishment_years_of_the_monograph_plots():
    # Estevam (2019), Fig. 2.2: the plots of the monograph and their establishment years
    est = col.ANOS_ESTABELECIMENTO
    assert {k: est[k] for k in "ABDHIKLOR"} == {"A": 1998, "B": 1998, "D": 1998, "H": 2004,
                                                "I": 2004, "K": 2006, "L": 2009, "O": 2012,
                                                "R": 2014}
    assert est["A+B"] == 1998 and set(col.AREAS_M2) <= set(est)


def test_schematic_curve_follows_the_four_phases():
    import numpy as np
    x, y, fases = col.curva_esquematica()
    assert list(fases) == ["colonization", "early", "maturity", "senescence"]
    assert y[0] == 0 and y.max() == pytest.approx(1.0, abs=0.02)
    assert x[int(np.argmax(y))] == pytest.approx(0.15, abs=0.01)     # peak ends the colonization
    meio = (x > 0.15) & (x <= 0.5)
    assert (np.diff(y[meio]) < 0).all()                              # strong thinning
    mad = (x > 0.5) & (x <= 0.72)
    assert abs(y[mad].max() - y[mad].min()) < 0.05                   # nearly flat
    assert y[-1] < y[mad].min()                                      # senescence declines


def test_regression_and_schematic_figures():
    import pandas as pd
    from manguetree import colonizacao_charts as cc
    est = _estilos()
    dens = col.com_idade(pd.DataFrame({"parcela": "K", "ano": [2002, 2004, 2008, 2016],
                                       "ind_ha": [700.0, 500.0, 360.0, 250.0]}), {"K": 2000})
    reg = col.regressao_log_linear(dens)
    f = cc.fig_regressao(dens, {"": reg}, est, "en")
    assert f.layout.xaxis.type == "log" and f.layout.yaxis.type == "log"
    assert [t.name for t in f.data] == ["K", "Joint fit"]
    f = cc.fig_regressao(dens, {"K": reg}, est, "pt")
    assert f.data[-1].name == "Ajuste da parcela K"
    e = cc.fig_esquema(est, "en")
    assert len(e.data) == 1 and len(e.layout.shapes) == 4
    assert "not to scale" in e.layout.title.text


def test_page_export_tab_and_reclassify(tmp_path):
    at = _page_with_upload(tmp_path)
    assert not at.exception
    at.selectbox(key="colon_rc_cod_K").set_value("X").run()
    at.selectbox(key="colon_rc_cls_K_X").set_value("jovem")
    at.button(key="colon_rc_ok_K").click().run()
    assert not at.exception
    density = _density_table(at)
    assert density["K"].round(1).tolist() == [round(4 / 0.006, 1), round(3 / 0.006, 1)]
    at.button(key="colon_rc_clear_K").click().run()
    assert _density_table(at)["K"].round(1).tolist() == [round(4 / 0.006, 1), round(2 / 0.006, 1)]
    at.radio(key="colon_formato").set_value("largo").run()
    assert not at.exception


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PAGE = ROOT / "src" / "manguetree" / "app" / "pages" / "5_Colonizacao.py"


def _page_with_upload(tmp_path, run=True):
    from streamlit.testing.v1 import AppTest
    data = _workbook(tmp_path / "Parcela K.xlsx").read_bytes()
    at = AppTest.from_file(str(PAGE), default_timeout=60).run()
    at.file_uploader[0].set_value([("Parcela K.xlsx", data, XLSX)])
    at.run()
    if run:                                       # sidebar form: "Run analysis"
        next(b for b in at.button if "Run" in b.label).click().run()
    return at


def _density_table(at):
    """The ind/ha table of the density tab (float values, one column per plot)."""
    return next(d.value for d in at.dataframe
                if list(d.value.columns) == ["K"] and d.value["K"].dtype.kind == "f")


def test_page_without_upload_asks_for_files():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(PAGE), default_timeout=60).run()
    assert not at.exception and not at.dataframe


def test_page_shows_the_check_and_the_density(tmp_path):
    at = _page_with_upload(tmp_path)
    assert not at.exception and not at.error
    assert [t.label for t in at.tabs][:4] == ["Check", "Juvenile density", "Height", "Charts"]
    summary = at.dataframe[0].value
    assert summary["Plot"].tolist() == ["K"] and summary["Individuals"].tolist() == [7]
    assert summary["Repeated tags"].tolist() == [1] and summary["No cohort"].tolist() == [1]
    density = _density_table(at)
    assert density["K"].round(1).tolist() == [round(4 / 0.006, 1), round(2 / 0.006, 1)]


def test_page_year_correction_can_be_applied_and_undone(tmp_path):
    at = _page_with_upload(tmp_path)
    at.number_input(key="colon_fix_ano_K_1").set_value(2003)
    at.button(key="colon_fix_ok_K").click().run()
    assert not at.exception
    assert at.dataframe[1].value["Year"].tolist() == [2003, 2006]
    at.button(key="colon_fix_clear_K").click().run()
    assert at.dataframe[1].value["Year"].tolist() == [2005, 2006]


# --- validation against the monograph workbooks (private; skipped when absent)
needs_data = pytest.mark.skipif(not FOLDER.exists(), reason="NEMA workbooks not available")

#: the published table has 167 ind/ha for plot O in 2014 and 2015, but the plot's own
#: count is 12 juveniles (2000 ind/ha): a typing error of the table.
KNOWN_TABLE_ERRORS = {("O", 2014), ("O", 2015)}


@pytest.fixture(scope="module")
def monograph_plots():
    return [col.le_parcela(str(f)) for f in sorted(FOLDER.glob("Parcela *.xlsx"))]


@needs_data
def test_density_matches_the_monograph_table(monograph_plots):
    ref = col.le_tabela_densidade(str(FOLDER / "Tratamento" / "Grafico de densidade dinamica.xlsx"))
    dens = col.densidade_jovens(monograph_plots, incluir_sem_coorte=False)
    cmp = col.compara_com_referencia(dens, ref)
    assert len(cmp) >= 100
    wrong = {(r.parcela, r.ano) for r in cmp.itertuples() if not r.igual}
    assert wrong <= KNOWN_TABLE_ERRORS, sorted(wrong - KNOWN_TABLE_ERRORS)


@needs_data
def test_joined_a_and_b_equals_the_mean_of_the_two(monograph_plots):
    dens = col.densidade_jovens(monograph_plots)
    ab = col.densidade_jovens(monograph_plots, unidas={"A+B": ["A", "B"]})
    ab = ab[ab["parcela"] == "A+B"].set_index("ano")["ind_ha"]
    a = dens[dens["parcela"] == "A"].set_index("ano")["ind_ha"]
    b = dens[dens["parcela"] == "B"].set_index("ano")["ind_ha"]
    assert ((a + b) / 2 - ab).abs().max() < 1e-6      # equal areas: the mean of densities


def test_results_wait_for_the_run_button(tmp_path):
    at = _page_with_upload(tmp_path, run=False)
    assert not at.exception
    assert not any(list(d.value.columns) == ["K"] for d in at.dataframe)
    next(b for b in at.button if "Run" in b.label).click().run()
    assert not at.exception and _density_table(at) is not None


def test_version_label_has_no_citation_in_parentheses(tmp_path):
    at = _page_with_upload(tmp_path, run=False)
    assert at.radio(key="colon_versao").options == ["Only individuals with a cohort",
                                                    "Including individuals without a cohort"]


def test_join_groups_are_free_and_disjoint():
    unidas, rep = col.monta_unidas([["A", "B"], ["B", "D", "H"], ["K"], ["X", "Y"]],
                                   {"A", "B", "D", "H", "K"})
    assert unidas == {"A+B": ["A", "B"], "D+H": ["D", "H"]} and rep == ["B"]
    unidas, rep = col.monta_unidas([["D", "H", "K"], ["B", "A"]], {"A", "B", "D", "H", "K"})
    assert unidas == {"D+H+K": ["D", "H", "K"], "A+B": ["A", "B"]} and rep == []
    assert col.monta_unidas([["A"]], {"A"}) == ({}, [])


def test_establishment_year_of_a_union_is_the_oldest():
    assert col.ano_estabelecimento("K") == 2006
    assert col.ano_estabelecimento("D+H+K") == 1998 and col.ano_estabelecimento("K+L") == 2006
    assert col.ano_estabelecimento("Z") == 0


def test_count_by_year_and_cohort(plot_k):
    c = col.contagem_por_ano([plot_k], ["jovem"], por="classe", agrupar="coorte")
    t = c.pivot_table(index="ano", columns="grupo", values="n", aggfunc="sum", fill_value=0)
    assert t.loc[2005].to_dict() == {"2004": 1, "2005": 3, "2007": 1, "sem coorte": 1}
    assert t.loc[2006].to_dict() == {"2004": 1, "2005": 1, "2007": 1, "sem coorte": 1}
    assert list(col.ordem_coortes(["sem coorte", "2007", "<1998", "2004"])) == ["<1998", "2004", "2007", "sem coorte"]


def test_count_joins_codes_or_keeps_them_apart(plot_k):
    juntos = col.contagem_por_ano([plot_k], ["X", "N1", "J"], por="codigo", agrupar="nenhum")
    assert juntos.groupby("ano")["n"].sum().to_dict() == {2005: 6, 2006: 6}      # J + N1 + X together
    apart = col.contagem_por_ano([plot_k], ["X", "N1", "J"], por="codigo", agrupar="codigo")
    assert apart[apart["ano"] == 2006].set_index("grupo")["n"].to_dict() == {"J": 4, "N1": 1, "X": 1}
    por_esp = col.contagem_por_ano([plot_k], ["jovem"], por="classe", agrupar="especie")
    assert por_esp[por_esp["ano"] == 2005].set_index("grupo")["n"].to_dict() == {"Av": 3, "Lg": 3}
    assert col.contagem_por_ano([plot_k], [], por="classe").empty


def test_count_joined_plots(tmp_path):
    a = col.le_parcela(_workbook(tmp_path / "Parcela K.xlsx"))
    b = col.le_parcela(_workbook(tmp_path / "Parcela L.xlsx", "L"))
    c = col.contagem_por_ano([a, b], ["jovem"], agrupar="nenhum", unidas={"K+L": ["K", "L"]})
    assert c["parcela"].unique().tolist() == ["K+L"] and c.set_index("ano")["n"].to_dict() == {2005: 12, 2006: 8}


def test_height_of_other_classes(tmp_path):
    path = _workbook(tmp_path / "Parcela K.xlsx")
    wb = openpyxl.load_workbook(path)
    wb["K"].cell(row=8, column=16).value = 12              # individual 2 is dead (X) in 2006, height 12
    wb.save(path)
    p = col.le_parcela(path)
    mortos = col.estatistica_altura([p], classes=("morto",))
    assert mortos[["ano", "n", "media"]].values.tolist() == [[2006, 1, 12.0]]
    juntos = col.estatistica_altura([p], classes=("jovem", "morto"), por_classe=True)
    assert set(juntos["classe"]) == {"jovem", "morto"}
    so_j = col.estatistica_altura([p]).set_index("ano")["n"]
    assert so_j.to_dict() == {2005: 6, 2006: 4}              # default is still juveniles only


def test_extra_verification_tables(plot_k):
    r = col.resumo(plot_k)
    assert r["sem_coorte"] == 1 and r["especies"] == ["Av", "Lg"]
    cod = col.tabela_codigos_por_ano(plot_k).set_index("ano")
    assert cod.loc[2005, "J"] == 6 and cod.loc[2006, "J"] == 4 and cod.loc[2006, "X"] == 1
    reg = col.tabela_registros(plot_k).set_index("ano")
    assert reg.loc[2005].to_dict() == {"registros": 6, "novos": 6, "ultimos": 0}
    assert reg.loc[2006].to_dict() == {"registros": 6, "novos": 0, "ultimos": 0}
    esp = col.tabela_especies(plot_k).set_index("especie")
    assert esp.loc["Av"].tolist() == [3, 3, 1] and esp.loc["Lg"].tolist() == [3, 3, 0]
    alt = col.tabela_alertas_altura(plot_k).set_index("ano")
    assert alt.loc[2005, "linhas_j"] == 6 and alt.loc[2005, "altura_maxima"] == 30
    assert alt["sem_altura"].sum() == 0 and alt["suspeitas"].sum() == 0
    assert col.tabela_blocos(plot_k)["registros"].tolist() == [6, 6]
    assert col.tabela_alertas_altura(plot_k, maximo_cm=40).set_index("ano").loc[2006, "suspeitas"] == 1


def test_count_figure(plot_k):
    from manguetree import colonizacao_charts as cc
    est = _estilos()
    c = col.contagem_por_ano([plot_k], ["jovem"], agrupar="coorte")
    f = cc.fig_contagem(c, est, "en", "coorte")
    assert [t.name for t in f.data] == ["2004", "2005", "2007", "No cohort"] and f.layout.barmode == "stack"
    assert f.data[-1].marker.color == "#B8C2BC"
    p = cc.fig_contagem(c, est, "pt", "coorte", percentual=True)
    assert tuple(p.layout.yaxis.range) == (0, 100) and p.data[-1].name == "Sem coorte"
    assert sum(t.y[0] for t in p.data) == pytest.approx(100)
    e = cc.fig_contagem(col.contagem_por_ano([plot_k], ["jovem"], agrupar="especie"), est, "en", "especie")
    assert [t.name for t in e.data] == ["Avicennia schaueriana", "Laguncularia racemosa"]
    n = cc.fig_contagem(col.contagem_por_ano([plot_k], ["jovem"], agrupar="nenhum"), est, "en", "nenhum")
    assert n.layout.showlegend is False


def test_height_chart_names_classes(plot_k):
    from manguetree import colonizacao_charts as cc
    est = col.estatistica_altura([plot_k], classes=("jovem", "morto"), por_classe=True)
    f = cc.fig_altura(est, _estilos(), "en")
    assert any("juveniles" in t.name for t in f.data)


def test_page_charts_tab_shows_every_chart_without_switching(tmp_path):
    at = _page_with_upload(tmp_path)
    assert not at.exception
    assert [t.label for t in at.tabs][4:9] == ["Density", "Age", "Height", "Count by cohort", "Jiménez schematic"]
    at.radio(key="colon_ct_por").set_value("codigo").run()
    at.multiselect(key="colon_ct_itens_codigo").set_value(["J", "X"]).run()
    at.radio(key="colon_ct_pilha").set_value("item").run()
    at.checkbox(key="colon_ct_pct").set_value(True).run()
    assert not at.exception
    at.radio(key="colon_fit_modo").set_value("plot").run()
    assert not at.exception


def test_page_joined_plots_apply_to_every_tab(tmp_path):
    from streamlit.testing.v1 import AppTest
    ks = [(f"Parcela {l}.xlsx", _workbook(tmp_path / f"Parcela {l}.xlsx", l).read_bytes(), XLSX)
          for l in ("K", "L")]
    at = AppTest.from_file(str(PAGE), default_timeout=60).run()
    at.file_uploader[0].set_value(ks).run()
    at.multiselect(key="colon_join_1").set_value(["K", "L"])      # form widget: applied on submit
    next(b for b in at.button if "Run" in b.label).click().run()
    assert not at.exception
    dens = next(d.value for d in at.dataframe
                if list(d.value.columns) == ["K+L"] and d.value["K+L"].dtype.kind == "f")
    assert dens["K+L"].round(1).tolist() == [round(8 / 0.012, 1), round(4 / 0.012, 1)]
    assert any("K+L" in c.value for c in at.caption)


def test_chart_texts_can_be_edited(tmp_path):
    import json
    at = _page_with_upload(tmp_path)
    at.checkbox(key="adjtxt_colon_dens").set_value(True).run()
    at.text_input(key="adjtit_colon_dens").set_value("My title").run()
    at.text_input(key="adjxt_colon_dens").set_value("Years").run()
    at.text_input(key="adjyt_colon_dens").set_value("Juveniles per ha").run()
    assert not at.exception
    specs = [json.loads(e.proto.spec) for e in at.get("plotly_chart")]
    assert any(sp["layout"]["title"]["text"] == "My title"
               and sp["layout"]["xaxis"]["title"]["text"] == "Years"
               and sp["layout"]["yaxis"]["title"]["text"] == "Juveniles per ha" for sp in specs)


def test_colonization_page_is_hidden_unless_switched_on(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from manguetree import charts
    monkeypatch.delenv("MANGUETREE_COLONIZACAO", raising=False)
    assert charts.colonizacao_enabled() is False
    at = AppTest.from_file(str(PAGE), default_timeout=60).run()
    assert not at.exception
    assert any("teste" in i.value or "testing" in i.value for i in at.info)
    assert not at.sidebar.file_uploader if hasattr(at.sidebar, "file_uploader") else True
    monkeypatch.setenv("MANGUETREE_COLONIZACAO", "true")
    assert charts.colonizacao_enabled() is True
