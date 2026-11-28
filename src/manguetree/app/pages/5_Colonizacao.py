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
from manguetree import exportar
from manguetree import i18n
from manguetree import nomes as arq_nome
from manguetree.i18n import t

st.set_page_config(layout="wide", page_title=t("colon.page_title"), page_icon=ui.PAGE_ICON)
LANG = i18n.language_selector(st.sidebar)        # first on every page (see i18n.py)
arq_nome.definir(t("file.colonization"))             # file names: Colonizacao_...
ui.sidebar_nav(st.sidebar, tab_icons=("evolucao", "verificacao", "exportar"),
               subtab_icons=("densidade", "altura", "idade_parcela", "dinamica", "coorte", "curva_jimenez"))
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
    except col.ErroLeitura as e:
        erros.append(t("colon.read_error", file=up.name, error=t(f"colon.err.{e.codigo}", **e.params)))
    except Exception as e:
        erros.append(t("colon.read_error", file=up.name, error=str(e)))
# the same plot in two files: only the first one is used (area, corrections and charts
# are per plot, so two copies would collide)
_por_letra = {}
for p in parcelas:
    if p.parcela in _por_letra:
        erros.append(t("colon.dup_plot", plot=p.parcela, first=_por_letra[p.parcela].arquivo,
                       file=p.arquivo))
    else:
        _por_letra[p.parcela] = p
parcelas = list(_por_letra.values())
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


def _limpa_na_unidade(df):
    """Height columns of the clean tables ("altura_cm", "2005 altura_cm") in the chosen unit."""
    cols = [c for c in df.columns if str(c).endswith("altura_cm")]
    if not cols or UH == "cm":
        return df
    out = df.copy()
    out[cols] = out[cols].astype(float) * ui._un.fator_cm(UH)
    return out.rename(columns={c: str(c).replace("altura_cm", f"altura_{UH}") for c in cols})


# column names of the tables shown and saved (internal names -> catalog keys)
_COLS = {"parcela": "colon.col.plot", "ano": "colon.col.year", "especie": "colon.col.species",
         "classe": "colon.col.class", "codigo": "colon.col.code", "membros": "colon.col.members",
         "n_parcelas": "colon.col.n_plots", "incompleta": "colon.col.incomplete",
         "grupo": "colon.exp.group", "area_ha": "colon.exp.area_ha",
         "ind_ha": "colon.chart.density_axis", "relativa": "colon.exp.relative",
         "coleta": "colon.height.collection", "data": "colon.height.date",
         "coluna": "colon.col.column", "usada": "colon.height.used", "individuo": "colon.exp.individual",
         "linha": "colon.col.row", "lado": "colon.exp.side", "lacres": "colon.exp.tags",
         "coorte": "colon.exp.cohort", "categoria_coorte": "colon.exp.cohort_category",
         "troncos_vivos": "colon.exp.live_trunks", "n_jovens": "colon.exp.n_juveniles",
         "usada_na_analise": "colon.exp.used", "bloco": "colon.col.block", "rotulo": "colon.col.label",
         "origem": "colon.col.origin", "coleta_altura": "colon.col.height_column",
         "registros": "colon.col.records"}
_COLS_ALT = {"media": "colon.height.mean", "altura": "colon.height.mean", "dp": "colon.height.sd",
             "minimo": "colon.height.min", "maximo": "colon.height.max"}


def _traduz(df, agrupar=None):
    """A table of this page with the column names (and units) and the coded values (class,
    cohort category, collection, species, group) in the language of the screen."""
    out = df.copy()
    if "classe" in out:
        out["classe"] = out["classe"].map(lambda c: t(f"colon.cls.{c}") if isinstance(c, str) and c else c)
    if "categoria_coorte" in out:
        out["categoria_coorte"] = out["categoria_coorte"].map(
            lambda c: t(f"colon.exp.cat_{c}") if isinstance(c, str) and c else c)
    for c in ("coleta", "rotulo"):
        if c in out:
            out[c] = out[c].map(lambda v: col.traduz_rotulo(v) if isinstance(v, str) else v)
    if "origem" in out:
        out["origem"] = out["origem"].map(_origem)
    if "especie" in out:
        out["especie"] = out["especie"].map(lambda e: _esp(col.SEM_ESPECIE if str(e).strip() in ("", "?") else e))
    if "grupo" in out and agrupar:
        out["grupo"] = out["grupo"].map(lambda g: cc.nome_grupo(g, agrupar, LANG))
    if "usada" in out:
        out["usada"] = out["usada"].map(lambda u: "●" if u == True else "")   # noqa: E712 (numpy bools)
    nomes = {c: t(k) for c, k in _COLS.items()}
    nomes.update({c: t(k, u=UH) for c, k in _COLS_ALT.items()})
    nomes.update({"n": "N", "n_altura": "N"})
    for c in out.columns:                      # clean tables: "altura_m", "2005 codigo"...
        partes = str(c).split(" ", 1)
        ano, nome = (partes[0], partes[1]) if len(partes) == 2 and partes[0].isdigit() else ("", str(c))
        if nome.startswith("altura_"):
            novo = t("colon.exp.height", u=nome.split("_", 1)[1])
        elif nome == "codigo":
            novo = t("colon.col.code")
        else:
            continue
        nomes[c] = f"{ano} {novo}".strip()
    return out.rename(columns=nomes)


def _casas(df):
    """Heights in metres keep three decimals (24,25 cm -> 0,243 m, not 0,24 m)."""
    return {c: 3 for c in df.columns if UH == "m" and str(c).endswith("(m)")}


@st.cache_data(show_spinner=False)
def _bytes_tab(_df, chave, formato, lang):
    return exportar.bytes_tabela(_df, formato, lang)


def _classe(cl):
    return t(f"colon.class.{cl}")


def _esp(e):
    """Species code as shown in the tables ("?" is the label of the ones without species)."""
    return t("colon.species.none") if e == col.SEM_ESPECIE else e


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
            value=float(col.AREAS_M2.get(p.parcela, col.AREA_PADRAO_M2)), step=1.0,
            key=f"colon_area_{p.parcela}")
        if p.parcela not in col.AREAS_M2:
            st.caption(t("colon.area_unknown", plot=p.parcela, area=ui.num(col.AREA_PADRAO_M2, 0, LANG)))
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
VERSAO = st.radio(t("colon.cfg.version"), ("com", "sem"), key="colon_versao", horizontal=True,
                  format_func=_versao, help=t("colon.cfg.version_help"))
COM_SEM_COORTE = VERSAO == "com"
# joined plots: a year with data of only part of the plots can be hidden (live control)
OCULTAR = bool(CFG and UNIDAS and st.checkbox(
    t("colon.cfg.hide_incomplete"), key="colon_ocultar", help=t("colon.cfg.hide_incomplete_help")))


def _aviso_incompletas(df):
    """Says which years of a joined plot hold data of only part of its plots."""
    for uniao, grupos in col.lista_incompletas(df).items():
        for membros, anos in grupos.items():
            st.caption(t("colon.warn.incomplete", union=uniao, years=", ".join(map(str, anos)),
                         plots=membros.replace("+", " + ")))


UH = ui.altura_unidade()                       # unit of the heights shown (m or cm)
COLS_ALT = ("media", "dp", "minimo", "maximo")


def _na_unidade(df, cols=COLS_ALT):
    """Heights of the colonization tables are typed and calculated in cm: shown in ``UH``."""
    cols = [c for c in cols if c in df.columns]
    if not cols or UH == "cm":
        return df
    out = df.copy()
    out[cols] = out[cols].astype(float) * ui._un.fator_cm(UH)
    return out


def _selecao_altura():
    """Collections the user picked by hand ({(plot, year): (block, column)}), kept in the widget
    state of the picker in the height tab; a year not picked follows the automatic rule."""
    sel = {}
    for k, v in st.session_state.items():
        if isinstance(k, str) and k.startswith("colon_sel|") and isinstance(v, tuple):
            _, parc, ano = k.split("|")
            sel[(parc, int(ano))] = v
    return sel


def _modo_altura():
    return st.session_state.get("colon_modo_altura", "mais_dados")


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
    return _na_unidade(col.estatistica_altura(
        parcelas, incluir_sem_coorte=COM_SEM_COORTE, unidas=UNIDAS, por_especie=por_esp,
        minimo_cm=col.ALTURA_1M_CM if um_m else None, classes=classes or ("jovem",),
        por_classe=por_classe and len(classes) > 1, ocultar_incompletas=OCULTAR,
        selecao=_selecao_altura(), modo=_modo_altura()))


def _painel_coletas():
    """Mean, SD and N of every collection of the years that have more than one, and the choice of
    the one that goes to the statistics and charts (automatic unless picked)."""
    classes = st.session_state.get("colon_h_classes") or ["jovem"]
    tc = col.tabela_alturas_coletas(
        parcelas, incluir_sem_coorte=COM_SEM_COORTE, classes=classes,
        selecao=_selecao_altura(), modo=_modo_altura(),
        minimo_cm=col.ALTURA_1M_CM if st.session_state.get("colon_h_1m") else None)
    multi = _na_unidade(tc[tc["varias"]] if not tc.empty else tc)
    if multi.empty:
        return
    with st.expander(t("colon.height.collections"), expanded=False):
        st.caption(t("colon.height.collections_help"))
        nomes = {"parcela": t("colon.col.plot"), "ano": t("colon.col.year"),
                 "coleta": t("colon.height.collection"), "data": t("colon.height.date"),
                 "coluna": t("colon.col.height_column"), "n": "N",
                 "media": t("colon.height.mean", u=UH), "dp": t("colon.height.sd", u=UH),
                 "minimo": t("colon.height.min", u=UH), "maximo": t("colon.height.max", u=UH),
                 "usada": t("colon.height.used")}
        vista = _traduz(multi.drop(columns=["bloco", "varias", "chave"]))
        st.dataframe(ui.estilo2(vista, LANG, casas=_casas(vista)), hide_index=True, width="stretch")
        exportar.botoes(st, _traduz(multi.drop(columns=["varias", "chave"])), arq_nome.arquivo(t("file.colon_collections")),
                        "exp_colon_coletas", LANG, titulo=t("colon.height.collections"))
        for (parc, ano), g in multi.groupby(["parcela", "ano"]):
            opcoes = ["auto"] + list(g["chave"])
            rot = {c: f"{col.traduz_rotulo(r.coleta)} (col. {r.coluna}, N={r.n})"
                   for c, r in zip(g["chave"], g.itertuples())}
            st.selectbox(f"{parc} {ano}", opcoes, key=f"colon_sel|{parc}|{ano}",
                         format_func=lambda c, rot=rot: t("colon.height.auto")
                         if c == "auto" else rot[c])


tab_graf, tab_verif, tab_exp = st.tabs([
    t("colon.tab.charts"), t("colon.tab.verify"), t("colon.tab.export")])
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
        t("colon.col.years"): [t("colon.years_range", a=r["anos"][0], b=r["anos"][1])
                               if r["anos"] else "-" for r in resumos],
        t("colon.col.species_list"): [", ".join(map(_esp, r["especies"])) or "-" for r in resumos],
        t("colon.col.area_used"): [(AREAS if CFG else areas_in)[r["parcela"]] for r in resumos],
        t("colon.col.no_cohort"): [r["sem_coorte"] for r in resumos],
        t("colon.col.excluded"): [r["excluidos"] for r in resumos],
        t("colon.col.repeated_tags"): [r["lacres_repetidos"] for r in resumos],
        t("colon.col.notes"): [r["anotacoes"] for r in resumos],
        t("colon.col.unknown_codes"): [", ".join(r["codigos_desconhecidos"]) or "-"
                                       for r in resumos],
    }), hide_index=True, width="stretch")
    st.caption(t("colon.verify.excluded_note"))
    _areas_v = AREAS if CFG else areas_in
    _sem_area = [p.parcela for p in parcelas if p.parcela not in col.AREAS_M2
                 and float(_areas_v[p.parcela]) == col.AREA_PADRAO_M2]
    if _sem_area:
        st.warning(t("colon.verify.area_unknown", plots=", ".join(_sem_area),
                     area=ui.num(col.AREA_PADRAO_M2, 0, LANG)))

    for p in parcelas:
        with st.expander(t("colon.plot_expander", plot=p.parcela, file=p.arquivo),
                         expanded=len(parcelas) == 1):
            # collections and years
            st.markdown("**" + t("colon.sub.blocks") + "**")
            blocos = col.tabela_blocos(p)
            st.dataframe(pd.DataFrame({
                t("colon.col.block"): blocos["bloco"] + 1,
                t("colon.col.label"): blocos["rotulo"].map(col.traduz_rotulo),
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
                    t("colon.col.species"): esp["especie"].map(_esp),
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
                    t("colon.col.max_height", u=UH): alt["altura_maxima"] * ui._un.fator_cm(UH),
                    t("colon.col.suspect"): alt["suspeitas"],
                }), hide_index=True, width="stretch")
                st.caption(t("colon.verify.alerts_note"))

            # every odd cell, with row and column of the entry sheet: nothing leaves the
            # calculation, the spreadsheet is what gets corrected
            st.markdown("**" + t("colon.sub.to_fix") + "**")
            pend = col.tabela_pendencias(p)
            if pend.empty:
                st.write(t("colon.nothing"))
            else:
                def _valor(r):
                    if r.problema == "altura":
                        v = f"{float(r.valor):g}"          # 707.7 -> "707,7"; 700.0 -> "700"
                        return (v.replace(".", ",") if LANG == "pt" else v) + " cm"
                    if r.problema == "sem_especie":
                        return r.valor or t("colon.to_fix.blank")
                    return str(r.valor)
                st.dataframe(pd.DataFrame({
                    t("colon.col.row"): pend["linha"],
                    t("colon.col.column"): pend["coluna"],
                    t("colon.col.tag"): pend["lacre"],
                    t("colon.col.year"): pend["ano"],
                    t("colon.col.problem"): pend["problema"].map(lambda k: t(f"colon.to_fix.{k}")),
                    t("colon.col.value"): [_valor(r) for r in pend.itertuples()],
                }), hide_index=True, width="stretch")
                st.caption(t("colon.to_fix.note"))

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
                for codigo, prm, _ in p.avisos:
                    st.warning(t(f"colon.warn.{codigo}", **{
                        k: col.traduz_rotulo(v) if k in ("bloco", "a", "b") else v
                        for k, v in prm.items()}))

# ------------------------------------------------------------------ charts
with tab_graf:
    if not CFG:
        _precisa_rodar()
    else:
        _nota_juncao()
        g_dens_t, g_alt_t, g_idade_t, g_cruz_t, g_coorte_t, g_jim_t = st.tabs([
            t("colon.gtab.density"), t("colon.gtab.height"), t("colon.gtab.age"),
            t("colon.gtab.cross"), t("colon.gtab.cohort"), t("colon.gtab.jimenez")])
        d_all = col.densidade_jovens(parcelas, incluir_sem_coorte=COM_SEM_COORTE,
                                     unidas=UNIDAS, areas=AREAS, ocultar_incompletas=OCULTAR)

        # --- density: curve per plot, species composition, then the tables
        with g_dens_t:
            ui.report_section(t("colon.gtab.density"))
            if d_all.empty:
                st.info(t("colon.density.empty"))
            else:
                series = sorted(d_all["parcela"].unique())
                bar = ui.barra(st)
                escolha = bar.multiselect(t("colon.chart.plots"), series, default=series,
                                          key="colon_g_pl")
                tipo_d = bar.selectbox(t("temporal.chart"), ("line", "markers", "bar", "hbar"),
                                       key="colon_dens_tipo", width=200,
                                       format_func=lambda k: t(f"temporal.chart.{k}"))
                g_log = bar.checkbox(t("colon.chart.log"), key="colon_g_log")
                g_dens = d_all[d_all["parcela"].isin(escolha)]
                if g_dens.empty:
                    st.info(t("colon.density.empty"))
                else:
                    ui.show(st, cc.fig_curva_densidade(g_dens, estilos, LANG, g_log, tipo_d),
                            "colon_dens", estilos, barra=bar)
                    _aviso_incompletas(g_dens)
                g_rel = col.densidade_relativa(parcelas, incluir_sem_coorte=COM_SEM_COORTE,
                                               unidas=UNIDAS, areas=AREAS,
                                               ocultar_incompletas=OCULTAR)
                if g_rel.empty:
                    st.info(t("colon.density.empty"))
                else:
                    st.divider()
                    bar2 = ui.barra(st)
                    plot_g = bar2.selectbox(t("colon.chart.plot"), sorted(g_rel["parcela"].unique()),
                                            key="colon_g_plot", width=220)
                    g_pct = bar2.selectbox(t("colon.chart.metric"), ("relative", "density"),
                                           key="colon_g_metric", width=240,
                                           format_func=lambda k: t(f"colon.chart.metric_{k}")) == "relative"
                    ui.show(st, cc.fig_composicao(g_rel, estilos, plot_g, g_pct, LANG),
                            "colon_esp", estilos, barra=bar2)
                st.caption(t("colon.chart.reference_note"))
                st.divider()
                st.write(t("colon.density.intro"))
                por_especie = st.checkbox(t("colon.density.by_species"), key="colon_especie")
                dens = col.densidade_jovens(parcelas, incluir_sem_coorte=COM_SEM_COORTE, unidas=UNIDAS,
                                            areas=AREAS, por_especie=por_especie,
                                            ocultar_incompletas=OCULTAR)
                dens = dens[dens["parcela"].isin(escolha)]      # same plots as the chart
                if not dens.empty:
                    dens["serie"] = (dens["parcela"] + " " + dens["especie"].map(_esp)) if por_especie \
                        else dens["parcela"]
                    st.subheader(t("colon.density.table"))
                    _ano = t("colon.col.year")
                    tabela = dens.pivot_table(index="ano", columns="serie", values="ind_ha",
                                              aggfunc="first").rename_axis(index=_ano, columns=None)
                    st.dataframe(ui.estilo2(tabela, LANG), width="stretch")
                    st.subheader(t("colon.density.counts"))
                    st.dataframe(dens.pivot_table(index="ano", columns="serie", values="n",
                                                  aggfunc="first").astype("Int64").rename_axis(
                                                      index=_ano, columns=None), width="stretch")
                    st.caption(t("colon.density.note"))
                    _aviso_incompletas(dens)
                    exportar.botoes(st, _traduz(dens.drop(columns=["serie"])), arq_nome.arquivo(t("file.colon_density")), "exp_colon_dens",
                                    LANG, titulo=t("colon.density.download"))
                    rel = col.densidade_relativa(parcelas, incluir_sem_coorte=COM_SEM_COORTE,
                                                 unidas=UNIDAS, areas=AREAS,
                                                 ocultar_incompletas=OCULTAR)
                    rel = rel[rel["parcela"].isin(escolha)]
                    st.subheader(t("colon.density.relative"))
                    st.dataframe(ui.estilo2(rel.assign(serie=rel["parcela"] + " " + rel["especie"].map(_esp)).pivot_table(
                        index="ano", columns="serie", values="relativa", aggfunc="first").rename_axis(
                            index=_ano, columns=None), LANG),
                        width="stretch")
                    st.caption(t("colon.density.relative_note"))

        # --- height: chart first, then the table of the collections used
        with g_alt_t:
            ui.report_section(t("colon.gtab.height"))
            bar = ui.barra(st)
            bar.selectbox(t("colon.height.mode"), ["mais_dados", "ultima"], key="colon_modo_altura",
                          width=300, format_func=lambda m: t(f"colon.height.mode_{m}"),
                          help=t("colon.height.mode_help"))
            tipo_a = bar.selectbox(t("temporal.chart"), ui.SERIES_CHARTS + ("hbar_sd",), index=4, key="colon_alt_tipo",
                                   width=250, format_func=lambda k: t(f"temporal.chart.{k}"))
            est = _altura("colon_h")
            if est.empty:
                st.info(t("colon.height.empty"))
            else:
                st.caption(t("colon.chart.height_note"))
                ui.show(st, cc.fig_altura(est, estilos, LANG, tipo_a), "colon_alt", estilos, barra=bar)
                _aviso_incompletas(est)
                _painel_coletas()
                vista = _traduz(est.drop(columns=["n_parcelas"], errors="ignore"))
                st.dataframe(ui.estilo2(vista, LANG, casas=_casas(vista)), hide_index=True,
                             width="stretch")
                st.caption(t("colon.height.note"))
                exportar.botoes(st, _traduz(est), arq_nome.arquivo(t("file.colon_height")), "exp_colon_alt", LANG,
                                titulo=t("colon.density.download"))

        # --- age: density against plot age (square axes, 0 to 10 years), optional fitted curve
        with g_idade_t:
            ui.report_section(t("colon.gtab.age"))
            if d_all.empty:
                st.info(t("colon.density.empty"))
            else:
                series_r = sorted(d_all["parcela"].unique())
                inicio = {}
                with st.expander(t("colon.chart.start_title")):
                    st.caption(t("colon.chart.start_hint"))
                    caixas = st.columns(5)
                    for i_q, q in enumerate(series_r):
                        inicio[q] = caixas[i_q % 5].number_input(
                            t("colon.chart.start_year", plot=q), min_value=0, max_value=2100,
                            value=col.ano_estabelecimento(q), step=1, key=f"colon_inicio_{q}")
                r_df = col.com_idade(d_all, inicio)
                _fora = [q for q in series_r if not inicio.get(q)]
                if _fora:                       # no start year: the plot cannot have an age
                    st.caption(t("colon.chart.no_start", plots=", ".join(_fora)))
                bar = ui.barra(st)
                tipo_i = bar.selectbox(t("temporal.chart"), ("markers", "line", "bar", "hbar"),
                                       key="colon_idade_tipo", width=220,
                                       format_func=lambda k: t(f"temporal.chart.{k}"))
                log_i = bar.selectbox(t("colon.chart.y_scale"), ("linear", "log"), key="colon_idade_escala",
                                      width=130, format_func=lambda k: t(f"colon.chart.scale_{k}")) == "log"
                if r_df[(r_df["idade"] > 0) & (r_df["ind_ha"] > 0)].empty:
                    st.info(t("colon.chart.regression_need"))
                else:
                    c_graf, c_dir = st.columns([3, 2], gap="medium")
                    # fitted curve: its switch, the fit and the equations sit to the right of the chart
                    curva = c_dir.checkbox(t("colon.chart.show_fit"), value=True, key="colon_idade_curva")
                    modo_r = c_dir.selectbox(t("colon.chart.fit_mode"), ("all", "plot"), key="colon_fit_modo",
                                             disabled=not curva,
                                             format_func=lambda k: t(f"colon.chart.fit_mode_{k}"))
                    regs = ({"": col.regressao_log_linear(r_df)} if modo_r == "all" else
                            {q: col.regressao_log_linear(r_df[r_df["parcela"] == q])
                             for q in sorted(r_df["parcela"].unique())})
                    regs = {k: v for k, v in regs.items() if v}
                    larg, alt_ = cc.TAMANHO_IDADE
                    ui.show(c_graf, cc.fig_idade(r_df, regs, estilos, LANG, tipo_i, log_i, curva),
                            "colon_reg", {**estilos, "width": larg, "height": alt_}, barra=bar)
                    with c_dir:
                        _aviso_incompletas(r_df)
                        if curva and not regs:
                            st.info(t("colon.chart.regression_need"))
                        for rotulo, r in (regs.items() if curva else ()):
                            st.caption(t("colon.chart.regression_equation",
                                         label=(f"{rotulo}: " if rotulo else ""),
                                         a=ui.num(r["a"], 3, LANG), b=ui.num(r["b"], 3, LANG),
                                         c=ui.num(float(__import__("math").exp(r["a"])), 1, LANG),
                                         se=ui.num(r["ep_b"], 3, LANG), r2=ui.num(r["r2"], 3, LANG),
                                         n=r["n"]))
                        if curva:
                            st.caption(t("colon.chart.regression_note"))

        # --- height crossed with density: lines over the years or scatter plot with equation
        with g_cruz_t:
            ui.report_section(t("colon.gtab.cross"))
            st.write(t("colon.cross.intro"))
            alt_c = _na_unidade(col.estatistica_altura(
                parcelas, incluir_sem_coorte=COM_SEM_COORTE, unidas=UNIDAS,
                ocultar_incompletas=OCULTAR, selecao=_selecao_altura(), modo=_modo_altura()))
            cruz = col.cruzar_altura_densidade(d_all, alt_c)
            if cruz.empty:
                st.info(t("colon.cross.need"))
            else:
                series_c = sorted(cruz["parcela"].unique())
                bar = ui.barra(st)
                forma = bar.selectbox(t("colon.cross.mode"), ("line", "xy"), key="colon_cruz_modo",
                                      width=200, format_func=lambda k: t(f"colon.cross.mode_{k}"))
                eixo_x = bar.selectbox(t("colon.cross.x_axis"), ("altura", "densidade"),
                                       key="colon_cruz_x", width=150, disabled=forma == "line",
                                       format_func=lambda k: t(f"colon.cross.x_{k}"))
                esc_c = bar.multiselect(t("colon.chart.plots"), series_c, default=series_c,
                                        key="colon_cruz_pl")
                c_log = bar.checkbox(t("colon.chart.log"), key="colon_cruz_log")
                cruz_g = cruz[cruz["parcela"].isin(esc_c)]
                if cruz_g.empty:
                    st.info(t("colon.cross.need"))
                else:
                    fig_c = (cc.fig_cruzamento_linha(cruz_g, estilos, LANG, c_log) if forma == "line"
                             else cc.fig_cruzamento_xy(cruz_g, estilos, LANG, eixo_x, c_log))
                    ui.show(st, fig_c, "colon_cruz", estilos, barra=bar)
                    _aviso_incompletas(cruz_g)
                    nx, ny = ((t("colon.cross.x_altura").lower(), t("colon.cross.x_densidade").lower())
                              if eixo_x == "altura" else
                              (t("colon.cross.x_densidade").lower(), t("colon.cross.x_altura").lower()))
                    for q, sub in cruz_g.groupby("parcela"):
                        xs, ys = ((sub["altura"], sub["ind_ha"]) if eixo_x == "altura"
                                  else (sub["ind_ha"], sub["altura"]))
                        r = col.regressao_linear(xs, ys)
                        if r is None:
                            continue
                        if forma == "line":
                            st.caption(t("colon.cross.corr", plot=q, r=ui.num(r["r"], 2, LANG), n=r["n"]))
                        else:
                            p_txt = "< 0,001" if r["p"] < 0.001 and LANG == "pt" else \
                                "< 0.001" if r["p"] < 0.001 else ui.num(r["p"], 3, LANG)
                            st.markdown(t("colon.cross.equation", plot=q, y=ny, x=nx,
                                          a=ui.num(r["a"], 3, LANG),
                                          sinal="+" if r["b"] >= 0 else "-",
                                          b=ui.num(abs(r["b"]), 3, LANG), r=ui.num(r["r"], 3, LANG),
                                          p=p_txt, r2=ui.num(r["r2"], 3, LANG), n=r["n"]))
                    st.caption(t("colon.cross.note"))
                    nomes_c = {"parcela": t("colon.col.plot"), "ano": t("colon.col.year"),
                               "ind_ha": t("colon.chart.density_axis"),
                               "altura": t("colon.height.mean", u=UH),
                               "dp": t("colon.height.sd", u=UH), "n_altura": "N",
                               "membros": t("colon.col.members"),
                               "incompleta": t("colon.col.incomplete")}
                    st.dataframe(ui.estilo2(cruz_g.rename(columns=nomes_c), LANG),
                                 hide_index=True, width="stretch")
                    exportar.botoes(st, _traduz(cruz_g), arq_nome.arquivo(t("file.colon_cross")), "exp_colon_cruz",
                                    LANG, titulo=t("colon.gtab.cross"))

        # --- count by year, stacked by cohort, species or item
        with g_coorte_t:
            ui.report_section(t("colon.gtab.cohort"))
            st.write(t("colon.count.intro"))
            codigos_ach = sorted({c for p in parcelas for c in p.codigos})
            classes_ach = sorted({col.classifica(c, p.classes_manuais) for p in parcelas
                                  for c in p.codigos} - {"vazio"})
            bar1 = ui.barra(st)
            por = bar1.selectbox(t("colon.count.by"), ("classe", "codigo"), key="colon_ct_por",
                                 width=150, format_func=lambda k: t(f"colon.count.by_{k}"))
            if por == "classe":
                opcoes = classes_ach
                padrao = [c for c in ("jovem",) if c in opcoes]
                fmt = lambda c: t(f"colon.cls.{c}")
            else:
                opcoes, padrao, fmt = codigos_ach, [c for c in ("J",) if c in codigos_ach], str
            itens = bar1.multiselect(t("colon.count.items"), opcoes, default=padrao,
                                     key=f"colon_ct_itens_{por}", format_func=fmt)
            empilha = bar1.selectbox(t("colon.count.stack"), ("coorte", "especie", "item", "nenhum"),
                                     key="colon_ct_pilha", width=200,
                                     format_func=lambda k: t(f"colon.count.stack_{k}"))
            agrupar = por if empilha == "item" else empilha
            cont = col.contagem_por_ano(parcelas, itens, por=por, agrupar=agrupar, unidas=UNIDAS,
                                        incluir_sem_coorte=COM_SEM_COORTE,
                                        ocultar_incompletas=OCULTAR)
            if cont.empty:
                st.info(t("colon.count.empty"))
            else:
                bar2 = ui.barra(st)
                alvo = bar2.selectbox(t("colon.count.plot"), ["__todas__"] + sorted(cont["parcela"].unique()),
                                      key="colon_ct_parcela", width=200,
                                      format_func=lambda v: t("colon.count.all_plots") if v == "__todas__" else v)
                pct = bar2.checkbox(t("colon.count.percent"), key="colon_ct_pct")
                vista = cont if alvo == "__todas__" else cont[cont["parcela"] == alvo]
                grupos_v = cc.grupos_contagem(vista, agrupar)
                padrao_c = cc.cores_contagem(grupos_v, agrupar, estilos)
                cores_u = {}
                with bar2.popover(t("colon.count.colors"), icon=":material/palette:") as pop_c:
                    modo_c = pop_c.selectbox(t("colon.count.colors_mode"),
                                             ("padrao", "paleta", "gradiente", "cada"),
                                             key="colon_ct_cor_modo",
                                             format_func=lambda k: t(f"colon.count.colors_{k}"))
                    if modo_c == "paleta":
                        pal = pop_c.selectbox(t("colon.count.colors_palette"), list(ui.PALETAS),
                                              key="colon_ct_cor_pal",
                                              format_func=lambda c: t(f"palette.{c}"))
                        cores_u = {g: ui.PALETAS[pal][i % len(ui.PALETAS[pal])]
                                   for i, g in enumerate(grupos_v)}
                    elif modo_c == "gradiente":
                        base = pop_c.color_picker(t("colon.count.colors_base"), "#2A9D8F",
                                                  key="colon_ct_cor_base")
                        cores_u = cc.gradiente(base, grupos_v)
                    elif modo_c == "cada":
                        for g in grupos_v:
                            cores_u[g] = pop_c.color_picker(
                                cc.nome_grupo(g, agrupar, LANG), cc.hex_cor(padrao_c[g]),
                                key=f"colon_ct_cor_{agrupar}_{g}")
                ui.show(st, cc.fig_contagem(vista, estilos, LANG, agrupar, pct, cores_u or None),
                        "colon_cont", estilos, barra=bar2)
                st.caption(t("colon.count.note"))
                tab_c = vista.groupby(["ano", "grupo"])["n"].sum().unstack(fill_value=0)
                tab_c.columns = [cc.nome_grupo(g, agrupar, LANG) for g in tab_c.columns]
                tab_c.index.name = t("colon.col.year")
                if pct:                        # the table shows what the chart shows
                    tab_c = tab_c.div(tab_c.sum(axis=1).where(lambda x: x > 0), axis=0) * 100
                    st.dataframe(ui.estilo2(tab_c, LANG), width="stretch")
                    st.caption(t("colon.count.percent_note"))
                else:
                    st.dataframe(tab_c, width="stretch")
                exportar.botoes(st, _traduz(vista, agrupar), arq_nome.arquivo(t("file.colon_count")), "exp_colon_cont", LANG,
                                titulo=t("colon.density.download"))

        # --- Jimenez schematic next to the observed density (same size)
        with g_jim_t:
            ui.report_section(t("colon.gtab.jimenez"))
            s1, s2 = st.columns(2)
            f_esq = cc.fig_esquema(estilos, LANG)
            f_dir = None if d_all.empty else cc.fig_curva_densidade(d_all, estilos, LANG)
            cc.alinhar(*(f for f in (f_esq, f_dir) if f is not None))     # axes at the same heights
            with s1:
                ui.show(st, f_esq, "colon_schema", estilos, botoes=False)
            with s2:
                if f_dir is None:
                    st.info(t("colon.density.empty"))
                else:
                    ui.show(st, f_dir, "colon_schema_obs", estilos, botoes=False)

def _verificacao_pdf():
    """Counts of the check of each plot, for the PDF: individuals without a cohort, the cells
    to fix (by kind) and the repeated tags."""
    out = []
    for p in parcelas:
        r = col.resumo(p)
        pend = col.tabela_pendencias(p)["problema"].value_counts()
        out.append({"parcela": p.parcela, "sem_coorte": r["sem_coorte"],
                    "lacres_repetidos": r["lacres_repetidos"],
                    **{k: int(pend.get(k, 0)) for k in ("coorte_posterior", "coorte_invalida",
                                                         "altura", "sem_especie")}})
    return out


# ------------------------------------------------------------------ export
with tab_exp:
    st.write(t("colon.export.intro"))
    e1, e2 = st.columns(2)
    formato = e1.radio(t("colon.export.format"), ("longo", "largo"), key="colon_formato",
                       format_func=lambda k: t(f"colon.export.format_{k}"))
    so_usadas = e2.checkbox(t("colon.export.only_used"), value=False, key="colon_usadas",
                            disabled=formato == "largo")
    longo, largo = _tabelas_limpas(parcelas, _SIG)
    longo, largo = _limpa_na_unidade(longo), _limpa_na_unidade(largo)
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
            col.densidade_jovens(parcelas, incluir_sem_coorte=COM_SEM_COORTE, unidas=UNIDAS, areas=AREAS,
                                 ocultar_incompletas=OCULTAR),
            lang=LANG, figures=figs,
            params={"versao": VERSAO, "areas": AREAS, "unidas": UNIDAS or {}, "ocultar": OCULTAR},
            alturas=_na_unidade(col.estatistica_altura(
                parcelas, incluir_sem_coorte=COM_SEM_COORTE, unidas=UNIDAS, ocultar_incompletas=OCULTAR,
                selecao=_selecao_altura(), modo=_modo_altura())),
            relativa=col.densidade_relativa(parcelas, incluir_sem_coorte=COM_SEM_COORTE, unidas=UNIDAS,
                                            areas=AREAS, ocultar_incompletas=OCULTAR),
            verificacao=_verificacao_pdf(), unidade=UH),
            arq_nome.arquivo(t("file.report")) + ".pdf",
            (_SIG, VERSAO, LANG, OCULTAR, repr(sorted(AREAS.items())), repr(UNIDAS)))
    d1, d2 = st.columns(2)
    _fmt = d1.radio(t("export.format_choice"), ("csv", "txt"), horizontal=True, key="colon_fmt",
                    format_func=lambda f: t(f"export.fmt_{f}"))
    d1.download_button(t("colon.export.csv"), _bytes_tab(_traduz(mostrado), (_SIG, formato, so_usadas, UH, LANG), _fmt, LANG),
                       file_name=arq_nome.arquivo(t(f"file.colon_clean_{formato}")) + f".{_fmt}", mime=exportar.MIME[_fmt],
                       key="colon_csv")
    # the Excel file is big: it is built only when asked for
    if d2.button(t("colon.export.prepare_xlsx"), key="colon_xlsx_prep"):
        _buf = io.BytesIO()
        with st.spinner(t("colon.export.preparing")):
            _buf = io.BytesIO(exportar.bytes_xlsx({
                t("colon.export.sheet_long"): _traduz(longo), t("colon.export.sheet_wide"): _traduz(largo),
                t("colon.export.sheet_blocks"): _traduz(pd.concat(
                    [col.tabela_blocos(p).assign(parcela=p.parcela) for p in parcelas]))}, LANG))
        st.session_state["colon_xlsx_bytes"] = ((_SIG, UH, LANG), _buf.getvalue())
    _pronto = st.session_state.get("colon_xlsx_bytes")
    if _pronto and _pronto[0] == (_SIG, UH, LANG):     # unit or language changed: prepare again
        d2.download_button(t("colon.export.xlsx"), _pronto[1], file_name=arq_nome.arquivo(t("file.tables")) + ".xlsx",
                           key="colon_xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
