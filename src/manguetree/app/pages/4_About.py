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
import streamlit as st

from manguetree import __version__, branding
from manguetree import charts as ui
from manguetree import i18n
from manguetree.i18n import t

st.set_page_config(layout="wide", page_title=t("about.page_title"))
LANG = i18n.language_selector(st.sidebar)        # first on every page (see i18n.py)
ui.sidebar_nav(st.sidebar)
ui.quit_button(st.sidebar)

ui.topo(t("about.title"), t("about.subtitle"))

st.header(t("about.what_title"))
st.write(t("about.what"))
st.markdown(t("about.features"))

st.header(t("about.method_title"))
st.markdown(t("about.method") + "\n" + t("about.method_extra"))

st.header(t("about.authors_title"))
st.markdown("\n".join(f"- {a}" for a in ("Lucas Silva Pereira", "Laiza Lacerda Motta", "Tatiane Costa da Matta",
                                         "Filipe de Oliveira Chaves",
                                         "Mário Luiz Gomes Soares")))
st.write(t("about.affiliation"))
st.markdown(t("about.contact", email=branding.EMAIL))

st.header(t("about.cite_title"))
st.write(t("about.cite_intro"))
st.code(branding.CITATION, language=None)
st.caption(t("about.cite_note"))

st.header(t("about.license_title"))
st.write(t("about.license", version=__version__))
st.markdown(t("about.repository", url=branding.REPO_URL))
