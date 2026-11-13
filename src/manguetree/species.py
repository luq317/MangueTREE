# -*- coding: utf-8 -*-
"""
species.py
==========
Neotropical mangrove species table and the resolver that turns the species
text typed in a field sheet into a scientific name.

The table (``data/species_neotropics.csv``) lists species, aliases and the
regions where each occurs. Genus abbreviations (e.g. "Av") are resolved with
regional defaults (``data/genus_defaults.csv``): where a genus has more than one
species and no default is justified, the abbreviation is "ambiguous" and the
stem is not counted as a species.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
from unidecode import unidecode

REGIONS = {
    "BR_S_SE": "Brazil: South and Southeast",
    "BR_N_NE": "Brazil: North and Northeast",
    "CARIBBEAN_ATLANTIC": "Caribbean and Western Atlantic",
    "EASTERN_PACIFIC": "Eastern Pacific (Americas)",
}

_DATA = Path(__file__).parent / "data"

# Genus -> abbreviations used in field sheets (lower case, as in genus_defaults.csv)
_GENUS_ABBREVIATIONS = {
    "avicennia": ("av",), "rhizophora": ("rh",), "laguncularia": ("lg",),
    "conocarpus": ("cn", "ce", "co"), "pelliciera": ("pe",),
}


def _norm(text):
    """Lower case, no accents, dots/underscores/hyphens as spaces, collapsed spaces."""
    t = unidecode(str(text).lower())
    for ch in ".,_-'\"()":
        t = t.replace(ch, " ")
    return " ".join(t.split())


def _strip_suffix(key):
    """Drop a trailing author abbreviation ("rhizophora mangle l") and treat a trailing
    "sp"/"spp" as genus only ("rhizophora sp" -> "rhizophora")."""
    toks = key.split()
    if len(toks) == 2 and toks[1] in ("sp", "spp"):
        return toks[0]
    while len(toks) > 2 and len(toks[-1]) == 1:
        toks.pop()
    return " ".join(toks)


def load_species_table(path=None):
    """Read the species table (default: the one shipped with the package)."""
    p = Path(path) if path else _DATA / "species_neotropics.csv"
    return pd.read_csv(p, dtype=str, keep_default_na=False)


def load_genus_defaults(path=None):
    """Read the regional genus-abbreviation defaults (empty code = ambiguous)."""
    p = Path(path) if path else _DATA / "genus_defaults.csv"
    return pd.read_csv(p, dtype=str, keep_default_na=False)


@dataclass(frozen=True)
class Resolution:
    code: Optional[str]
    scientific_name: Optional[str]
    genus: Optional[str]
    status: Literal["ok", "genus_default", "ambiguous", "unknown"]
    raw: str


class SpeciesResolver:
    """Resolve field-sheet species text for one region."""

    def __init__(self, table, region, genus_defaults):
        if region not in REGIONS:
            raise ValueError(f"unknown region: {region}")
        self.region = region
        self._by_code = {r["code"]: r for r in table.to_dict("records")}
        gd = genus_defaults[genus_defaults["region"] == region]
        self._abbrev = {_norm(a): (c or None) for a, c in zip(gd["abbreviation"], gd["code"])}
        builtin = {(r["code"], _norm(k)) for r in load_species_table().to_dict("records")
                   for k in [r["scientific_name"], r["code"]] + r["aliases"].split("|")}
        self._exact = {}
        user_keys = {}
        for r in self._by_code.values():
            keys = [r["scientific_name"], r["code"]] + str(r.get("aliases", "")).split("|")
            for k in keys:
                k = _norm(k)
                if not k:
                    continue
                if (r["code"], k) not in builtin:
                    user_keys.setdefault(k, r["code"])      # added by the user
                # a short code that is also a regional genus abbreviation (e.g. "Rh")
                # belongs to the genus default, not to the species
                elif not (k in self._abbrev and self._abbrev[k] != r["code"]):
                    self._exact.setdefault(k, r["code"])
        # user-provided aliases take priority over the regional genus defaults
        self._collisions = []
        for k, code in user_keys.items():
            shadowed = self._exact.get(k)
            if shadowed is not None and shadowed != code:
                self._collisions.append((k, code, shadowed))
        self._exact.update(user_keys)
        self._genus_of_abbrev = {}
        for genus, abbrs in _GENUS_ABBREVIATIONS.items():
            for a in abbrs:
                self._genus_of_abbrev[a] = genus.capitalize()
        for r in self._by_code.values():
            g = r["genus"]
            self._genus_of_abbrev.setdefault(_norm(g)[:2], g)

    def alias_collisions(self):
        """(alias, user code, code it shadows) for each user alias that overrides a
        built-in name or alias of another species. Overriding a regional genus
        default (e.g. "av") is the intended workflow and is not reported."""
        return list(self._collisions)

    def _species(self, code, status, raw):
        r = self._by_code[code]
        return Resolution(code, r["scientific_name"], r["genus"], status, raw)

    def _genus_level(self, key, raw):
        """Genus abbreviation (or full genus name) -> default species or ambiguous."""
        full = {g: a for g, a in _GENUS_ABBREVIATIONS.items()}
        if key in full:                      # genus written in full
            abbrs = full[key]
            genus = key.capitalize()
            hit = next((a for a in abbrs if a in self._abbrev), None)
        elif key in self._abbrev or key in self._genus_of_abbrev:
            hit = key if key in self._abbrev else None
            genus = self._genus_of_abbrev.get(key)
        else:
            return None
        if hit is None:
            return Resolution(None, None, genus, "unknown" if genus is None else "ambiguous", raw)
        code = self._abbrev[hit]
        if code is None or code not in self._by_code:
            return Resolution(None, None, genus, "ambiguous", raw)
        return self._species(code, "genus_default", raw)

    def resolve(self, raw):
        if raw is None or (not isinstance(raw, str) and pd.isna(raw)):
            return Resolution(None, None, None, "unknown", "")
        key = _norm(raw)
        if key in self._exact:
            return self._species(self._exact[key], "ok", str(raw))
        stripped = _strip_suffix(key)
        if stripped != key and stripped in self._exact:
            return self._species(self._exact[stripped], "ok", str(raw))
        res = self._genus_level(stripped, str(raw))
        if res is not None:
            return res
        return Resolution(None, None, None, "unknown", str(raw))
