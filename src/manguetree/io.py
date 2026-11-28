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
    "tree_id":   ["tree_id", "tree", "ind", "individuo", "individuos", "arvore", "no", "num", "numero"],
    "n_stems":   ["n_stems", "stems", "n tr", "n trs", "n de troncos", "no trs",
                  "nº tr's", "n troncos", "tronco"],
    "species":   ["species", "spp", "especie", "especies", "sp"],
    "dbh":       ["dbh_cm", "dbh", "dap", "diametro"],
    "height":    ["height_m", "height", "altura", "alt corr", "altura corrigida",
                  "alt med", "alt"],
    "condition": ["condition", "cond", "condicao", "status", "vivo morto", "vivo/morto", "estado"],
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
                          "area parcela", "area da parcela m2", "parcela m2", "area total",
                          "area total m2", "area ha", "area da parcela ha", "plot area ha",
                          "area amostrada", "area amostrada m2", "area amostrada ha",
                          "area amostral", "area amostral m2", "area amostral ha",
                          "sampled area", "sampled area m2", "sampled area ha",
                          "sample area", "sample area m2", "sample area ha"})
# Units found in a header (in parentheses, brackets or as the last word) and the factor that
# brings the values to the unit the app works in (cm for DBH, m for height, m2 for area).
_UNIT_FACTORS = {
    "dbh": {"mm": 0.1, "m": 100.0},
    "height": {"cm": 0.01, "mm": 0.001},
    "area": {"ha": 10000.0},
}
_UNIT_TARGET = {"dbh": "cm", "height": "m", "area": "m2"}
# Numeric columns whose unreadable text is kept for validation.
RAW_COLUMNS = {"dbh": "_raw_dbh", "height": "_raw_height"}
_HEADER_SCAN_ROWS = 25
_MAX_DATA_ROWS = 20000


def clean_name(name):
    """Lower case, no accents, no punctuation and no unit in parentheses."""
    t = unidecode(str(name).lower())
    t = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", t)
    t = t.replace(".", "").replace("_", " ").replace("'", "")
    return " ".join(t.split())


def header_unit(name):
    """Unit written in a header: in parentheses or brackets, else the last word
    ("DAP (mm)" -> "mm", "Altura cm" -> "cm"); None when there is none."""
    t = unidecode(str(name)).lower().replace("\u00b2", "2")
    m = re.search(r"\(([^)]*)\)|\[([^\]]*)\]", t)
    if m:
        u = (m.group(1) or m.group(2) or "").strip()
    else:
        toks = re.findall(r"[a-z0-9]+", t)
        u = toks[-1] if len(toks) > 1 else ""
    u = u.replace(" ", "")
    return u or None


def unit_factor(kind, header):
    """(factor, unit) to convert a column of ``kind`` ("dbh", "height", "area") written in the
    unit of its ``header`` to the app unit; (1.0, None) when no conversion is needed."""
    u = header_unit(header)
    f = _UNIT_FACTORS[kind].get(u)
    return (f, u) if f else (1.0, None)


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
    conversions = []
    out = out[[c for c in COLUMN_ALIASES if c in out.columns]]
    for c in NUMERIC:
        if c in out.columns:
            parsed = to_numeric(out[c])
            if c in RAW_COLUMNS:
                raw = _unreadable_text(out[c], parsed)
                if raw.notna().any():
                    out[RAW_COLUMNS[c]] = raw
            if c in _UNIT_FACTORS:
                src = next((col for col, std in mapping.items() if std == c), None)
                f, unit = unit_factor(c, src) if src is not None else (1.0, None)
                if unit:
                    parsed = parsed * f
                    conversions.append({"column": c, "from_unit": unit, "to_unit": _UNIT_TARGET[c],
                                        "header": str(src)})
            out[c] = parsed
    out["source_row"] = list(source_rows)
    keys = [c for c in _ROW_KEYS + list(RAW_COLUMNS.values()) if c in out.columns]
    if keys:
        out = out.dropna(subset=keys, how="all")
    out = out.reset_index(drop=True)
    if conversions:
        out.attrs["unit_conversions"] = conversions
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
        m = re.match(r"^\s*([0-9][0-9.,]*)\s*(m2|m\u00b2|ha)?\s*$", value.strip().lower())
        if m:
            txt = m.group(1)
            # thousands marks in m2 ("1.000", "1.000,5", "1,000"): a plot of 1 m2 does not exist
            if m.group(2) != "ha" and re.fullmatch(r"[1-9]\d{0,2}(\.\d{3})+(,\d+)?", txt):
                txt = txt.replace(".", "")
            elif m.group(2) != "ha" and re.fullmatch(r"[1-9]\d{0,2}(,\d{3})+(\.\d+)?", txt):
                txt = txt.replace(",", "")
            num = to_numeric(pd.Series([txt])).iloc[0]
            if m.group(2) == "ha" and pd.notna(num):
                num = num * 10000.0
            value = num
        else:
            value = to_numeric(pd.Series([value])).iloc[0]
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if pd.notna(v) and v > 0 else None


def _area_text_unit(value):
    """Unit written after the number in an area cell ("0,01 ha" -> "ha", "100 m²" -> "m2"),
    else None."""
    if not isinstance(value, str):
        return None
    m = re.match(r"^\s*[0-9][0-9.,]*\s*(m2|m²|ha)\s*$", value.strip().lower())
    if not m:
        return None
    return "ha" if m.group(1) == "ha" else "m2"


def _find_area_ex(top, cell_ref, fallback, label_rows=None):
    """(area, source, info): the cell right of an area label (searched in ``label_rows``,
    default all of ``top``), else ``cell_ref``, else fallback. The value may sit one empty cell
    further right or right below the label; a label written in hectares ("Area (ha)") is
    converted to m2. ``info`` has "converted_from" (unit) and "invalid_value" (a label with 0
    or a negative number) when they apply."""
    rows = list(top if label_rows is None else label_rows)
    info = {}
    for ri, row in enumerate(rows):
        for j, v in enumerate(row):
            if not _is_area_label(v):
                continue
            cands = []
            if j + 1 < len(row):
                cands.append(row[j + 1])
                if row[j + 1] is None and j + 2 < len(row):
                    cands.append(row[j + 2])
            if ri + 1 < len(rows) and j < len(rows[ri + 1]):
                cands.append(rows[ri + 1][j])
            for cell in cands:
                num = _area_number(cell)
                if num is None:
                    if isinstance(cell, (int, float)) and not isinstance(cell, bool) and cell <= 0:
                        info["invalid_value"] = float(cell)
                    continue
                # a unit written with the value ("0,01 ha", "100 m²") was applied by
                # _area_number and wins over the unit of the label (no double conversion)
                cell_unit = _area_text_unit(cell)
                if cell_unit is not None:
                    if cell_unit == "ha":
                        info["converted_from"] = "ha"
                    return num, "label", info
                f, unit = unit_factor("area", v)
                if unit:
                    info["converted_from"] = unit
                return num * f, "label", info
    if cell_ref:
        pr = parse_cell_ref(cell_ref)
        if pr and pr[0] < len(top) and pr[1] < len(top[pr[0]]):
            num = _area_number(top[pr[0]][pr[1]])
            if num is not None:
                return num, "cell", info
    return fallback, "fallback", info


def _find_area(top, cell_ref, fallback, label_rows=None):
    """(area, source): see ``_find_area_ex``."""
    area, source, _ = _find_area_ex(top, cell_ref, fallback, label_rows)
    return area, source


def _merged_ranges(file_or_path, sheet_name):
    """Merged-cell ranges of one sheet as (min_row, min_col, max_row, max_col), 1-based,
    read straight from the .xlsx XML (the read-only reader of openpyxl does not fill them)."""
    import re as _re
    import zipfile
    import xml.etree.ElementTree as ET
    if hasattr(file_or_path, "seek"):
        file_or_path.seek(0)
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
          "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    with zipfile.ZipFile(file_or_path) as z:
        wbx = ET.fromstring(z.read("xl/workbook.xml"))
        sheets = wbx.find("m:sheets", ns)
        entries = list(sheets) if sheets is not None else []
        if isinstance(sheet_name, int):
            entry = entries[sheet_name]
        else:
            entry = next(e for e in entries if e.get("name") == sheet_name)
        rid = entry.get("{%s}id" % ns["r"])
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = next(r.get("Target") for r in rels if r.get("Id") == rid)
        path = target.lstrip("/") if target.startswith("/") else "xl/" + target
        xml = z.read(path).decode("utf-8", "ignore")
    out = []
    for ref in _re.findall(r'<mergeCell\s+ref="([A-Z]+\d+):([A-Z]+\d+)"', xml):
        a, b = parse_cell_ref(ref[0]), parse_cell_ref(ref[1])
        if a and b:
            out.append((a[0] + 1, a[1] + 1, b[0] + 1, b[1] + 1))
    return out


# Columns that describe the whole tree, so a merged cell over its stems means "same value for
# every stem". DBH and height are per stem (height only on the first stem): never filled.
_MERGE_FILL = frozenset({"tree_id", "n_stems", "species", "condition"})


def _fill_merged(file_or_path, sheet_name, rows, header_idx):
    """Copy the value of each vertically merged data range into its empty cells (the way
    Excel shows it), only in the tree-level columns (``_MERGE_FILL``) below the header;
    ``rows`` is edited in place. Returns how many cells were filled."""
    if header_idx is None:
        return 0
    header = rows[header_idx]
    mapping = _column_map(header)
    cols = {i + 1 for i, h in enumerate(header) if h in mapping and mapping[h] in _MERGE_FILL}
    if not cols:
        return 0
    try:
        ranges = _merged_ranges(file_or_path, sheet_name)
    except Exception:
        return 0
    filled = 0
    for r1, c1, r2, c2, in ranges:
        if r2 <= r1 or r1 > len(rows) or r1 <= header_idx + 1:
            continue
        for c in range(c1, c2 + 1):
            if c not in cols:
                continue
            top_row = rows[r1 - 1]
            if c - 1 >= len(top_row) or top_row[c - 1] is None:
                continue
            for r in range(r1 + 1, min(r2, len(rows)) + 1):
                row = rows[r - 1]
                while len(row) < c:
                    row.append(None)
                if row[c - 1] is None:
                    row[c - 1] = top_row[c - 1]
                    filled += 1
    return filled


def _has_formulas_without_value(file_or_path, sheet_name, header, header_idx):
    """True when the DBH column holds formulas (cells starting with "=") whose results were
    not stored in the file (files written by scripts and never opened in Excel)."""
    try:
        if hasattr(file_or_path, "seek"):
            file_or_path.seek(0)
        wb = openpyxl.load_workbook(file_or_path, read_only=True, data_only=False)
        try:
            ws = wb.worksheets[sheet_name] if isinstance(sheet_name, int) else wb[sheet_name]
            ws.reset_dimensions()
            mapping = _column_map(header)
            idx = next((i for i, h in enumerate(header) if h in mapping and mapping[h] == "dbh"), None)
            if idx is None:
                return False
            for n, values in enumerate(ws.iter_rows(values_only=True)):
                if n <= header_idx:
                    continue
                if n > header_idx + 300:
                    break
                v = values[idx] if idx < len(values) else None
                if isinstance(v, str) and v.startswith("="):
                    return True
        finally:
            wb.close()
    except Exception:
        return False
    return False


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
    truncated = False
    try:
        rows = []
        header_idx = None
        it = iter(ws.iter_rows(values_only=True))
        for values in it:
            rows.append(list(values))
            if header_idx is None:
                if len(rows) > _HEADER_SCAN_ROWS:
                    break
                found = set(_column_map(values).values())
                if REQUIRED.issubset(found):
                    header_idx = len(rows) - 1
            elif len(rows) - header_idx > _MAX_DATA_ROWS:
                for extra in it:                   # is there anything left beyond the limit?
                    if any(v is not None and str(v).strip() != "" for v in extra):
                        truncated = True
                        break
                break
    finally:
        wb.close()
    merged_filled = _fill_merged(file_or_path, sheet_name, rows, header_idx)

    top = rows[:_HEADER_SCAN_ROWS]
    # the area label is searched only above the header row, never among the data
    label_rows = top[:header_idx] if header_idx is not None else top
    area, source, area_info = _find_area_ex(top, cell_ref, float(area_fallback), label_rows)

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
    if area_info.get("converted_from"):
        out.attrs["area_converted_from"] = area_info["converted_from"]
    if "invalid_value" in area_info and source == "fallback":
        out.attrs["area_invalid_value"] = area_info["invalid_value"]
    if truncated:
        out.attrs["rows_truncated"] = _MAX_DATA_ROWS
    if merged_filled:
        out.attrs["merged_cells_filled"] = merged_filled
    if "dbh" in out.columns and len(out) and out["dbh"].isna().all() and \
            _has_formulas_without_value(file_or_path, sheet_name, header, header_idx):
        out.attrs["formulas_without_value"] = True
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
    text = _read_text(file_or_path)
    raw = pd.read_csv(_stdio.StringIO(text), sep=delimiter, dtype=str, keep_default_na=False)
    if raw.shape[1] < 3:                      # wrong delimiter: try the usual ones
        for alt in (";", ",", "\t"):
            if alt == delimiter:
                continue
            try_raw = pd.read_csv(_stdio.StringIO(text), sep=alt, dtype=str, keep_default_na=False)
            if try_raw.shape[1] >= 3:
                raw = try_raw
                break
    raw = raw.loc[:, ~pd.Index(raw.columns).duplicated(keep="first")]
    out = _normalise(raw, range(2, 2 + len(raw)))
    # a text file carries no plot area: the caller supplies it (the validation reports
    # "area_fallback" until it does)
    out.attrs["area_source"] = "fallback"
    return out


def has_required_columns(df):
    return df is not None and REQUIRED.issubset(set(df.columns))


def accepted_names(columns=("tree_id", "species", "dbh", "condition"), per_column=5):
    """Short text listing the names accepted for each essential column (for error messages)."""
    return "; ".join(f"{c}: " + ", ".join(COLUMN_ALIASES[c][:per_column]) for c in columns)


def missing_columns(df):
    """Essential columns that ``df`` lacks, in the usual order."""
    have = set(df.columns) if df is not None else set()
    return [c for c in ("tree_id", "species", "dbh", "condition") if c not in have]
