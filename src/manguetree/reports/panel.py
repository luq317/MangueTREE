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
"""Summary panel of the single-plot report, drawn natively for the A4 portrait page (no
screenshot of the screen panel): DBH classes with proportional bars, species contribution,
mortality bars and the Holdridge complexity index."""
from __future__ import annotations

import numpy as np
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Table, TableStyle, KeepTogether, Spacer
from xml.sax.saxutils import escape

from manguetree import calc as mc, i18n
from manguetree.reports import theme, formatting as fm

EDGES = (2.5, 5.0, 7.5, 10.0, 12.5)


def _c(h):
    return colors.HexColor(h)


def _bar(value, vmax, width, color, height=9, label=None, font="LiberationSans"):
    """Horizontal bar proportional to ``value / vmax`` with the number at its end."""
    d = Drawing(width, height)
    w = 0 if not vmax else max(0.0, min(1.0, value / vmax)) * (width - 26)
    d.add(Rect(0, 1, width - 26, height - 2, fillColor=_c(theme.GRID), strokeColor=None))
    if w > 0:
        d.add(Rect(0, 1, w, height - 2, fillColor=_c(color), strokeColor=None))
    d.add(String(width - 24, 2.2, label if label is not None else "", fontName=font, fontSize=7.5,
                 fillColor=_c(theme.INK)))
    return d


def _class_labels(lang):
    f = lambda v: fm.fmt_br(v, 1, lang).replace(",0", "").replace(".0", "")
    out = [("< " + f(EDGES[0]))]
    out += [f"{f(a)} a {f(b)}" if lang == "pt" else f"{f(a)} to {f(b)}" for a, b in zip(EDGES, EDGES[1:])]
    out.append("≥ " + f(EDGES[-1]))
    return out


def painel_vertical(res, lang, width, fonts):
    """Flowables of the panel. ``fonts``: (regular, bold) names registered in reportlab."""
    reg, bold = fonts
    T = lambda k, **kw: i18n.t(k, lang, **kw)
    s = res["summary"]
    d = res["data"]
    live = d[d["dbh"].notna() & (d["dbh"] > 0) & d["live"]]
    cnt = np.histogram(live["dbh"], bins=[-np.inf] + list(EDGES) + [np.inf])[0]
    head = ParagraphStyle("ph", fontName=bold, fontSize=theme.SIZE_H3, leading=14, textColor=_c(theme.TEAL))
    cell = ParagraphStyle("pc", fontName=reg, fontSize=theme.SIZE_SMALL, leading=11.5, textColor=_c(theme.INK))
    cellb = ParagraphStyle("pcb", parent=cell, fontName=bold)
    small = ParagraphStyle("ps", fontName=reg, fontSize=8, leading=10, textColor=_c(theme.INK_2))

    # --- classes -----------------------------------------------------------------------
    bw = width * 0.62
    mx = int(cnt.max()) if cnt.size else 0
    rows = [[Paragraph(escape(T("report.panel.class")), cellb), Paragraph(escape(T("report.panel.stems")), cellb)]]
    for lab, n in zip(_class_labels(lang), cnt):
        rows.append([Paragraph(escape(lab) + " cm", cell),
                     _bar(int(n), mx, bw, theme.NAVY if int(n) == mx else theme.TEAL, label=str(int(n)), font=reg)])
    t_cls = Table(rows, colWidths=[width * 0.22, bw], hAlign="LEFT")
    t_cls.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.6, _c(theme.RULE)),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                               ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
                               ("LEFTPADDING", (0, 0), (-1, -1), 2)]))

    # --- species ------------------------------------------------------------------------
    sp = mc.species_parameters(res).sort_values("ba_total_ha", ascending=False)
    cores = theme.species_colors(sp["species"])
    rows = [[Paragraph(escape(T("report.panel.species")), cellb), Paragraph("DeR (%)", cellb),
             Paragraph(escape(T("report.panel.ba_live")), cellb), Paragraph(escape(T("report.panel.ba_dead")), cellb)]]
    for _, r in sp.iterrows():
        nome = T("labels.unidentified") if r["species"] == mc.UNIDENTIFIED_LABEL else str(r["species"])
        rows.append([Paragraph(f'<font color="{cores[r["species"]]}">■</font> <i>{escape(nome)}</i>', cell),
                     Paragraph(fm.fmt_br(r["rel_density"], 1, lang), cell),
                     Paragraph(fm.fmt_br(r["ba_live_ha"], 2, lang), cell),
                     Paragraph(fm.fmt_br(r["ba_dead_ha"], 2, lang), cell)])
    t_sp = Table(rows, colWidths=[width * 0.50, width * 0.15, width * 0.17, width * 0.18], hAlign="LEFT")
    t_sp.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.6, _c(theme.RULE)),
                              ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                              ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
                              ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))

    # --- mortality and Holdridge ---------------------------------------------------------
    m1, m2 = float(s.get("mortality_stems_pct") or 0), float(s.get("mortality_ba_pct") or 0)
    mw = width * 0.60
    rows = [[Paragraph(escape(T("report.panel.mort_stems")), cell), _bar(m1, 100, mw, theme.AMBER, label=fm.fmt_br(m1, 1, lang) + "%", font=reg)],
            [Paragraph(escape(T("report.panel.mort_ba")), cell), _bar(m2, 100, mw, theme.AMBER, label=fm.fmt_br(m2, 1, lang) + "%", font=reg)]]
    t_m = Table(rows, colWidths=[width * 0.38, mw], hAlign="LEFT")
    t_m.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 2),
                             ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
    ic = res.get("complexity", {})
    ic25 = ic.get("dbh_gt_2.5", {}).get("ci"); ic10 = ic.get("dbh_gt_10", {}).get("ci")
    hold = Paragraph(f'<b>{escape(T("report.panel.holdridge"))}</b>: '
                     f'&gt; 2,5 cm = {fm.fmt_br(ic25, 2, lang)} · &gt; 10 cm = {fm.fmt_br(ic10, 2, lang)}'
                     if lang == "pt" else
                     f'<b>{escape(T("report.panel.holdridge"))}</b>: '
                     f'&gt; 2.5 cm = {fm.fmt_br(ic25, 2, lang)} · &gt; 10 cm = {fm.fmt_br(ic10, 2, lang)}', small)

    box = Table([[Paragraph(escape(T("report.panel.classes")), head)], [t_cls],
                 [Paragraph(escape(T("report.panel.contribution")), head)], [t_sp],
                 [Paragraph(escape(T("report.panel.mortality")), head)], [t_m], [hold]],
                colWidths=[width])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _c(theme.CALLOUT_BG)),
                             ("BOX", (0, 0), (-1, -1), 0.6, _c(theme.RULE)),
                             ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                             ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                             ("TOPPADDING", (0, 0), (0, 0), 7), ("TOPPADDING", (0, 2), (0, 2), 8),
                             ("TOPPADDING", (0, 4), (0, 4), 8), ("BOTTOMPADDING", (0, -1), (0, -1), 8)]))
    return [KeepTogether([box])]
