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
unidades.py
===========
Unit of the heights shown by the app (metres or centimetres).

The calculation always uses metres (structure) or centimetres (colonization, as typed in
the NEMA workbooks); the choice is only for what is shown, saved and printed: tables,
charts, Excel, CSV and TXT files, the summary panel and the PDF reports. The choice lives in
the session (``unidade_altura``), set by the "Height unit" control of the sidebar.
"""
import numpy as np
import pandas as pd

UNIDADES = ("m", "cm")

#: columns (and summary keys) of the structure results that hold a height in metres
HEIGHT_COLS = frozenset({"height", "height_mean_m", "height_sd_m", "height_min_m",
                         "height_max_m", "canopy_height_m"})


def altura_unidade():
    """"m" or "cm", as chosen in the sidebar (default "m")."""
    try:
        import streamlit as st
        u = st.session_state.get("unidade_altura", "m")
    except Exception:
        u = "m"
    return u if u in UNIDADES else "m"


def fator_m(unidade=None):
    """Factor that turns metres into ``unidade`` (1 for m, 100 for cm)."""
    return 100.0 if (unidade or altura_unidade()) == "cm" else 1.0


def fator_cm(unidade=None):
    """Factor that turns centimetres into ``unidade`` (1 for cm, 0.01 for m)."""
    return 1.0 if (unidade or altura_unidade()) == "cm" else 0.01


def _conv(obj, f):
    if isinstance(obj, pd.DataFrame):
        if obj.attrs.get("alt_un") == "cm":
            return obj
        cols = [c for c in obj.columns if c in HEIGHT_COLS]
        if not cols:
            return obj
        out = obj.copy()
        out[cols] = out[cols].astype(float) * f
        out.attrs["alt_un"] = "cm"
        return out
    if isinstance(obj, dict):
        return {k: (v * f if k in HEIGHT_COLS and isinstance(v, (int, float, np.floating))
                    and not isinstance(v, bool) else _conv(v, f))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_conv(x, f) for x in obj]
    return obj


def na_unidade(obj, unidade=None):
    """Copy of a structure result (dict of tables and summary), table or list of results with
    the height columns and keys (``HEIGHT_COLS``) in the chosen unit; metres return the
    object unchanged. Call it once per object: converted tables are marked and skipped."""
    if (unidade or altura_unidade()) == "m":
        return obj
    return _conv(obj, 100.0)
