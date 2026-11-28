# -*- coding: utf-8 -*-
# MangueTREE: structural analysis of mangrove forest plots.
# Copyright (c) 2026 Lucas Silva Pereira, Laiza Lacerda Motta, Tatiane Costa da Matta,
# Filipe de Oliveira Chaves, Mário Luiz Gomes Soares.
#
# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along with this
# program. If not, see <https://www.gnu.org/licenses/>.
"""
exportar.py
===========
One place for every table the app saves, so all pages export the same way:

* three formats: an organised Excel workbook (bold header, fitted columns, frozen header,
  filter, numbers shown with two decimals), a CSV that opens correctly in Excel (Portuguese:
  ``;`` between fields and ``,`` as decimal mark; English: ``,`` and ``.``; UTF-8 with BOM so
  the accents are right) and a TXT separated by tabs;
* numbers with two decimals in CSV and TXT (Excel keeps the full value and shows two);
* ``tabela_da_figura``: the table behind a chart, read from the figure itself, so every chart
  can save its data the way it saves its picture.
"""
import io
import re
import zipfile

import numpy as np
import pandas as pd

from manguetree import i18n

FORMATOS = ("xlsx", "csv", "txt")
EXTENSAO = {"xlsx": "xlsx", "csv": "csv", "txt": "txt"}
MIME = {"xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "csv": "text/csv", "txt": "text/plain"}
CASAS = 2


def separadores(lang):
    """(field separator, decimal mark) of the CSV in ``lang``."""
    return (";", ",") if str(lang).startswith("pt") else (",", ".")


def _plano(df):
    """Table with its named or non-trivial index turned into columns."""
    if df is None:
        return pd.DataFrame()
    if type(df).__name__ == "Styler":
        df = df.data
    nomeado = any(n is not None for n in df.index.names)
    if nomeado or not isinstance(df.index, pd.RangeIndex):
        df = df.reset_index()
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [" ".join(str(p) for p in c if str(p) != "") for c in df.columns]
    return df


def casas2(df, casas=CASAS):
    """Copy with the float columns rounded to two decimals."""
    out = _plano(df).copy()
    for c in out.columns:
        if pd.api.types.is_float_dtype(out[c]):
            out[c] = out[c].round(casas)
    return out


def bytes_csv(df, lang=None):
    """CSV for Excel: separators of the language, two decimals, UTF-8 with BOM."""
    sep, dec = separadores(lang or i18n.get_lang())
    return _plano(df).to_csv(index=False, sep=sep, decimal=dec,
                             float_format=f"%.{CASAS}f").encode("utf-8-sig")


def bytes_txt(df, lang=None):
    """Text separated by tabs, decimal mark of the language, two decimals, UTF-8 with BOM."""
    _, dec = separadores(lang or i18n.get_lang())
    return _plano(df).to_csv(index=False, sep="\t", decimal=dec,
                             float_format=f"%.{CASAS}f").encode("utf-8-sig")


def organiza_planilha(ws, casas=CASAS):
    """Header in bold on a coloured band, fitted columns, frozen header, filter and a number
    format with ``casas`` decimals on the float cells."""
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    if ws.max_row < 1 or ws.max_column < 1:
        return
    faixa = PatternFill("solid", fgColor="1F3B4D")
    fino = Side(style="thin", color="B8C4CC")
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = faixa
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = Border(bottom=fino)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    fmt = "0." + "0" * casas if casas else "0"
    for col in ws.columns:
        largura = 0
        for c in col:
            if c.row > 1 and isinstance(c.value, float):
                c.number_format = fmt
            texto = ("%.*f" % (casas, c.value)) if isinstance(c.value, float) else str(c.value or "")
            largura = max(largura, len(texto))
        ws.column_dimensions[col[0].column_letter].width = max(10, min(60, largura + 3))
    ws.row_dimensions[1].height = 30


def organiza_pasta(wb, casas=CASAS):
    """``organiza_planilha`` in every sheet of an openpyxl workbook."""
    for ws in wb.worksheets:
        organiza_planilha(ws, casas)


def _nome_aba(nome, usados):
    nome = "".join("_" if ch in '[]:*?/\\' else ch for ch in str(nome))[:31] or "Sheet"
    base, k = nome, 2
    while nome.lower() in usados:
        nome = f"{base[:28]}_{k}"
        k += 1
    usados.add(nome.lower())
    return nome


def nome_unico(nome, usados, maximo=26):
    """Sheet name for a table: no characters Excel refuses, at most ``maximo`` characters and
    different from every name in ``usados`` (case aside); a repeated one gets " (2)", " (3)"...
    Two plots whose names start alike, or a plot named like a summary sheet, keep both sheets."""
    base = re.sub(r"[\\/*?:\[\]]", "", str(nome))[:maximo] or "parc"
    vistos = {str(u).lower() for u in usados}
    out, n = base, 2
    while out.lower() in vistos:
        suf = f" ({n})"
        out, n = base[:maximo - len(suf)] + suf, n + 1
    return out


def bytes_xlsx(tabelas, lang=None):
    """Organised Excel workbook. ``tabelas`` is a DataFrame or {sheet name: DataFrame}."""
    if not isinstance(tabelas, dict):
        tabelas = {"Data": tabelas}
    buf = io.BytesIO()
    usados = set()
    with pd.ExcelWriter(buf, engine="openpyxl") as xls:
        for nome, df in tabelas.items():
            _plano(df).to_excel(xls, sheet_name=_nome_aba(nome, usados), index=False)
        if not tabelas:
            pd.DataFrame().to_excel(xls, sheet_name="Data")
        organiza_pasta(xls.book)
    return buf.getvalue()


def organiza_bytes(dados):
    """Reformat an .xlsx made elsewhere (bytes) with ``organiza_pasta``."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(dados))
    organiza_pasta(wb)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def bytes_tabela(df, formato, lang=None, nome="Data"):
    """Bytes of one table in ``formato`` (xlsx, csv or txt)."""
    if formato == "xlsx":
        return bytes_xlsx({nome: df}, lang)
    if formato == "csv":
        return bytes_csv(df, lang)
    if formato == "txt":
        return bytes_txt(df, lang)
    raise ValueError("formato deve ser xlsx, csv ou txt")


def bytes_zip(tabelas, formato, lang=None):
    """ZIP with one csv or txt file per table (for exports that have several tables)."""
    buf = io.BytesIO()
    usados = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, df in tabelas.items():
            # file names without accents or spaces (as every other file of the app), not cut
            # to the 31 characters of an Excel sheet
            from manguetree.nomes import slug
            base = slug(nome, 60) or "Tabela"
            arq, k = base, 2
            while arq.lower() in usados:
                arq, k = f"{base}-{k}", k + 1
            usados.add(arq.lower())
            z.writestr(f"{arq}.{EXTENSAO[formato]}", bytes_tabela(df, formato, lang, _nome_aba(nome, set())))
    return buf.getvalue()


def botoes(container, df, base, key, lang=None, tabelas=None, titulo=None, lado_a_lado=True,
           nota=None):
    """Download buttons Excel / CSV / TXT for ``df`` (or, with ``tabelas``, for a dict of
    tables: Excel with one sheet per table, CSV and TXT as a ZIP with one file each)."""
    import streamlit as st
    T = i18n.t
    lang = lang or i18n.get_lang()
    if titulo:                                   # bold title (no icon), same height in every column
        container.markdown(f"**{titulo}**")
    cols = container.columns(3) if lado_a_lado else [container] * 3
    for col, f in zip(cols, FORMATOS):
        rot = {"xlsx": T("export.fmt_xlsx", lang), "csv": T("export.fmt_csv", lang),
               "txt": T("export.fmt_txt", lang)}[f]
        if tabelas is not None:
            if f == "xlsx":
                dados, arq, mime = bytes_xlsx(tabelas, lang), f"{base}.xlsx", MIME["xlsx"]
            else:
                dados, arq, mime = bytes_zip(tabelas, f, lang), f"{base}_{f}.zip", "application/zip"
        else:
            dados, arq, mime = bytes_tabela(df, f, lang, base[:31]), f"{base}.{f}", MIME[f]
        col.download_button(rot, data=dados, file_name=arq, mime=mime, key=f"{key}_{f}",
                            width="stretch")
    if nota:
        container.caption(nota)


# --------------------------------------------------------------------------
# Table behind a chart
# --------------------------------------------------------------------------

def _titulo_eixo(eixo, padrao):
    t = getattr(getattr(eixo, "title", None), "text", None)
    return str(t) if t else padrao


def _lista(v):
    if v is None:
        return []
    return list(np.asarray(v).ravel()) if not isinstance(v, (list, tuple)) else list(v)


def tabela_da_figura(fig):
    """DataFrame with the data drawn in a Plotly figure (``None`` if there is nothing to
    save). Lines, points and bars: one column per series against the x values (or x, y and
    series in long form when the series do not share x values); error bars as a column;
    box and violin plots: every value of every group; pie charts: labels and values."""
    if fig is None or not len(fig.data):
        return None
    xt = _titulo_eixo(fig.layout.xaxis, "x")
    yt = _titulo_eixo(fig.layout.yaxis, "y")
    T = i18n.t                                   # column names in the language of the screen
    serie_t, grupo_t, valor_t, dp_t = (T("chart.table.series"), T("chart.table.group"),
                                       T("chart.table.value"), T("chart.table.sd"))
    series, longos = [], []
    for tr in fig.data:
        tipo = getattr(tr, "type", "")
        nome = str(tr.name) if getattr(tr, "name", None) else ""
        if tipo in ("box", "violin"):
            vals = _lista(tr.y if tr.y is not None else tr.x)
            if vals:
                grupos = _lista(tr.x) if tr.y is not None and tr.x is not None else [nome] * len(vals)
                longos.append(pd.DataFrame({xt if tr.x is not None else grupo_t: grupos[:len(vals)],
                                            yt: vals}))
            continue
        if tipo == "pie":
            if tr.values is not None:
                series.append(("pie", pd.DataFrame({grupo_t: _lista(tr.labels),
                                                    nome or valor_t: _lista(tr.values)})))
            continue
        if tipo not in ("scatter", "scattergl", "bar"):
            continue
        x, y = _lista(tr.x), _lista(tr.y)
        if getattr(tr, "orientation", None) == "h":
            x, y = y, x
        if not y or not x or all(v is None for v in y):
            continue                                    # legend-only traces
        d = pd.DataFrame({"x": x[:len(y)], "y": y[:len(x)]})
        err = getattr(tr, "error_y", None)
        if err is not None and getattr(err, "array", None) is not None:
            d["err"] = _lista(err.array)[:len(d)]
        series.append((nome or yt, d))
    if longos:
        return pd.concat(longos, ignore_index=True)
    if not series:
        return None
    if series[0][0] == "pie":
        return series[0][1]
    nomes = [n for n, _ in series]
    comp = max(len(d) for _, d in series)
    todos = pd.concat([d["x"] for _, d in series]).nunique()
    if todos <= 1.5 * comp:                             # series share the x values: wide table
        out, vistos = None, {}
        for n, d in series:
            vistos[n] = vistos.get(n, 0) + 1
            col = n if nomes.count(n) == 1 else f"{n} ({vistos[n]})"
            sub = d.drop_duplicates("x").set_index("x")
            part = pd.DataFrame({col: sub["y"]})
            if "err" in sub:
                part[f"{col} ({dp_t})"] = sub["err"]
            out = part if out is None else out.join(part, how="outer")
        out = out.sort_index().rename_axis(xt).reset_index()
        return out
    longo = []
    for n, d in series:
        d = d.rename(columns={"x": xt, "y": yt, "err": dp_t})
        d.insert(0, serie_t, n)
        longo.append(d)
    return pd.concat(longo, ignore_index=True)
