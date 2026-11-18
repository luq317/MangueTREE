import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import test_app_smoke as smoke          # noqa: E402
from manguetree import charts as ui      # noqa: E402
from manguetree.i18n import t            # noqa: E402


def _labels(at):
    return [tb.label for tb in at.tabs]


def test_check_tab_before_export_on_every_page():
    at = smoke._upload("1_Single_plot.py", "guaratiba_T2_2009.xlsx")
    assert _labels(at)[-2:] == [t("tab.check", "en"), t("single.tab.export", "en")]
    at = smoke._upload("2_Multiple_plots.py", "guaratiba_T2_2009.xlsx")
    smoke._run_button(at).click().run()
    assert _labels(at)[-2:] == [t("tab.check", "en"), t("multi.tab.export", "en")]


def test_structure_cards_in_lab_order():
    at = smoke._upload("1_Single_plot.py", "guaratiba_T2_2009.xlsx")
    names = [m.label for m in at.metric]
    first = [ui.label(k, "en") for k in ("mean_dbh_cm", "height_mean_m", "canopy_height_m",
                                         "density_live_ha", "ba_live_ha")]
    assert names[:5] == first
    assert names.index(ui.label("n_species_live", "en")) > names.index(ui.label("complexity_10", "en"))
    height = next(m for m in at.metric if m.label == ui.label("height_mean_m", "en"))
    assert "±" in height.value


def test_species_shares_sum_to_100():
    import pandas as pd
    from manguetree import calc as mc
    from manguetree.species import SpeciesResolver, load_genus_defaults, load_species_table
    res_ = SpeciesResolver(load_species_table(), "BR_S_SE", load_genus_defaults())
    df = pd.DataFrame({"tree_id": [1, 2, 3, 4], "species": ["Rm", "Rm", "Lg", "Av"],
                       "dbh": [5.0, 6.0, 7.0, 8.0], "height": [3, 4, 5, 5],
                       "condition": ["v", "v", "v", "m"]})
    r = mc.analyze(df, 100.0, res_)
    for base in ("density", "ba"):
        sh = ui.species_shares(r, base)
        assert abs(sum(v for (s, c), v in sh.items() if c == "live") - 100) < 1e-9
    assert ui.species_shares(r, "density")[("Rhizophora mangle", "live")] == 200 / 3
