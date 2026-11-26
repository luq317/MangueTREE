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
"""File names for everything the app lets the user save (figures, tables, reports, ZIPs).

Pattern: ``<plot>[_<year>]_<what>.<ext>`` with no accents and no spaces, e.g.
``H2_Altura-e-perfil.png``. The first part (the "prefix") is set by each page once the plot is
known and kept in the session, so every download button of that page uses it."""
import re
import unicodedata

_KEY = "_nome_prefixo"


def slug(texto, max_len=60):
    """Text as a file-name piece: no accents, no HTML, letters and digits joined by hyphens."""
    s = unicodedata.normalize("NFD", str(texto))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")
    return s[:max_len].strip("-")


def lista_parcelas(parcelas, lang="pt", maximo=4):
    """"F2-H2-J2" for a few plots; "7-parcelas" / "7-plots" when the list would be long."""
    nomes = [slug(p, 20) for p in dict.fromkeys(map(str, parcelas)) if slug(p, 20)]
    if len(nomes) <= maximo:
        return "-".join(nomes)
    return f"{len(nomes)}-{'parcelas' if lang == 'pt' else 'plots'}"


def definir(*partes):
    """Sets the prefix of this session (empty pieces are skipped)."""
    import streamlit as st
    st.session_state[_KEY] = "_".join(p for p in (slug(x, 40) for x in partes if x not in (None, "")) if p)


def prefixo():
    try:
        import streamlit as st
        return st.session_state.get(_KEY, "")
    except Exception:
        return ""


def arquivo(*partes):
    """Base name (no extension): prefix + the given pieces, e.g. arquivo("Painel resumo") -> "H2_Painel-resumo"."""
    p = [prefixo()] + [slug(x) for x in partes]
    return "_".join(x for x in p if x) or "MangueTREE"
