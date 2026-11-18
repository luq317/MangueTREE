# -*- coding: utf-8 -*-
"""
template.py
===========
Data template offered for download on the home page: the columns the app reads, a
few example rows and a sheet with instructions and the species codes. Portuguese or
English headers; Excel (data + instructions) or CSV (data only).
"""
import io

import pandas as pd

from manguetree import i18n
from manguetree.species import load_species_table

HEADERS = {
    "pt": ["Indivíduo", "Nº troncos", "Espécie", "DAP (cm)", "Altura (m)", "Condição",
           "Lacre", "Latitude", "Longitude", "Observação"],
    "en": ["tree_id", "n_stems", "species", "dbh_cm", "height_m", "condition",
           "tag", "latitude", "longitude", "note"],
}
EXAMPLE = [
    [1, 1, "Rm", 8.4, 6.2, "v", "1001", -23.0012, -43.5671, ""],
    [2, 2, "Av", 12.1, 7.8, "v", "1002", -23.0012, -43.5671, ""],
    [2, 2, "Av", 5.3, 5.1, "v", "1002", -23.0012, -43.5671, ""],
    [3, 1, "Lg", 4.0, 3.9, "v", "1003", -23.0012, -43.5671, ""],
    [4, 1, "Rm", 6.7, None, "m", "1004", -23.0012, -43.5671, ""],
]


def data_frame(lang):
    return pd.DataFrame(EXAMPLE, columns=HEADERS[lang])


def instructions(lang):
    T = lambda k: i18n.t(k, lang)
    rows = [[T(f"template.col.{c}"), T(f"template.desc.{c}")] for c in
            ("tree_id", "n_stems", "species", "dbh", "height", "condition", "tag", "lat", "lon", "note")]
    rows += [["", ""], [T("template.area"), T("template.area_desc")], ["", ""],
             [T("template.codes"), ""]]
    sp = load_species_table()
    rows += [[r["code"], r["scientific_name"]] for _, r in sp.iterrows()]
    rows += [["Av", T("template.av")]]
    return pd.DataFrame(rows, columns=[T("template.h1"), T("template.h2")])


def excel_bytes(lang):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xls:
        # the plot area goes in the first rows, as in the field sheets the app reads
        pd.DataFrame([[i18n.t("template.area_cell", lang), 100]]).to_excel(
            xls, sheet_name=i18n.t("template.sheet_data", lang), index=False, header=False)
        data_frame(lang).to_excel(xls, sheet_name=i18n.t("template.sheet_data", lang),
                                  index=False, startrow=2)
        instructions(lang).to_excel(xls, sheet_name=i18n.t("template.sheet_help", lang), index=False)
        for ws in xls.book.worksheets:
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = max(
                    12, min(60, max(len(str(c.value or "")) for c in col) + 2))
    return buf.getvalue()


def csv_bytes(lang):
    sep = ";" if lang == "pt" else ","
    dec = "," if lang == "pt" else "."
    return data_frame(lang).to_csv(index=False, sep=sep, decimal=dec).encode("utf-8-sig")
