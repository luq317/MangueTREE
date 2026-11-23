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
icons.py
========
MangueTREE's own icon set (SVG files in ``app/assets/icons``), drawn from the logo:
green canopy, brown trunk and prop roots with blue tips.

Streamlit tabs and page links accept only emoji or Material icons, so the icons are
placed with CSS (``::before`` with an SVG data URI). Each analysis page has a single
``st.tabs`` call, so tabs are matched by position (``data-key``).
"""
import base64
from functools import lru_cache
from pathlib import Path

ICON_DIR = Path(__file__).parent / "app" / "assets" / "icons"

NAV_ICONS = {"Home": "inicio", "1_Single_plot": "parcela_unica",
             "2_Multiple_plots": "multiplas", "3_Temporal": "temporal", "4_About": "sobre",
             "5_Colonizacao": "dinamica"}


@lru_cache(maxsize=None)
def data_uri(name):
    """``data:image/svg+xml;base64,...`` of icon ``name`` ('' if the file is missing)."""
    path = ICON_DIR / f"{name}.svg"
    if not path.exists():
        return ""
    return "data:image/svg+xml;base64," + base64.b64encode(path.read_bytes()).decode()


def img(name, size=20, valign="-4px"):
    """Inline ``<img>`` tag for markdown with ``unsafe_allow_html``."""
    uri = data_uri(name)
    return (f'<img src="{uri}" width="{size}" height="{size}" alt="" '
            f'style="vertical-align:{valign};margin-right:8px">') if uri else ""


def _before(selector, name, size=18):
    return (f'{selector}::before{{content:"";display:inline-block;width:{size}px;'
            f'height:{size}px;margin-right:7px;vertical-align:-3px;flex-shrink:0;'
            f'background:url("{data_uri(name)}") no-repeat center/contain;}}')


def css(tab_icons=(), subtab_icons=()):
    """CSS that places the nav icons and, by position, the icons of the page's tabs.
    ``subtab_icons`` are those of tabs nested inside a tab (they never inherit the icons of
    the page's own tabs)."""
    nav = '[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]'
    rules = [_before(f'{nav}[href="{"" if k == "Home" else k.split("_", 1)[1]}"]', v)
             for k, v in NAV_ICONS.items()]
    rules += [_before(f'[role="tablist"] [data-testid="stTab"][data-key="{i}"] p', name)
              for i, name in enumerate(tab_icons) if name]
    if subtab_icons:
        sub = '[role="tabpanel"] [role="tablist"] [data-testid="stTab"]'
        rules.append(f'{sub} p::before{{display:none;}}')
        rules += [_before(f'{sub}[data-key="{i}"] p', name)
                  for i, name in enumerate(subtab_icons) if name]
    rules.append('[data-testid="stTab"] p{display:flex;align-items:center;}')
    # selector titles (Métrica, Condição, Tipo de gráfico...) stand out from the options
    rules.append('[data-testid="stWidgetLabel"] p{font-weight:600!important;color:#1F4D3A;}'
                 '[data-testid="stCheckbox"] [data-testid="stWidgetLabel"] p'
                 '{font-weight:400!important;color:inherit;}')
    # metric cards: labels wrap instead of being cut, values never end in "..."
    rules.append('[data-testid="stMetricLabel"] p,[data-testid="stMetricLabel"] div'
                 '{white-space:normal!important;overflow:visible!important;text-overflow:clip!important;}'
                 '[data-testid="stMetricValue"],[data-testid="stMetricValue"] div'
                 '{font-size:1.35rem;white-space:normal!important;overflow:visible!important;'
                 'text-overflow:clip!important;}'
                 '[data-testid="stMetricLabel"] p{font-size:0.8rem!important;}'
                 '[data-testid="stMetric"]{height:100%;padding:10px 14px!important;}')
    return "<style>" + "".join(rules) + "</style>"
