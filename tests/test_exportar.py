# -*- coding: utf-8 -*-
"""Tests of manguetree.exportar: formats, two decimals and the table behind a chart."""
import io

import openpyxl
import pandas as pd
import plotly.graph_objects as go

from manguetree import exportar


def _df():
    return pd.DataFrame({"ano": [2004, 2005], "dens": [1.234, 2.5], "esp": ["Av", "Lg"]})


def test_csv_for_excel_in_portuguese_and_english():
    pt = exportar.bytes_csv(_df(), "pt")
    assert pt.startswith(b"\xef\xbb\xbf")                                  # BOM: accents in Excel
    assert pt.decode("utf-8-sig").splitlines() == ["ano;dens;esp", "2004;1,23;Av", "2005;2,50;Lg"]
    en = exportar.bytes_csv(_df(), "en").decode("utf-8-sig").splitlines()
    assert en == ["ano,dens,esp", "2004,1.23,Av", "2005,2.50,Lg"]


def test_txt_is_tab_separated_with_two_decimals():
    txt = exportar.bytes_txt(_df(), "pt").decode("utf-8-sig").splitlines()
    assert txt == ["ano\tdens\tesp", "2004\t1,23\tAv", "2005\t2,50\tLg"]


def test_xlsx_is_organised_and_keeps_the_full_value():
    wb = openpyxl.load_workbook(io.BytesIO(exportar.bytes_xlsx({"Dados": _df()})))
    ws = wb["Dados"]
    assert ws.freeze_panes == "A2" and ws["A1"].font.bold and ws.auto_filter.ref
    assert ws["B2"].value == 1.234 and ws["B2"].number_format == "0.00"
    assert ws.column_dimensions["A"].width >= 10


def test_index_and_multiindex_become_columns():
    piv = pd.DataFrame({"H": [1.0, 2.0]}, index=pd.Index([2004, 2005], name="Ano"))
    assert exportar.bytes_csv(piv, "pt").decode("utf-8-sig").splitlines()[0] == "Ano;H"


def test_zip_has_one_file_per_table():
    import zipfile
    z = zipfile.ZipFile(io.BytesIO(exportar.bytes_zip({"a": _df(), "b": _df()}, "csv", "pt")))
    assert sorted(z.namelist()) == ["a.csv", "b.csv"]


def test_table_of_a_line_chart_with_error_bars_and_legend_dummy():
    f = go.Figure()
    f.add_trace(go.Scatter(x=[2004, 2005], y=[1.5, 2.5], name="H", error_y=dict(array=[.1, .2])))
    f.add_trace(go.Scatter(x=[2005, 2006], y=[3, 4], name="I"))
    f.add_trace(go.Scatter(x=[None], y=[None], name="legend only"))
    f.update_layout(xaxis_title="Year", yaxis_title="Density")
    t = exportar.tabela_da_figura(f)
    assert list(t.columns) == ["Year", "H", "H (SD)", "I"]
    assert t["Year"].tolist() == [2004, 2005, 2006] and t["I"].isna().tolist() == [True, False, False]


def test_table_of_box_pie_and_empty_figures():
    b = go.Figure(go.Box(y=[1, 2, 3], x=["a", "a", "b"], name="s"))
    assert len(exportar.tabela_da_figura(b)) == 3
    p = go.Figure(go.Pie(labels=["x", "y"], values=[1, 2]))
    assert exportar.tabela_da_figura(p).shape == (2, 2)
    assert exportar.tabela_da_figura(go.Figure()) is None
