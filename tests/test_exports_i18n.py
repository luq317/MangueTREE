# -*- coding: utf-8 -*-
"""Bilingual PDF/Excel exports, optional seal and citation footer."""
import io
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from manguetree import calc as mc, charts, io as mio, report
from manguetree.species import SpeciesResolver, load_genus_defaults, load_species_table

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def f2():
    df, area = mio.load_excel_sheet(str(ROOT / "data" / "guaratiba_T2_2009.xlsx"),
                                    "F2", "", 100.0)
    return mc.analyze(df.dropna(subset=["dbh"]), area,
                      SpeciesResolver(load_species_table(), "BR_S_SE", load_genus_defaults()))


def _text(pdf, tmp_path):
    if shutil.which("pdftotext") is None:
        pytest.skip("pdftotext not available")
    p = tmp_path / "r.pdf"
    p.write_bytes(pdf)
    return subprocess.run(["pdftotext", str(p), "-"], capture_output=True,
                          text=True).stdout


@pytest.fixture(scope="module")
def pdf_pt(f2):
    return report.single_plot_report(f2, lang="pt")


@pytest.fixture(scope="module")
def pdf_en(f2):
    return report.single_plot_report(f2, lang="en")


def test_pdf_portuguese_accents(pdf_pt, tmp_path):
    txt = _text(pdf_pt, tmp_path)
    for s in ("Área basal", "m²/ha", "≥"):
        assert s in txt


def test_pdf_english_has_no_portuguese(pdf_en, tmp_path):
    txt = _text(pdf_en, tmp_path)
    for s in ("Parcela", "Espécie", "Densidade", "Gerado"):
        assert s not in txt
    assert "Basal area" in txt


def test_pdf_footer_citation(pdf_en, pdf_pt, tmp_path):
    en = _text(pdf_en, tmp_path)
    assert "MangueTREE v1.3.1" in en and "Pereira LS et al. (2026)" in en
    assert "github.com/luq317/MangueTREE" in en
    assert "linkedin" not in en.lower() and "@" not in en
    pt = _text(pdf_pt, tmp_path)
    assert "Pereira LS et al. (2026)" in pt and "Referências" in pt
    assert "@" not in pt


def test_no_em_dash_in_pdf(pdf_en, pdf_pt, tmp_path):
    assert "—" not in _text(pdf_en, tmp_path)
    assert "—" not in _text(pdf_pt, tmp_path)


def test_seal_off_by_default(f2, monkeypatch):
    calls = []
    for name in ("selo_mini_png_bytes", "_selo_png"):
        orig = getattr(report, name)
        monkeypatch.setattr(report, name,
                            lambda *a, _o=orig, _n=name, **k: (calls.append(_n), _o(*a, **k))[1])
    report.single_plot_report(f2)
    assert calls == []
    report.single_plot_report(f2, seal=True)
    assert "selo_mini_png_bytes" in calls
    est = {"paleta": charts.PALETAS["default"]}
    fig = charts.fig_ivi(f2["importance"], est, "en")
    assert len(fig.layout.images) == 0
    fig = charts.add_seal(charts.fig_ivi(f2["importance"], dict(est, seal=True), "en"))
    assert len(fig.layout.images) == 1
    img = fig.layout.images[0]
    assert img.y < 0 and img.xanchor == "right"        # below the axes, lower right corner


def test_excel_sheet_names_follow_language(f2):
    en = pd.ExcelFile(io.BytesIO(charts.to_excel_bytes(f2, "en")))
    pt = pd.ExcelFile(io.BytesIO(charts.to_excel_bytes(f2, "pt")))
    assert en.sheet_names != pt.sheet_names
    assert "Issues" in en.sheet_names and "Problemas" in pt.sheet_names
    assert all(len(s) <= 31 and not set("[]:*?/\\") & set(s)
               for s in en.sheet_names + pt.sheet_names)
    assert list(en.parse("Issues").columns)[4] == "Detail"
    assert list(pt.parse("Problemas").columns)[4] == "Detalhe"


def test_multiple_and_temporal_reports_are_bilingual(f2, tmp_path):
    res = [f2]
    df_param = pd.DataFrame([{"plot": "F2", "density_live_ha": 1.0, "ba_live_ha": 2.0}])
    pdf = report.multiple_plots_report(res, df_param, f2["importance"], None, lang="en")
    txt = _text(pdf, tmp_path)
    assert "Multiple-plot analysis" in txt and "Pereira LS et al. (2026)" in txt
    serie = pd.DataFrame({"year": [2009, 2010], "density_live_ha": [1.0, 2.0]})
    pdf = report.temporal_report(serie, None, lang="pt")
    txt = _text(pdf, tmp_path)
    assert "Análise temporal de parcela" in txt and "2009 a 2010" in txt


def _t2_multi(lang):
    """Multiple-plots inputs from every sheet of T2 2009 (as the page builds them)."""
    sp = SpeciesResolver(load_species_table(), "BR_S_SE", load_genus_defaults())
    path = str(ROOT / "data" / "guaratiba_T2_2009.xlsx")
    results = []
    for sheet in pd.ExcelFile(path).sheet_names:
        try:
            df, area = mio.load_excel_sheet(path, sheet, "", 100.0)
            results.append(mc.analyze(df.dropna(subset=["dbh"]), area, sp, plot_name=sheet))
        except Exception:
            continue
    rows = [{"plot": r["plot_name"], "plot_area_m2": r["summary"]["plot_area_m2"],
             "n_species_live": r["summary"]["n_species_live"],
             "density_live_ha": r["summary"]["density_live_ha"],
             "ba_live_ha": r["summary"]["ba_live_ha"],
             "mean_dbh_cm": r["summary"]["mean_dbh_cm"],
             "height_mean_m": r["summary"]["height_mean_m"],
             "canopy_height_m": r["summary"]["canopy_height_m"],
             "complexity_2_5": r["complexity"]["dbh_gt_2.5"]["ci"],
             "complexity_10": r["complexity"]["dbh_gt_10"]["ci"],
             "mortality_stems_pct": r["summary"]["mortality_stems_pct"]} for r in results]
    df_param = pd.DataFrame(rows)
    return results, df_param, mc.pooled_importance(results)


@pytest.mark.parametrize("lang", ["en", "pt"])
def test_comparison_table_never_splits_words(lang, tmp_path):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    results, df_param, ivi = _t2_multi(lang)
    shown = charts.for_display(df_param, lang=lang).round(2)
    width = report._LARGURA_UTIL                  # portrait usable width (the shipped case)
    lay = report.table_layout(shown, lang, width)
    assert lay["fits"] and abs(sum(lay["widths"]) - width) < 1
    for head, w in zip(lay["header"], lay["widths"]):
        for word in head.split():
            assert stringWidth(word, report._FONT_BOLD, lay["hdr_size"]) <= w - 2 * report._PAD
    pdf = report.multiple_plots_report(results, df_param, ivi, None, lang=lang)
    txt = _text(pdf, tmp_path)
    assert "Holdridge" in txt


def test_decimal_comma_only_in_portuguese(pdf_pt, pdf_en, tmp_path):
    assert "26,55" in _text(pdf_pt, tmp_path)
    assert "26.55" in _text(pdf_en, tmp_path)
    assert "26.55" not in _text(pdf_pt, tmp_path)


def test_missing_cells_use_catalog_text():
    assert report._cell_text(float("nan"), "en") == "n/a"
    assert report._cell_text(float("nan"), "pt") == "n/d"
    assert report._cell_text(None, "en") == "n/a"


def test_class_note_only_in_single_report(pdf_en, tmp_path):
    results, df_param, ivi = _t2_multi("en")
    multi = _text(report.multiple_plots_report(results, df_param, ivi, None, lang="en"),
                  tmp_path)
    assert "≥" not in multi
    assert "includes its lower limit" in _text(pdf_en, tmp_path)


def test_stem_count_mismatch_plural():
    from manguetree.validation import Issue, describe
    mk = lambda d, r: Issue.make("stem_count_mismatch", "warning", 1, 1, {
        "declared": d, "rows": r,
        "variant": ("d1" if d == "1" else "dn") + ("r1" if r == 1 else "rn")})
    assert describe(mk("2", 1), "en") == "declared 2 stems, 1 row"
    assert describe(mk("1", 2), "en") == "declared 1 stem, 2 rows"
    assert describe(mk("3", 5), "pt") == "declarados 3 troncos, 5 linhas"
    assert describe(mk("2", 1), "pt") == "declarados 2 troncos, 1 linha"
    assert describe(mk("1", 1), "pt") == "declarado 1 tronco, 1 linha"


def test_wide_table_stays_portrait_and_shrinks(tmp_path):
    if shutil.which("pdfinfo") is None:
        pytest.skip("pdfinfo not available")
    wide = pd.DataFrame({f"Extraordinarily{j}": [1.0] for j in range(11)})
    pdf = report._gerar("t", "", [("tab", wide)], "en", False)
    p = tmp_path / "w.pdf"; p.write_bytes(pdf)
    out = subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True).stdout
    assert "595.276 x 841.89" in out                  # reports are always A4 portrait


def test_file_names_pattern():
    """Saved files are named <plot>[_<year>]_<what>, with no accents or spaces."""
    from manguetree import nomes
    assert nomes.slug("Altura e perfil") == "Altura-e-perfil"
    assert nomes.slug("Relação <b>Altura × DAP</b>") == "Relacao-Altura-DAP"
    assert nomes.lista_parcelas(["F2", "H2", "J2"]) == "F2-H2-J2"
    assert nomes.lista_parcelas(list("ABCDEFG"), "pt") == "7-parcelas"
    assert nomes.lista_parcelas(list("ABCDEFG"), "en") == "7-plots"
    assert nomes.arquivo("x") == "x"                        # no prefix outside a session


def test_file_name_locale_keys_pair():
    from manguetree import i18n
    for k in ("file.figures", "file.report", "file.panel", "file.tables", "file.tables_evol",
              "file.tables_mort", "file.colonization"):
        for lang in ("pt", "en"):
            v = i18n.t(k, lang)
            assert v and v != k and "." not in v and " " not in v, (k, lang, v)
