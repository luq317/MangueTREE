"""The engine must reproduce the NEMA/UERJ lab spreadsheet ("Resumo" sheet).

tests/data/reference_values.csv is written by the private converter that turns the
lab workbooks into data/*.xlsx; each row holds the lab's own cached results for one
survey (file, sheet).
"""
import csv
from pathlib import Path

import pytest

from manguetree import calc, io as mio
from manguetree.species import SpeciesResolver, load_genus_defaults, load_species_table

RES = SpeciesResolver(load_species_table(), "BR_S_SE", load_genus_defaults())

ROOT = Path(__file__).resolve().parents[1]
REF_CSV = ROOT / "tests" / "data" / "reference_values.csv"

with open(REF_CSV, newline="", encoding="utf-8") as fh:
    REFERENCE = list(csv.DictReader(fh))

COMPARED = ["n_live", "density_live_ha", "density_dead_ha",
            "ba_live_ha", "ba_dead_ha", "mean_dbh_cm"]


def test_reference_table_has_all_surveys():
    assert len(REFERENCE) == 18
    files = {row["file"] for row in REFERENCE}
    assert files == {"guaratiba_T2_2009.xlsx", "guaratiba_H2_2003_2025.xlsx"}


@pytest.mark.parametrize("ref", REFERENCE, ids=lambda r: f"{r['file']}-{r['sheet']}")
def test_matches_lab_spreadsheet(ref):
    df, area = mio.load_excel_sheet(ROOT / "data" / ref["file"], ref["sheet"])
    assert df is not None
    assert area == pytest.approx(float(ref["plot_area_m2"]))
    res = calc.analyze(df, area, RES, plot_name=ref["plot"])
    s = res["summary"]
    for key in COMPARED:
        assert s[key] == pytest.approx(float(ref[key]), rel=1e-6), key
    # The lab height mean is AVERAGE(K8:K3000), i.e. every recorded height, while
    # the engine averages heights of counted stems only. Compare heights only when
    # every recorded height is on a live stem with DBH (no dead stem with height,
    # no orphan height without condition or DBH, as in H2 2018).
    if int(ref["n_dead_with_height"]) == 0 and int(ref["n_height_not_live"]) == 0:
        assert s["height_mean_m"] == pytest.approx(float(ref["height_mean_m"]), rel=1e-6)
