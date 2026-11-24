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
"""Number format (PT-BR / English), automatic texts and the grouped data check."""
from __future__ import annotations

import pandas as pd

from manguetree import i18n


def _casas(v, dec):
    """Results show two decimals (00,00); counts (dec 0) of whole numbers stay whole."""
    if dec >= 2:
        return dec
    return 0 if dec == 0 and abs(v - round(v)) < 1e-9 else 2


def fmt_br(v, dec=1, lang="pt") -> str:
    """12500.5 -> '12.500,5' (pt) / '12,500.5' (en); missing values -> '-'."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "-"
    if v != v:
        return "-"
    dec = _casas(v, dec)
    s = f"{v:,.{dec}f}"
    if lang == "pt":
        s = s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return s


def plotly_separators(lang="pt") -> str:
    """Plotly ``layout.separators``: decimal then thousands."""
    return ",." if lang == "pt" else ".,"


def mpl_formatter(lang="pt", dec=None):
    """Matplotlib FuncFormatter with the language's decimal mark."""
    from matplotlib.ticker import FuncFormatter

    def _f(x, _pos=None):
        d = dec if dec is not None else (0 if abs(x - round(x)) < 1e-9 else 1)
        return fmt_br(x, d, lang)
    return FuncFormatter(_f)


# --- text without repetition ------------------------------------------------------------
def join_leaders(items, lang="pt") -> list:
    """Merges plots that lead more than one indicator.

    ``items``: [(indicator_text, plot_name, value_text), ...]. Returns one clause per plot:
    the same plot leading two indicators becomes a single sentence."""
    T = lambda k, **kw: i18n.t(k, lang, **kw)
    by_plot = {}
    for ind, plot, val in items:
        by_plot.setdefault(plot, []).append((ind, val))
    out = []
    for plot, lst in by_plot.items():
        if len(lst) == 1:
            out.append(T("report.lead.one", plot=plot, indicator=lst[0][0], value=lst[0][1]))
        else:
            a, b = lst[0], lst[1]
            out.append(T("report.lead.two", plot=plot, ind1=a[0], val1=a[1], ind2=b[0], val2=b[1]))
    return out


# --- data check, grouped ----------------------------------------------------------------
def group_issues(issues_df, lang="pt", examples=2, max_rows=8):
    """Groups the issues table by (problem, severity).

    ``issues_df``: frame from ``charts.issues_display_frame`` in ``lang``. Returns
    (n_errors, n_warnings, table); the table has one row per problem category (errors first,
    then the most frequent) with the columns category | severity | count | example | action,
    named in ``lang``. It has at most ``max_rows`` rows (the rest merge into one row)."""
    from manguetree import charts as ui
    if issues_df is None:
        return None
    kind = ui.issue_column_label("kind", lang)
    sev = ui.issue_column_label("severity", lang)
    det = ui.issue_column_label("detail", lang)
    act = ui.issue_column_label("action", lang)
    if issues_df.empty:
        return 0, 0, pd.DataFrame()
    err_label = ui.severity_label("error", lang)
    n_err = int((issues_df[sev] == err_label).sum())
    n_warn = int((issues_df[sev] == ui.severity_label("warning", lang)).sum())
    rows = []
    for (k, s), g in issues_df.groupby([kind, sev], sort=False):
        ex = [str(x) for x in g[det].astype(str) if x][:examples]
        actions = [a for a in g[act].astype(str).unique() if a]
        rows.append({"_err": s != err_label, "_n": -len(g),
                     "cat": k, "sev": s, "n": len(g), "ex": "; ".join(ex),
                     "act": actions[0] if actions else ""})
    rows.sort(key=lambda r: (r["_err"], r["_n"], r["cat"]))
    if len(rows) > max_rows:
        rest = rows[max_rows - 1:]
        rows = rows[:max_rows - 1] + [{"cat": i18n.t("report.verification.other", lang), "sev": "",
                                       "n": sum(r["n"] for r in rest), "ex": "", "act": ""}]
    T = lambda k: i18n.t(f"report.verif.col.{k}", lang)
    table = pd.DataFrame([{T("category"): r["cat"], T("severity"): r["sev"], T("count"): r["n"],
                           T("example"): r["ex"], T("action"): r["act"]} for r in rows])
    return n_err, n_warn, table
