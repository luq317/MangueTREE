# -*- coding: utf-8 -*-
"""
i18n.py
=======
Minimal internationalisation core: JSON catalogs (``locales/<lang>.json``, flat
dotted keys) and a ``t()`` lookup with fallback English -> the key itself.

Works outside Streamlit (library use, tests): streamlit is imported lazily and
any failure falls back to ``DEFAULT``.
"""
import json
from functools import lru_cache
from types import MappingProxyType
from importlib import resources

LANGUAGES = {"en": "English", "pt": "Português"}
DEFAULT = "en"
SESSION_KEY = "lang"
CHOICE_KEY = "_lang"      # plain (non-widget) copy of the choice, survives page changes

# (lang, key) pairs that were requested but not found in that language's catalog.
MISSING: set = set()


@lru_cache(maxsize=None)
def catalog(lang):
    """Return the read-only catalog of ``lang`` (empty if the language has no file)."""
    try:
        path = resources.files("manguetree").joinpath("locales", f"{lang}.json")
        return MappingProxyType(json.loads(path.read_text(encoding="utf-8")))
    except (FileNotFoundError, OSError):
        return MappingProxyType({})


def get_lang():
    """Current UI language: session_state["lang"] inside Streamlit, else DEFAULT."""
    try:
        import streamlit as st
        # "lang" is the selector widget's key; Streamlit drops it on a page change (widget
        # ids include the page), so the last choice is also kept in a plain key.
        ss = st.session_state
        lang = ss.get(SESSION_KEY, ss.get(CHOICE_KEY, DEFAULT))
    except Exception:
        return DEFAULT
    return lang if lang in LANGUAGES else DEFAULT


def fmt_number(value, lang):
    """Floats as ``%g`` text (comma decimal separator in Portuguese)."""
    text = f"{value:g}"
    return text.replace(".", ",") if lang == "pt" else text


def t(key, lang=None, **params):
    """Translate ``key`` into ``lang`` (default: current language).

    Falls back to the English text, then to the key itself; missing entries are
    recorded in ``MISSING``. Float params are formatted per language.
    """
    lang = lang or get_lang()
    text = catalog(lang).get(key)
    if text is None:
        MISSING.add((lang, key))
        text = catalog(DEFAULT).get(key)
        if text is None:
            return key
    params = {k: fmt_number(v, lang) if isinstance(v, float) else v
              for k, v in params.items()}
    try:
        return text.format(**params)
    except (KeyError, IndexError, ValueError):
        return text


def language_selector(container):
    """Render the language selectbox in ``container``; return the chosen code.

    Call it first on EVERY page: the widget key is dropped on pages that do not render
    it, and its default is restored here from the plain ``_lang`` copy.
    """
    import streamlit as st
    codes = list(LANGUAGES)
    current = container.selectbox(
        t("app.language", get_lang()), codes, index=codes.index(get_lang()),
        format_func=LANGUAGES.get, key=SESSION_KEY)
    st.session_state[CHOICE_KEY] = current
    return current
