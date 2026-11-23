# -*- coding: utf-8 -*-
"""
calc.py
=======
Structural and phytosociological calculations for mangrove forests, following
Cintrón & Schaeffer-Novelli (1984) and Pool, Snedaker & Lugo (1977).

Functions are pure (DataFrame in, results out) so they can be tested and reused
by every page of the MangueTREE app.

Standard input columns (see ``manguetree.io``):
    tree_id   -> tree identifier (repeated for the stems of the same tree)
    n_stems   -> number of stems of the tree
    species   -> species name or code as written in the field sheet
    dbh       -> diameter at breast height (cm)
    height    -> height (m) (usually recorded on the first stem of each tree)
    condition -> 'v' (live) or 'm' (dead)
    tag, note, lat, lon, source_row -> optional

Units: DBH in cm; height in m; plot area in m2; basal area in m2;
density in stems/ha.
"""

import numpy as np
import pandas as pd
from manguetree.io import to_numeric
from manguetree.validation import is_blank, normalise_condition as _normalise_condition, validate

# ---------------------------------------------------------------------------
# 1. SPECIES COLOURS
# ---------------------------------------------------------------------------
# Species resolution lives in manguetree.species (regional species table).
# Colour per genus (consistent across charts)
GENUS_COLORS = {
    "Rhizophora":   "#2E8B57",   # sea green
    "Avicennia":    "#E4A11B",   # amber
    "Laguncularia": "#4C78A8",   # blue
    "Conocarpus":   "#9C755F",   # brown
    "Pelliciera":   "#8E6BB0",   # purple
    "Indeterminada": "#999999",
}


UNIDENTIFIED_LABEL = "Unidentified"   # per-species tables: stems without a resolved species

# Distinct shade per species inside a genus hue: factor > 0 mixes with white, < 0 with black.
_SPECIES_SHADES = {
    "Rhizophora mangle": 0.0, "Rhizophora racemosa": 0.38, "Rhizophora harrisonii": -0.32,
    "Avicennia schaueriana": 0.0, "Avicennia germinans": 0.38, "Avicennia bicolor": -0.32,
}


def _shade(hex_color, factor):
    h = hex_color.lstrip("#")
    rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    target = 255 if factor > 0 else 0
    rgb = [round(c + (target - c) * abs(factor)) for c in rgb]
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def species_color(name):
    """Colour of a species: the genus hue, with a fixed distinct shade per species."""
    if not isinstance(name, str) or not name.strip() or name == UNIDENTIFIED_LABEL:
        return GENUS_COLORS["Indeterminada"]
    base = GENUS_COLORS.get(name.split()[0], GENUS_COLORS["Indeterminada"])
    if name in _SPECIES_SHADES:
        factor = _SPECIES_SHADES[name]
    else:       # species outside the built-in table: a stable shade from the name
        import hashlib
        factor = (int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16) % 7 - 3) * 0.12
    return _shade(base, factor)


def species_short(name):
    """'Rhizophora mangle' -> 'R. mangle' (other labels are returned unchanged)."""
    if not isinstance(name, str) or name == UNIDENTIFIED_LABEL:
        return name
    parts = name.split()
    return f"{parts[0][0]}. {' '.join(parts[1:])}" if len(parts) > 1 else name


# ---------------------------------------------------------------------------
# 2. DATA PREPARATION
# ---------------------------------------------------------------------------
MISSING_CONDITION_OPTIONS = ("exclude", "live", "dead")


def prepare(df, resolver, missing_condition="exclude"):
    """
    Standardise types and add derived columns:
        condition ('live'/'dead'), live (bool), species_code, scientific_name,
        genus, species_status, true_mangrove, basal_area_m2 (per stem).
    ``resolver`` is a ``manguetree.species.SpeciesResolver``. Stems whose species is
    "ambiguous" or "unknown" get ``scientific_name = None``: they count in density
    and basal area but not as a species.
    Stems whose condition is blank or not recognised are dropped when
    ``missing_condition == "exclude"`` (default, as in the lab spreadsheet), or
    counted as "live"/"dead" when the user chooses so, but only for BLANK conditions:
    unrecognised codes (e.g. "x") are always dropped.
    ``species_label`` is the species name for per-species tables, with "Unidentified"
    for stems whose species is unresolved. Heights <= 0 become NaN.
    Stem basal area (Cintrón 1984, p.92): g (m2) = 0.00007854 * DBH^2 (DBH in cm).
    """
    if missing_condition not in MISSING_CONDITION_OPTIONS:
        raise ValueError(f"missing_condition must be one of {MISSING_CONDITION_OPTIONS}")
    if "condition" not in df.columns:
        raise ValueError("missing required column: condition")
    d = df.copy()
    cond = d["condition"].map(_normalise_condition)
    blank = d["condition"].map(is_blank)
    if missing_condition == "exclude":
        keep = cond.notna()
    else:
        # fill only blank conditions; unrecognised codes stay excluded
        cond = cond.where(~blank, missing_condition)
        keep = cond.notna()
    d = d.loc[keep].copy()
    cond = cond.loc[keep]
    d["condition"] = cond.astype(object)
    d["live"] = (d["condition"] == "live").astype(bool)

    raw = d["species"] if "species" in d.columns else pd.Series([None] * len(d), index=d.index)
    res = raw.map(resolver.resolve)
    d["species_code"] = res.map(lambda r: r.code)
    d["scientific_name"] = res.map(lambda r: r.scientific_name)
    d["genus"] = res.map(lambda r: r.genus)
    d["species_status"] = res.map(lambda r: r.status)
    d["species_label"] = d["scientific_name"].fillna(UNIDENTIFIED_LABEL)
    tm = {r["code"]: str(r["true_mangrove"]).strip().lower() == "true"
          for r in resolver._by_code.values()}
    d["true_mangrove"] = d["species_code"].map(tm).fillna(False).astype(bool)

    for c in ["dbh", "height", "lat", "lon", "n_stems"]:
        if c in d.columns:
            d[c] = to_numeric(d[c])
    if "dbh" not in d.columns:
        d["dbh"] = np.nan
    if "height" not in d.columns:
        d["height"] = np.nan

    # Heights are used only when positive; 0 or negative values are reported by
    # validation ("height excluded") and left out of every height statistic.
    d["height"] = d["height"].where(d["height"] > 0)

    d["basal_area_m2"] = (d["dbh"] ** 2) * 0.00007854
    return d


def _ft(plot_area_m2):
    """Expansion factor to one hectare."""
    return 10000.0 / float(plot_area_m2)


# ---------------------------------------------------------------------------
# 3. AGGREGATE STRUCTURAL PARAMETERS
# ---------------------------------------------------------------------------
# Jimenez, Lugo & Cintron (1985, Biotropica 17(3):177-185, Fig. 1): stem density of mangrove
# stands falls as a negative power of the mean DBH, ln(y) = ln(7496) - 1.4934 ln(x), with y in
# trees per 0.1 ha and x in cm (114 stands, r2 = 0.73). Cavalcanti et al. (2009) use it per hectare.
JIMENEZ_LN_A = float(np.log(7496.0))
JIMENEZ_B = 1.4934
JIMENEZ_TO_HA = 10.0              # 0.1 ha -> 1 ha


def jimenez_density_ha(dbh_cm):
    """Expected live stem density (stems/ha) of a mangrove stand of mean DBH ``dbh_cm`` (cm),
    from the theoretical curve of Jimenez et al. (1985). Accepts a number or an array."""
    x = np.asarray(dbh_cm, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        y = JIMENEZ_TO_HA * np.exp(JIMENEZ_LN_A - JIMENEZ_B * np.log(x))
    y = np.where(x > 0, y, np.nan)
    return float(y) if y.ndim == 0 else y


def quadratic_mean_dbh(ba_ha, density_ha):
    """
    Diameter of the stem of mean basal area (Cintrón 1984, p.93-94):
        DBH = sqrt( (BA * 12732.39) / n )
    BA in m2/ha, n in stems/ha. It is NOT the arithmetic mean of DBHs.
    """
    if density_ha and density_ha > 0:
        return float(np.sqrt((ba_ha * 12732.39) / density_ha))
    return 0.0


def structural_summary(d, plot_area_m2, canopy_n=10):
    """
    Plot-level metrics. Uses valid stems only (DBH > 0). Heights (mean, sd, min,
    max, canopy) come from live stems only; ``canopy_height_m`` is the mean of the
    ``canopy_n`` tallest live heights.
    Returns a dict with density, basal area, mean DBH, heights and mortality.
    """
    if int(canopy_n) < 1:
        raise ValueError("canopy_n must be >= 1")
    ft = _ft(plot_area_m2)
    val = d[d["dbh"].notna() & (d["dbh"] > 0)]
    live = val[val["live"]]
    dead = val[~val["live"]]

    n_live = len(live)
    n_dead = len(dead)
    n_stems = len(val)

    density_live = n_live * ft
    density_dead = n_dead * ft
    ba_live = live["basal_area_m2"].sum() * ft
    ba_dead = dead["basal_area_m2"].sum() * ft
    ba_total = ba_live + ba_dead

    # trees (not stems)
    n_live_trees = live["tree_id"].nunique() if "tree_id" in live.columns else n_live

    # Heights: LIVE stems with a recorded height only (the NEMA protocol records no
    # height for dead trees; Estrada 2013, p.151). Canopy height = mean of the
    # ``canopy_n`` tallest live heights (an adaptation; see the paper).
    h = live["height"].dropna()
    h_mean = float(h.mean()) if not h.empty else 0.0
    h_sd = float(h.std()) if len(h) > 1 else 0.0
    h_min = float(h.min()) if not h.empty else 0.0
    h_max = float(h.max()) if not h.empty else 0.0
    h_canopy = float(h.nlargest(int(canopy_n)).mean()) if not h.empty else 0.0

    mean_dbh = quadratic_mean_dbh(ba_live, density_live)

    mort_stems = (n_dead / n_stems * 100) if n_stems else 0.0
    mort_ba = (ba_dead / ba_total * 100) if ba_total else 0.0

    return {
        "plot_area_m2": float(plot_area_m2),
        "n_stems": n_stems,
        "n_live": n_live,
        "n_dead": n_dead,
        "n_live_trees": int(n_live_trees),
        "density_live_ha": density_live,
        "density_dead_ha": density_dead,
        "density_total_ha": density_live + density_dead,
        "ba_live_ha": ba_live,
        "ba_dead_ha": ba_dead,
        "ba_total_ha": ba_total,
        "mean_dbh_cm": mean_dbh,
        "height_mean_m": h_mean,
        "height_sd_m": h_sd,
        "height_min_m": h_min,
        "height_max_m": h_max,
        "canopy_height_m": h_canopy,
        "mortality_stems_pct": mort_stems,
        "mortality_ba_pct": mort_ba,
        "n_species_live": int(live["scientific_name"].nunique()),
        "stems_per_tree": (n_live / n_live_trees) if n_live_trees else 0.0,
    }


# ---------------------------------------------------------------------------
# 4. IMPORTANCE VALUE (IVI) — Cintrón 1984, p.96-97
# ---------------------------------------------------------------------------
def importance_value(d, plot_area_m2, unit_col=None):
    """
    Phytosociological table per species (Cintrón & Schaeffer-Novelli 1984). Relative
    values are computed over live stems with an identified species (stems whose
    species is ambiguous or unknown are left out of the denominators):
        rel_density   = n_sp / n_total * 100
        rel_dominance = ba_sp / ba_total * 100
        rel_frequency = freq_sp / sum_freq * 100
        ivi           = rel_density + rel_dominance + rel_frequency   (max 300)

    ``unit_col``: column holding the sampling units used for frequency (e.g.
    subplots or stations). Without it, frequency and IVI cannot be computed and
    the table holds only the relative density and dominance. ``plot_area_m2`` is the TOTAL sampled area
    behind the stems (for pooled plots, the sum of their areas).
    """
    ft = _ft(plot_area_m2)
    live = d[d["dbh"].notna() & (d["dbh"] > 0) & d["live"]]
    base = live[live["scientific_name"].notna()]  # identified species only
    if base.empty:
        return pd.DataFrame()

    n_total = len(base)
    ba_total = base["basal_area_m2"].sum()

    rows = []
    with_freq = unit_col is not None and unit_col in base.columns
    # U = every sampling unit with a live stem, also those with unresolved species only
    n_units = live[unit_col].nunique() if with_freq else 0

    for sp, sub in base.groupby("scientific_name"):
        n = len(sub)
        ba = sub["basal_area_m2"].sum()
        row = {
            "species": sp,
            "genus": sub["genus"].iloc[0],
            "n_stems": n,
            "density_ha": n * ft,
            "ba_ha": ba * ft,
            "rel_density": n / n_total * 100 if n_total else 0,
            "rel_dominance": ba / ba_total * 100 if ba_total else 0,
        }
        if with_freq:
            row["abs_frequency"] = (sub[unit_col].nunique() / n_units * 100) if n_units else 0.0
        rows.append(row)

    tab = pd.DataFrame(rows)

    if with_freq:
        sum_freq = tab["abs_frequency"].sum()
        tab["rel_frequency"] = tab["abs_frequency"] / sum_freq * 100 if sum_freq else 0
        tab["ivi"] = tab["rel_density"] + tab["rel_dominance"] + tab["rel_frequency"]
        tab = tab.sort_values("ivi", ascending=False)
    else:
        tab = tab.sort_values(["rel_dominance", "rel_density"], ascending=False)

    return tab.reset_index(drop=True)


def pooled_importance(results):
    """IVI over several analysed plots (plots are the sampling units for frequency).
    Absolute density and basal area are per hectare of the TOTAL area (sum of the
    plot areas), so stems summed over plots are divided by the summed area.
    Each result is one sampling unit, identified by its ``plot_name``; a result
    without a name is identified by its position in ``results``."""
    frames = []
    for i, res in enumerate(results):
        dd = res["data"][res["data"]["live"] & res["data"]["dbh"].notna()
                         & (res["data"]["dbh"] > 0)].copy()
        name = res.get("plot_name")
        dd["plot"] = name if name not in (None, "") else f"plot {i + 1}"
        frames.append(dd)
    if not frames:
        return pd.DataFrame()
    total_area = float(sum(r["summary"]["plot_area_m2"] for r in results))
    return importance_value(pd.concat(frames, ignore_index=True), total_area,
                            unit_col="plot")


# ---------------------------------------------------------------------------
# 5. DBH CLASSES — as in the lab spreadsheet (<2.5 / 2.5-10 / ≥10 cm)
# ---------------------------------------------------------------------------
def dbh_classes(d, plot_area_m2, limits=(2.5, 10.0)):
    """
    Live stems in DBH classes: density and basal area per class (index
    ``dbh_class``) and species (columns). ``limits`` are the cuts (cm), strictly
    increasing; intervals are closed on the left (the top class is "≥ last cut").
    Stems with an unresolved species form the column "Unidentified".
    """
    limits = tuple(float(x) for x in limits)
    if any(b <= a for a, b in zip(limits, limits[1:])):
        raise ValueError(f"DBH class cuts must be strictly increasing, got {limits}")
    ft = _ft(plot_area_m2)
    base = d[d["dbh"].notna() & (d["dbh"] > 0)]
    base = base[base["live"]].copy()
    if base.empty:
        return pd.DataFrame(), pd.DataFrame()

    bins = [-np.inf] + list(limits) + [np.inf]
    labels = [f"< {limits[0]:g}"]
    for i in range(len(limits) - 1):
        labels.append(f"{limits[i]:g}–{limits[i+1]:g}")
    labels.append(f"≥ {limits[-1]:g}")
    base["dbh_class"] = pd.cut(base["dbh"], bins=bins, labels=labels, right=False)

    density = (base.groupby(["dbh_class", "species_label"], observed=True)
               .size().mul(ft).unstack(fill_value=0))
    basal = (base.groupby(["dbh_class", "species_label"], observed=True)["basal_area_m2"]
             .sum().mul(ft).unstack(fill_value=0))
    density.columns.name = None
    basal.columns.name = None
    return density, basal


def diameter_distribution(d, plot_area_m2, class_width=5.0):
    """
    Live stems in REGULAR diameter classes (reverse-J) and De Liocourt's
    quotient q = N_i / N_(i+1) between consecutive classes.
    Returns (table, info). ``class_width`` in cm (default 5).
    Table columns: class_cm, midpoint_cm, n, density_ha, q.
    """
    ft = _ft(plot_area_m2)
    base = d[d["dbh"].notna() & (d["dbh"] > 0)]
    base = base[base["live"]]
    if base.empty:
        return pd.DataFrame(), {"q_mean": None, "class_width": class_width, "n_classes": 0}

    dmax = float(base["dbh"].max())
    top = (np.ceil(dmax / class_width) + 1) * class_width
    bins = np.arange(0, top + class_width, class_width)
    cats = pd.cut(base["dbh"], bins=bins, right=False)
    counts = cats.value_counts().sort_index()

    rows = []
    for interval, n in counts.items():
        rows.append({"class_cm": f"{interval.left:g}–{interval.right:g}",
                     "midpoint_cm": (interval.left + interval.right) / 2,
                     "n": int(n), "density_ha": n * ft})
    tab = pd.DataFrame(rows)
    # drop empty classes at the top (above the largest stem)
    while len(tab) > 1 and tab.iloc[-1]["n"] == 0:
        tab = tab.iloc[:-1]

    N = tab["n"].values
    q_col, qs = [], []
    for i in range(len(N)):
        if i < len(N) - 1 and N[i + 1] > 0:
            q = N[i] / N[i + 1]
            q_col.append(q)
            qs.append(q)
        else:
            q_col.append(np.nan)
    tab["q"] = q_col

    q_mean = float(np.mean(qs)) if qs else None
    # No automatic interpretation: q is descriptive (De Liocourt 1898).
    info = {"q_mean": q_mean, "class_width": class_width, "n_classes": len(tab)}
    return tab, info


# ---------------------------------------------------------------------------
# 6. HOLDRIDGE COMPLEXITY INDEX — Pool, Snedaker & Lugo (1977)
# ---------------------------------------------------------------------------
def complexity_index(d, plot_area_m2, canopy_height_m, dbh_cut_cm):
    """
    Holdridge complexity index: CI = s * d * b * h * 10^-3, on a 0.1 ha basis
    (Holdridge 1967; Pool et al. 1977, p.195 and 209). s, d and b use the SAME
    set of live stems with DBH strictly greater than ``dbh_cut_cm`` (Pool et al.
    compute one index with > 2.5 cm and another with > 10 cm):
        s = number of species among those stems (stems with unresolved species
            add no species)
        d = number of those stems per 0.1 ha (all of them, so it agrees with
            the plot density)
        b = their basal area (m2) per 0.1 ha
        h = canopy height (m), given by the caller
    """
    ft = _ft(plot_area_m2)
    val = d[d["live"] & d["dbh"].notna() & (d["dbh"] > 0) & (d["dbh"] > dbh_cut_cm)]

    s = int(val["scientific_name"].nunique())  # nunique ignores unresolved species
    d_01 = (len(val) * ft) / 10.0                       # stems per 0.1 ha
    b_01 = (val["basal_area_m2"].sum() * ft) / 10.0     # basal area m2 per 0.1 ha
    h = canopy_height_m
    ci = s * d_01 * b_01 * h * 1e-3
    return {
        "s": s,
        "d_per_0_1ha": d_01,
        "b_per_0_1ha": b_01,
        "h_m": h,
        "dbh_cut_cm": dbh_cut_cm,
        "ci": ci,
    }


# ---------------------------------------------------------------------------
# 7. FULL ANALYSIS (convenience)
# ---------------------------------------------------------------------------
def analyze(df, plot_area_m2, resolver, dbh_limits=(2.5, 10.0), unit_col=None,
            plot_name=None, class_width=5.0, canopy_n=10, missing_condition="exclude"):
    """
    Run the whole pipeline and return a dict with the results.
    ``class_width`` is the width (cm) of the reverse-J diameter classes;
    ``canopy_n`` is how many of the tallest live heights make the canopy height.
    ``complexity`` holds the two Holdridge indices (DBH > 2.5 cm and DBH > 10 cm).
    """
    issues = validate(df, resolver, missing_condition=missing_condition)
    d = prepare(df, resolver, missing_condition=missing_condition)
    if plot_name is not None:
        d["plot"] = plot_name
    summary = structural_summary(d, plot_area_m2, canopy_n=canopy_n)
    importance = importance_value(d, plot_area_m2, unit_col=unit_col)
    dbh_density, dbh_ba = dbh_classes(d, plot_area_m2, limits=dbh_limits)
    diam, diam_info = diameter_distribution(d, plot_area_m2, class_width=class_width)
    h_canopy = summary["canopy_height_m"]
    complexity = {
        "dbh_gt_2.5": complexity_index(d, plot_area_m2, h_canopy, 2.5),
        "dbh_gt_10": complexity_index(d, plot_area_m2, h_canopy, 10.0),
    }
    return {
        "data": d,
        "plot_name": plot_name,
        "summary": summary,
        "importance": importance,
        "dbh_density": dbh_density,
        "dbh_ba": dbh_ba,
        "diameter_dist": diam,
        "diameter_info": diam_info,
        "complexity": complexity,
        "issues": issues,
    }


# Columns of the comparison / time-series tables that are labels or plot attributes,
# not metrics: kept in the tables, left out of metric selectors, radar and PDF figures.
NON_METRIC_COLUMNS = ("plot", "year", "plot_area_m2")


def metric_columns(df):
    """Metric columns of a comparison / series table (everything but NON_METRIC_COLUMNS)."""
    return [c for c in df.columns if c not in NON_METRIC_COLUMNS]


# ---------------------------------------------------------------------------
# 8. FULL PARAMETER SETS (time series and comparisons, v1.1.0)
# ---------------------------------------------------------------------------
def _valid(d):
    return d[d["dbh"].notna() & (d["dbh"] > 0)]


def _canopy(heights, n=10):
    h = heights.dropna().sort_values(ascending=False)
    return float(h.head(int(n)).mean()) if not h.empty else np.nan


def plot_parameters(res, dbh_limits=(2.5, 10.0)):
    """Every plot-level parameter of one analysis, flat (internal names).

    Includes the structural summary, the two Holdridge indices, stem counts, stems
    without DBH (left out of density and basal area, as in the NEMA/UERJ spreadsheet)
    and, for each DBH class, live and dead density and basal area. Class columns are
    named ``"<parameter> [<class>]"``.
    """
    s = dict(res["summary"])
    d = res["data"]
    ft = _ft(s["plot_area_m2"])
    out = {k: s[k] for k in (
        "plot_area_m2", "mean_dbh_cm", "height_mean_m", "height_sd_m", "height_min_m",
        "height_max_m", "canopy_height_m", "density_live_ha", "density_dead_ha",
        "density_total_ha", "ba_live_ha", "ba_dead_ha", "ba_total_ha", "n_live", "n_dead",
        "n_stems", "n_live_trees", "stems_per_tree", "mortality_stems_pct",
        "mortality_ba_pct", "n_species_live") if k in s}
    out["complexity_2_5"] = res["complexity"]["dbh_gt_2.5"]["ci"]
    out["complexity_10"] = res["complexity"]["dbh_gt_10"]["ci"]
    no_dbh = d[~(d["dbh"].fillna(0) > 0)]
    out["n_dead_no_dbh"] = int((~no_dbh["live"]).sum()) if "live" in no_dbh else 0
    out["n_live_no_dbh"] = int(no_dbh["live"].sum()) if "live" in no_dbh else 0
    v = _valid(d)
    limits = tuple(float(x) for x in dbh_limits)
    bins = [-np.inf] + list(limits) + [np.inf]
    labels = [f"< {limits[0]:g}"] + [f"{a:g}–{b:g}" for a, b in zip(limits, limits[1:])] \
        + [f"≥ {limits[-1]:g}"]
    cls = pd.cut(v["dbh"], bins=bins, labels=labels, right=False)
    for lab in labels:
        sub = v[cls == lab]
        for cond, part in (("live", sub[sub["live"]]), ("dead", sub[~sub["live"]])):
            out[f"density_{cond}_ha [{lab}]"] = len(part) * ft
            out[f"ba_{cond}_ha [{lab}]"] = float(part["basal_area_m2"].sum()) * ft
    return out


SPECIES_METRICS = (
    "n_live", "n_dead", "n_stems",
    "density_live_ha", "density_dead_ha", "density_total_ha",
    "ba_live_ha", "ba_dead_ha", "ba_total_ha",
    "share_density_live_pct", "share_density_dead_pct", "share_density_total_pct",
    "share_ba_live_pct", "share_ba_dead_pct", "share_ba_total_pct",
    "mean_dbh_cm", "height_mean_m", "canopy_height_m", "rel_density", "rel_dominance",
)


def species_parameters(res, canopy_n=10):
    """Every per-species parameter of one analysis (one row per species).

    Densities and basal areas per hectare (live, dead, total), the contribution (%)
    of each species to the plot's live, dead and total density and basal area, the
    quadratic mean DBH and the heights of the live stems, and the relative density
    and dominance of the phytosociology table.
    """
    d = _valid(res["data"])
    ft = _ft(res["summary"]["plot_area_m2"])
    tot = {}
    for cond, part in (("live", d[d["live"]]), ("dead", d[~d["live"]]), ("total", d)):
        tot[("density", cond)] = len(part)
        tot[("ba", cond)] = float(part["basal_area_m2"].sum())
    imp = res.get("importance")
    imp = imp.set_index("species") if imp is not None and not imp.empty else None
    rows = []
    for sp, sub in d.groupby("species_label"):
        live, dead = sub[sub["live"]], sub[~sub["live"]]
        row = {"species": sp, "n_live": len(live), "n_dead": len(dead), "n_stems": len(sub)}
        for cond, part in (("live", live), ("dead", dead), ("total", sub)):
            n, ba = len(part), float(part["basal_area_m2"].sum())
            row[f"density_{cond}_ha"] = n * ft
            row[f"ba_{cond}_ha"] = ba * ft
            row[f"share_density_{cond}_pct"] = 100 * n / tot[("density", cond)] \
                if tot[("density", cond)] else 0.0
            row[f"share_ba_{cond}_pct"] = 100 * ba / tot[("ba", cond)] if tot[("ba", cond)] else 0.0
        row["mean_dbh_cm"] = quadratic_mean_dbh(row["ba_live_ha"], row["density_live_ha"])
        h = live["height"].dropna() if "height" in live else pd.Series(dtype=float)
        row["height_mean_m"] = float(h.mean()) if not h.empty else np.nan
        row["canopy_height_m"] = _canopy(h, canopy_n)
        row["rel_density"] = float(imp.loc[sp, "rel_density"]) if imp is not None and sp in imp.index else np.nan
        row["rel_dominance"] = float(imp.loc[sp, "rel_dominance"]) if imp is not None and sp in imp.index else np.nan
        rows.append(row)
    return pd.DataFrame(rows, columns=["species", *SPECIES_METRICS])

