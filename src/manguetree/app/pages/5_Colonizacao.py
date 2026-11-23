# -*- coding: utf-8 -*-
"""
Colonization dynamics (MangueTREE): reads the NEMA colonization workbooks (one per plot)
and shows what was read before any result: collections and years, codes, cohorts,
repeated tags and ignored notes. After "Run analysis" (sidebar form) it computes the
density and height of the juveniles, the charts and the clean export.

Only the data-entry sheet of each plot is read; the calculation sheets are ignored.
Text comes from the catalogs (keys "colon.*").
"""
import io

import pandas as pd
import streamlit as st

from manguetree import charts as ui
from manguetree import colonizacao as col
from manguetree import colonizacao_charts as cc
from manguetree import i18n
from manguetree.i18n import t

st.set_page_config(layout="wide", page_title=t("colon.page_title"), page_icon=ui.PAGE_ICON)
LANG = i18n.language_selector(st.sidebar)        # first on every page (see i18n.py)
ui.sidebar_nav(st.sidebar, tab_icons=("verificacao", "dinamica", "altura", "evolucao", "exportar"),
               subtab_icons=("densidade", "idade_parcela", "altura", "coorte", "curva_jimenez"))
if not ui.colonizacao_enabled():                 # preview page: hidden unless switched on
    st.info(t("colon.disabled"))
    st.stop()
ui.topo(t("colon.title"), t("colon.subtitle"))
st.markdown(t("colon.intro"))

ui.icon_heading(st.sidebar, "configuracoes", t("sidebar.settings"))
uploads = st.sidebar.file_uploader(t("colon.upload"), type=["xlsx"], key="upload_colon",
                                   accept_multiple_files=True, help=t("colon.upload_hint"))
if not uploads:
    ui.icon_note(st, "enviar", t("colon.upload_prompt"))
    st.stop()

# Corrections and the analysis settings belong to the files they were made for.
_fid = tuple(sorted(getattr(u, "file_id", u.name) for u in uploads))
if st.session_state.get("colon_file") != _fid:
    st.session_state["colon_anos"] = {}
    st.session_state["colon_classes"] = {}
    st.session_state.pop("colon_cfg", None)
    st.session_state["colon_file"] = _fid
CORRECOES = st.session_state.setdefault("colon_anos", {})
RECLASSES = st.session_state.setdefault("colon_classes", {})


@st.cache_resource(show_spinner=False)       # same object on every rerun: nothing is copied
def _ler(nome, dados, anos, classes):
    return col.le_parcela(io.BytesIO(dados), nome_arquivo=nome, anos_manuais=dict(anos),
                          classes_manuais=dict(classes))


parcelas, erros = [], []
for up in uploads:
    try:
        correcoes = tuple(sorted(CORRECOES.get(up.name, {}).items()))
        reclasses = tuple(sorted(RECLASSES.get(up.name, {}).items()))
        with st.spinner(t("colon.reading", file=up.name)):
            parcelas.append(_ler(up.name, up.getvalue(), correcoes, reclasses))
    except Exception as e:
        erros.append(t("colon.read_error", file=up.name, error=str(e)))
for msg in erros:
    st.error(msg)
if not parcelas:
    st.stop()
PLOTS = [p.parcela for p in parcelas]


# what the parsed files depend on (heavy tables are cached with this signature)
_SIG = (_fid, repr(sorted(CORRECOES.items())), repr(sorted(RECLASSES.items())))


@st.cache_data(show_spinner=False)
def _tabelas_limpas(_parcelas, sig):
    return col.tabela_limpa(_parcelas, "longo"), col.tabela_limpa(_parcelas, "largo")


@st.cache_data(show_spinner=False)
def _csv(_df, chave):
    return _df.to_csv(index=False).encode("utf-8")


def _classe(cl):
    return t(f"colon.class.{cl}")


def _versao(v):
    return t(f"colon.density.version_{v}")


def _origem(o):
    return t(f"colon.origin.{(o or '-').replace(' ', '_')}")


# --- analysis settings: one form, one click (the others pages work the same way)
with st.sidebar.form("cfg_colon"):
    st.caption(t("colon.cfg.hint"))
    st.markdown("**" + t("colon.areas") + "**")
    st.caption(t("colon.areas_hint"))
    areas_in = {}
    for p in parcelas:
        areas_in[p.parcela] = st.number_input(
            t("colon.area_label", plot=p.parcela), min_value=1.0, max_value=100000.0,
            value=float(col.AREAS_M2.get(p.parcela, 60.0)), step=1.0, key=f"colon_area_{p.parcela}")
    grupos_in = []
    if len(PLOTS) >= 2:
        st.markdown("**" + t("colon.cfg.join_title") + "**")
        st.caption(t("colon.cfg.join_hint"))
        for n in range(1, min(3, len(PLOTS) // 2) + 1):
            grupos_in.append(st.multiselect(t("colon.cfg.join_group", n=n), PLOTS,
                                            key=f"colon_join_{n}"))
    enviado = st.form_submit_button(t("multi.run"), type="primary")
if enviado:
    _unidas, _repetidas = col.monta_unidas(grupos_in, set(PLOTS))
    st.session_state["colon_cfg"] = {"areas": dict(areas_in),
                                     "unidas": _unidas, "repetidas": _repetidas}
CFG = st.session_state.get("colon_cfg")
if CFG:
    AREAS, UNIDAS = CFG["areas"], (CFG["unidas"] or None)
    if CFG["repetidas"]:
        st.sidebar.warning(t("colon.cfg.repeated", plots=", ".join(CFG["repetidas"])))

ui.icon_heading(st.sidebar, "estilo", t("sidebar.style_sub"), 3)
paleta_nome = st.sidebar.selectbox(t("sidebar.palette"), list(ui.PALETAS), key="pal_colon",
                                   format_func=lambda c: ui.palette_label(c, LANG))
ui.use_palette(paleta_nome)
show_seal = ui.seal_checkbox(st.sidebar)
estilos = ui.style_controls(st.sidebar, "colon", paleta_nome, show_seal)


def _precisa_rodar():
    st.info(t("colon.run_first"))


def _nota_juncao():
    if UNIDAS:
        st.caption(t("colon.cfg.joined", groups=", ".join(UNIDAS)))


# individuals counted: a live control (no need to run again)
VERSAO = st.radio(t("colon.cfg.version"), ("sem", "com"), key="colon_versao", horizontal=True,
                  format_func=_versao)
COM_SEM_COORTE = VERSAO == "com"


def _altura(pref):
    """Height controls (classes, by class, species, 1 m) and the statistics they give; the cohort
    choice is the page's (radio above the tabs)."""
    h0, h1 = st.columns([2, 1])
    classes = h0.multiselect(
        t("colon.height.classes"), ["jovem", "plantula", "propagulo", "morto", "incerto"],
        default=["jovem"], key=f"{pref}_classes", format_func=lambda c: t(f"colon.cls.{c}"))
    por_classe = h1.checkbox(t("colon.height.by_class"), key=f"{pref}_por_classe",
                             disabled=len(classes) < 2)
    h2, h3 = st.columns(2)
    por_esp = h2.checkbox(t("colon.density.by_species"), key=f"{pref}_especie")
    um_m = h3.checkbox(t("colon.height.one_m"), key=f"{pref}_1m")
    return col.estatistica_altura(
        parcelas, incluir_sem_coorte=COM_SEM_COORTE, unidas=UNIDAS, por_especie=por_esp,
        minimo_cm=col.ALTURA_1M_CM if um_m else None, classes=classes or ("jovem",),
        por_classe=por_classe and len(classes) > 1)


tab_verif, tab_dens, tab_alt, tab_graf, tab_exp = st.tabs([
    t("colon.tab.verify"), t("colon.tab.density"), t("colon.tab.height"), t("colon.tab.charts"),
    t("colon.tab.export")])
rel = est = None

# ------------------------------------------------------------------ verification
with tab_verif:
    st.write(t("colon.verify.intro"))
    resumos = [col.resumo(p) for p in parcelas]
    st.subheader(t("colon.verify.summary"))
    st.dataframe(pd.DataFrame({
        t("colon.col.plot"): [r["parcela"] for r in resumos],
        t("colon.col.file"): [r["arquivo"] for r in resumos],
        t("colon.col.individuals"): [r["individuos"] for r in resumos],
        t("colon.col.blocks"): [r["blocos"] for r in resumos],
        t("colon.col.years"): [f"{r['anos'][0]} a {r['anos'][1]}" if r["anos"] else "-"
                               for r in resumos],
        t("colon.col.species_list"): [", ".join(r["especies"]) or "-" for r in resumos],
        t("colon.col.no_cohort"): [r["sem_coorte"] for r in resumos],
        t("colon.col.excluded"): [r["excluidos"] for r in resumos],
        t("colon.col.repeated_tags"): [r["lacres_repetidos"] for r in resumos],
        t("colon.col.notes"): [r["anotacoes"] for r in resumos],
        t("colon.col.unknown_codes"): [", ".join(r["codigos_desconhecidos"]) or "-"
                                       for r in resumos],
    }), hide_index=True, width="stretch")
    st.caption(t("colon.verify.excluded_note"))

    for p in parcelas:
        with st.expander(t("colon.plot_expander", plot=p.parcela, file=p.arquivo),
                         expanded=len(parcelas) == 1):
            # collections and years
            st.markdown("**" + t("colon.sub.blocks") + "**")
            blocos = col.tabela_blocos(p)
            st.dataframe(pd.DataFrame({
                t("colon.col.block"): blocos["bloco"] + 1,
                t("colon.col.label"): blocos["rotulo"],
                t("colon.col.column"): blocos["coluna"],
                t("colon.col.date"): blocos["data"],
                t("colon.col.year"): blocos["ano"].astype("Int64"),
                t("colon.col.origin"): blocos["origem"].map(_origem),
                t("colon.col.height_column"): blocos["coleta_altura"],
                t("colon.col.records"): blocos["registros"],
            }), hide_index=True, width="stretch")
            st.caption(t("colon.sub.blocks_note"))
            with st.popover(t("colon.fix.title")):
                num = st.selectbox(t("colon.fix.block"), list(blocos["bloco"] + 1),
                                   key=f"colon_fix_bloco_{p.parcela}")
                ano_atual = blocos.loc[blocos["bloco"] == num - 1, "ano"].iloc[0]
                novo = st.number_input(t("colon.fix.year"), min_value=1900, max_value=2100,
                                       value=int(ano_atual) if pd.notna(ano_atual) else 2000,
                                       step=1, key=f"colon_fix_ano_{p.parcela}_{num}")
                c1, c2 = st.columns(2)
                if c1.button(t("colon.fix.apply"), key=f"colon_fix_ok_{p.parcela}"):
                    CORRECOES.setdefault(p.arquivo, {})[int(num) - 1] = int(novo)
                    st.rerun()
                if c2.button(t("colon.fix.clear"), key=f"colon_fix_clear_{p.parcela}"):
                    CORRECOES.pop(p.arquivo, None)
                    st.rerun()

            left, right = st.columns(2, gap="large")
            with left:
                st.markdown("**" + t("colon.sub.codes") + "**")
                cod = col.tabela_codigos(p)
                st.dataframe(pd.DataFrame({
                    t("colon.col.code"): cod["codigo"],
                    t("colon.col.class"): cod["classe"].map(_classe),
                    t("colon.col.count"): cod["n"],
                }), hide_index=True, width="stretch")
                st.caption(t("colon.codes.note"))
                with st.popover(t("colon.reclass.title")):
                    cod_sel = st.selectbox(t("colon.reclass.code"), list(cod["codigo"]),
                                           key=f"colon_rc_cod_{p.parcela}")
                    atual = col.classifica(cod_sel, p.classes_manuais)
                    opcoes = list(col.CLASSES_EDITAVEIS)
                    cls_sel = st.selectbox(t("colon.reclass.class"), opcoes,
                                           index=opcoes.index(atual) if atual in opcoes else 0,
                                           key=f"colon_rc_cls_{p.parcela}_{cod_sel}",
                                           format_func=_classe)
                    r1, r2 = st.columns(2)
                    if r1.button(t("colon.reclass.apply"), key=f"colon_rc_ok_{p.parcela}"):
                        RECLASSES.setdefault(p.arquivo, {})[cod_sel] = cls_sel
                        st.rerun()
                    if r2.button(t("colon.reclass.clear"), key=f"colon_rc_clear_{p.parcela}"):
                        RECLASSES.pop(p.arquivo, None)
                        st.rerun()
                    st.caption(t("colon.reclass.note"))
                if p.classes_manuais:
                    st.caption(t("colon.reclass.active", items=", ".join(
                        f"{k} = {_classe(v)}" for k, v in sorted(p.classes_manuais.items()))))
            with right:
                st.markdown("**" + t("colon.sub.cohorts") + "**")
                coh = col.tabela_coortes(p)
                st.dataframe(pd.DataFrame({
                    t("colon.col.year"): coh["ano"],
                    t("colon.col.j_valid"): coh["j_valido"],
                    t("colon.col.j_none"): coh["j_sem_coorte"],
                    t("colon.col.j_impossible"): coh["j_coorte_impossivel"],
                    "N1": coh["n1"], "N2": coh["n2"],
                }), hide_index=True, width="stretch")

            # more checks: codes by year, records, species and heights
            l2, r2_ = st.columns(2, gap="large")
            with l2:
                st.markdown("**" + t("colon.sub.codes_year") + "**")
                st.dataframe(col.tabela_codigos_por_ano(p).rename(columns={"ano": t("colon.col.year")}),
                             hide_index=True, width="stretch")
            with r2_:
                st.markdown("**" + t("colon.sub.records") + "**")
                reg = col.tabela_registros(p)
                st.dataframe(pd.DataFrame({
                    t("colon.col.year"): reg["ano"], t("colon.col.records"): reg["registros"],
                    t("colon.col.new"): reg["novos"], t("colon.col.last"): reg["ultimos"],
                }), hide_index=True, width="stretch")
                st.caption(t("colon.verify.records_note"))
            l3, r3 = st.columns(2, gap="large")
            with l3:
                st.markdown("**" + t("colon.sub.species") + "**")
                esp = col.tabela_especies(p)
                st.dataframe(pd.DataFrame({
                    t("colon.col.species"): esp["especie"],
                    t("colon.col.individuals"): esp["individuos"],
                    t("colon.col.ever_juvenile"): esp["ja_jovens"],
                    t("colon.col.no_cohort"): esp["sem_coorte"],
                }), hide_index=True, width="stretch")
            with r3:
                st.markdown("**" + t("colon.sub.alerts") + "**")
                alt = col.tabela_alertas_altura(p)
                st.dataframe(pd.DataFrame({
                    t("colon.col.year"): alt["ano"], t("colon.col.j_lines"): alt["linhas_j"],
                    t("colon.col.no_height"): alt["sem_altura"],
                    t("colon.col.max_height"): alt["altura_maxima"],
                    t("colon.col.suspect"): alt["suspeitas"],
                }), hide_index=True, width="stretch")
                st.caption(t("colon.verify.alerts_note"))

            st.markdown("**" + t("colon.sub.tags") + "**")
            if p.lacres_repetidos:
                mostra = ", ".join(str(x) for x in p.lacres_repetidos[:40])
                mais = len(p.lacres_repetidos) - 40
                st.write(t("colon.tags.found", n=len(p.lacres_repetidos), tags=mostra)
                         + (t("colon.tags.more", n=mais) if mais > 0 else ""))
            else:
                st.write(t("colon.nothing"))

            st.markdown("**" + t("colon.sub.notes") + "**")
            if p.linhas_anotacao:
                st.dataframe(pd.DataFrame({
                    t("colon.col.row"): [n for n, _ in p.linhas_anotacao],
                    t("colon.col.text"): [x for _, x in p.linhas_anotacao],
                }), hide_index=True, width="stretch")
            else:
                st.write(t("colon.nothing"))
            if p.avisos:
                st.markdown("**" + t("colon.sub.warnings") + "**")
                for tipo, msg, _ in p.avisos:
                    st.warning(f"{tipo}: {msg}")

# ------------------------------------------------------------------ density
with tab_dens:
    if not CFG:
        _precisa_rodar()
    else:
        st.write(t("colon.density.intro"))
        _nota_juncao()
        por_especie = st.checkbox(t("colon.density.by_species"), key="colon_especie")
        dens = col.densidade_jovens(parcelas, incluir_sem_coorte=COM_SEM_COORTE, unidas=UNIDAS,
                                    areas=AREAS, por_especie=por_especie)
        if dens.empty:
            st.info(t("colon.density.empty"))
        else:
            dens["serie"] = (dens["parcela"] + " " + dens["especie"]) if por_especie \
                else dens["parcela"]
            st.subheader(t("colon.density.table"))
            tabela = dens.pivot_table(index="ano", columns="serie", values="ind_ha",
                                      aggfunc="first")
            st.dataframe(tabela.round(1), width="stretch")
            st.subheader(t("colon.density.counts"))
            st.dataframe(dens.pivot_table(index="ano", columns="serie", values="n",
                                          aggfunc="first"), width="stretch")
            st.caption(t("colon.density.note"))
            st.download_button(t("colon.density.download"),
                               dens.drop(columns=["serie"]).to_csv(index=False).encode("utf-8"),
                               file_name="densidade_jovens.csv", mime="text/csv")
            rel = col.densidade_relativa(parcelas, incluir_sem_coorte=COM_SEM_COORTE,
                                         unidas=UNIDAS, areas=AREAS)
            st.subheader(t("colon.density.relative"))
            st.dataframe(rel.assign(serie=rel["parcela"] + " " + rel["especie"]).pivot_table(
                index="ano", columns="serie", values="relativa", aggfunc="first").round(1),
                width="stretch")
            st.caption(t("colon.density.relative_note"))

# ------------------------------------------------------------------ height
with tab_alt:
    if not CFG:
        _precisa_rodar()
    else:
        st.write(t("colon.height.intro"))
        _nota_juncao()
        est = _altura("colon_h")
        if est.empty:
            st.info(t("colon.height.empty"))
        else:
            nomes = {"parcela": t("colon.col.plot"), "ano": t("colon.col.year"),
                     "especie": t("colon.col.species"), "classe": t("colon.col.class"),
                     "n": "N", "media": t("colon.height.mean"), "dp": t("colon.height.sd"),
                     "minimo": t("colon.height.min"), "maximo": t("colon.height.max")}
            vista = est.copy()
            if "classe" in vista:
                vista["classe"] = vista["classe"].map(lambda c: t(f"colon.cls.{c}"))
            st.dataframe(vista.rename(columns=nomes).round(1), hide_index=True, width="stretch")
            st.caption(t("colon.height.note"))
            st.download_button(t("colon.density.download"), est.to_csv(index=False).encode("utf-8"),
                               file_name="altura.csv", mime="text/csv", key="colon_h_dl")

# ------------------------------------------------------------------ charts
with tab_graf:
    if not CFG:
        _precisa_rodar()
    else:
        _nota_juncao()
        g_dens_t, g_idade_t, g_alt_t, g_coorte_t, g_jim_t = st.tabs([
            t("colon.gtab.density"), t("colon.gtab.age"), t("colon.gtab.height"),
            t("colon.gtab.cohort"), t("colon.gtab.jimenez")])
        d_all = col.densidade_jovens(parcelas, incluir_sem_coorte=COM_SEM_COORTE,
                                     unidas=UNIDAS, areas=AREAS)

        # --- density: curve per plot and species composition
        with g_dens_t:
            ui.report_section(t("colon.gtab.density"))
            if d_all.empty:
                st.info(t("colon.density.empty"))
            else:
                g1, g2 = st.columns(2)
                g_log = g1.checkbox(t("colon.chart.log"), key="colon_g_log")
                series = sorted(d_all["parcela"].unique())
                escolha = g2.multiselect(t("colon.chart.plots"), series, default=series,
                                         key="colon_g_pl")
                g_dens = d_all[d_all["parcela"].isin(escolha)]
                if g_dens.empty:
                    st.info(t("colon.density.empty"))
                else:
                    ui.show(st, cc.fig_curva_densidade(g_dens, estilos, LANG, g_log),
                            "colon_dens", estilos)
                st.divider()
                g_rel = col.densidade_relativa(parcelas, incluir_sem_coorte=COM_SEM_COORTE,
                                               unidas=UNIDAS, areas=AREAS)
                if g_rel.empty:
                    st.info(t("colon.density.empty"))
                else:
                    s1, s2 = st.columns(2)
                    plot_g = s1.selectbox(t("colon.chart.plot"), sorted(g_rel["parcela"].unique()),
                                          key="colon_g_plot")
                    g_pct = s2.radio(t("colon.chart.metric"), ("relative", "density"),
                                     horizontal=True, key="colon_g_metric",
                                     format_func=lambda k: t(f"colon.chart.metric_{k}")) == "relative"
                    ui.show(st, cc.fig_composicao(g_rel, estilos, plot_g, g_pct, LANG),
                            "colon_esp", estilos)
                st.caption(t("colon.chart.reference_note"))

        # --- age: log-linear fit
        with g_idade_t:
            ui.report_section(t("colon.gtab.age"))
            if d_all.empty:
                st.info(t("colon.density.empty"))
            else:
                st.caption(t("colon.chart.start_hint"))
                series_r = sorted(d_all["parcela"].unique())
                inicio = {}
                caixas = st.columns(5)
                for i_q, q in enumerate(series_r):
                    inicio[q] = caixas[i_q % 5].number_input(
                        t("colon.chart.start_year", plot=q), min_value=0, max_value=2100,
                        value=col.ano_estabelecimento(q), step=1, key=f"colon_inicio_{q}")
                r_df = col.com_idade(d_all, inicio)
                modo_r = st.radio(t("colon.chart.fit_mode"), ("all", "plot"), horizontal=True,
                                  key="colon_fit_modo",
                                  format_func=lambda k: t(f"colon.chart.fit_mode_{k}"))
                regs = ({"": col.regressao_log_linear(r_df)} if modo_r == "all" else
                        {q: col.regressao_log_linear(r_df[r_df["parcela"] == q])
                         for q in sorted(r_df["parcela"].unique())})
                regs = {k: v for k, v in regs.items() if v}
                if not regs:
                    st.info(t("colon.chart.regression_need"))
                else:
                    ui.show(st, cc.fig_regressao(r_df, regs, estilos, LANG), "colon_reg", estilos)
                    for rotulo, r in regs.items():
                        st.caption(t("colon.chart.regression_equation",
                                     label=(f"{rotulo}: " if rotulo else ""),
                                     a=ui.num(r["a"], 3, LANG), b=ui.num(r["b"], 3, LANG),
                                     se=ui.num(r["ep_b"], 3, LANG), r2=ui.num(r["r2"], 3, LANG),
                                     n=r["n"]))
                    st.caption(t("colon.chart.regression_note"))

        # --- height
        with g_alt_t:
            ui.report_section(t("colon.gtab.height"))
            est_g = _altura("colon_gh")
            if est_g.empty:
                st.info(t("colon.height.empty"))
            else:
                st.caption(t("colon.chart.height_note"))
                ui.show(st, cc.fig_altura(est_g, estilos, LANG), "colon_alt", estilos)

        # --- count by year, stacked by cohort, species or item
        with g_coorte_t:
            ui.report_section(t("colon.gtab.cohort"))
            st.write(t("colon.count.intro"))
            codigos_ach = sorted({c for p in parcelas for c in p.codigos})
            classes_ach = sorted({col.classifica(c, p.classes_manuais) for p in parcelas
                                  for c in p.codigos} - {"vazio"})
            k1, k2, k3 = st.columns(3)
            por = k1.radio(t("colon.count.by"), ("classe", "codigo"), horizontal=True,
                           key="colon_ct_por", format_func=lambda k: t(f"colon.count.by_{k}"))
            if por == "classe":
                opcoes = classes_ach
                padrao = [c for c in ("jovem",) if c in opcoes]
                fmt = lambda c: t(f"colon.cls.{c}")
            else:
                opcoes, padrao, fmt = codigos_ach, [c for c in ("J",) if c in codigos_ach], str
            itens = k2.multiselect(t("colon.count.items"), opcoes, default=padrao,
                                   key=f"colon_ct_itens_{por}", format_func=fmt)
            empilha = k3.radio(t("colon.count.stack"), ("coorte", "especie", "item", "nenhum"),
                               horizontal=True, key="colon_ct_pilha",
                               format_func=lambda k: t(f"colon.count.stack_{k}"))
            agrupar = por if empilha == "item" else empilha
            cont = col.contagem_por_ano(parcelas, itens, por=por, agrupar=agrupar, unidas=UNIDAS)
            if cont.empty:
                st.info(t("colon.count.empty"))
            else:
                m1, m2 = st.columns(2)
                alvo = m1.selectbox(t("colon.count.plot"), ["__todas__"] + sorted(cont["parcela"].unique()),
                                    key="colon_ct_parcela",
                                    format_func=lambda v: t("colon.count.all_plots") if v == "__todas__" else v)
                pct = m2.checkbox(t("colon.count.percent"), key="colon_ct_pct")
                vista = cont if alvo == "__todas__" else cont[cont["parcela"] == alvo]
                ui.show(st, cc.fig_contagem(vista, estilos, LANG, agrupar, pct), "colon_cont",
                        estilos)
                st.caption(t("colon.count.note"))
                tab_c = vista.groupby(["ano", "grupo"])["n"].sum().unstack(fill_value=0)
                st.dataframe(tab_c, width="stretch")
                st.download_button(t("colon.density.download"),
                                   vista.to_csv(index=False).encode("utf-8"),
                                   file_name="contagem_por_ano.csv", mime="text/csv",
                                   key="colon_ct_dl")

        # --- Jimenez schematic next to the observed density
        with g_jim_t:
            ui.report_section(t("colon.gtab.jimenez"))
            st.caption(t("colon.chart.schema_note"))
            s1, s2 = st.columns(2)
            with s1:
                ui.show(st, cc.fig_esquema(estilos, LANG), "colon_schema", estilos)
            with s2:
                if d_all.empty:
                    st.info(t("colon.density.empty"))
                else:
                    ui.show(st, cc.fig_curva_densidade(d_all, estilos, LANG),
                            "colon_schema_obs", estilos)
            st.caption(t("colon.chart.reference_note"))

# ------------------------------------------------------------------ export
with tab_exp:
    st.write(t("colon.export.intro"))
    e1, e2 = st.columns(2)
    formato = e1.radio(t("colon.export.format"), ("longo", "largo"), key="colon_formato",
                       format_func=lambda k: t(f"colon.export.format_{k}"))
    so_usadas = e2.checkbox(t("colon.export.only_used"), value=False, key="colon_usadas",
                            disabled=formato == "largo")
    longo, largo = _tabelas_limpas(parcelas, _SIG)
    mostrado = largo if formato == "largo" else (
        longo[longo["usada_na_analise"]] if so_usadas else longo)
    st.subheader(t("colon.export.preview", n=len(mostrado)))
    vis = mostrado.head(500).apply(           # mixed number/text columns (cohort "<1998", "?")
        lambda c: c.map(lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))
        if c.dtype == object else c)
    st.dataframe(vis, hide_index=True, width="stretch")
    st.caption(t("colon.export.note"))
    from manguetree import report as rep
    if CFG:
        ui.pdf_block(st, "colon", lambda figs: rep.colonization_report(
            [col.resumo(p) for p in parcelas],
            col.densidade_jovens(parcelas, incluir_sem_coorte=COM_SEM_COORTE, unidas=UNIDAS, areas=AREAS),
            lang=LANG, figures=figs),
            "MangueTREE_colonizacao.pdf", (_SIG, COM_SEM_COORTE, LANG))
    d1, d2 = st.columns(2)
    d1.download_button(t("colon.export.csv"), _csv(mostrado, (_SIG, formato, so_usadas)),
                       file_name=f"colonizacao_{formato}.csv", mime="text/csv", key="colon_csv")
    # the Excel file is big: it is built only when asked for
    if d2.button(t("colon.export.prepare_xlsx"), key="colon_xlsx_prep"):
        _buf = io.BytesIO()
        with st.spinner(t("colon.export.preparing")):
            with pd.ExcelWriter(_buf, engine="openpyxl") as _xw:
                longo.to_excel(_xw, sheet_name=t("colon.export.sheet_long"), index=False)
                largo.to_excel(_xw, sheet_name=t("colon.export.sheet_wide"), index=False)
                pd.concat([col.tabela_blocos(p).assign(parcela=p.parcela)
                           for p in parcelas]).to_excel(
                    _xw, sheet_name=t("colon.export.sheet_blocks"), index=False)
        st.session_state["colon_xlsx_bytes"] = (_SIG, _buf.getvalue())
    _pronto = st.session_state.get("colon_xlsx_bytes")
    if _pronto and _pronto[0] == _SIG:
        d2.download_button(t("colon.export.xlsx"), _pronto[1], file_name="colonizacao_limpa.xlsx",
                           key="colon_xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
