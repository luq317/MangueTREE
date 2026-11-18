# -*- coding: utf-8 -*-
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
             "2_Multiple_plots": "multiplas", "3_Temporal": "temporal", "4_About": "sobre"}


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


def css(tab_icons=()):
    """CSS that places the nav icons and, by position, the icons of the page's tabs."""
    nav = '[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]'
    rules = [_before(f'{nav}[href="{"" if k == "Home" else k.split("_", 1)[1]}"]', v)
             for k, v in NAV_ICONS.items()]
    rules += [_before(f'[role="tablist"] [data-testid="stTab"][data-key="{i}"] p', name)
              for i, name in enumerate(tab_icons) if name]
    rules.append('[data-testid="stTab"] p{display:flex;align-items:center;}')
    return "<style>" + "".join(rules) + "</style>"
