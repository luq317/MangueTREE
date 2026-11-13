import json
from importlib import resources

import pandas as pd

from manguetree import i18n
from manguetree.validation import describe, validate, Issue
from manguetree.species import SpeciesResolver, load_genus_defaults, load_species_table


def _load(lang):
    return json.loads(resources.files("manguetree").joinpath(
        "locales", f"{lang}.json").read_text(encoding="utf-8"))


KINDS = ["dbh_without_condition", "condition_without_dbh", "unknown_condition",
         "unknown_species", "ambiguous_species", "stem_count_mismatch",
         "tree_without_stems", "implausible_value", "duplicate_tag",
         "tree_species_conflict", "dead_with_height", "non_numeric_value",
         "area_fallback", "ambiguous_height_column", "duplicate_year"]


def test_catalogs_have_same_keys():
    assert set(_load("en")) == set(_load("pt"))


def test_missing_key_falls_back(monkeypatch):
    key = "validation.severity.error"
    real = i18n.catalog
    monkeypatch.setattr(i18n, "catalog", lambda lang: (
        {k: v for k, v in real(lang).items() if k != key} if lang == "pt" else real(lang)))
    assert i18n.t(key, "pt") == _load("en")[key]
    assert ("pt", key) in i18n.MISSING
    assert i18n.t("no.such.key", "pt") == "no.such.key"


def test_catalog_is_read_only():
    import pytest
    with pytest.raises(TypeError):
        i18n.catalog("en")["x"] = "y"


def test_catalogs_have_same_placeholders():
    import re
    en, pt = _load("en"), _load("pt")
    ph = lambda v: set(re.findall(r"\{(\w+)\}", v))
    for k in en:
        assert ph(en[k]) == ph(pt[k]), k


def test_condition_without_dbh_is_translated_by_variant():
    df = pd.DataFrame({"source_row": [2], "tree_id": [1], "species": ["Rhizophora mangle"],
                       "dbh": [None], "condition": ["v"]})
    s = [i for i in validate(df, SpeciesResolver(load_species_table(), "BR_S_SE",
         load_genus_defaults())) if i.kind == "condition_without_dbh"][0]
    assert s.detail == "condition 'live' with no DBH"
    assert "viva" in describe(s, "pt")


def test_params_are_formatted():
    out = i18n.t("validation.detail.dbh_without_condition", "pt", dbh=14.9)
    assert "14,9" in out
    assert "14.9" in i18n.t("validation.detail.dbh_without_condition", "en", dbh=14.9)


def _has(cat, prefix):
    return prefix in cat or any(k.startswith(prefix + ".") for k in cat)


def test_every_issue_kind_has_texts():
    for lang in ("en", "pt"):
        cat = _load(lang)
        for kind in KINDS:
            assert f"validation.kind.{kind}" in cat, (lang, kind)
            assert _has(cat, f"validation.detail.{kind}"), (lang, kind)
            assert _has(cat, f"validation.action.{kind}"), (lang, kind)
        assert "validation.severity.error" in cat and "validation.severity.warning" in cat


def test_no_em_dash_in_catalogs():
    for lang in ("en", "pt"):
        assert all("—" not in v for v in _load(lang).values())


def test_describe_matches_detail_in_english():
    df = pd.DataFrame({
        "source_row": [2, 3, 4, 5, 6, 7],
        "tree_id": [1, 1, 2, 3, 4, 4],
        "tag": ["a", "a", None, None, None, None],
        "species": ["Rhizophora mangle", "Laguncularia racemosa", "Zzz", "Rhizophora", None, "Rhizophora mangle"],
        "dbh": [14.9, 0, 200, None, None, 5],
        "height": [3.0, 70, -1, 2, None, 4],
        "_raw_dbh": [None, None, None, None, "abc", None],
        "_raw_height": [None, None, None, None, "x", None],
        "condition": [None, "v", "q", "m", "v", "m"],
        "n_stems": [3, 3, 1, 1, 1, 1],
    })
    issues = validate(df, SpeciesResolver(load_species_table(), "BR_S_SE", load_genus_defaults()))
    issues.append(Issue.make("duplicate_year", "warning", None, None,
                            {"year": 2020, "sheets": "A, B"}))
    assert len(issues) > 8
    for s in issues:
        assert describe(s, "en") == s.detail
        assert describe(s, "pt")
    assert {s.kind for s in issues} >= {"implausible_value", "non_numeric_value",
                                        "dbh_without_condition", "stem_count_mismatch"}
