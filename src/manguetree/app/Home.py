import pandas as pd
import streamlit as st

from manguetree import __version__, branding
from manguetree import charts as ui
from manguetree import i18n
from manguetree.i18n import t
from manguetree.species import load_species_table

st.set_page_config(page_title=t("home.page_title"), page_icon="🌳", layout="wide")
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
        st.page_link(page, label=t("home.open_page"), icon="➡️")

left, right = st.columns([3, 2], gap="large")
with left:
    st.subheader(t("home.computes_title"))
    st.markdown(t("home.computes"))
with right:
    st.subheader(t("home.basis_title"))
    st.markdown(t("about.method"))
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
st.subheader(t("home.examples_title"))
st.markdown(t("home.examples", repo=branding.REPO_URL))

st.subheader(t("home.cite_title"))
st.code(branding.CITATION, language=None)
st.caption(t("about.cite_note"))
