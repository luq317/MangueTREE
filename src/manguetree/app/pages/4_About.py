import streamlit as st

from manguetree import __version__, branding
from manguetree import charts as ui
from manguetree import i18n
from manguetree.i18n import t

st.set_page_config(layout="wide", page_title=t("about.page_title"))
LANG = i18n.language_selector(st.sidebar)        # first on every page (see i18n.py)
ui.quit_button(st.sidebar)

ui.topo(t("about.title"), t("about.subtitle"))

st.header(t("about.what_title"))
st.write(t("about.what"))
st.markdown(t("about.features"))

st.header(t("about.method_title"))
st.markdown(t("about.method"))

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
