import io

import pandas as pd

from manguetree import calc as mc
from manguetree import io as mio
from manguetree import template as tpl
from manguetree.species import SpeciesResolver, load_genus_defaults, load_species_table

RES = SpeciesResolver(load_species_table(), "BR_S_SE", load_genus_defaults())


def test_template_excel_is_read_by_the_app(tmp_path):
    for lang, sheet in (("pt", "Dados"), ("en", "Data")):
        f = tmp_path / f"t_{lang}.xlsx"
        f.write_bytes(tpl.excel_bytes(lang))
        df, area = mio.load_excel_sheet(str(f), sheet, "", 50.0)
        assert area == 100 and mio.has_required_columns(df)
        r = mc.analyze(df, area, RES)
        assert r["summary"]["n_stems"] == 5 and r["summary"]["n_species_live"] == 3
        assert len(pd.ExcelFile(f).sheet_names) == 2


def test_template_csv_is_read_by_the_app(tmp_path):
    f = tmp_path / "t.csv"
    f.write_bytes(tpl.csv_bytes("pt"))
    df = mio.load_csv(str(f), ";")
    assert mio.has_required_columns(df) and len(df) == 5
