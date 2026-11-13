# -*- coding: utf-8 -*-
"""
validation.py
=============
Row-level validation of field-sheet data, run on the output of ``manguetree.io``
(before ``calc.prepare``). Instead of silently accepting incomplete rows, every
problem is reported as an ``Issue`` that points at the original sheet row.

``Issue.detail`` / ``Issue.action`` are the English texts, generated from the English
catalog (``locales/en.json``) with ``Issue.params``; ``describe(issue, lang)`` and
``describe_action(issue, lang)`` render the same message in any language.
"""
import re
from dataclasses import dataclass, field
from typing import Literal

import pandas as pd
from unidecode import unidecode

from manguetree import i18n
from manguetree.io import to_numeric

# Single source of truth for condition codes (also used by calc.prepare).
LIVE_CODES = frozenset({"v", "vivo", "viva", "live", "alive", "l"})
DEAD_CODES = frozenset({"m", "morto", "morta", "dead", "d"})


def is_blank(value):
    """True for None, NaN and empty / whitespace-only strings."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def normalise_condition(value):
    """Return 'live', 'dead' or None (blank or unrecognised code)."""
    if is_blank(value):
        return None
    t = unidecode(str(value)).strip().lower()
    t = re.sub(r"[\s.,;:]+$", "", t)          # "V.", "m ", "v;" -> "v", "m", "v"
    if t in LIVE_CODES:
        return "live"
    if t in DEAD_CODES:
        return "dead"
    return None


@dataclass(frozen=True)
class Limits:
    dbh_max_cm: float = 150.0
    height_max_m: float = 60.0


def _catalog_key(prefix, kind, variant, lang):
    """``prefix.kind.variant`` when that key exists (in ``lang`` or English), else ``prefix.kind``."""
    if variant:
        key = f"{prefix}.{kind}.{variant}"
        if key in i18n.catalog(lang) or key in i18n.catalog(i18n.DEFAULT):
            return key
    return f"{prefix}.{kind}"


@dataclass(frozen=True)
class Issue:
    """One data problem. ``params`` holds the values used in the message (plus an
    optional ``variant`` selecting a sub-key such as ``implausible_value.dbh_high``).
    It is a plain dict excluded from equality and hashing so the dataclass stays frozen
    and comparable by its English fields."""
    kind: str
    severity: Literal["error", "warning"]
    source_row: int | None
    tree_id: object
    detail: str
    action: str
    params: dict = field(default_factory=dict, compare=False, hash=False)

    @classmethod
    def make(cls, kind, severity, source_row, tree_id, params=None):
        """Build an issue whose English detail/action come from the English catalog."""
        params = dict(params or {})
        stub = cls(kind, severity, source_row, tree_id, "", "", params)
        return cls(kind, severity, source_row, tree_id,
                   describe(stub, "en"), describe_action(stub, "en"), params)


def describe(issue, lang=None):
    """Detail message of ``issue`` in ``lang``."""
    lang = lang or i18n.get_lang()
    p = {k: v for k, v in issue.params.items() if k != "variant"}
    key = _catalog_key("validation.detail", issue.kind, issue.params.get("variant"), lang)
    return i18n.t(key, lang, **p)


def describe_action(issue, lang=None):
    """Action applied for ``issue`` in ``lang`` (may be empty)."""
    lang = lang or i18n.get_lang()
    key = _catalog_key("validation.action", issue.kind, issue.params.get("variant"), lang)
    return i18n.t(key, lang)


def validate(df, resolver, limits=Limits(), missing_condition="exclude"):
    """Return the list of issues found in ``df`` (errors first, then by row).

    ``missing_condition`` is the user's choice for stems with a DBH and a blank
    condition ("exclude", "live" or "dead"); with "dead", such stems that carry a
    height are also reported as ``dead_with_height``.
    """
    issues = []
    n = len(df)
    col = lambda name: df[name] if name in df.columns else pd.Series([None] * n, index=df.index)
    dbh = to_numeric(col("dbh"))
    height = to_numeric(col("height"))
    srcrow = col("source_row")
    cond_col = col("condition")
    species_col = col("species")
    tree = col("tree_id")

    def row_of(i):
        v = srcrow.loc[i]
        if is_blank(v):
            return None
        return int(v)

    def tid(i):
        v = tree.loc[i]
        if is_blank(v):
            return None
        v = v.item() if hasattr(v, "item") else v
        return int(v) if isinstance(v, float) and v.is_integer() else v

    def add(kind, sev, i, **params):
        issues.append(Issue.make(kind, sev, row_of(i), tid(i), params))

    raw_dbh = col("_raw_dbh")
    raw_height = col("_raw_height")
    recorded = {}            # row -> True when the row records a stem (DBH, text DBH or condition)
    species_codes = {}
    for i in df.index:
        has_dbh = pd.notna(dbh.loc[i])
        if not is_blank(raw_dbh.loc[i]):
            add("non_numeric_value", "error", i, variant="dbh",
                text=str(raw_dbh.loc[i]).strip())
        if not is_blank(raw_height.loc[i]):
            add("non_numeric_value", "error", i, variant="height",
                text=str(raw_height.loc[i]).strip())
        raw_cond = cond_col.loc[i]
        cond = normalise_condition(raw_cond)
        recorded[i] = bool(has_dbh or not is_blank(raw_cond) or not is_blank(raw_dbh.loc[i]))

        if is_blank(raw_cond):
            if has_dbh:
                add("dbh_without_condition", "error", i, dbh=float(dbh.loc[i]))
        elif cond is None:
            add("unknown_condition", "error", i, value=str(raw_cond).strip())
        if cond is not None and not has_dbh:
            add("condition_without_dbh", "warning", i, variant=cond)

        raw_sp = species_col.loc[i]
        if not is_blank(raw_sp) or has_dbh:
            res = resolver.resolve(None if is_blank(raw_sp) else raw_sp)
            if res.status == "unknown":
                add("unknown_species", "error", i,
                    value="" if is_blank(raw_sp) else str(raw_sp).strip())
            elif res.status == "ambiguous":
                add("ambiguous_species", "error", i, value=str(raw_sp).strip())
            species_codes[i] = res.code

        d, h = dbh.loc[i], height.loc[i]
        if pd.notna(d):
            if d <= 0:
                add("implausible_value", "error", i, variant="dbh_nonpositive", value=float(d))
            elif d > limits.dbh_max_cm:
                add("implausible_value", "warning", i, variant="dbh_high",
                    value=float(d), limit=float(limits.dbh_max_cm))
        if pd.notna(h):
            if h <= 0:
                add("implausible_value", "error", i, variant="height_nonpositive",
                    value=float(h))
            elif h > limits.height_max_m:
                add("implausible_value", "warning", i, variant="height_high",
                    value=float(h), limit=float(limits.height_max_m))
        counted_dead = cond == "dead" or (cond is None and is_blank(raw_cond)
                                          and missing_condition == "dead" and has_dbh)
        if counted_dead and pd.notna(h):
            add("dead_with_height", "warning", i, height=float(h))

    # tree-level checks
    if "tree_id" in df.columns:
        key = tree.map(lambda v: None if is_blank(v) else v)
        nst = to_numeric(col("n_stems")) if "n_stems" in df.columns else None
        for t, idx in key.dropna().groupby(key.dropna()).groups.items():
            idx = list(idx)
            if nst is not None:
                declared = nst.loc[idx].dropna().unique()
                n_rows = sum(recorded.get(i, False) for i in idx)   # placeholders ignored
                if len(declared) > 0 and n_rows == 0:
                    add("tree_without_stems", "warning", idx[0])
                elif len(declared) > 0 and (len(declared) > 1 or int(declared[0]) != n_rows):
                    shown = "/".join(f"{x:g}" for x in sorted(declared))
                    variant = (("d1" if shown == "1" else "dn")
                               + ("r1" if n_rows == 1 else "rn"))   # singular/plural wording
                    add("stem_count_mismatch", "warning", idx[0], declared=shown,
                        rows=n_rows, variant=variant)
            codes = {species_codes[i] for i in idx if species_codes.get(i)}
            if len(codes) > 1:
                add("tree_species_conflict", "warning", idx[0], species=", ".join(sorted(codes)))

    if "tag" in df.columns:
        tags = df["tag"].map(lambda v: None if is_blank(v) else str(v).strip())
        for tg, idx in tags.dropna().groupby(tags.dropna()).groups.items():
            if len(idx) > 1:
                rows = ", ".join(str(row_of(i)) for i in idx)
                for i in idx:
                    add("duplicate_tag", "warning", i, tag=tg, rows=rows)

    src = df.attrs.get("height_source_header")
    if src is not None and unidecode(str(src)).lower().replace(".", "").strip() == "alt med":
        issues.append(Issue.make("ambiguous_height_column", "warning", None, None,
                                 {"source": str(src)}))
    if df.attrs.get("area_source") == "fallback":
        area = df.attrs.get("area_value")
        params = ({"variant": "value", "area": float(area)}
                  if isinstance(area, (int, float)) else {"variant": "default"})
        issues.append(Issue.make("area_fallback", "warning", None, None, params))

    issues.sort(key=lambda s: (s.severity != "error",
                               s.source_row if s.source_row is not None else 10**9))
    return issues


def issues_to_frame(issues):
    cols = ["kind", "severity", "source_row", "tree_id", "detail", "action"]
    return pd.DataFrame([[getattr(s, c) for c in cols] for s in issues], columns=cols)
