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

st.set_page_config(layout="wide", page_title=t("single.page_title"), page_icon=ui.PAGE_ICON)
LANG = i18n.language_selector(st.sidebar)        # first on every page (see i18n.py)
ui.sidebar_nav(st.sidebar, tab_icons=("inicio", "estrutura", "fitossociologia", "classes_dap", "altura", "mapa", "verificacao", "exportar"))
ui.topo(t("single.title"), t("single.subtitle"))
st.markdown(t("single.intro"))

# ---------------- SIDEBAR ----------------
ui.icon_heading(st.sidebar, "configuracoes", t("sidebar.settings"))
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
ui.icon_heading(st.sidebar, "estilo", t("sidebar.style"))
paleta_nome = st.sidebar.selectbox(t("sidebar.palette"), list(ui.PALETAS), key="pal_unica",
                                    format_func=lambda c: ui.palette_label(c, LANG))
ui.use_palette(paleta_nome)
show_seal = ui.seal_checkbox(st.sidebar)
estilos = ui.style_controls(st.sidebar, "unica", paleta_nome, show_seal)
ui.icon_heading(st.sidebar, "exportar", t("export.batch_title"), 3)
_dpi_lote = st.sidebar.select_slider(t("export.batch_dpi"), (150, 300, 450, 600), value=300, key="dpi_lote_unica")
ui.batch_png_button(st.sidebar, _dpi_lote, "MangueTREE_unica_figuras.zip")



# ---------------- CARGA ----------------
if not uploaded:
    ui.icon_note(st, "enviar", t("single.upload_prompt"))
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
cond_faltante = st.session_state.get("mc_unica", "exclude")
issues_unica = {"": validate(df, RESOLVER, missing_condition=cond_faltante)}
ui.validation_banner(issues_unica, LANG)
res = mc.analyze(df, area_final, RESOLVER, dbh_limits=limites,
                 plot_name=plot_name,
                 class_width=largura_classe, missing_condition=cond_faltante)
r = res["summary"]

# ---------------- DASHBOARD ----------------
N = lambda value, decimals: ui.num(value, decimals, LANG)      # decimal comma in Portuguese
tabs_all = st.tabs([t("single.tab.panel"), t("single.tab.structure"), t("single.tab.phyto"), t("single.tab.classes"),
                t("single.tab.height"), t("single.tab.map"), t("tab.check"), t("single.tab.export")])
tab_panel, tabs = tabs_all[0], tabs_all[1:]

# --- PAINEL RESUMO ---
with tab_panel:
    from manguetree import dashboard as dash
    cp1, cp2, cp3 = st.columns([1, 1, 1])
    with cp1:
        tema = st.radio(t("dashboard.theme"), ("light", "dark"), horizontal=True, key="tema_painel",
                        format_func=lambda k: t(f"dashboard.theme.{k}"))
    with cp2:
        ano_p = st.text_input(t("dashboard.year"), "", key="ano_painel")
    with cp3:
        dpi_p = st.select_slider(t("dashboard.dpi"), (150, 200, 300, 450, 600), value=300, key="dpi_painel")
    partes = ([t("dashboard.data_of", year=ano_p.strip())] if ano_p.strip() else []) + [
        t("dashboard.subtitle", area=N(area_final, 0), n=r["n_species_live"])]
    sub_p = " · ".join(partes)
    cores_p = ui.species_colors(res["data"]["species_label"].unique())
    st.iframe('<body style="margin:0">' + dash.panel_html(res, tema, LANG, cores_p, sub_p) + "</body>",
              height=730)      # keeps the SVG figures and the hover values
    d1, d2 = st.columns(2)
    PANEL_PNG = dash.summary_panel(res, tema, LANG, cores_p, "png", min(dpi_p, 200), sub_p)   # also goes in the PDF
    d1.download_button(t("dashboard.png"), dash.summary_panel(res, tema, LANG, cores_p, "png", dpi_p, sub_p),
                       file_name=f"MangueTREE_painel_{plot_name}.png", mime="image/png", type="primary")
    d2.download_button(t("dashboard.pdf"), dash.summary_panel(res, tema, LANG, cores_p, "pdf", 300, sub_p),
                       file_name=f"MangueTREE_painel_{plot_name}.pdf", mime="application/pdf")

# --- TAB 1: ESTRUTURA ---
with tabs[0]:
    ui.report_section(t("single.tab.structure"))
    L = lambda k: ui.label(k, LANG)
    st.subheader(t("single.structural"))
    # order asked by the lab: DBH, mean height, canopy, live density, live basal area;
    # every card has the same size (the SD sits on the value line, not below it)
    UN = st.radio(t("units.label"), ("ha", "count"), horizontal=True, key="units_unica",
                  format_func=lambda k: t(f"units.{k}"))
    _dens_card = ((L("density_live_ha"), N(r["density_live_ha"], 0)) if UN == "ha"
                  else (L("n_live"), f"{r['n_live']}"))
    cards = ((L("mean_dbh_cm"), N(r["mean_dbh_cm"], 2)),
             (L("height_mean_m"), f"{N(r['height_mean_m'], 2)} ± {N(r['height_sd_m'], 2)}"),
             (L("canopy_height_m"), N(r["canopy_height_m"], 2)),
             _dens_card,
             (L("ba_live_ha"), N(r["ba_live_ha"], 2)),
             (L("ba_total_ha"), N(r["ba_total_ha"], 2)),
             (L("mortality_stems_pct"), N(r["mortality_stems_pct"], 1)),
             (L("mortality_ba_pct"), N(r["mortality_ba_pct"], 1)),
             (L("stems_per_tree"), N(r["stems_per_tree"], 2)),
             (L("complexity_2_5"), N(res["complexity"]["dbh_gt_2.5"]["ci"], 2)),
             (L("complexity_10"), N(res["complexity"]["dbh_gt_10"]["ci"], 2)),
             (L("n_species_live"), f"{r['n_species_live']}"))
    for linha in (cards[0:6], cards[6:12]):
        for col, (lab, val) in zip(st.columns(len(linha)), linha):
            col.metric(lab, val, border=True)
    st.caption(t("method.heights_live_only"))
    st.caption(t("method.mean_dbh"))

    st.divider()
    ui.show_jimenez(st, pd.DataFrame({"plot": [plot_name], "mean_dbh_cm": [r["mean_dbh_cm"]],
                                      "density_live_ha": [r["density_live_ha"]]}), estilos, "1_jim", LANG)

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
            (L("density_live_ha") if UN == "ha" else L("n_live")): len(sub[sub["live"]]) * (ft if UN == "ha" else 1),
            (L("density_dead_ha") if UN == "ha" else L("n_dead")): len(sub[~sub["live"]]) * (ft if UN == "ha" else 1),
            L("ba_live_ha"): sub[sub["live"]]["basal_area_m2"].sum() * ft,
            L("ba_dead_ha"): sub[~sub["live"]]["basal_area_m2"].sum() * ft,
        })
    if resumo_gen:
        tg = pd.DataFrame(resumo_gen).set_index(L("genus"))
        # contribution (%) of each genus next to each value
        cols = []
        for c_ in list(tg.columns):
            tot = tg[c_].sum()
            tg[c_ + " (%)"] = 100 * tg[c_] / tot if tot > 0 else 0.0
            cols += [c_, c_ + " (%)"]
        tg = tg[cols]
        st.dataframe(tg.style.format(lambda v: N(v, 2)), width="stretch")

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
    ui.report_section(t("single.tab.phyto"))
    st.subheader(t("single.phyto_table"))
    ivi = res["importance"]
    if ivi is not None and not ivi.empty:
        st.dataframe(ui.for_display(ivi, lang=LANG).style.format(precision=2),
                     width="stretch")
        if "ivi" not in ivi.columns:
            st.caption(t("method.ivi_needs_units"))
        st.markdown(t("phyto.legend"))
        pct_f = st.checkbox(t("single.as_pct"), value=False, key="pct_fito")
        fig = ui.fig_phyto_100(ivi, estilos, LANG) if pct_f else ui.fig_ivi(ivi, estilos, LANG)
        if fig:
            ui.show(st, fig, "1_1", estilos)
    st.divider()
    st.subheader(t("single.ba_composition"))
    tipo = st.radio(t("single.chart_type"), ("pie", "treemap"), horizontal=True, key="tipo_ba_unica",
                    format_func=lambda k: t(f"single.chart_type.{k}", LANG))
    fig_c = ui.fig_composicao_ba(res, estilos, tipo, LANG)
    if fig_c:
        ui.show(st, fig_c, "1_2", estilos)

# --- TAB 3: CLASSES DE DAP ---
with tabs[2]:
    ui.report_section(t("single.tab.classes"))
    st.subheader(t("single.dbh_distribution"))
    st.caption(t("method.dbh_classes"))
    metrica = st.radio(t("single.metric"), ("density", "basal_area"), horizontal=True, key="metrica_unica",
                       format_func=lambda k: t(f"metric.{k}", LANG))
    pct_c = st.checkbox(t("single.as_pct"), value=False, key="pct_classes")
    UN_c = st.radio(t("units.label"), ("ha", "count"), horizontal=True, key="units_classes",
                    format_func=lambda k: t(f"units.{k}")) if metrica == "density" and not pct_c else "ha"
    dens_cl = res["dbh_density"] if UN_c == "ha" else res["dbh_density"] * (area_final / 10000.0)
    fig_cl = ui.fig_classes_dap(dens_cl, res["dbh_ba"], estilos, metrica, LANG, pct=pct_c)
    if fig_cl is not None and UN_c == "count":
        fig_cl.update_layout(yaxis_title=ui.label("n_live", LANG))
    if fig_cl:
        ui.show(st, fig_cl, "1_3", estilos)
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
        ui.show(st, fig_h, "1_4", estilos)

    st.divider()
    st.subheader(t("single.diameter_q"))
    dist = res["diameter_dist"]
    info = res["diameter_info"]
    fig_j = ui.fig_distribuicao_diametrica(dist, estilos, LANG)
    if fig_j is not None:
        ui.show(st, fig_j, "1_5", estilos)
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
    ui.report_section(t("single.tab.height"))
    st.subheader(t("single.height_dbh"))
    esp_disp = [s_ for s_ in res["data"].loc[res["data"]["live"], "species_label"].dropna().unique()]
    esp_sel = st.multiselect(t("single.regression_species"), esp_disp, default=esp_disp,
                             key="esp_regressao", format_func=lambda v: ui.species_name(v, LANG))
    fig_s, det = ui.fig_altura_dap(res, estilos, LANG, species=esp_sel)
    if fig_s:
        cg_, cd_ = st.columns([3, 2])
        ui.show(cg_, fig_s, "1_6", estilos)
        if det:
            with cd_:
                st.markdown("**" + t("single.regression_details") + "**")
                st.dataframe(pd.DataFrame(det), width="stretch", hide_index=True)
    else:
        st.warning(t("single.not_enough_height"))
    st.divider()
    st.subheader(t("single.vertical_profile"))
    cpk, cpw = st.columns([3, 1])
    with cpk:
        kind = st.radio(t("single.profile_kind"), ui.PROFILE_KINDS, horizontal=True, key="perfil_tipo",
                        format_func=lambda k: t(f"single.profile.{k}"))
    with cpw:
        largura_h = st.number_input(t("single.strata_width"), min_value=0.25, value=1.0, step=0.25,
                                    key="perfil_largura") if kind == "strata" else 1.0
    fig_p = ui.fig_perfil_vertical(res, estilos, LANG, kind=kind, strata_width=largura_h)
    if fig_p:
        ui.show(st, fig_p, "1_7", estilos)
    else:
        st.info(t("single.no_profile"))

# --- TAB 5: MAPA ---
d0 = res["data"]
with tabs[4]:
    st.subheader(t("single.location"))
    mp = d0[["lat", "lon"]].dropna() if {"lat", "lon"} <= set(d0.columns) else None
    if mp is not None and not mp.empty:
        ui.location_map(st, mp.assign(plot=str(res["plot_name"])), LANG)
    else:
        st.info(t("map.no_coordinates"))

# --- TAB 6: VERIFICAÇÃO DOS DADOS ---
with tabs[5]:
    ui.validation_panel(issues_unica, key="mc_unica", lang=LANG)

# --- TAB 7: EXPORTAÇÃO ---
with tabs[6]:
    st.subheader(t("single.export"))
    nome = res["plot_name"]
    # PDF report: prepared on click, with the charts as they are on screen
    sig = ("unica", getattr(uploaded, "file_id", uploaded.name), sheet, nome,
           round(area_final, 2), limites, largura_classe,
           ui.settings_signature(), cond_faltante, LANG, show_seal)
    from manguetree import report as rep
    _coords = mp.drop_duplicates().assign(plot=nome) if mp is not None and not mp.empty else None
    c1, c2, c3 = st.columns(3)
    with c1:
        ui.pdf_block(st, "unica", lambda figs: rep.single_plot_report(
            res, lang=LANG, seal=show_seal, figures=figs, panel_png=PANEL_PNG, coords=_coords),
            f"MangueTREE_{nome}.pdf", sig)
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
