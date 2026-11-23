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
import pandas as pd
import streamlit as st

from manguetree import __version__, branding
from manguetree import charts as ui
from manguetree import i18n
from manguetree.i18n import t
from manguetree.species import load_species_table

st.set_page_config(page_title=t("home.page_title"), page_icon=ui.PAGE_ICON, layout="wide")
LANG = i18n.language_selector(st.sidebar)        # first on every page (see i18n.py)
ui.sidebar_nav(st.sidebar)
ui.quit_button(st.sidebar)

ui.topo(t("home.title"), t("home.subtitle"))
st.markdown(t("home.description"))
st.caption(t("home.facts", version=__version__, url=branding.REPO_URL))

st.subheader(t("home.analyses_title"))
cards = (("single", "pages/1_Single_plot.py"), ("multiple", "pages/2_Multiple_plots.py"),
         ("temporal", "pages/3_Temporal.py"))
for col, (key, page) in zip(st.columns(3), cards):
    with col.container(border=True):
        st.markdown(f"**{t(f'home.page.{key}')}**")
        st.write(t(f"home.page.{key}_desc"))
        st.page_link(page, label=t("home.open_page") + " →")

left, right = st.columns([3, 2], gap="large")
with left:
    st.subheader(t("home.computes_title"))
    st.markdown(t("home.computes"))
with right:
    st.subheader(t("home.basis_title"))
    st.markdown(t("about.method") + "\n" + t("about.method_extra"))
    st.caption(t("home.more_about"))

with st.expander(t("home.format_title")):
    st.markdown(t("home.format_intro"))
    columns = ["tree_id", "n_stems", "species", "dbh_cm", "height_m", "condition",
               "latitude", "longitude", "note"]
    st.table(pd.DataFrame({
        t("home.col.column"): columns,
        t("home.col.description"): [t(f"home.field.{c}") for c in columns],
        t("home.col.unit"): [t(f"home.unit.{c}") for c in columns],
    }))
    st.markdown(t("home.format_pt_headers"))

    st.markdown("#### " + t("home.species_title"))
    st.write(t("home.species_intro"))
    table = load_species_table()
    st.table(pd.DataFrame({
        t("home.col.code"): table["code"],
        t("home.col.species"): table["scientific_name"],
        t("home.col.genus"): table["genus"],
        t("home.col.type"): table["true_mangrove"].map(
            lambda v: t("home.type.true") if str(v).strip().lower() == "true"
            else t("home.type.associate")),
    }))
    st.caption(t("home.species_note"))

st.markdown("---")
ui.icon_heading(st, "relatorio", t("template.title"), 3)
st.write(t("template.intro"))
from manguetree import template as tpl
tl_lang = st.radio(t("template.lang"), ("pt", "en"), horizontal=True, key="tpl_lang",
                   index=0 if LANG == "pt" else 1,
                   format_func=lambda c: f"{i18n.FLAGS[c]} {i18n.LANGUAGES[c]}")
ct1, ct2 = st.columns(2)
ct1.download_button(t("template.excel"), tpl.excel_bytes(tl_lang),
                    file_name=f"MangueTREE_{'modelo' if tl_lang == 'pt' else 'template'}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
ct2.download_button(t("template.csv"), tpl.csv_bytes(tl_lang),
                    file_name=f"MangueTREE_{'modelo' if tl_lang == 'pt' else 'template'}.csv", mime="text/csv")

st.markdown("---")
st.subheader(t("home.examples_title"))
st.markdown(t("home.examples", repo=branding.REPO_URL))

st.subheader(t("home.cite_title"))
st.code(branding.CITATION, language=None)
st.caption(t("about.cite_note"))
