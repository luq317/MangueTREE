import pandas as pd
import pytest

from manguetree import calc
from manguetree.species import (REGIONS, SpeciesResolver, load_genus_defaults,
                                load_species_table)


def _resolver(region, table=None):
    return SpeciesResolver(load_species_table() if table is None else table,
                           region, load_genus_defaults())


def test_guaratiba_codes_resolve_in_southeast():
    r = _resolver("BR_S_SE")
    got = [r.resolve(x) for x in ["As", "as", "Rh", "Lg"]]
    assert [g.scientific_name for g in got] == [
        "Avicennia schaueriana", "Avicennia schaueriana",
        "Rhizophora mangle", "Laguncularia racemosa"]
    assert [g.status for g in got] == ["ok", "ok", "genus_default", "ok"]


def test_full_names_resolve_everywhere():
    for region in REGIONS:
        res = _resolver(region).resolve("Avicennia germinans")
        assert res.status == "ok" and res.code == "Ag"
    assert _resolver("BR_S_SE").resolve("A. germinans").status == "ok"


def test_av_is_schaueriana_in_every_region():
    for region in REGIONS:
        res = _resolver(region).resolve("Av")
        assert res.code == "As" and res.scientific_name == "Avicennia schaueriana"
        assert res.genus == "Avicennia"
        assert _resolver(region).resolve("Ag").code == "Ag"


def test_nema_codes_in_south_southeast():
    """Field sheets of NEMA/UERJ write AV, RH and LG (v1.0.1)."""
    r = _resolver("BR_S_SE")
    for raw, code in (("AV", "As"), ("av", "As"), ("RH", "Rm"), ("LG", "Lg"), ("Ag", "Ag"), ("AS", "As")):
        assert r.resolve(raw).code == code, raw
    assert r.resolve("AV").scientific_name == "Avicennia schaueriana"
    assert r.resolve("Ag").scientific_name == "Avicennia germinans"


def test_genus_abbreviation_defaults_per_region():
    for region in REGIONS:
        assert _resolver(region).resolve("Lg").code == "Lg"
        assert _resolver(region).resolve("Cn").code == "Ce"
    assert _resolver("BR_S_SE").resolve("Rh").code == "Rm"
    for region in ("BR_N_NE", "CARIBBEAN_ATLANTIC", "EASTERN_PACIFIC"):
        assert _resolver(region).resolve("Rh").status == "ambiguous"
    for region in ("CARIBBEAN_ATLANTIC", "EASTERN_PACIFIC"):
        assert _resolver(region).resolve("Pe").status == "ambiguous"
        assert _resolver(region).resolve("Pr").code == "Pr"
        assert _resolver(region).resolve("Pb").code == "Pb"


def test_species_codes_are_unique_two_letters():
    t = load_species_table()
    assert len(t) == 10 and t["code"].is_unique
    assert t["code"].str.fullmatch("[A-Z][a-z]").all()
    assert t["code"].str.lower().is_unique        # codes are case-insensitive
    assert _resolver("BR_S_SE").resolve("Avicennia germinans").code == "Ag"


def test_unknown_does_not_count_as_species():
    df = pd.DataFrame({
        "tree_id": [1, 2, 3], "species": ["As", "Rh", "xx"],
        "dbh": [10.0, 5.0, 8.0], "height": [6.0, 4.0, 5.0],
        "condition": ["v", "v", "v"],
    })
    res = calc.analyze(df, 100.0, _resolver("BR_S_SE"))
    assert res["summary"]["n_species_live"] == 2
    assert res["summary"]["n_live"] == 3          # still real stems
    assert res["complexity"]["dbh_gt_2.5"]["s"] == 2
    assert set(res["importance"]["species"]) == {"Avicennia schaueriana", "Rhizophora mangle"}
    assert res["data"]["species_status"].tolist() == ["ok", "genus_default", "unknown"]


def test_user_table_extends_list():
    t = load_species_table()
    extra = pd.DataFrame([{
        "code": "XG", "scientific_name": "Xylocarpus granatum", "genus": "Xylocarpus",
        "aliases": "xg", "regions": "BR_S_SE", "true_mangrove": "true", "source": "user"}])
    r = _resolver("BR_S_SE", pd.concat([t, extra], ignore_index=True))
    assert r.resolve("xg").status == "ok"


def test_every_species_has_source():
    t = load_species_table()
    assert t["source"].fillna("").str.strip().ne("").all()


def test_aliases_ignore_case_accents_dots():
    r = _resolver("BR_S_SE")
    assert r.resolve("mangue vermelho").code == "Rm"
    assert r.resolve("MANGLE  ROJO").code == "Rm"
    assert r.resolve("AV").code == "As"


def test_chart_axes_use_full_numbers():
    import plotly.graph_objects as go
    from manguetree import charts
    fig = charts._layout(go.Figure(go.Bar(x=["F1"], y=[12500])), {})
    assert fig.layout.yaxis.exponentformat == "none"
    assert fig.layout.yaxis.separatethousands is True
