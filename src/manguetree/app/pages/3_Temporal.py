# -*- coding: utf-8 -*-
"""
Temporal analysis (MangueTREE): follows the SAME plot over the years (structural
parameters and mortality).

Expected input: an Excel workbook where each sheet is one survey (one year) of the
same plot. The year is read from the sheet name (e.g. 'g2-2013', '2014') or given
manually. Results in session_state use language independent keys and internal column
names; text comes from the catalogs.
"""
import re
import io
import numpy as np
import pandas as pd
import streamlit as st

from manguetree import calc as mc
from manguetree import charts as ui
from manguetree import io as mio
from manguetree import i18n
from manguetree.i18n import t
from manguetree.validation import Issue

st.set_page_config(layout="wide", page_title=t("temporal.page_title"), page_icon=ui.PAGE_ICON)
LANG = i18n.language_selector(st.sidebar)        # first on every page (see i18n.py)
ui.sidebar_nav(st.sidebar, tab_icons=("evolucao", "especies", "mortalidade", "serie", "verificacao", "exportar"))
ui.topo(t("temporal.title"), t("temporal.subtitle"))
st.markdown(t("temporal.intro"))

def _extrai_ano(nome):
    m = re.search(r"(19|20)\d{2}", str(nome))
    return int(m.group(0)) if m else None


ui.icon_heading(st.sidebar, "configuracoes", t("sidebar.settings"))
uploaded = st.sidebar.file_uploader(t("sidebar.excel_file"), type=["xlsx"], key="upload_temp")
RESOLVER = ui.sidebar_species_settings(st.sidebar)

if not uploaded:
    ui.icon_note(st, "enviar", t("temporal.upload_prompt"))
    st.stop()

try:
    abas = ui.sheet_names(uploaded)
except Exception as e:
    st.error(t("sidebar.excel_error", error=str(e)))
    st.stop()

# Results belong to the file they were computed from: a new upload clears them.
_fid = getattr(uploaded, "file_id", uploaded.name)
if st.session_state.get("temp_file") != _fid:
    for _k in ('temp_serie', 'temp_esp', 'temp_sig', 'temp_issues', 'temp_ignoradas', 'pdf_temp', 'pdf_sig_temp'):
        st.session_state.pop(_k, None)
    st.session_state["temp_file"] = _fid

# --- Fora do formulário: atualizam ao vivo ---
ui.icon_heading(st.sidebar, "estilo", t("sidebar.style_sub"), 3)
paleta_nome = st.sidebar.selectbox(t("sidebar.palette"), list(ui.PALETAS), key="pal_temp",
                                    format_func=lambda c: ui.palette_label(c, LANG))
show_seal = ui.seal_checkbox(st.sidebar)
estilos = {"paleta": ui.PALETAS[paleta_nome], "tamanho_titulo": 14, "tamanho_eixos": 11,
           "seal": show_seal}
selecionadas = st.sidebar.multiselect(t("temporal.surveys_to_include"), options=abas,
                                      default=abas,
                                      key=f"sheets_temp_{uploaded.name}_{uploaded.size}")

# --- Atribuição de ano por aba (auto + ajuste manual) ---
st.subheader(t("temporal.confirm_years"))
st.caption(t("temporal.years_hint"))
anos_por_aba = {}
cols = st.columns(min(len(selecionadas), 4)) if selecionadas else [st]
for i, aba in enumerate(selecionadas):
    det = _extrai_ano(aba)          # None when the sheet name has no year: the user must give it
    with cols[i % len(cols)]:
        anos_por_aba[aba] = st.number_input(f"{aba}", min_value=1900, max_value=2100,
                                            value=det, step=1, key=f"ano_{aba}")
sem_ano = [a for a, v in anos_por_aba.items() if v is None]
if sem_ano:
    st.warning(t("temporal.year_not_detected", sheets=", ".join(sem_ano)))
    st.stop()
# Repeated years are reported after the analysis, by the duplicate_year issue in the
# data-check panel (only for the sheets actually analysed; ignored sheets do not count).

# --- Formulário: preencha e clique UMA vez (sem apertar Enter em cada campo) ---
with st.sidebar.form("cfg_temp"):
    st.caption(t("sidebar.form_hint"))
    cell_area = st.text_input(t("sidebar.area_cell_sheets"), "", key="cell_temp")
    area_padrao = st.number_input(t("sidebar.default_area"), min_value=1.0,
                                  value=100.0, step=10.0, key="area_temp")
    tc1, tc2 = st.columns(2)
    with tc1:
        c1 = st.number_input(t("sidebar.dbh_class1"), value=2.5, step=0.5, key="cut1_temp")
    with tc2:
        c2 = st.number_input(t("sidebar.dbh_class2"), value=10.0, step=1.0, key="cut2_temp")
    submitted = st.form_submit_button(t("temporal.run"), type="primary")
limites = tuple(sorted([c1, c2]))
if limites[0] >= limites[1]:
    st.sidebar.error(t("sidebar.cutoffs_equal"))
    st.stop()

# Processa só ao clicar (ou quando região, tabela de espécies ou a escolha para troncos
# sem condição mudam); guarda em session_state para os seletores atualizarem ao vivo.
cond_faltante = st.session_state.get("mc_temp", "exclude")
cfg_sig = (ui.settings_signature(), cond_faltante)
if submitted or (st.session_state.get("temp_serie") is not None
                 and st.session_state.get("temp_sig") != cfg_sig):
    resultados = []
    ignoradas = {}
    problemas = {}
    with st.spinner(t("temporal.processing")):
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
            res["year"] = int(anos_por_aba[aba])
            resultados.append(res)
        # repeated years among the sheets actually analysed (ignored sheets do not count)
        por_ano = {}
        for res in resultados:
            por_ano.setdefault(res["year"], []).append(res["plot_name"])
        for res in resultados:
            if len(por_ano[res["year"]]) > 1:
                res["issues"] = list(res["issues"]) + [Issue.make(
                    "duplicate_year", "warning", None, None,
                    {"year": res["year"], "sheets": ", ".join(por_ano[res["year"]])})]
            problemas[(res["year"], res["plot_name"])] = res["issues"]

    if len({r["year"] for r in resultados}) < 2:
        for k in ("temp_serie", "temp_esp"):
            st.session_state.pop(k, None)
        st.error(t("temporal.need_two_years"))
        if ignoradas:
            st.caption(t("sheets.ignored") + " " + ", ".join(
                f"{a} ({t('sheets.reason.' + m)})" for a, m in ignoradas.items()))
        st.stop()

    serie = []
    for res in sorted(resultados, key=lambda r: r["year"]):
        r = res["summary"]
        serie.append({
            "year": res["year"],
            "plot_area_m2": r["plot_area_m2"],
            "n_species_live": r["n_species_live"],
            "density_live_ha": r["density_live_ha"],
            "ba_live_ha": r["ba_live_ha"],
            "mean_dbh_cm": r["mean_dbh_cm"],
            "canopy_height_m": r["canopy_height_m"],
            "complexity_2_5": res["complexity"]["dbh_gt_2.5"]["ci"],
            "complexity_10": res["complexity"]["dbh_gt_10"]["ci"],
            "mortality_stems_pct": r["mortality_stems_pct"],
        })
    df_serie = pd.DataFrame(serie).groupby("year", as_index=False).mean(numeric_only=True)
    # counts and areas stay integers when no year was averaged (the mean makes them floats)
    df_serie = ui.integer_counts(df_serie)
    st.session_state["temp_serie"] = df_serie
    st.session_state["temp_esp"] = ui.serie_por_especie(resultados)
    st.session_state["temp_ignoradas"] = ignoradas
    st.session_state["temp_issues"] = problemas
    st.session_state["temp_sig"] = cfg_sig

df_serie = st.session_state.get("temp_serie")
if df_serie is None:
    st.info(t("temporal.confirm_prompt"))
    st.stop()
df_esp = st.session_state.get("temp_esp")
ignoradas = st.session_state.get("temp_ignoradas", {})
if ignoradas:
    st.caption(t("sheets.ignored") + " " + ", ".join(
        f"{a} ({t('sheets.reason.' + m)})" for a, m in ignoradas.items()))

st.success(t("temporal.analysed", n=len(df_serie), first=int(df_serie["year"].min()),
             last=int(df_serie["year"].max())))
problemas = st.session_state.get("temp_issues", {})
UNITS = (t("labels.year"), t("labels.sheet"))
ui.validation_banner(problemas, LANG)
df_problemas = ui.issues_frame_by_unit(problemas, UNITS, LANG)

tabs = st.tabs([t("temporal.tab.evolution"), t("temporal.tab.species"),
                t("temporal.tab.mortality"), t("temporal.tab.series"), t("tab.check"),
                t("temporal.tab.export")])

with tabs[0]:
    st.subheader(t("temporal.evolution"))
    params = ui.metric_columns(df_serie)
    modo = st.radio(t("temporal.display_mode"), ("separate", "dual"),
                    horizontal=True, key="modo_evol",
                    format_func=lambda k: t(f"temporal.mode.{k}", LANG))
    if modo == "separate":
        padrao = [p for p in ["ba_live_ha", "density_live_ha"] if p in params]
        escolhidos = st.multiselect(t("temporal.parameters"), params, default=padrao,
                                    key="params_sep",
                                    format_func=lambda c: ui.label(c, LANG))
        for p in escolhidos:
            st.plotly_chart(ui.fig_temporal(df_serie, estilos, p, lang=LANG),
                            width="stretch", config=ui.PLOT_CONFIG)
    else:
        st.caption(t("temporal.dual_hint"))
        cE, cD = st.columns(2)
        with cE:
            esq = st.multiselect(t("temporal.left_axis"), params,
                                 default=[p for p in ["ba_live_ha"] if p in params],
                                 key="eixo_esq", format_func=lambda c: ui.label(c, LANG))
        with cD:
            dire = st.multiselect(t("temporal.right_axis"), params,
                                  default=[p for p in ["canopy_height_m"] if p in params],
                                  key="eixo_dir", format_func=lambda c: ui.label(c, LANG))
        if esq and dire:
            st.plotly_chart(ui.fig_temporal_multi(df_serie, estilos, esq, dire, LANG),
                            width="stretch", config=ui.PLOT_CONFIG)
        else:
            st.info(t("temporal.pick_each_axis"))

with tabs[1]:
    st.subheader(t("temporal.by_species"))
    if df_esp is None or df_esp.empty:
        st.info(t("temporal.no_species_data"))
    else:
        st.caption(t("temporal.species_hint"))
        metricas_esp = ["density_ha", "ba_ha", "mean_dbh_cm", "height_mean_m",
                        "ba_contribution_pct"]
        cm1, cm2 = st.columns([2, 1])
        with cm1:
            met_e = st.selectbox(t("temporal.species_metric"), metricas_esp,
                                 key="met_esp_temp",
                                 format_func=lambda c: ui.label(c, LANG))
        with cm2:
            tipo = st.radio(t("single.chart_type"), ("line", "area"), key="tipo_esp_temp",
                            horizontal=True, format_func=lambda k: t(f"temporal.type.{k}", LANG))
        fig_e = ui.fig_serie_especie(df_esp, estilos, met_e, tipo=tipo, lang=LANG)
        if fig_e:
            st.plotly_chart(fig_e, width="stretch", config=ui.PLOT_CONFIG)
        # pivot table: year x species of the chosen metric
        piv = df_esp.pivot_table(index="year", columns="species", values=met_e,
                                 aggfunc="mean")
        piv.columns = [ui.species_name(c, LANG) for c in piv.columns]
        piv.index.name = ui.label("year", LANG)
        st.dataframe(piv.style.format("{:.2f}", na_rep="-"), width="stretch")
        st.download_button(t("temporal.species_csv"),
                           data=ui.for_display(df_esp, lang=LANG).to_csv(
                               index=False).encode("utf-8"),
                           file_name=t("file.series_by_species"), mime="text/csv")

with tabs[2]:
    st.subheader(t("temporal.mortality"))
    st.plotly_chart(ui.fig_temporal(df_serie, estilos, "mortality_stems_pct",
                                    t("temporal.mortality"), LANG),
                    width="stretch", config=ui.PLOT_CONFIG)

with tabs[3]:
    _tab = ui.for_display(df_serie, lang=LANG).set_index(ui.label("year", LANG))
    st.dataframe(_tab.style.format(ui.format_by_dtype(_tab)), width="stretch")

with tabs[4]:
    ui.validation_panel(problemas, UNITS, key="mc_temp", lang=LANG)

with tabs[5]:
    st.subheader(t("temporal.export"))
    sig = ("temp", tuple(df_serie["year"].tolist()), cfg_sig, LANG, show_seal)
    if st.session_state.get("pdf_sig_temp") != sig:
        with st.spinner(t("export.preparing_pdf_all")):
            try:
                from manguetree import report as rep
                st.session_state["pdf_temp"] = rep.temporal_report(
                    df_serie, df_esp,
                    ui.issues_frame_by_unit(problemas, (t("labels.year"),
                                                        t("labels.sheet")), LANG),
                    lang=LANG, seal=show_seal)
                st.session_state["pdf_sig_temp"] = sig
            except Exception as e:
                st.session_state["pdf_temp"] = None
                st.warning(t("export.pdf_unavailable", error=str(e)))
    cc = st.columns(3)
    with cc[0]:
        if st.session_state.get("pdf_temp"):
            st.download_button(t("export.pdf"), data=st.session_state["pdf_temp"],
                               file_name=t("file.temporal_pdf"), mime="application/pdf",
                               type="primary")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xls:
        ui.for_display(df_serie, lang=LANG).to_excel(
            xls, sheet_name=t("sheet.time_series"), index=False)
        if df_esp is not None and not df_esp.empty:
            ui.for_display(df_esp, lang=LANG).round(3).to_excel(
                xls, sheet_name=t("sheet.by_species"), index=False)
        df_problemas.to_excel(xls, sheet_name=t("sheet.issues"), index=False)
    buf.seek(0)
    with cc[1]:
        st.download_button(t("export.excel"), data=buf.getvalue(),
                           file_name=t("file.temporal_xlsx"),
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with cc[2]:
        st.download_button(t("temporal.series_csv"),
                           data=ui.for_display(df_serie, lang=LANG).to_csv(
                               index=False).encode("utf-8"),
                           file_name=t("file.series"), mime="text/csv")
    st.caption(t("export.temporal_note"))
