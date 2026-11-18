import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import test_app_smoke as smoke          # noqa: E402
from manguetree import calc as mc        # noqa: E402
from manguetree import charts as ui      # noqa: E402
from manguetree import dashboard as dash  # noqa: E402
from manguetree import io as mio         # noqa: E402
from manguetree.i18n import t            # noqa: E402
from manguetree.species import SpeciesResolver, load_genus_defaults, load_species_table  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = SpeciesResolver(load_species_table(), "BR_S_SE", load_genus_defaults())


def _res():
    df, a = mio.load_excel_sheet(str(ROOT / "data" / "guaratiba_T2_2009.xlsx"), "F2", "", 100.0)
    return mc.analyze(df, a, RES, plot_name="F2")


def test_summary_panel_png_and_pdf_both_themes():
    r = _res()
    for theme in ("light", "dark"):
        assert dash.summary_panel(r, theme, "pt", dpi=60).startswith(b"\x89PNG")
    assert dash.summary_panel(r, "light", "en", fmt="pdf", dpi=60).startswith(b"%PDF")


def test_every_vertical_profile_kind():
    r = _res()
    for kind in ui.PROFILE_KINDS:
        assert ui.fig_perfil_vertical(r, {"paleta": ["#000", "#111"]}, "pt", kind=kind) is not None


def test_regression_for_one_species():
    _fig, det = ui.fig_altura_dap(_res(), {"paleta": ["#000"]}, "en", species=["Rhizophora mangle"])
    assert len(det) == 1


def test_single_plot_opens_on_summary_panel():
    at = smoke._upload("1_Single_plot.py", "guaratiba_T2_2009.xlsx")
    assert not at.exception
    assert at.tabs[0].label == t("single.tab.panel", "en")


def test_multiple_species_tab_before_ivi():
    at = smoke._upload("2_Multiple_plots.py", "guaratiba_T2_2009.xlsx")
    smoke._run_button(at).click().run()
    assert not at.exception
    labels = [tb.label for tb in at.tabs]
    assert labels.index(t("multi.tab.species", "en")) < labels.index(t("multi.tab.ivi", "en"))
