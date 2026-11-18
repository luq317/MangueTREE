# -*- coding: utf-8 -*-
"""
Temporal analysis (MangueTREE): follows plots over the years.

Expected input: one Excel workbook per plot, each sheet one survey (one year). The
year is read from the sheet name (e.g. 'g2-2013', '2014') or given manually. Several
workbooks (plots) can be analysed together. Results in session_state use language
independent keys and internal column names; text comes from the catalogs.
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
from manguetree.validation import Issue

st.set_page_config(layout="wide", page_title=t("temporal.page_title"), page_icon=ui.PAGE_ICON)
LANG = i18n.language_selector(st.sidebar)        # first on every page (see i18n.py)
ui.sidebar_nav(st.sidebar, tab_icons=("evolucao", "especies", "mortalidade",
                                      "serie", "verificacao", "exportar"))
ui.topo(t("temporal.title"), t("temporal.subtitle"))
st.markdown(t("temporal.intro"))


def _extrai_ano(nome):
    m = re.search(r"(19|20)\d{2}", str(nome))
    return int(m.group(0)) if m else None


def _plot_name(file_name):
    return file_name.rsplit(".", 1)[0]


ui.icon_heading(st.sidebar, "configuracoes", t("sidebar.settings"))
uploads = st.sidebar.file_uploader(t("sidebar.excel_file"), type=["xlsx"], key="upload_temp",
                                   accept_multiple_files=True, help=t("temporal.files_hint"))
RESOLVER = ui.sidebar_species_settings(st.sidebar)

if not uploads:
    ui.icon_note(st, "enviar", t("temporal.upload_prompt"))
    st.caption(t("temporal.files_hint"))
    st.stop()

abas_por_arquivo = {}
for up in uploads:
    try:
        abas_por_arquivo[up.name] = ui.sheet_names(up)
    except Exception as e:
        st.error(t("sidebar.excel_error", error=str(e)))
        st.stop()
arquivos = {up.name: up for up in uploads}
MULTI = len(uploads) > 1

# Results belong to the files they were computed from: a new upload clears them.
_fid = tuple(sorted(getattr(u, "file_id", u.name) for u in uploads))
if st.session_state.get("temp_file") != _fid:
    for _k in ("temp_serie", "temp_esp", "temp_sig", "temp_issues",
               "temp_ignoradas", "pdf_temp", "pdf_sig_temp"):
        st.session_state.pop(_k, None)
    st.session_state["temp_file"] = _fid

# --- Fora do formulário: atualizam ao vivo ---
ui.icon_heading(st.sidebar, "estilo", t("sidebar.style_sub"), 3)
paleta_nome = st.sidebar.selectbox(t("sidebar.palette"), list(ui.PALETAS), key="pal_temp",
                                    format_func=lambda c: ui.palette_label(c, LANG))
show_seal = ui.seal_checkbox(st.sidebar)
estilos = {"paleta": ui.PALETAS[paleta_nome], "tamanho_titulo": 14, "tamanho_eixos": 11,
           "seal": show_seal}
selecionadas = {}
for nome, abas in abas_por_arquivo.items():
    up = arquivos[nome]
    selecionadas[nome] = st.sidebar.multiselect(
        t("temporal.surveys_to_include") + (f" · {_plot_name(nome)}" if MULTI else ""),
        options=abas, default=abas, key=f"sheets_temp_{up.name}_{up.size}")

# --- Ano de cada aba: detectado no nome; pede só o que falta, o resto fica num expansor ---
anos_por_aba = {}
faltando = [(n, a) for n, abas in selecionadas.items() for a in abas if _extrai_ano(a) is None]
if faltando:
    st.subheader(t("temporal.confirm_years"))
    st.caption(t("temporal.years_hint"))
box = st.expander(t("temporal.years_check"), expanded=False)
for nome, abas in selecionadas.items():
    cols = st.columns(4) if faltando else box.columns(4)
    for i, aba in enumerate(abas):
        det = _extrai_ano(aba)
        key = f"ano_{aba}" if not MULTI else f"ano_{nome}_{aba}"
        container = (cols[i % 4]) if det is None else box
        anos_por_aba[(nome, aba)] = container.number_input(
            f"{_plot_name(nome) + ' · ' if MULTI else ''}{aba}", min_value=1900, max_value=2100,
            value=det, step=1, key=key)
sem_ano = [a for (n, a), v in anos_por_aba.items() if v is None]
if sem_ano:
    st.warning(t("temporal.year_not_detected", sheets=", ".join(sem_ano)))
    st.stop()

# --- Formulário: preencha e clique UMA vez (sem apertar Enter em cada campo) ---
with st.sidebar.form("cfg_temp"):
    st.caption(t("sidebar.form_hint"))
    cell_area = st.text_input(t("sidebar.area_cell_sheets"), "", key="cell_temp")
    area_padrao = st.number_input(t("sidebar.default_area"), min_value=1.0,
                                  value=100.0, step=10.0, key="area_temp",
                                  help=t("sidebar.default_area_help"))
    tc1, tc2 = st.columns(2)
    with tc1:
        c1 = st.number_input(t("sidebar.dbh_class1"), value=2.5, step=0.5, key="cut1_temp",
                             help=t("sidebar.dbh_cut_help"))
    with tc2:
        c2 = st.number_input(t("sidebar.dbh_class2"), value=10.0, step=1.0, key="cut2_temp",
                             help=t("sidebar.dbh_cut_help"))
    submitted = st.form_submit_button(t("temporal.run"), type="primary")
limites = tuple(sorted([c1, c2]))
if limites[0] >= limites[1]:
    st.sidebar.error(t("sidebar.cutoffs_equal"))
    st.stop()

cond_faltante = st.session_state.get("mc_temp", "exclude")
cfg_sig = (ui.settings_signature(), cond_faltante, limites)
if submitted or (st.session_state.get("temp_serie") is not None
                 and st.session_state.get("temp_sig") != cfg_sig):
    resultados = []
    ignoradas = {}
    problemas = {}
    with st.spinner(t("temporal.processing")):
        for nome, abas in selecionadas.items():
            for aba in abas:
                df, area = mio.load_excel_sheet(arquivos[nome], aba, cell_area, area_padrao)
                rotulo = f"{_plot_name(nome)} · {aba}" if MULTI else aba
                if df is None or not mio.has_required_columns(df):
                    ignoradas[rotulo] = "no_columns"
                    continue
                if df.empty:
                    ignoradas[rotulo] = "no_data"
                    continue
                res = mc.analyze(df, area, RESOLVER, dbh_limits=limites, plot_name=aba,
                                 missing_condition=cond_faltante)
                if res["summary"]["n_stems"] == 0:
                    ignoradas[rotulo] = "no_stems"
                    continue
                res["year"] = int(anos_por_aba[(nome, aba)])
                res["plot"] = _plot_name(nome)
                resultados.append(res)
        # repeated years within a plot, among the sheets actually analysed
        por_ano = {}
        for res in resultados:
            por_ano.setdefault((res["plot"], res["year"]), []).append(res["plot_name"])
        for res in resultados:
            if len(por_ano[(res["plot"], res["year"])]) > 1:
                res["issues"] = list(res["issues"]) + [Issue.make(
                    "duplicate_year", "warning", None, None,
                    {"year": res["year"],
                     "sheets": ", ".join(por_ano[(res["plot"], res["year"])])})]
            chave = ((res["plot"], res["year"], res["plot_name"]) if MULTI
                     else (res["year"], res["plot_name"]))
            problemas[chave] = res["issues"]

    if len({r["year"] for r in resultados}) < 2:
        for k in ("temp_serie", "temp_esp"):
            st.session_state.pop(k, None)
        st.error(t("temporal.need_two_years"))
        if ignoradas:
            st.caption(t("sheets.ignored") + " " + ", ".join(
                f"{a} ({t('sheets.reason.' + m)})" for a, m in ignoradas.items()))
        st.stop()

    serie, esp = [], []
    for res in sorted(resultados, key=lambda r: (r["plot"], r["year"])):
        serie.append({"plot": res["plot"], "year": res["year"],
                      **mc.plot_parameters(res, dbh_limits=limites)})
        sp = mc.species_parameters(res)
        sp.insert(0, "year", res["year"])
        sp.insert(0, "plot", res["plot"])
        esp.append(sp)
    # sheets of the same plot and year are averaged; a species absent from one of them
    # counts as zero there
    df_serie = (pd.DataFrame(serie).groupby(["plot", "year"], as_index=False, sort=True)
                .mean(numeric_only=True))
    df_esp = pd.concat(esp, ignore_index=True)
    df_esp = (df_esp.pivot_table(index=["plot", "year"], columns="species",
                                 values=list(mc.SPECIES_METRICS), aggfunc="mean")
              .stack(level="species", future_stack=True).reset_index())
    zero = [c for c in mc.SPECIES_METRICS if not c.startswith(("mean_", "height_", "canopy_", "rel_"))]
    df_esp[zero] = df_esp[zero].fillna(0.0)
    df_esp = df_esp.dropna(subset=["n_stems"])
    df_esp = df_esp[df_esp["n_stems"] > 0].reset_index(drop=True)
    st.session_state["temp_serie"] = ui.integer_counts(df_serie)
    st.session_state["temp_esp"] = df_esp
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
PLOTS = list(dict.fromkeys(df_serie["plot"]))
MULTI = len(PLOTS) > 1

st.success(t("temporal.analysed", n=df_serie["year"].nunique(), first=int(df_serie["year"].min()),
             last=int(df_serie["year"].max())))
problemas = st.session_state.get("temp_issues", {})
UNITS = ((t("labels.plot"), t("labels.year"), t("labels.sheet")) if MULTI
         else (t("labels.year"), t("labels.sheet")))
ui.validation_banner(problemas, LANG)
df_problemas = ui.issues_frame_by_unit(problemas, UNITS, LANG)

# series used by the charts: per plot, or the mean of the plots
VIEW = "plots"
if MULTI:
    VIEW = st.radio(t("temporal.view"), ("plots", "mean"), horizontal=True, key="view_temp",
                    format_func=lambda k: t(f"temporal.view.{k}"))
serie_media = df_serie.drop(columns="plot").groupby("year", as_index=False).mean(numeric_only=True)
params = [c for c in mc.metric_columns(df_serie)]

tabs = st.tabs([t("temporal.tab.evolution"), t("temporal.tab.species"),
                t("temporal.tab.mortality"), t("temporal.tab.series"), t("tab.check"),
                t("temporal.tab.export")])
GAPS = st.checkbox(t("temporal.gaps"), value=False, key="gaps_temp")

with tabs[0]:
    st.subheader(t("temporal.evolution"))
    cm, cg = st.columns([2, 1])
    with cm:
        modo = st.radio(t("temporal.display_mode"), ("separate", "dual"),
                        horizontal=True, key="modo_evol",
                        format_func=lambda k: t(f"temporal.mode.{k}", LANG))
    with cg:
        grafico = st.radio(t("temporal.chart"), ("line", "bar"), horizontal=True, key="graf_evol",
                           format_func=lambda k: t(f"temporal.chart.{k}"))
    if modo == "separate":
        padrao = [p for p in ["mean_dbh_cm", "height_mean_m", "canopy_height_m",
                              "density_live_ha", "ba_live_ha"] if p in params]
        escolhidos = st.multiselect(t("temporal.parameters"), params, default=padrao,
                                    key="params_sep",
                                    format_func=lambda c: ui.label(c, LANG))
        for a, b in zip(escolhidos[0::2], escolhidos[1::2] + [None]):
            ca, cb = st.columns(2)
            for col, p in ((ca, a), (cb, b)):
                if p:
                    col.plotly_chart(ui.fig_series(df_serie, estilos, p, VIEW, grafico, LANG, GAPS),
                                     width="stretch", config=ui.PLOT_CONFIG)
    else:
        st.caption(t("temporal.dual_hint"))
        cE, cD = st.columns(2)
        with cE:
            esq = st.multiselect(t("temporal.left_axis"), params,
                                 default=[p for p in ["density_live_ha"] if p in params],
                                 key="eixo_esq", format_func=lambda c: ui.label(c, LANG))
        with cD:
            dire = st.multiselect(t("temporal.right_axis"), params,
                                  default=[p for p in ["height_mean_m"] if p in params],
                                  key="eixo_dir", format_func=lambda c: ui.label(c, LANG))
        base = serie_media if MULTI else df_serie
        if esq and dire:
            st.plotly_chart(ui.fig_temporal_multi(base, estilos, esq, dire, LANG),
                            width="stretch", config=ui.PLOT_CONFIG)
        else:
            st.info(t("temporal.pick_each_axis"))

with tabs[1]:
    st.subheader(t("temporal.by_species"))
    if df_esp is None or df_esp.empty:
        st.info(t("temporal.no_species_data"))
    else:
        st.caption(t("temporal.species_hint"))
        c1_, c2_, c3_ = st.columns([2, 2, 1])
        with c1_:
            opcoes_e = list(ui.LIVE_DEAD_METRICS) + list(mc.SPECIES_METRICS)
            met_e = st.selectbox(t("temporal.species_metric"), opcoes_e,
                                 index=opcoes_e.index("density_live_ha"),
                                 key="met_esp_temp", format_func=lambda c: ui.label(c, LANG))
        with c2_:
            tipo = st.radio(t("temporal.chart"), ("line", "bar", "stack", "stack100"),
                            index=3, key="tipo_esp_temp", horizontal=True,
                            format_func=lambda k: t(f"temporal.chart.{k}"))
        with c3_:
            valores = st.checkbox(t("temporal.show_values"), value=False, key="val_esp_temp")
        if MULTI:
            escolha = st.selectbox(t("temporal.plot_choice"), ["__mean__"] + PLOTS, key="plot_esp_temp",
                                   format_func=lambda p: t("temporal.all_plots_mean") if p == "__mean__" else p)
        else:
            escolha = PLOTS[0]
        if escolha == "__mean__":
            base_e = df_esp.drop(columns="plot").groupby(["year", "species"], as_index=False).mean(numeric_only=True)
        else:
            base_e = df_esp[df_esp["plot"] == escolha]
        fig_e = ui.fig_species_series(base_e, estilos, met_e, tipo, valores, LANG, GAPS)
        if fig_e:
            st.plotly_chart(fig_e, width="stretch", config=ui.PLOT_CONFIG)
        # the table below shows the same data as the chart, and says so
        cols_tab = list(ui.LIVE_DEAD_METRICS[met_e][:2]) if met_e in ui.LIVE_DEAD_METRICS else [met_e]
        nome_parcela = t("temporal.all_plots_mean") if escolha == "__mean__" else escolha
        st.markdown("**" + t("temporal.table_of", metric=ui.label(met_e, LANG),
                             plot=nome_parcela) + "**")
        piv = base_e.pivot_table(index="year", columns="species", values=cols_tab, aggfunc="mean")
        if len(cols_tab) == 1:
            piv.columns = [ui.species_name(sp, LANG) for _m, sp in piv.columns]
        else:
            piv.columns = [f"{ui.species_name(sp, LANG)} · {ui.label(m, LANG)}" for m, sp in piv.columns]
        piv.index.name = ui.label("year", LANG)
        st.dataframe(piv.style.format(lambda v: ui.num(v, 2, LANG), na_rep="-"), width="stretch")
        st.download_button(t("temporal.species_csv"),
                           data=ui.for_display(df_esp, lang=LANG).to_csv(
                               index=False).encode("utf-8"),
                           file_name=t("file.series_by_species"), mime="text/csv")

with tabs[2]:
    st.subheader(t("temporal.mortality"))
    ca, cb = st.columns(2)
    ca.plotly_chart(ui.fig_series(df_serie, estilos, "mortality_stems_pct", VIEW, "line", LANG, GAPS),
                    width="stretch", config=ui.PLOT_CONFIG)
    cb.plotly_chart(ui.fig_series(df_serie, estilos, "mortality_ba_pct", VIEW, "line", LANG, GAPS),
                    width="stretch", config=ui.PLOT_CONFIG)
    st.markdown("#### " + t("temporal.mortality_species"))
    base_m = (df_esp.drop(columns="plot").groupby(["year", "species"], as_index=False).mean(numeric_only=True)
              if MULTI else df_esp)
    cm1, cm2 = st.columns(2)
    for col_, met_ in ((cm1, "live_dead_density"), (cm2, "live_dead_ba")):
        f_ = ui.fig_species_series(base_m, estilos, met_, "stack", False, LANG, GAPS)
        if f_:
            col_.plotly_chart(f_, width="stretch", config=ui.PLOT_CONFIG)
    st.caption(t("temporal.no_dbh_note"))
    cols_nd = ["plot", "year", "n_dead", "n_dead_no_dbh", "n_live_no_dbh"] if MULTI else \
        ["year", "n_dead", "n_dead_no_dbh", "n_live_no_dbh"]
    st.dataframe(ui.for_display(df_serie[cols_nd], lang=LANG), hide_index=True, width="stretch")

with tabs[3]:
    _tab = ui.for_display(df_serie if MULTI else df_serie.drop(columns="plot"), lang=LANG)
    _tab = _tab.set_index(([ui.label("plot", LANG)] if MULTI else []) + [ui.label("year", LANG)])
    st.dataframe(_tab.style.format(ui.format_by_dtype(_tab)), width="stretch")

with tabs[4]:
    ui.validation_panel(problemas, UNITS, key="mc_temp", lang=LANG)

with tabs[5]:
    st.subheader(t("temporal.export"))
    # the PDF keeps the main parameters (mean of the plots when there are several)
    principais = [c for c in ("mean_dbh_cm", "height_mean_m", "canopy_height_m", "density_live_ha",
                              "density_dead_ha", "ba_live_ha", "ba_dead_ha", "mortality_stems_pct",
                              "complexity_2_5", "complexity_10", "n_species_live")
                  if c in serie_media.columns]
    pdf_serie = ui.integer_counts(serie_media[["year", *principais]])
    pdf_esp = None
    if df_esp is not None and not df_esp.empty:
        pdf_esp = (df_esp.drop(columns="plot").groupby(["year", "species"], as_index=False)
                   .mean(numeric_only=True)
                   .rename(columns={"density_live_ha": "density_ha", "ba_live_ha": "ba_ha",
                                    "share_ba_live_pct": "ba_contribution_pct"})
                   [["year", "species", "density_ha", "ba_ha", "mean_dbh_cm", "height_mean_m",
                     "ba_contribution_pct"]])
    sig = ("temp", tuple(PLOTS), tuple(df_serie["year"].tolist()), cfg_sig, LANG, show_seal)
    if st.session_state.get("pdf_sig_temp") != sig:
        with st.spinner(t("export.preparing_pdf_all")):
            try:
                from manguetree import report as rep
                st.session_state["pdf_temp"] = rep.temporal_report(
                    pdf_serie, pdf_esp, df_problemas, lang=LANG, seal=show_seal)
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
