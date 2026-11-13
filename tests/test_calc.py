import pandas as pd
import pytest

from manguetree import calc
from manguetree.species import SpeciesResolver, load_genus_defaults, load_species_table

RES = SpeciesResolver(load_species_table(), "BR_S_SE", load_genus_defaults())


def _plot():
    # Third stem has a DBH but no tree id and a blank condition
    return pd.DataFrame({
        "tree_id": [1, 2, None],
        "species": ["As", "Rh", "av"],
        "dbh": [10.0, 5.0, 14.9],
        "height": [6.0, 4.0, None],
        "condition": ["v", "m", None],
    })


def test_stem_without_condition_is_excluded_by_default():
    s = calc.analyze(_plot(), 100.0, RES)["summary"]
    assert s["n_live"] == 1 and s["n_dead"] == 1 and s["n_stems"] == 2


@pytest.mark.parametrize("choice, n_live, n_dead", [("live", 2, 1), ("dead", 1, 2)])
def test_missing_condition_choice(choice, n_live, n_dead):
    s = calc.analyze(_plot(), 100.0, RES, missing_condition=choice)["summary"]
    assert (s["n_live"], s["n_dead"]) == (n_live, n_dead)


def test_prepare_normalises_condition():
    d = calc.prepare(_plot(), RES, missing_condition="live")
    assert d["condition"].tolist() == ["live", "dead", "live"]
    assert d["live"].tolist() == [True, False, True]
    with pytest.raises(ValueError):
        calc.prepare(_plot(), RES, missing_condition="maybe")


def test_missing_condition_column_is_an_error():
    df = _plot().drop(columns="condition")
    with pytest.raises(ValueError, match="missing required column: condition"):
        calc.analyze(df, 100.0, RES)


# ---------------------------------------------------------------------------
# Method checks on a synthetic 100 m2 plot (expected values worked out by hand)
# ---------------------------------------------------------------------------
G = 0.00007854  # m2 per cm2 of DBH (Cintron & Schaeffer-Novelli 1984, p.92)


def _synthetic():
    # live: DBH 1,3,5,8,11,12,15,20 ; dead: DBH 4,6 (dead stems carry no height)
    return pd.DataFrame({
        "tree_id": list(range(1, 11)),
        "species": ["Rh", "Rh", "As", "As", "Lg", "Rh", "As", "Rh", "Rh", "As"],
        "dbh": [1, 3, 5, 8, 11, 12, 15, 20, 4, 6],
        "height": [2, 3, 4, 5, 6, 7, 8, 9, None, None],
        "condition": ["v"] * 8 + ["m", "m"],
        "unit": ["u1", "u1", "u2", "u2", "u1", "u2", "u1", "u1", "u2", "u2"],
    })


def _prepared():
    return calc.prepare(_synthetic(), RES)


def test_basal_area_formula():
    d = _prepared()
    assert d.loc[d["dbh"] == 20, "basal_area_m2"].iloc[0] == pytest.approx(0.00007854 * 400)


def test_quadratic_mean_dbh_is_not_arithmetic_mean():
    s = calc.structural_summary(_prepared(), 100.0)
    # live: 8 stems -> 800/ha ; sum DBH^2 = 1+9+25+64+121+144+225+400 = 989
    ba_ha = G * 989 * 100
    expected = (ba_ha * 12732.39 / 800) ** 0.5            # ~ 11.2 cm
    assert s["mean_dbh_cm"] == pytest.approx(expected)
    arithmetic = (1 + 3 + 5 + 8 + 11 + 12 + 15 + 20) / 8   # 9.375
    assert abs(s["mean_dbh_cm"] - arithmetic) > 1.0
    assert calc.quadratic_mean_dbh(ba_ha, 800) == pytest.approx(expected)


def test_single_plot_has_relative_values_only():
    t = calc.importance_value(_prepared(), 100.0)
    assert "ivi" not in t.columns and "rel_frequency" not in t.columns
    assert t["rel_density"].sum() == pytest.approx(100.0)
    assert t["rel_dominance"].sum() == pytest.approx(100.0)
    # live stems: Rh 4 (1,3,12,20), As 3 (5,8,15), Lg 1 (11) -> 50 / 37.5 / 12.5 %
    rd = dict(zip(t["species"], t["rel_density"]))
    assert rd["Rhizophora mangle"] == pytest.approx(50.0)
    assert rd["Avicennia schaueriana"] == pytest.approx(37.5)
    assert rd["Laguncularia racemosa"] == pytest.approx(12.5)


def test_ivi_sums_300_with_units():
    t = calc.importance_value(_prepared(), 100.0, unit_col="unit")
    assert t["ivi"].sum() == pytest.approx(300.0)
    assert t["rel_frequency"].sum() == pytest.approx(100.0)
    assert "rel_frequency" in t.columns


def test_dbh_class_edges_match_lab_rule():
    df = pd.DataFrame({"tree_id": [1, 2], "species": ["Rh", "Rh"],
                       "dbh": [2.5, 10.0], "height": [3, 5], "condition": ["v", "v"]})
    dens, _ = calc.dbh_classes(calc.prepare(df, RES), 100.0)
    # closed on the left: 2.5 -> middle class, 10.0 -> top class
    assert dens.loc["2.5–10"].sum() == pytest.approx(100.0)   # 1 stem * 100
    assert dens.loc["≥ 10"].sum() == pytest.approx(100.0)
    assert "< 2.5" not in dens.index


def test_holdridge_uses_same_cut_for_s_d_b():
    d = _prepared()
    h = 5.5
    c10 = calc.complexity_index(d, 100.0, h, 10.0)
    # DBH > 10: 11, 12, 15, 20 (Lg, Rh, Av, Rh) -> s = 3, 4 stems
    assert c10["s"] == 3
    assert c10["d_per_0_1ha"] == pytest.approx(4 * 100 / 10)                 # 40
    assert c10["b_per_0_1ha"] == pytest.approx(G * (121 + 144 + 225 + 400) * 100 / 10)
    assert c10["ci"] == pytest.approx(3 * 40 * (G * 890 * 10) * 5.5 * 1e-3)
    assert c10["dbh_cut_cm"] == 10.0 and c10["h_m"] == 5.5
    c25 = calc.complexity_index(d, 100.0, h, 2.5)
    # DBH > 2.5: all live except DBH 1 -> 7 stems, 3 species
    assert c25["s"] == 3
    assert c25["d_per_0_1ha"] == pytest.approx(70.0)
    assert c25["b_per_0_1ha"] == pytest.approx(G * (9 + 25 + 64 + 890) * 10)
    assert c25["ci"] == pytest.approx(3 * 70 * (G * 988 * 10) * 5.5 * 1e-3)


def test_holdridge_strict_greater_than_cut():
    df = pd.DataFrame({"tree_id": [1, 2], "species": ["Rh", "As"],
                       "dbh": [10.0, 12.0], "height": [5, 6], "condition": ["v", "v"]})
    c = calc.complexity_index(calc.prepare(df, RES), 100.0, 6.0, 10.0)
    assert c["s"] == 1 and c["d_per_0_1ha"] == pytest.approx(10.0)   # only DBH 12


def test_s_counts_only_species_in_the_cut():
    df = pd.DataFrame({"tree_id": [1, 2], "species": ["Rh", "As"],
                       "dbh": [4.0, 12.0], "height": [5, 6], "condition": ["v", "v"]})
    c = calc.complexity_index(calc.prepare(df, RES), 100.0, 6.0, 10.0)
    assert c["s"] == 1


def test_heights_use_live_stems_only():
    df = pd.DataFrame({"tree_id": [1, 2, 3], "species": ["Rh", "Rh", "Rh"],
                       "dbh": [5, 6, 7], "height": [4, 6, 10], "condition": ["v", "v", "m"]})
    s = calc.structural_summary(calc.prepare(df, RES), 100.0, canopy_n=10)
    assert s["height_mean_m"] == 5.0
    assert s["height_max_m"] == 6.0
    assert s["height_min_m"] == 4.0
    assert s["canopy_height_m"] == 5.0


def test_canopy_n_is_configurable():
    s = calc.structural_summary(_prepared(), 100.0, canopy_n=2)
    assert s["canopy_height_m"] == pytest.approx((9 + 8) / 2)
    assert calc.structural_summary(_prepared(), 100.0)["canopy_height_m"] == pytest.approx(5.5)


def test_holdridge_zero_when_no_large_stems():
    df = pd.DataFrame({"tree_id": [1, 2], "species": ["Rh", "As"],
                       "dbh": [3.0, 8.0], "height": [3, 5], "condition": ["v", "v"]})
    r = calc.analyze(df, 100.0, RES)
    c = r["complexity"]["dbh_gt_10"]
    assert c["ci"] == 0 and c["s"] == 0 and c["d_per_0_1ha"] == 0 and c["b_per_0_1ha"] == 0
    assert r["complexity"]["dbh_gt_2.5"]["ci"] > 0
    assert "complexity_index" not in r["summary"]


def test_analyze_returns_both_holdridge_indices():
    r = calc.analyze(_synthetic(), 100.0, RES)
    assert set(r["complexity"]) == {"dbh_gt_2.5", "dbh_gt_10"}
    assert r["complexity"]["dbh_gt_10"]["dbh_cut_cm"] == 10.0
    assert r["complexity"]["dbh_gt_2.5"]["dbh_cut_cm"] == 2.5
    assert r["complexity"]["dbh_gt_10"]["h_m"] == pytest.approx(r["summary"]["canopy_height_m"])
    assert r["complexity"]["dbh_gt_10"]["ci"] == pytest.approx(3 * 40 * (G * 890 * 10) * 5.5 * 1e-3)


def test_only_dead_stems_plot():
    df = pd.DataFrame({"tree_id": [1, 2], "species": ["Rh", "As"],
                       "dbh": [5.0, 9.0], "height": [None, None], "condition": ["m", "m"]})
    r = calc.analyze(df, 100.0, RES)
    assert r["summary"]["n_live"] == 0
    assert r["summary"]["mean_dbh_cm"] == 0
    assert r["summary"]["height_mean_m"] == 0 and r["summary"]["canopy_height_m"] == 0
    assert r["importance"].empty
    assert r["complexity"]["dbh_gt_10"]["ci"] == 0


def test_diameter_distribution_has_no_interpretation_text():
    tab, info = calc.diameter_distribution(_prepared(), 100.0, class_width=5.0)
    assert set(info) >= {"q_mean", "class_width", "n_classes"}
    assert "interpretation" not in info
    # live DBH 1,3 | 5,8 | 11,12 | 15 | 20 -> counts 2,2,2,1,1
    assert tab["n"].tolist() == [2, 2, 2, 1, 1]
    assert tab["q"].iloc[0] == pytest.approx(1.0)


def test_holdridge_counts_unresolved_species_in_d_and_b_not_in_s():
    df = pd.DataFrame({"tree_id": [1, 2], "species": ["Rh", "xx"],
                       "dbh": [12.0, 15.0], "height": [6, 7], "condition": ["v", "v"]})
    c = calc.complexity_index(calc.prepare(df, RES), 100.0, 6.5, 10.0)
    assert c["s"] == 1                                            # unknown adds no species
    assert c["d_per_0_1ha"] == pytest.approx(2 * 100 / 10)        # both stems counted
    assert c["b_per_0_1ha"] == pytest.approx(G * (144 + 225) * 10)


def test_canopy_n_must_be_positive():
    with pytest.raises(ValueError):
        calc.structural_summary(_prepared(), 100.0, canopy_n=0)
    with pytest.raises(ValueError):
        calc.analyze(_synthetic(), 100.0, RES, canopy_n=0)
