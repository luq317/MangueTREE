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
io.py
=====
Reading and normalisation of field files (.xlsx/.csv/.txt) into the MangueTREE
standard table, one row per stem, with the internal columns

    tree_id, n_stems, species, dbh, height, condition, tag, note, lat, lon, source_row

(only those present in the file, plus ``source_row``, the 1-based row number of the
stem in the original file). Numeric columns accept a decimal comma ("12,6") and
blank cells (" ") become NaN. A non-blank DBH or height cell that cannot be read as
a number also becomes NaN, but its raw text is kept in the hidden columns
``_raw_dbh`` / ``_raw_height`` so that validation can report it.

Sheet tables carry ``df.attrs["area_source"]`` ("label", "cell" or "fallback"; text
files are always "fallback", since they hold no area),
``df.attrs["area_value"]`` and, when a height column was found,
``df.attrs["height_source_header"]`` (the header text it was read from).
"""

import io as _stdio
import re

import openpyxl
import pandas as pd
from unidecode import unidecode

# Standard column -> accepted names (Portuguese lab names and the English names
# of the example files). Within each list, earlier aliases take priority.
COLUMN_ALIASES = {
    "tree_id":   ["tree_id", "tree", "ind", "individuo", "individuos", "arvore"],
    "n_stems":   ["n_stems", "stems", "n tr", "n trs", "n de troncos", "no trs",
                  "nº tr's", "n troncos", "tronco"],
    "species":   ["species", "spp", "especie", "especies", "sp"],
    "dbh":       ["dbh_cm", "dbh", "dap", "diametro"],
    "height":    ["height_m", "height", "altura", "alt corr", "altura corrigida",
                  "alt med", "alt"],
    "condition": ["condition", "cond", "condicao"],
    "tag":       ["tag", "lacre"],
    "note":      ["note", "notes", "obs", "observacao", "observacoes"],
    "lat":       ["lat", "latitude", "lattitude"],
    "lon":       ["lon", "long", "longitude"],
}
REQUIRED = {"tree_id", "species", "dbh", "condition"}
NUMERIC = ["n_stems", "dbh", "height", "lat", "lon"]
# Columns of which at least one must be filled for a row to be kept.
_ROW_KEYS = ["species", "dbh", "condition"]
# Cleaned labels (see ``_area_label_key``) that announce the plot area in a sheet header.
_AREA_LABELS = frozenset({"plot area m2", "plot area", "area", "area m2", "area da parcela",
                          "area parcela", "area da parcela m2", "parcela m2"})
# Numeric columns whose unreadable text is kept for validation.
RAW_COLUMNS = {"dbh": "_raw_dbh", "height": "_raw_height"}
_HEADER_SCAN_ROWS = 25
_MAX_DATA_ROWS = 5000


def clean_name(name):
    """Lower case, no accents, no punctuation and no unit in parentheses."""
    t = unidecode(str(name).lower())
    t = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", t)
    t = t.replace(".", "").replace("_", " ").replace("'", "")
    return " ".join(t.split())


_CLEAN_ALIASES = {k: [clean_name(a) for a in v] for k, v in COLUMN_ALIASES.items()}


def parse_cell_ref(ref_str):
    """'B4' -> (row_index, col_index), both 0-based. None if not a cell reference."""
    if not isinstance(ref_str, str) or len(ref_str) < 2:
        return None
    m = re.match(r"([A-Z]+)(\d+)$", ref_str.strip().upper())
    if not m:
        return None
    col_str, row_str = m.groups()
    col_idx = 0
    for ch in col_str:
        col_idx = col_idx * 26 + (ord(ch) - ord("A") + 1)
    return int(row_str) - 1, col_idx - 1


def _first_token(name):
    """First token of a cleaned name, split on spaces and letter/digit boundaries."""
    toks = re.findall(r"[a-z]+|\d+", name)
    return toks[0] if toks else ""


def _column_map(cols):
    """
    Map original column names to standard names; each standard column takes one
    source column. Two global passes: (1) exact match of the cleaned name, for every
    standard column, in alias priority order; (2) for the columns still unmapped,
    a substring match for aliases of 4+ letters, or, for shorter aliases, a match
    of the first token of the cleaned header ("dap cm", "dap1" -> "dap"; "lon gps"
    -> "lon", but "xlon" does not).
    """
    cleaned = {}
    for col in cols:
        if col is None or (not isinstance(col, str) and pd.isna(col)):
            continue
        cleaned[col] = clean_name(col)
    mapping = {}
    taken = set()

    def _assign(std, hit):
        if hit is not None:
            mapping[hit] = std
            taken.add(std)

    for std, aliases in _CLEAN_ALIASES.items():
        for a in aliases:
            hit = next((c for c, cn in cleaned.items()
                        if cn == a and c not in mapping), None)
            if hit is not None:
                _assign(std, hit)
                break
    for std, aliases in _CLEAN_ALIASES.items():
        if std in taken:
            continue
        hit = None
        for a in aliases:
            if len(a.replace(" ", "")) <= 3:
                hit = next((c for c, cn in cleaned.items()
                            if _first_token(cn) == a and c not in mapping), None)
            else:
                hit = next((c for c, cn in cleaned.items()
                            if a in cn and c not in mapping), None)
            if hit is not None:
                break
        _assign(std, hit)
    return mapping


def to_numeric(series):
    """Text with decimal comma -> float; blank or non-numeric cells -> NaN."""
    s = pd.Series(series)
    if s.dtype == object or pd.api.types.is_string_dtype(s):
        s = s.map(lambda v: v.strip().replace(",", ".") if isinstance(v, str) else v)
        s = s.map(lambda v: None if isinstance(v, str) and v == "" else v)
    return pd.to_numeric(s, errors="coerce").astype(float)


def _blank_to_none(v):
    return None if isinstance(v, str) and v.strip() == "" else v


def _unreadable_text(original, parsed):
    """Raw text of the non-blank cells that ``to_numeric`` turned into NaN (else None)."""
    bad = parsed.isna().to_numpy() & original.notna().to_numpy()
    return pd.Series([str(v).strip() if b else None
                      for v, b in zip(original.to_numpy(), bad)], index=original.index,
                     dtype=object)


def _normalise(df, source_rows):
    """Rename to standard columns, keep only those, convert numerics, drop empty rows."""
    mapping = _column_map(df.columns)
    out = pd.DataFrame({std: df[col].map(_blank_to_none).to_numpy()
                        for col, std in mapping.items()})
    out = out[[c for c in COLUMN_ALIASES if c in out.columns]]
    for c in NUMERIC:
        if c in out.columns:
            parsed = to_numeric(out[c])
            if c in RAW_COLUMNS:
                raw = _unreadable_text(out[c], parsed)
                if raw.notna().any():
                    out[RAW_COLUMNS[c]] = raw
            out[c] = parsed
    out["source_row"] = list(source_rows)
    keys = [c for c in _ROW_KEYS + list(RAW_COLUMNS.values()) if c in out.columns]
    if keys:
        out = out.dropna(subset=keys, how="all")
    out = out.reset_index(drop=True)
    height_src = next((col for col, std in mapping.items() if std == "height"), None)
    if height_src is not None:
        out.attrs["height_source_header"] = str(height_src)
    return out


def _open_sheet(file_or_path, sheet_name):
    if hasattr(file_or_path, "seek"):
        file_or_path.seek(0)
    wb = openpyxl.load_workbook(file_or_path, read_only=True, data_only=True)
    ws = wb.worksheets[sheet_name] if isinstance(sheet_name, int) else wb[sheet_name]
    ws.reset_dimensions()    # some writers store a wrong <dimension>; read all rows
    return wb, ws


def _area_label_key(value):
    """Cleaned header label: no accents, no ':' and no unit brackets ("Área (m²):" -> "area")."""
    if not isinstance(value, str):
        return ""
    return clean_name(unidecode(value).replace("²", "2").replace(":", " "))


def _is_area_label(value):
    key = _area_label_key(value)
    if key in _AREA_LABELS:
        return True
    # a bare "Parcela" is a plot name label unless the unit is written ("Parcela (m2)")
    return key == "parcela" and "m2" in unidecode(str(value)).replace("²", "2").lower()


def _area_number(value):
    """Positive number from a numeric cell or text with decimal comma; else None."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str):
        value = to_numeric(pd.Series([value])).iloc[0]
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if pd.notna(v) and v > 0 else None


def _find_area(top, cell_ref, fallback, label_rows=None):
    """(area, source): the cell right of an area label (searched in ``label_rows``,
    default all of ``top``), else ``cell_ref``, else fallback."""
    for row in (top if label_rows is None else label_rows):
        for j, v in enumerate(row[:-1]):
            if _is_area_label(v):
                num = _area_number(row[j + 1])
                if num is not None:
                    return num, "label"
    if cell_ref:
        pr = parse_cell_ref(cell_ref)
        if pr and pr[0] < len(top) and pr[1] < len(top[pr[0]]):
            num = _area_number(top[pr[0]][pr[1]])
            if num is not None:
                return num, "cell"
    return fallback, "fallback"


def load_excel_sheet(file_or_path, sheet_name, cell_ref=None, area_fallback=100.0):
    """
    Read one Excel sheet. The header row is the first of the top rows that holds
    all required columns; data follow it. Plot area: the numeric (or decimal-comma
    text) cell right of an area label in the top rows ("plot_area_m2", "Área (m²)",
    "Área da parcela", "Parcela (m2)"...), else the cell ``cell_ref`` (e.g. "B4"),
    else ``area_fallback``; ``table.attrs["area_source"]`` tells which one was used.
    Returns (table, area); table is None if no header is found.
    """
    try:
        wb, ws = _open_sheet(file_or_path, sheet_name)
    except Exception:
        return None, float(area_fallback)
    try:
        rows = []
        header_idx = None
        for values in ws.iter_rows(values_only=True):
            rows.append(list(values))
            if header_idx is None:
                if len(rows) > _HEADER_SCAN_ROWS:
                    break
                found = set(_column_map(values).values())
                if REQUIRED.issubset(found):
                    header_idx = len(rows) - 1
            elif len(rows) - header_idx > _MAX_DATA_ROWS:
                break
    finally:
        wb.close()

    top = rows[:_HEADER_SCAN_ROWS]
    # the area label is searched only above the header row, never among the data
    label_rows = top[:header_idx] if header_idx is not None else top
    area, source = _find_area(top, cell_ref, float(area_fallback), label_rows)

    if header_idx is None:
        return None, area
    header = rows[header_idx]
    data = rows[header_idx + 1:]
    width = len(header)
    data = [(r + [None] * width)[:width] for r in data]
    raw = pd.DataFrame(data, columns=range(width), dtype=object)
    raw.columns = [h if h is not None else f"_col{i}" for i, h in enumerate(header)]
    raw = raw.loc[:, ~pd.Index(raw.columns).duplicated(keep="first")]
    first = header_idx + 2          # 1-based row number of the first data row
    out = _normalise(raw, range(first, first + len(raw)))
    out.attrs["area_source"] = source
    out.attrs["area_value"] = area
    return out, area


def _read_text(file_or_path):
    """Decoded text of a path or file object: UTF-8 (with or without BOM), else
    Windows-1252, else Latin-1 (which accepts any byte)."""
    if hasattr(file_or_path, "read"):
        if hasattr(file_or_path, "seek"):
            file_or_path.seek(0)
        data = file_or_path.read()
    else:
        with open(file_or_path, "rb") as fh:
            data = fh.read()
    if isinstance(data, str):
        return data
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def load_csv(file_or_path, delimiter=";"):
    """Read a .csv/.txt file (header on line 1) into the standard table."""
    raw = pd.read_csv(_stdio.StringIO(_read_text(file_or_path)), sep=delimiter,
                      dtype=str, keep_default_na=False)
    raw = raw.loc[:, ~pd.Index(raw.columns).duplicated(keep="first")]
    out = _normalise(raw, range(2, 2 + len(raw)))
    # a text file carries no plot area: the caller supplies it (the validation reports
    # "area_fallback" until it does)
    out.attrs["area_source"] = "fallback"
    return out


def has_required_columns(df):
    return df is not None and REQUIRED.issubset(set(df.columns))
