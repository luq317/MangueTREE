# -*- coding: utf-8 -*-
"""
Multiple plots analysis (MangueTREE): SPATIAL comparison between plots (one sheet per
plot). For change over the years use the Temporal page. Results in session_state use
language independent keys and internal column names; text comes from the catalogs.
"""
import re
import io
import pandas as pd
import streamlit as st

from manguetree import calc as mc
from manguetree import charts as ui
from manguetree import io as mio
from manguetree import i18n
from manguetree.i18n import t

st.set_page_config(layout="wide", page_title=t("multi.page_title"), page_icon=ui.PAGE_ICON)
LANG = i18n.language_selector(st.sidebar)        # first on every page (see i18n.py)
ui.sidebar_nav(st.sidebar, tab_icons=("evolucao", "especies", "fitossociologia", "mapa", "verificacao", "exportar"))
ui.topo(t("multi.title"), t("multi.subtitle"))
st.markdown(t("multi.intro"))
st.caption(t("multi.see_temporal"))

ui.icon_heading(st.sidebar, "configuracoes", t("sidebar.settings"))
uploaded = st.sidebar.file_uploader(t("sidebar.excel_file"), type=["xlsx"], key="upload_multi")
RESOLVER = ui.sidebar_species_settings(st.sidebar)

if not uploaded:
    ui.icon_note(st, "enviar", t("multi.upload_prompt"))
    st.stop()

try:
    abas = ui.sheet_names(uploaded)
except Exception as e:
    st.error(t("sidebar.excel_error", error=str(e)))
    st.stop()

# Results belong to the file they were computed from: a new upload clears them.
_fid = getattr(uploaded, "file_id", uploaded.name)
if st.session_state.get("multi_file") != _fid:
    for _k in ('multi_resultados', 'multi_sig', 'multi_issues', 'multi_ignoradas', 'pdf_multi', 'pdf_sig_multi', 'pdfx_multi'):
        st.session_state.pop(_k, None)
    st.session_state["multi_file"] = _fid

# --- Fora do formulário: a paleta re-estiliza ao vivo ---
ui.icon_heading(st.sidebar, "estilo", t("sidebar.style_sub"), 3)
paleta_nome = st.sidebar.selectbox(t("sidebar.palette"), list(ui.PALETAS), key="pal_multi",
                                    format_func=lambda c: ui.palette_label(c, LANG))
ui.use_palette(paleta_nome)
show_seal = ui.seal_checkbox(st.sidebar)
estilos = ui.style_controls(st.sidebar, "multi", paleta_nome, show_seal)
ui.icon_heading(st.sidebar, "exportar", t("export.batch_title"), 3)
_dpi_lote = st.sidebar.select_slider(t("export.batch_dpi"), (150, 300, 450, 600), value=300, key="dpi_lote_multi")
ui.batch_png_button(st.sidebar, _dpi_lote, "MangueTREE_multi_figuras.zip")


# --- Formulário: preencha tudo e clique UMA vez (sem apertar Enter em cada campo) ---
with st.sidebar.form("cfg_multi"):
    st.caption(t("sidebar.form_hint"))
    cell_area = st.text_input(t("sidebar.area_cell_sheets"), "", key="cell_multi")
    area_padrao = st.number_input(t("sidebar.default_area"), min_value=1.0,
                                  value=100.0, step=10.0, key="area_multi")
    cc1, cc2 = st.columns(2)
    with cc1:
        c1 = st.number_input(t("sidebar.dbh_class1"), value=2.5, step=0.5, key="cut1_multi")
    with cc2:
        c2 = st.number_input(t("sidebar.dbh_class2"), value=10.0, step=1.0, key="cut2_multi")
    selecionadas = st.multiselect(t("multi.plots_to_analyse"), options=abas, default=abas,
                                  key=f"sheets_multi_{uploaded.name}_{uploaded.size}")
    submitted = st.form_submit_button(t("multi.run"), type="primary")
limites = tuple(sorted([c1, c2]))
if limites[0] >= limites[1]:
    st.sidebar.error(t("sidebar.cutoffs_equal"))
    st.stop()

# Processa SÓ ao clicar em Executar (ou quando região, tabela de espécies ou a escolha
# para troncos sem condição mudam); guarda em session_state para que os seletores
# dos gráficos atualizem ao vivo sem precisar reexecutar.
cond_faltante = st.session_state.get("mc_multi", "exclude")
cfg_sig = (ui.settings_signature(), cond_faltante)
if submitted or (st.session_state.get("multi_resultados")
                 and st.session_state.get("multi_sig") != cfg_sig):
    resultados = []
    ignoradas = {}
    problemas = {}
    with st.spinner(t("multi.processing", n=len(selecionadas))):
        for aba in selecionadas:
            df, area = mio.load_excel_sheet(uploaded, aba, cell_area, area_padrao)
            if df is None or not mio.has_required_columns(df):
                ignoradas[aba] = "no_columns"
                continue
            if df.empty:
                ignoradas[aba] = "no_data"
                continue
            res = mc.analyze(df, area, RESOLVER, dbh_limits=limites, plot_name=aba,
                             missing_condition=cond_faltante)
            if res["summary"]["n_stems"] == 0:
                ignoradas[aba] = "no_stems"
                continue
            resultados.append(res)
            problemas[aba] = res["issues"]
    st.session_state["multi_sig"] = cfg_sig
    st.session_state["multi_issues"] = problemas
    st.session_state["multi_resultados"] = resultados
    st.session_state["multi_ignoradas"] = ignoradas

resultados = st.session_state.get("multi_resultados")
if not resultados:
    st.info(t("multi.select_prompt"))
    st.stop()
ignoradas = st.session_state.get("multi_ignoradas", {})

st.success(t("multi.processed", n=len(resultados)))
if ignoradas:
    st.caption(t("sheets.ignored") + " " + ", ".join(
        f"{a} ({t('sheets.reason.' + m)})" for a, m in ignoradas.items()))
problemas = st.session_state.get("multi_issues", {})
SHEET = t("labels.sheet")
ui.validation_banner(problemas, LANG)
df_problemas = ui.issues_frame_by_unit(problemas, SHEET, LANG)

# ---------------- TABELA COMPARATIVA ----------------
share_base = st.session_state.get("multi_share_base", "density")
especies_todas = sorted({sp for res in resultados for (sp, _c) in ui.species_shares(res, share_base)},
                        key=lambda s: (s == mc.UNIDENTIFIED_LABEL, s))
linhas = []
for res in resultados:
    r = res["summary"]
    linha = {       # order asked by the lab; number of species last
        "plot": res["plot_name"],
        "plot_area_m2": r["plot_area_m2"],
        "mean_dbh_cm": r["mean_dbh_cm"],
        "height_mean_m": r["height_mean_m"],
        "height_sd_m": r["height_sd_m"],
        "canopy_height_m": r["canopy_height_m"],
        "density_live_ha": r["density_live_ha"],
        "n_live": r["n_live"],
        "ba_live_ha": r["ba_live_ha"],
    }
    shares = ui.species_shares(res, share_base)
    for cond in ("live", "dead"):
        for sp in especies_todas:
            linha[ui.share_column(sp, cond, share_base, LANG)] = shares.get((sp, cond), 0.0)
    linha.update({
        "mortality_stems_pct": r["mortality_stems_pct"],
        "complexity_2_5": res["complexity"]["dbh_gt_2.5"]["ci"],
        "complexity_10": res["complexity"]["dbh_gt_10"]["ci"],
        "n_species_live": r["n_species_live"],
    })
    linhas.append(linha)
df_param = ui.integer_counts(pd.DataFrame(linhas))      # internal column names; shown through ui.for_display

tabs = st.tabs([t("multi.tab.compare"), t("multi.tab.species"),
                t("multi.tab.ivi"), t("multi.tab.map"), t("tab.check"), t("multi.tab.export")])

with tabs[0]:
    ui.report_section(t("multi.tab.compare"))
    # first the normalised profile, then the free chart (opens on the DBH of each plot)
    met_radar = ["mean_dbh_cm", "height_mean_m", "canopy_height_m", "density_live_ha",
                 "ba_live_ha", "complexity_2_5", "n_species_live"]
    met_radar = [m for m in met_radar if m in ui.metric_columns(df_param)]
    if len(df_param) >= 2 and len(met_radar) >= 3:
        ui.show(st, ui.fig_radar(df_param, estilos, met_radar, LANG), "2_1", estilos)
        st.caption(t("multi.radar_note"))
        st.divider()
    base_params = [c for c in ui.metric_columns(df_param) if str(c).isidentifier()]
    cf1, cf2, cf3 = st.columns(3)
    modo_f = cf1.radio(t("multi.free_mode"), ("single", "dual", "xy"), horizontal=True,
                       key="modo_livre", format_func=lambda k: t(f"multi.free.{k}"))
    tipo_f, estilo_2 = "bar", "lines+markers"
    if modo_f == "single":
        tipo_f = cf2.radio(t("multi.chart_kind"), ("box", "violin", "bar", "line"), horizontal=True,
                           key="tipo_livre", format_func=lambda k: t(f"multi.kind.{k}"))
    elif modo_f == "dual":
        estilo_2 = cf2.radio(t("multi.second_style"), ("lines+markers", "markers"), horizontal=True,
                             key="estilo_2", format_func=lambda k: t(f"multi.second_style.{k}"))
    ca_, cb_ = st.columns(2)
    metrica = ca_.selectbox(t("multi.compare_by"), base_params,
                            index=base_params.index("mean_dbh_cm") if "mean_dbh_cm" in base_params else 0,
                            key="metrica_multi", format_func=lambda c: ui.label(c, LANG))
    segunda = None
    if modo_f != "single":
        segunda = cb_.selectbox(t("multi.second_param"), base_params,
                                index=min(1, len(base_params) - 1), key="metrica_multi_b",
                                format_func=lambda c: ui.label(c, LANG))
    ui.show(st, ui.fig_free_compare(df_param, estilos, modo_f, metrica, segunda, LANG,
                                        kind=tipo_f, resultados=resultados, second_style=estilo_2), "2_2", estilos)
    if modo_f == "single" and tipo_f in ("box", "violin"):
        st.caption(t("multi.kind_note"))
    st.divider()
    st.subheader(t("multi.params_by_plot"))
    st.radio(t("multi.share_base"), ("density", "ba"), key="multi_share_base", horizontal=True,
             format_func=lambda b: t(f"multi.share.{b}"))
    _tab = ui.for_display(df_param, lang=LANG).set_index(ui.label("plot", LANG))
    st.dataframe(_tab.style.format(ui.format_by_dtype(_tab)), width="stretch")
    st.divider()
    ui.show_jimenez(st, df_param, estilos, "2_jim", LANG)

with tabs[1]:
    ui.report_section(t("multi.tab.species"))
    st.subheader(t("multi.species_title"))
    st.caption(t("multi.species_caption"))
    ccol1, ccol2 = st.columns(2)
    with ccol1:
        met_esp = st.radio(t("single.metric"), ("ba_ha", "density_ha"),
                           horizontal=True, key="met_esp",
                           format_func=lambda k: ui.label(k, LANG))
    with ccol2:
        cond_esp = st.radio(t("labels.condition"), ("both", "live", "dead"),
                            horizontal=True, key="cond_esp",
                            format_func=lambda k: ui.condition_label(k, LANG))
    metrica_key = "area" if met_esp == "ba_ha" else "densidade"
    df_long = ui.dados_especies_parcelas(resultados, metrica=metrica_key)
    y_lab = ui.label(met_esp, LANG)
    if met_esp == "density_ha":
        UN_m = st.radio(t("units.label"), ("ha", "count"), horizontal=True, key="units_multi",
                        format_func=lambda k: t(f"units.{k}"))
        if UN_m == "count":           # stems/ha back to stems in each plot
            areas = {res["plot_name"]: res["summary"]["plot_area_m2"] for res in resultados}
            df_long = df_long.assign(value=df_long["value"] * df_long["plot"].map(areas) / 10000.0)
            y_lab = ui.label("n_stems", LANG)
    cs1, cs2 = st.columns([2, 1])
    with cs1:
        tipo_st = st.radio(t("temporal.chart"), ("stack", "stack100"), horizontal=True,
                           key="tipo_st_multi", format_func=lambda k: t(f"temporal.chart.{k}"))
    with cs2:
        val_st = st.checkbox(t("temporal.show_values"), value=False, key="val_st_multi")
    df_st = df_long if cond_esp == "both" else df_long[df_long["condition"] == cond_esp]
    fig_st = ui.fig_species_plots_stacked(df_st, estilos, y_lab, tipo_st, val_st, LANG)
    if fig_st:
        ui.show(st, fig_st, "2_3", estilos)
    else:
        st.warning(t("multi.no_data_combo"))
    # pivot table: plots in rows, components (species + L/D) in columns
    if not df_long.empty:
        dft = df_long.copy()
        if cond_esp != "both":
            dft = dft[dft["condition"] == cond_esp]
        dft["component"] = (dft["species"].map(lambda v: ui.species_name(v, LANG))
                            + " (" + dft["condition"].map(
                                lambda v: ui.condition_label(v, LANG)).str[0] + ")")
        piv = dft.pivot_table(index="plot", columns="component", values="value",
                              aggfunc="sum", fill_value=0)
        piv.index.name = ui.label("plot", LANG)
        st.dataframe(piv.style.format("{:.2f}"), width="stretch")
        st.download_button(t("multi.species_csv"),
                           data=piv.to_csv().encode("utf-8"),
                           file_name=t("file.species_by_plot"), mime="text/csv")

with tabs[2]:
    ui.report_section(t("multi.tab.ivi"))
    st.subheader(t("multi.ivi_title"))
    st.caption(t("method.ivi_multi"))
    # densidade e área basal absolutas: troncos somados / soma das áreas das parcelas
    ivi = mc.pooled_importance(resultados)
    if ivi is not None and not ivi.empty:
        st.dataframe(ui.for_display(ivi, lang=LANG).style.format(precision=2),
                     width="stretch")
        fig = ui.fig_ivi(ivi, estilos, LANG)
        if fig:
            ui.show(st, fig, "2_4", estilos)

with tabs[3]:
    map_rows = []
    for res in resultados:
        d = res["data"]
        if "lat" in d.columns and "lon" in d.columns:
            m = d[["lat", "lon"]].dropna().drop_duplicates()
            if not m.empty:
                map_rows.append({**m.iloc[0].to_dict(), "plot": str(res["plot_name"])})
    st.subheader(t("multi.locations"))
    if map_rows:
        ui.location_map(st, pd.DataFrame(map_rows), LANG)
    else:
        st.info(t("map.no_coordinates"))

with tabs[4]:
    ui.validation_panel(problemas, SHEET, key="mc_multi", lang=LANG)

with tabs[5]:
    st.subheader(t("multi.export"))
    # IVI agregado e contribuição por espécie (para o relatório)
    ivi_all = mc.pooled_importance(resultados)
    df_long_esp = ui.dados_especies_parcelas(resultados, "area")

    sig = ("multi", tuple(r["plot_name"] for r in resultados), limites, cfg_sig, LANG, show_seal)
    from manguetree import report as rep
    _coords = None
    for res in resultados:
        d = res["data"]
        if "lat" in d.columns and "lon" in d.columns:
            m = d[["lat", "lon"]].dropna().drop_duplicates()
            if not m.empty:
                r_ = m.iloc[[0]].assign(plot=str(res["plot_name"]))
                _coords = r_ if _coords is None else pd.concat([_coords, r_], ignore_index=True)
    cc = st.columns(3)
    ui.pdf_block(cc[0], "multi", lambda figs: rep.multiple_plots_report(
        resultados, df_param, ivi_all, df_long_esp,
        ui.issues_frame_by_unit(problemas, t("labels.sheet"), LANG),
        lang=LANG, seal=show_seal, figures=figs, coords=_coords),
        t("file.multi_pdf"), sig)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xls:
        ui.for_display(df_param, lang=LANG).to_excel(
            xls, sheet_name=t("sheet.comparison"), index=False)
        if ivi_all is not None and not ivi_all.empty:
            ui.for_display(ivi_all, lang=LANG).round(3).to_excel(
                xls, sheet_name=t("sheet.ivi"), index=False)
        for res in resultados:
            nome = re.sub(r"[\\/*?:\[\]]", "", str(res["plot_name"]))[:26]
            ui.tabela_por_especie(res, LANG).round(3).to_excel(
                xls, sheet_name=(nome or "parc")[:26], index=False)
        df_problemas.to_excel(xls, sheet_name=t("sheet.issues"), index=False)
    buf.seek(0)
    with cc[1]:
        st.download_button(t("export.excel"), data=buf.getvalue(),
                           file_name=t("file.multi_xlsx"),
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with cc[2]:
        st.download_button(t("multi.comparison_csv"),
                           data=ui.for_display(df_param, lang=LANG).to_csv(
                               index=False).encode("utf-8"),
                           file_name=t("file.comparison"), mime="text/csv")
    st.caption(t("export.multi_note"))
