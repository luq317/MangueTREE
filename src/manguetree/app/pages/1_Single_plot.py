# -*- coding: utf-8 -*-
"""
Single plot analysis (MangueTREE): structural and phytosociological parameters of
one plot. All visible text comes from the catalogs (manguetree/locales).
"""
import streamlit as st
import pandas as pd

from manguetree import calc as mc
from manguetree import charts as ui
from manguetree import io as mio
from manguetree import i18n
from manguetree.i18n import t
from manguetree.validation import validate

st.set_page_config(layout="wide", page_title=t("single.page_title"), page_icon="📊")
LANG = i18n.language_selector(st.sidebar)        # first on every page (see i18n.py)
ui.sidebar_nav(st.sidebar)
ui.topo(t("single.title"), t("single.subtitle"))
st.markdown(t("single.intro"))

# ---------------- SIDEBAR ----------------
st.sidebar.header(t("sidebar.settings"))
uploaded = st.sidebar.file_uploader(t("single.upload"),
                                    type=["xlsx", "csv", "txt"], key="upload_unico")
# A workbook can hold several plots (one per sheet): the user picks the sheet.
sheet, sheet_count = 0, 1
if uploaded and uploaded.name.lower().endswith(".xlsx"):
    try:
        sheet_names = ui.sheet_names(uploaded)
    except Exception as e:
        st.error(t("single.read_error", error=str(e)))
        st.stop()
    sheet_count = len(sheet_names)
    if sheet_count > 1:
        sheet = st.sidebar.selectbox(t("single.sheet"), sheet_names,
                                     key=f"sheet_unica_{uploaded.name}_{uploaded.size}")
RESOLVER = ui.sidebar_species_settings(st.sidebar)
delimiter = st.sidebar.text_input(t("single.delimiter"), ";", key="delim_unico")
DEFAULT_AREA = 100.0
area_parcela = st.sidebar.number_input(t("single.plot_area"), min_value=1.0,
                                       value=DEFAULT_AREA, step=10.0, key="area_unica")
# only text files need it: a workbook carries its own plot area (or is flagged by the check)
area_confirmed = False
if uploaded and uploaded.name.lower().endswith((".csv", ".txt")):
    area_confirmed = st.sidebar.checkbox(t("single.area_confirm"), key="area_ok_unica",
                                         help=t("single.area_confirm_help"))
cell_area = st.sidebar.text_input(t("single.area_cell"), "", key="cell_unica",
                                  help=t("single.area_cell_help"))
st.sidebar.divider()
st.sidebar.subheader(t("sidebar.dbh_classes"))
c1 = st.sidebar.number_input(t("sidebar.cutoff1"), value=2.5, step=0.5, key="cut1_unica")
c2 = st.sidebar.number_input(t("sidebar.cutoff2"), value=10.0, step=1.0, key="cut2_unica")
limites = tuple(sorted([c1, c2]))
if limites[0] >= limites[1]:
    st.sidebar.error(t("sidebar.cutoffs_equal"))
    st.stop()

st.sidebar.divider()
largura_classe = st.sidebar.number_input(t("single.class_width"),
                                          min_value=1.0, value=5.0, step=1.0, key="width_unica")

st.sidebar.divider()
st.sidebar.header(t("sidebar.style"))
paleta_nome = st.sidebar.selectbox(t("sidebar.palette"), list(ui.PALETAS), key="pal_unica",
                                    format_func=lambda c: ui.palette_label(c, LANG))
tam_titulo = st.sidebar.slider(t("sidebar.title_font"), 10, 24, 14, key="tit_unica")
tam_eixos = st.sidebar.slider(t("sidebar.axis_font"), 8, 20, 11, key="eix_unica")
show_seal = ui.seal_checkbox(st.sidebar)
estilos = {"paleta": ui.PALETAS[paleta_nome], "tamanho_titulo": tam_titulo,
           "tamanho_eixos": tam_eixos, "seal": show_seal}


# ---------------- CARGA ----------------
if not uploaded:
    st.info(t("single.upload_prompt"))
    st.stop()

area_final = area_parcela
try:
    if uploaded.name.lower().endswith((".csv", ".txt")):
        df = mio.load_csv(uploaded, delimiter)
        # A text file has no plot area: the sidebar value is used, and the data check
        # warns until the user changes it from the default.
        df.attrs["area_value"] = float(area_parcela)
        if float(area_parcela) != DEFAULT_AREA or area_confirmed:
            df.attrs["area_source"] = "user"
    else:
        df, area_enc = mio.load_excel_sheet(uploaded, sheet, cell_area, area_parcela)
        if area_enc:
            area_final = area_enc
except Exception as e:
    st.error(t("single.read_error", error=str(e)))
    st.stop()

if not mio.has_required_columns(df):
    st.error(t("single.missing_columns"))
    st.stop()

if df.empty:
    st.error(t("single.no_rows"))
    st.stop()

# Linhas sem DAP seguem para a validação (o cálculo ignora DAP ausente ou <= 0).
n_validos = int((df["dbh"] > 0).sum())
st.success(t("single.processed", n=n_validos, rows=len(df), area=float(area_final)))
plot_name = str(sheet) if sheet_count > 1 else uploaded.name.rsplit(".", 1)[0]
st.caption(t("single.plot_label", name=plot_name))
# the panel validates with the same choice for stems without condition as the analysis
cond_faltante = ui.validation_panel(
    {"": validate(df, RESOLVER, missing_condition=st.session_state.get("mc_unica", "exclude"))},
    key="mc_unica", lang=LANG)
res = mc.analyze(df, area_final, RESOLVER, dbh_limits=limites,
                 plot_name=plot_name,
                 class_width=largura_classe, missing_condition=cond_faltante)
r = res["summary"]

# ---------------- DASHBOARD ----------------
N = lambda value, decimals: ui.num(value, decimals, LANG)      # decimal comma in Portuguese
tabs = st.tabs([t("single.tab.structure"), t("single.tab.phyto"), t("single.tab.classes"),
                t("single.tab.height"), t("single.tab.map"), t("single.tab.export")])

# --- TAB 1: ESTRUTURA ---
with tabs[0]:
    L = lambda k: ui.label(k, LANG)
    st.subheader(t("single.structural"))
    a, b, c, d = st.columns(4)
    a.metric(L("mean_dbh_cm"), N(r["mean_dbh_cm"], 2))
    a.metric(L("n_species_live"), f"{r['n_species_live']}")
    b.metric(L("height_mean_m"), N(r["height_mean_m"], 2), f"± {N(r['height_sd_m'], 2)}")
    b.metric(L("canopy_height_m"), N(r["canopy_height_m"], 2))
    c.metric(L("density_live_ha"), N(r["density_live_ha"], 0))
    c.metric(L("stems_per_tree"), N(r["stems_per_tree"], 2))
    d.metric(L("ba_live_ha"), N(r["ba_live_ha"], 2))
    d.metric(L("complexity_2_5"), N(res["complexity"]["dbh_gt_2.5"]["ci"], 2))
    d.metric(L("complexity_10"), N(res["complexity"]["dbh_gt_10"]["ci"], 2))
    st.caption(t("method.heights_live_only"))
    st.caption(t("method.mean_dbh"))

    st.divider()
    e, f, g = st.columns(3)
    e.metric(L("ba_total_ha"), N(r["ba_total_ha"], 2))
    f.metric(L("mortality_stems_pct"), N(r["mortality_stems_pct"], 1))
    g.metric(L("mortality_ba_pct"), N(r["mortality_ba_pct"], 1))

    st.divider()
    st.subheader(t("single.by_genus"))
    col_g, col_der = st.columns(2)
    d0 = res["data"]
    d0 = d0[d0["dbh"].notna() & (d0["dbh"] > 0)]
    ft = mc._ft(area_final)
    resumo_gen = []
    # genera come from the species table (via the resolver), in order of appearance
    for gen in d0["genus"].dropna().unique():
        sub = d0[d0["genus"] == gen]
        if sub.empty:
            continue
        resumo_gen.append({
            L("genus"): gen,
            L("density_live_ha"): len(sub[sub["live"]]) * ft,
            L("density_dead_ha"): len(sub[~sub["live"]]) * ft,
            L("ba_live_ha"): sub[sub["live"]]["basal_area_m2"].sum() * ft,
            L("ba_dead_ha"): sub[~sub["live"]]["basal_area_m2"].sum() * ft,
        })
    if resumo_gen:
        st.dataframe(pd.DataFrame(resumo_gen).set_index(L("genus"))
                     .style.format("{:.2f}"), width="stretch")

    with st.expander(t("method.holdridge_title")):
        st.write(t("method.holdridge"))
        cx1, cx2 = st.columns(2)
        for col, key, lab in ((cx1, "dbh_gt_2.5", "complexity_2_5"),
                              (cx2, "dbh_gt_10", "complexity_10")):
            with col:
                st.caption(L(lab))
                cx = res["complexity"][key]
                st.table(pd.DataFrame({
                    t("home.col.column"): [t(f"complexity.{k}") for k in cx],
                    t("labels.value"): [round(v, 3) if isinstance(v, float) else v
                                        for v in cx.values()]}).set_index(t("home.col.column")))

# --- TAB 2: FITOSSOCIOLOGIA ---
with tabs[1]:
    st.subheader(t("single.phyto_table"))
    ivi = res["importance"]
    if ivi is not None and not ivi.empty:
        st.dataframe(ui.for_display(ivi, lang=LANG).style.format(precision=2),
                     width="stretch")
        if "ivi" not in ivi.columns:
            st.caption(t("method.ivi_needs_units"))
        fig = ui.fig_ivi(ivi, estilos, LANG)
        if fig:
            st.plotly_chart(fig, width="stretch", config=ui.PLOT_CONFIG)
    st.divider()
    st.subheader(t("single.ba_composition"))
    tipo = st.radio(t("single.chart_type"), ("pie", "treemap"), horizontal=True, key="tipo_ba_unica",
                    format_func=lambda k: t(f"single.chart_type.{k}", LANG))
    fig_c = ui.fig_composicao_ba(res, estilos, tipo, LANG)
    if fig_c:
        st.plotly_chart(fig_c, width="stretch", config=ui.PLOT_CONFIG)

# --- TAB 3: CLASSES DE DAP ---
with tabs[2]:
    st.subheader(t("single.dbh_distribution"))
    st.caption(t("method.dbh_classes"))
    metrica = st.radio(t("single.metric"), ("density", "basal_area"), horizontal=True, key="metrica_unica",
                       format_func=lambda k: t(f"metric.{k}", LANG))
    fig_cl = ui.fig_classes_dap(res["dbh_density"], res["dbh_ba"], estilos, metrica, LANG)
    if fig_cl:
        st.plotly_chart(fig_cl, width="stretch", config=ui.PLOT_CONFIG)
    c1_, c2_ = st.columns(2)
    with c1_:
        st.caption(ui.label("density_ha", LANG))
        st.dataframe(ui.for_display(res["dbh_density"], lang=LANG).style.format("{:.1f}"),
                     width="stretch")
    with c2_:
        st.caption(ui.label("ba_ha", LANG))
        st.dataframe(ui.for_display(res["dbh_ba"], lang=LANG).style.format("{:.3f}"),
                     width="stretch")
    st.divider()
    fig_h = ui.fig_hist_dap(res, estilos, LANG)
    if fig_h:
        st.plotly_chart(fig_h, width="stretch", config=ui.PLOT_CONFIG)

    st.divider()
    st.subheader(t("single.diameter_q"))
    dist = res["diameter_dist"]
    info = res["diameter_info"]
    fig_j = ui.fig_distribuicao_diametrica(dist, estilos, LANG)
    if fig_j is not None:
        st.plotly_chart(fig_j, width="stretch", config=ui.PLOT_CONFIG)
        cq1, cq2 = st.columns([2, 1])
        with cq1:
            st.dataframe(ui.for_display(dist, lang=LANG).style.format({
                         ui.label("midpoint_cm", LANG): "{:.1f}",
                         ui.label("density_ha", LANG): "{:.0f}",
                         ui.label("q", LANG): "{:.2f}"}, na_rep="-"),
                         width="stretch")
        with cq2:
            if info.get("q_mean") is not None:
                st.metric(t("single.q_mean"), N(info["q_mean"], 2))
            st.caption(t("method.q_note"))
    else:
        st.info(t("single.no_live_for_dist"))

# --- TAB 4: ALTURA & PERFIL ---
with tabs[3]:
    st.subheader(t("single.height_dbh"))
    fig_s, det = ui.fig_altura_dap(res, estilos, LANG)
    if fig_s:
        st.plotly_chart(fig_s, width="stretch", config=ui.PLOT_CONFIG)
        if det:
            with st.expander(t("single.regression_details")):
                st.dataframe(pd.DataFrame(det), width="stretch")
    else:
        st.warning(t("single.not_enough_height"))
    st.divider()
    st.subheader(t("single.vertical_profile"))
    fig_p = ui.fig_perfil_vertical(res, estilos, LANG)
    if fig_p:
        st.plotly_chart(fig_p, width="stretch", config=ui.PLOT_CONFIG)
    else:
        st.info(t("single.no_profile"))

# --- TAB 5: MAPA ---
d0 = res["data"]
with tabs[4]:
    st.subheader(t("single.location"))
    mp = d0[["lat", "lon"]].dropna() if {"lat", "lon"} <= set(d0.columns) else None
    if mp is not None and not mp.empty:
        st.map(mp)
    else:
        st.info(t("map.no_coordinates"))

# --- TAB 6: EXPORTAÇÃO ---
with tabs[5]:
    st.subheader(t("single.export"))
    nome = res["plot_name"]
    # Relatório PDF gerado uma vez por configuração (download em 1 clique)
    sig = ("unica", getattr(uploaded, "file_id", uploaded.name), sheet, nome,
           round(area_final, 2), limites, largura_classe,
           ui.settings_signature(), cond_faltante, LANG, show_seal)
    if st.session_state.get("pdf_sig_unica") != sig:
        with st.spinner(t("export.preparing_pdf")):
            try:
                from manguetree import report as rep
                st.session_state["pdf_unica"] = rep.single_plot_report(res, lang=LANG, seal=show_seal)
                st.session_state["pdf_sig_unica"] = sig
            except Exception as e:
                st.session_state["pdf_unica"] = None
                st.warning(t("export.pdf_unavailable", error=str(e)))
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.session_state.get("pdf_unica"):
            st.download_button(t("export.pdf"), data=st.session_state["pdf_unica"],
                               file_name=f"MangueTREE_{nome}.pdf", mime="application/pdf",
                               type="primary")
    with c2:
        st.download_button(t("export.excel"), data=ui.to_excel_bytes(res, LANG),
                           file_name=f"MangueTREE_{nome}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with c3:
        st.download_button(t("export.by_species_csv"),
                           data=ui.tabela_por_especie(res, LANG).to_csv(index=False).encode("utf-8"),
                           file_name=f"{t('file.by_species')}_{nome}.csv", mime="text/csv")
    st.caption(t("export.single_note"))
    st.divider()
    st.subheader(t("single.loaded_data"))
    st.dataframe(ui.for_display(d0, data_table=True, lang=LANG), width="stretch")
