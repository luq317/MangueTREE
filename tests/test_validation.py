from pathlib import Path

import pandas as pd
import pytest

from manguetree import calc, io, validation
from manguetree.species import SpeciesResolver, load_genus_defaults, load_species_table
from manguetree.validation import Limits

DATA = Path(__file__).resolve().parents[1] / "data"
RES = SpeciesResolver(load_species_table(), "BR_S_SE", load_genus_defaults())


def _df(**cols):
    n = len(next(iter(cols.values())))
    d = {"tree_id": list(range(1, n + 1)), "species": ["Rh"] * n, "dbh": [5.0] * n,
         "height": [None] * n, "condition": ["v"] * n, "source_row": list(range(2, n + 2))}
    d.update(cols)
    return pd.DataFrame(d)


def _of(issues, kind):
    return [i for i in issues if i.kind == kind]


def test_dbh_without_condition_is_flagged_and_excluded():
    df = pd.DataFrame({"tree_id": [1, 2, None], "species": ["As", "Rh", "av"],
                       "dbh": [10.0, 5.0, 14.9], "height": [6.0, 4.0, None],
                       "condition": ["v", "m", None], "source_row": [2, 3, 4]})
    r = calc.analyze(df, 100.0, RES)
    hits = _of(r["issues"], "dbh_without_condition")
    assert len(hits) == 1 and hits[0].source_row == 4 and hits[0].severity == "error"
    assert hits[0].action == "excluded unless user chooses live/dead"
    assert r["summary"]["n_stems"] == 2
    assert calc.analyze(df, 100.0, RES, missing_condition="live")["summary"]["n_live"] == 2


def test_dead_with_height_is_flagged():
    df = _df(height=[4.0, 6.0, 10.0], condition=["v", "v", "m"])
    hits = _of(validation.validate(df, RES), "dead_with_height")
    assert len(hits) == 1 and hits[0].source_row == 4 and hits[0].action == "height ignored"


def test_stem_count_mismatch():
    df = _df(tree_id=[3], n_stems=[2])
    hits = _of(validation.validate(df, RES), "stem_count_mismatch")
    assert len(hits) == 1 and hits[0].source_row == 2 and hits[0].tree_id == 3
    ok = _df(tree_id=[3, 3], n_stems=[2, 2])
    assert not _of(validation.validate(ok, RES), "stem_count_mismatch")


def test_condition_codes():
    df = _df(condition=["Vivo", "DEAD", "x"])
    issues = validation.validate(df, RES)
    bad = _of(issues, "unknown_condition")
    assert len(bad) == 1 and bad[0].source_row == 4 and bad[0].action == "excluded"
    s = calc.analyze(df, 100.0, RES)["summary"]
    assert (s["n_live"], s["n_dead"]) == (1, 1)


def test_implausible_values():
    df = _df(dbh=[0.0, -1.0, 200.0, 5.0], height=[None, None, None, 70.0])
    hits = _of(validation.validate(df, RES, Limits()), "implausible_value")
    assert sorted(i.severity for i in hits) == ["error", "error", "warning", "warning"]
    assert sorted(i.source_row for i in hits) == [2, 3, 4, 5]


def test_condition_without_dbh():
    df = _df(dbh=[None])
    hits = _of(validation.validate(df, RES), "condition_without_dbh")
    assert len(hits) == 1 and hits[0].severity == "warning"


def test_species_issues_and_conflict():
    df = _df(tree_id=[1, 1, 2], species=["Rh", "As", "zzz"])
    iss = validation.validate(df, RES)
    assert len(_of(iss, "tree_species_conflict")) == 1
    assert [i.source_row for i in _of(iss, "unknown_species")] == [4]
    amb = _df(species=["Rh"])  # genus abbreviation, ambiguity depends on region defaults
    validation.validate(amb, RES)  # must not crash


def test_duplicate_tag_and_blank_tree_ids():
    df = _df(tree_id=[None, None, 3], tag=["A1", "A1", None], n_stems=[2, 2, None])
    iss = validation.validate(df, RES)
    assert len(_of(iss, "duplicate_tag")) == 2
    assert not _of(iss, "stem_count_mismatch")


def test_sorted_errors_first_and_frame():
    df = _df(dbh=[200.0, 0.0])
    iss = validation.validate(df, RES)
    assert iss[0].severity == "error"
    f = validation.issues_to_frame(iss)
    assert list(f.columns) == ["kind", "severity", "source_row", "tree_id", "detail", "action"]
    assert list(validation.issues_to_frame([]).columns) == list(f.columns)


def test_clean_guaratiba_file_has_no_errors():
    df, _ = io.load_excel_sheet(DATA / "guaratiba_T2_2009.xlsx", "F2")
    iss = validation.validate(df, RES)
    assert not [i for i in iss if i.severity == "error"]


@pytest.mark.parametrize("choice", ["live", "dead"])
def test_unknown_condition_stays_excluded_under_missing_condition(choice):
    df = _df(condition=["x", None, "v"])
    base = calc.analyze(df, 100.0, RES)["summary"]
    s = calc.analyze(df, 100.0, RES, missing_condition=choice)["summary"]
    assert s["n_stems"] == base["n_stems"] + 1  # only the blank one is added, not "x"
    assert s["n_" + choice] == base["n_" + choice] + 1


def test_blank_condition_counted_dead_when_chosen():
    df = _df(condition=["v", None])
    s = calc.analyze(df, 100.0, RES, missing_condition="dead")["summary"]
    assert (s["n_live"], s["n_dead"]) == (1, 1)


def test_ambiguous_species_is_flagged():
    res = SpeciesResolver(load_species_table(), "BR_N_NE", load_genus_defaults())
    assert res.resolve("Rh").status == "ambiguous"
    hits = _of(validation.validate(_df(species=["Rh"]), res), "ambiguous_species")
    assert len(hits) == 1 and hits[0].severity == "error" and hits[0].source_row == 2


def test_validate_minimal_columns_and_float_tree_id():
    df = pd.DataFrame({"tree_id": [3.0], "species": ["Rh"], "dbh": [0.0],
                       "condition": ["v"], "source_row": [5]})
    iss = validation.validate(df, RES)
    assert len(iss) == 1 and iss[0].tree_id == 3 and isinstance(iss[0].tree_id, int)
