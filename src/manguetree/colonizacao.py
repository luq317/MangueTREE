# -*- coding: utf-8 -*-
"""
colonizacao.py
==============
Leitura das planilhas de dinamica de colonizacao do NEMA/UERJ (uma por parcela) e
calculo da densidade de jovens. Le so a aba de digitacao da parcela (e, para o ano
de cada coleta, a tabela "coluna ref" da aba de contagem); todas as abas de calculo
sao ignoradas.

Regras (definidas em 20/11/2026, ver especificacao do modulo):

* densidade de jovens = individuos com codigo J / area (ind/ha); cada individuo
  conta uma vez;
* TR (tronco adicional) nao entra em ind/ha; entra na densidade de troncos;
* N1 e N2 nao entram (situacao incerta); N3 = Y (morto); mortes: X, Y, N3, M;
* E e a aba Excluidos ficam fora dos calculos;
* duas versoes: sem indivíduos sem coorte e com eles;
* parcelas unidas (A+B): somar contagens e areas.

O leitor nao grava nada e nao altera a planilha.
"""

import datetime as _dt
import re
import unicodedata as _unicodedata
from collections import Counter, OrderedDict
from dataclasses import dataclass, field

import numpy as np
import openpyxl
import pandas as pd
from openpyxl.utils import column_index_from_string

# --------------------------------------------------------------------------
# Codigos
# --------------------------------------------------------------------------

#: classe de cada codigo (depois de maiusculas, sem espacos e sem asterisco)
CLASSES = OrderedDict([
    ("J", "jovem"),
    ("PL", "plantula"),
    ("PR", "propagulo"),
    ("TR", "tronco"),
    ("X", "morto"), ("Y", "morto"), ("N3", "morto"), ("M", "morto"),
    ("N1", "incerto"), ("N2", "incerto"),
    ("E", "excluido"),
])
_TRONCO_RE = re.compile(r"^(?:(X|Y|M|N1|N2|N3)TR|TR(X|Y|M))$")

#: classes que contam como vivas na leitura (jovem e outros estagios)
VIVAS = ("jovem", "plantula", "propagulo")

PALAVRAS_ANOTACAO = ("VERIFICAR", "NAO RESOLVIDO", "NÃO RESOLVIDO", "LINHAS ANTES",
                     "PARA FAZER")


def normaliza_codigo(valor):
    """Maiusculas, sem espacos e sem asterisco; vazio vira ''."""
    if valor is None:
        return ""
    t = str(valor).strip().upper().replace("*", "").replace(" ", "")
    return "" if t in ("-", ".") else t


#: classes que o usuario pode atribuir a um codigo na tela de verificacao
CLASSES_EDITAVEIS = ("jovem", "plantula", "propagulo", "tronco", "tronco_morto",
                     "tronco_incerto", "morto", "incerto", "excluido")


def classifica(codigo, manuais=None):
    """Classe de um codigo ja normalizado: jovem, plantula, propagulo, tronco,
    tronco_morto, tronco_incerto, morto, incerto, excluido, vazio ou desconhecido.
    ``manuais`` e {codigo: classe} escolhido pelo usuario e vale antes da regra padrao."""
    if not codigo:
        return "vazio"
    if manuais and codigo in manuais and manuais[codigo] in CLASSES_EDITAVEIS:
        return manuais[codigo]
    if codigo in CLASSES:
        return CLASSES[codigo]
    m = _TRONCO_RE.match(codigo)
    if m:
        c = m.group(1) or m.group(2)
        return "tronco_incerto" if c in ("N1", "N2") else "tronco_morto"
    return "desconhecido"


# --------------------------------------------------------------------------
# Estruturas
# --------------------------------------------------------------------------

@dataclass
class Bloco:
    """Um bloco anual (ou de uma coleta): colunas de Tipo e de Altura."""
    indice: int
    col_tipo: int                       # primeira coluna de Tipo (base 0)
    cols_tipo: list = field(default_factory=list)
    cols_altura: list = field(default_factory=list)
    col_altura_ano: int = None          # coluna de altura usada para o ano
    rotulo_ano: object = None           # ano escrito no bloco ("<1998" ou inteiro)
    coletas: list = field(default_factory=list)   # [(numero, data)]
    ano: int = None
    origem_ano: str = ""                # "rotulo", "coluna ref", "data" ou "manual"

    @property
    def data(self):
        datas = [d for _, d in self.coletas if d is not None]
        return max(datas) if datas else None

    @property
    def rotulo(self):
        if self.rotulo_ano is not None:
            return str(self.rotulo_ano)
        nums = [n for n, _ in self.coletas if n is not None]
        if nums:
            return f"Coleta {nums[-1]}" if len(nums) == 1 else f"Coletas {nums[0]} a {nums[-1]}"
        return f"bloco {self.indice + 1}"


@dataclass
class Individuo:
    """Um individuo (grupo de linhas separado por linha em branco)."""
    parcela: str
    grupo: int
    linhas: list                         # numeros das linhas na planilha (base 1)
    coorte: object                       # int, "<1998", "?" ou None
    especie: str
    lado: str
    lacres: list
    por_bloco: dict                      # indice do bloco -> dict(codigo, classe, altura, troncos_vivos)


@dataclass
class ParcelaLida:
    parcela: str
    arquivo: str
    aba: str
    blocos: list
    individuos: list
    codigos: Counter
    avisos: list                         # (tipo, mensagem, linha ou None)
    excluidos: int = 0
    linhas_anotacao: list = field(default_factory=list)
    lacres_repetidos: list = field(default_factory=list)
    classes_manuais: dict = field(default_factory=dict)   # {codigo: classe} do usuario

    def anos(self):
        return sorted({b.ano for b in self.blocos if b.ano is not None})


# --------------------------------------------------------------------------
# Utilidades de leitura
# --------------------------------------------------------------------------

def _vazio(v):
    return v is None or (isinstance(v, str) and v.strip() in ("", "-"))


def _texto(v):
    return "" if v is None else str(v).strip()


def _como_data(v):
    """Data como datetime ou texto dd/mm/aaaa; None se nao for data."""
    if isinstance(v, _dt.datetime):
        return v
    if isinstance(v, _dt.date):
        return _dt.datetime(v.year, v.month, v.day)
    if isinstance(v, str):
        m = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*", v)
        if m:
            d, mth, a = (int(x) for x in m.groups())
            try:
                return _dt.datetime(a, mth, d)
            except ValueError:
                return None
    return None


def _como_numero(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        t = v.strip().replace(",", ".")
        try:
            return float(t)
        except ValueError:
            return None
    return None


def _como_ano(v):
    """Ano escrito no cabecalho: inteiro de 4 digitos ou '<1998'."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)) and float(v) == int(v) and 1900 <= int(v) <= 2100:
        return int(v)
    if isinstance(v, str):
        t = v.strip()
        if re.fullmatch(r"<\s*\d{4}", t):
            return t.replace(" ", "")
        if re.fullmatch(r"\d{4}", t) and 1900 <= int(t) <= 2100:
            return int(t)
    return None


def _sem_acento(t):
    return "".join(ch for ch in _unicodedata.normalize("NFKD", str(t))
                   if not _unicodedata.combining(ch))


def _nome_campo(v):
    return _sem_acento(_texto(v)).lower().replace(".", "").strip()


def _letra_da_planilha(nome_arquivo):
    m = re.search(r"parcela\s+([A-Za-z]{1,2})\b", nome_arquivo, re.I)
    return m.group(1).upper() if m else None


def _aba(wb, *nomes):
    """Aba cujo nome (sem acento, maiusculas, sem espacos) esta em nomes."""
    alvo = {_sem_acento(n).strip().upper() for n in nomes}
    for ws in wb.worksheets:
        if _sem_acento(ws.title).strip().upper() in alvo:
            return ws
    return None


def _linhas(ws):
    return [tuple(r) for r in ws.iter_rows(values_only=True)]


# --------------------------------------------------------------------------
# Tabela "coluna ref" da aba de contagem
# --------------------------------------------------------------------------

def le_coluna_ref(wb):
    """{indice de coluna (base 0): ano} da tabela "coluna ref" da aba Contagem."""
    ws = _aba(wb, "Contagem")
    if ws is None:
        return {}
    rows = _linhas(ws)
    ini = None
    for i, r in enumerate(rows[:15]):
        if r and _nome_campo(r[0]) == "coluna ref":
            ini = i
            break
    if ini is None:
        return {}
    ref = {}
    for r in rows[ini + 1:]:
        if len(r) < 2 or _vazio(r[0]):
            continue
        letra = _texto(r[0]).upper()
        ano = _como_ano(r[1])
        if re.fullmatch(r"[A-Z]{1,3}", letra) and isinstance(ano, int):
            ref[column_index_from_string(letra) - 1] = ano
    return ref


# --------------------------------------------------------------------------
# Leitura da aba de digitacao
# --------------------------------------------------------------------------

def _acha_cabecalho(rows):
    for i, r in enumerate(rows[:12]):
        if any(_nome_campo(c) == "lacre" for c in r):
            return i
    raise ValueError("Nao encontrei a linha de campos (com 'Lacre') nas primeiras linhas da aba.")


def _colunas_fixas(campos):
    fixos = {}
    for j, c in enumerate(campos):
        n = _nome_campo(c)
        if n in ("tipo atual",):
            fixos.setdefault("tipo_atual", j)
        elif n in ("ind", "individuo"):
            fixos.setdefault("ind", j)
        elif n == "lado":
            fixos.setdefault("lado", j)
        elif n == "coleta":
            fixos.setdefault("coleta", j)
        elif n == "coorte":
            fixos.setdefault("coorte", j)
        elif n.startswith("tipo de diametro"):
            fixos.setdefault("tipo_diametro", j)
        elif n == "lacre":
            fixos.setdefault("lacre", j)
        elif n in ("especie", "sp"):
            fixos.setdefault("especie", j)
    return fixos


def _monta_blocos(campos, rows_acima):
    """Blocos a partir da linha de campos e das linhas acima dela."""
    cols_tipo = [j for j, c in enumerate(campos)
                 if _nome_campo(c).startswith("tipo")
                 and _nome_campo(c) not in ("tipo atual",)
                 and not _nome_campo(c).startswith("tipo de diametro")]
    blocos, atual = [], None
    for j in cols_tipo:
        if atual is not None and j - atual.cols_tipo[-1] == 1:
            atual.cols_tipo.append(j)
        else:
            atual = Bloco(indice=len(blocos), col_tipo=j, cols_tipo=[j])
            blocos.append(atual)
    limites = [b.col_tipo for b in blocos] + [len(campos) + 50]
    for k, b in enumerate(blocos):
        fim = limites[k + 1]
        b.cols_altura = [j for j in range(b.col_tipo, min(fim, len(campos)))
                         if _nome_campo(campos[j]).startswith("altura")]
    # rotulos acima do cabecalho: ano, "Coleta N" e data, por coluna
    for k, b in enumerate(blocos):
        fim = limites[k + 1]
        for r in rows_acima:
            for j in range(b.col_tipo, min(fim, len(r))):
                v = r[j]
                if _vazio(v):
                    continue
                ano = _como_ano(v)
                if ano is not None and b.rotulo_ano is None:
                    b.rotulo_ano = ano
                    continue
                m = re.fullmatch(r"\s*coleta\s*(\d+)\s*", str(v), re.I)
                if m:
                    b.coletas.append([int(m.group(1)), None, j])
                    continue
        # datas: na mesma coluna de cada rotulo de coleta (ou na primeira coluna do bloco)
        for r in rows_acima:
            for j in range(b.col_tipo, min(fim, len(r))):
                d = _como_data(r[j])
                if d is None:
                    continue
                for c in b.coletas:
                    if c[2] == j and c[1] is None:
                        c[1] = d
                        break
                else:
                    if not any(c[2] == j for c in b.coletas):
                        b.coletas.append([None, d, j])
        b.coletas = [(n, d) for n, d, _ in sorted(b.coletas, key=lambda c: c[2])]
    return blocos


def _tipo_linha(row, fixos, blocos, colunas_fixas=()):
    """True se a linha tem lacre, tipo ou algum campo fixo preenchido (tipo atual,
    ind, lado, coleta, coorte, especie)."""
    if "lacre" in fixos and fixos["lacre"] < len(row) and not _vazio(row[fixos["lacre"]]):
        return True
    for j in colunas_fixas:
        if j < len(row) and not _vazio(row[j]):
            return True
    for b in blocos:
        for j in b.cols_tipo:
            if j < len(row) and not _vazio(row[j]):
                return True
    return False


def le_parcela(origem, parcela=None, anos_manuais=None, nome_arquivo=None, classes_manuais=None):
    """Le uma planilha de dinamica de colonizacao.

    ``origem`` e um caminho ou um objeto de arquivo (upload). ``parcela`` e a letra
    da parcela (se faltar, sai do nome do arquivo: "Parcela K.xlsx"). ``anos_manuais``
    e {indice do bloco: ano} para corrigir a tabela coleta -> ano. ``classes_manuais`` e
    {codigo: classe} para reclassificar codigos (ver ``CLASSES_EDITAVEIS``).
    """
    nome = nome_arquivo or (origem if isinstance(origem, str) else getattr(origem, "name", "planilha"))
    wb = openpyxl.load_workbook(origem, read_only=True, data_only=True)
    parcela = (parcela or _letra_da_planilha(str(nome)) or "").upper()
    if not parcela:
        raise ValueError("Nao consegui saber a letra da parcela pelo nome do arquivo "
                         "(use o formato 'Parcela K.xlsx').")
    ws = _aba(wb, parcela)
    if ws is None:
        raise ValueError(f"Nao encontrei a aba '{parcela}' (aba de digitacao) em {nome}.")
    rows = _linhas(ws)
    iref = _acha_cabecalho(rows)
    campos = rows[iref]
    fixos = _colunas_fixas(campos)
    if "lacre" not in fixos or "coorte" not in fixos:
        raise ValueError("A aba nao tem as colunas Lacre e Coorte no cabecalho.")
    blocos = _monta_blocos(campos, rows[:iref])
    avisos = []

    # --- anos dos blocos
    ref = le_coluna_ref(wb)
    for b in blocos:
        if anos_manuais and b.indice in anos_manuais:
            b.ano, b.origem_ano = int(anos_manuais[b.indice]), "manual"
        elif isinstance(b.rotulo_ano, int):
            b.ano, b.origem_ano = b.rotulo_ano, "rotulo"
        elif b.rotulo_ano is not None:                  # "<1998"
            b.ano, b.origem_ano = None, "rotulo"
        elif b.col_tipo in ref:
            b.ano, b.origem_ano = ref[b.col_tipo], "coluna ref"
        elif b.data is not None:
            b.ano, b.origem_ano = b.data.year, "data"
        else:
            avisos.append(("bloco sem ano", f"{b.rotulo}: nao foi possivel definir o ano", None))

    vistos = {}
    for b in blocos:
        if b.ano is None:
            continue
        if b.ano in vistos:
            avisos.append(("ano repetido", f"{b.rotulo} e {vistos[b.ano].rotulo} caem em {b.ano}; vale o ultimo", None))
        vistos[b.ano] = b

    # --- altura usada em cada bloco: ultima coluna de altura com algum numero
    dados = rows[iref + 1:]
    for b in blocos:
        com_valor = []
        for j in b.cols_altura:
            for r in dados:
                if j < len(r) and _como_numero(r[j]) is not None:
                    com_valor.append(j)
                    break
        b.col_altura_ano = com_valor[-1] if com_valor else None

    # --- individuos
    codigos = Counter()
    individuos, anotacoes = [], []
    lacres = Counter()
    blocos_linhas, atual = [], []          # blocos de linhas separados por linha em branco
    for k, r in enumerate(dados):
        num = iref + 2 + k                                # numero da linha (base 1)
        if _tipo_linha(r, fixos, blocos):
            atual.append((num, r))
            continue
        texto = " ".join(_texto(c) for c in r if isinstance(c, str) and not _vazio(c))
        if texto:                                         # anotacao: ignorada, nao separa
            if "nao preencher" not in _sem_acento(texto).lower():
                anotacoes.append((num, texto))
            continue
        if atual:                                         # linha em branco: fecha o bloco
            blocos_linhas.append(atual)
            atual = []
    if atual:
        blocos_linhas.append(atual)

    col_ind = fixos.get("ind")
    col_lado = fixos.get("lado")

    def chave_ind(r):
        if col_ind is None or col_ind >= len(r) or _vazio(r[col_ind]):
            return None
        lado = r[col_lado] if col_lado is not None and col_lado < len(r) else None
        return (_texto(lado), _texto(r[col_ind]))

    grupo = 0
    for linhas_bloco in blocos_linhas:
        # linhas com o mesmo numero de individuo (e lado) formam um individuo (varios
        # lacres e troncos); linha sem numero e um individuo de lacre unico
        partes, chave_ant = [], None
        for x in linhas_bloco:
            ch = chave_ind(x[1])
            if not partes or ch is None or ch != chave_ant:
                partes.append([])
            partes[-1].append(x)
            chave_ant = ch
        do_bloco = []
        for parte in partes:
            do_bloco.append(_monta_individuo(parcela, grupo, parte, fixos, blocos, avisos,
                                               classes_manuais))
            grupo += 1
        individuos.extend(do_bloco)

    for ind in individuos:
        for b in blocos:
            d = ind.por_bloco.get(b.indice)
            if d and d["codigo"]:
                codigos[d["codigo"]] += 1
        for lac in ind.lacres:
            lacres[lac] += 1
    repetidos = sorted([l for l, n in lacres.items() if n > 1], key=str)

    # --- excluidos (so contagem, ficam fora dos calculos)
    exc = 0
    wse = _aba(wb, "Excluidos")
    if wse is not None:
        er = _linhas(wse)
        try:
            ie = _acha_cabecalho(er)
            exc = sum(1 for r in er[ie + 1:] if not all(_vazio(c) for c in r))
        except ValueError:
            exc = 0

    return ParcelaLida(parcela=parcela, arquivo=str(nome), aba=ws.title, blocos=blocos,
                       individuos=individuos, codigos=codigos, avisos=avisos,
                       excluidos=exc, linhas_anotacao=anotacoes, lacres_repetidos=repetidos,
                       classes_manuais=dict(classes_manuais or {}))


def _monta_individuo(parcela, grupo, linhas, fixos, blocos, avisos, classes_manuais=None):
    def cel(r, nome):
        j = fixos.get(nome)
        return r[j] if j is not None and j < len(r) else None

    coorte = None
    for _, r in linhas:
        v = cel(r, "coorte")
        if not _vazio(v):
            coorte = _como_ano(v) if _como_ano(v) is not None else _texto(v)
            break
    especie, lado = "", ""
    for _, r in linhas:
        if not especie and not _vazio(cel(r, "especie")):
            especie = _texto(cel(r, "especie"))
        if not lado and not _vazio(cel(r, "lado")):
            lado = _texto(cel(r, "lado"))
    lacres = [cel(r, "lacre") for _, r in linhas if not _vazio(cel(r, "lacre"))]

    por_bloco = {}
    for b in blocos:
        melhor = None                       # (classe, codigo, altura) da linha principal
        troncos_vivos = 0
        n_jovens = 0                        # linhas com J (um individuo pode ter 2 lacres em J)
        alturas_j = []                      # altura (cm) de cada linha com J (None se nao medida)
        codigos_linhas = []
        for num, r in linhas:
            ultimo = ""
            for j in b.cols_tipo:
                if j < len(r) and not _vazio(r[j]):
                    ultimo = normaliza_codigo(r[j])
            if not ultimo:
                continue
            cl = classifica(ultimo, classes_manuais)
            alt = None
            if b.col_altura_ano is not None and b.col_altura_ano < len(r):
                alt = _como_numero(r[b.col_altura_ano])
            codigos_linhas.append((ultimo, cl, alt, num))
            if cl == "tronco":
                troncos_vivos += 1
            elif cl == "jovem":
                n_jovens += 1
                alturas_j.append(alt)
        if not codigos_linhas:
            continue
        # linha principal: a que nao e tronco; se houver varias, a de maior prioridade
        prio = {"jovem": 0, "plantula": 1, "propagulo": 2, "incerto": 3, "morto": 4,
                "excluido": 5, "desconhecido": 6}
        principais = [c for c in codigos_linhas if c[1] in prio]
        if principais:
            melhor = sorted(principais, key=lambda c: prio[c[1]])[0]
        else:
            melhor = codigos_linhas[0]
        por_bloco[b.indice] = {"codigo": melhor[0], "classe": melhor[1], "altura": melhor[2],
                               "linha": melhor[3], "troncos_vivos": troncos_vivos,
                               "n_jovens": n_jovens, "alturas_j": alturas_j}
    return Individuo(parcela=parcela, grupo=grupo, linhas=[n for n, _ in linhas], coorte=coorte,
                     especie=especie, lado=lado, lacres=lacres, por_bloco=por_bloco)


# --------------------------------------------------------------------------
# Tabela por individuo e ano, areas e densidade
# --------------------------------------------------------------------------

#: area das parcelas da Area I (m2), valida para todos os anos lidos (planilhas
#: oficiais da monografia de Motta, 2026). Pode ser sobrescrita por parcela e ano.
#: ano de estabelecimento (demarcacao) de cada parcela da Area I, lido da Figura 2.2 de
#: Estevam (2019, p. 39). Nas duas figuras de Estevam (2013, Fig. 10, so ate a parcela M) so a
#: G muda (1999 la, 2000 em 2019); a G nao esta entre as planilhas da monografia.
#: As planilhas confirmam: os individuos de K comecam em 2006 e os de L em 2009.
ANOS_ESTABELECIMENTO = {"A": 1998, "B": 1998, "C": 1998, "D": 1998, "E": 1998, "F": 1998,
                        "G": 2000, "H": 2004, "I": 2004, "J": 2006, "K": 2006, "L": 2009,
                        "M": 2011, "N": 2012, "O": 2012, "P": 2013, "Q": 2014, "R": 2014,
                        "S": 2014, "A+B": 1998}

AREAS_M2 = {"A": 25.0, "B": 25.0, "D": 60.0, "H": 60.0, "I": 60.0, "K": 60.0,
            "L": 60.0, "O": 60.0, "R": 60.0}


def _categoria_coorte(coorte, ano):
    """valida (ano de coorte <= ano ou "<1998"), impossivel (coorte posterior ao ano)
    ou sem (sem coorte: "?" ou em branco)."""
    if isinstance(coorte, int):
        return "valida" if coorte <= ano else "impossivel"
    if isinstance(coorte, str) and coorte.startswith("<"):
        return "valida"
    return "sem"


def tabela_individuos(parcela):
    """DataFrame com uma linha por individuo e ano de analise.

    Colunas: parcela, grupo, linha, ano, bloco, coorte, categoria_coorte, especie,
    codigo, classe, altura, troncos_vivos, n_jovens (linhas com J: dois lacres em J no
    mesmo individuo contam dois jovens, como nas planilhas). Quando dois blocos caem no
    mesmo ano vale o ultimo (e a leitura avisa).
    """
    memo = getattr(parcela, "_tabela_individuos", None)
    if memo is not None:                      # a leitura nao muda: a tabela fica guardada
        return memo.copy()
    por_ano = {b.ano: b for b in parcela.blocos if b.ano is not None}   # vale o ultimo do ano
    linhas = []
    for ind in parcela.individuos:
        for ano, b in por_ano.items():
            d = ind.por_bloco.get(b.indice)
            if not d:
                continue
            linhas.append({"parcela": parcela.parcela, "grupo": ind.grupo, "linha": ind.linhas[0],
                           "ano": ano, "bloco": b.indice, "coorte": ind.coorte,
                           "categoria_coorte": _categoria_coorte(ind.coorte, ano),
                           "especie": ind.especie.strip().capitalize(), "codigo": d["codigo"],
                           "classe": d["classe"], "altura": d["altura"],
                           "troncos_vivos": d["troncos_vivos"], "n_jovens": d["n_jovens"],
                           "alturas_j": d["alturas_j"]})
    cols = ["parcela", "grupo", "linha", "ano", "bloco", "coorte", "categoria_coorte",
            "especie", "codigo", "classe", "altura", "troncos_vivos", "n_jovens",
            "alturas_j"]
    df = pd.DataFrame(linhas, columns=cols)
    parcela._tabela_individuos = df
    return df.copy()


def area_ha(parcela_letra, ano=None, areas=None):
    """Area da parcela em hectares."""
    a = (areas or AREAS_M2)
    if parcela_letra not in a:
        raise KeyError(f"Sem area configurada para a parcela {parcela_letra}")
    v = a[parcela_letra]
    if isinstance(v, dict):                    # {ano inicial: area}
        ini = max(k for k in v if k <= (ano if ano is not None else 9999))
        v = v[ini]
    return float(v) / 10000.0


def densidade_jovens(parcelas, incluir_sem_coorte=False, unidas=None, areas=None,
                     por_especie=False, troncos=False):
    """Densidade de jovens (ind/ha) por parcela e ano.

    ``parcelas`` e uma lista de ParcelaLida. ``unidas`` e {"A+B": ["A", "B"]}: soma
    contagens e areas. ``incluir_sem_coorte`` False e a versao de Estevam (2013) e
    Batista (2024); True e a de Motta (2026). ``troncos`` True conta tambem os troncos
    adicionais (TR) vivos (densidade de troncos, tr/ha).

    Retorna DataFrame: parcela, ano, [especie,] n, area_ha, ind_ha.
    """
    tabs = pd.concat([tabela_individuos(p) for p in parcelas], ignore_index=True) \
        if parcelas else pd.DataFrame()
    if tabs.empty:
        return pd.DataFrame(columns=["parcela", "ano", "n", "area_ha", "ind_ha"])
    j = tabs[tabs["classe"] == "jovem"]
    if not incluir_sem_coorte:
        j = j[j["categoria_coorte"] == "valida"]
    j = j.assign(n=j["n_jovens"] + (j["troncos_vivos"] if troncos else 0))
    chave = ["parcela", "ano"] + (["especie"] if por_especie else [])
    cont = j.groupby(chave, as_index=False)["n"].sum()
    # anos lidos de cada parcela (para mostrar 0 quando nao ha jovens)
    anos = tabs.groupby("parcela")["ano"].unique()
    if por_especie:
        esp = sorted(j["especie"].unique())          # so especies com algum jovem
        base = pd.DataFrame([(p, a, e) for p, aa in anos.items() for a in aa for e in esp],
                            columns=["parcela", "ano", "especie"])
    else:
        base = pd.DataFrame([(p, a) for p, aa in anos.items() for a in aa],
                            columns=["parcela", "ano"])
    cont = base.merge(cont, on=chave, how="left").fillna({"n": 0})
    cont["n"] = cont["n"].astype(int)
    cont["area_ha"] = [area_ha(p, a, areas) for p, a in zip(cont["parcela"], cont["ano"])]
    if unidas:
        partes = []
        resto = cont
        for nome, membros in unidas.items():
            sub = cont[cont["parcela"].isin(membros)]
            resto = resto[~resto["parcela"].isin(membros)]
            g = sub.groupby([c for c in chave if c != "parcela"], as_index=False)[["n", "area_ha"]].sum()
            g.insert(0, "parcela", nome)
            partes.append(g)
        cont = pd.concat([resto] + partes, ignore_index=True)
    cont["ind_ha"] = cont["n"] / cont["area_ha"]
    return cont.sort_values(chave).reset_index(drop=True)


# --------------------------------------------------------------------------
# Tabelas da verificacao
# --------------------------------------------------------------------------

def _letra_coluna(j):
    from openpyxl.utils import get_column_letter
    return get_column_letter(j + 1)


def tabela_blocos(parcela):
    """Coleta -> ano de analise: um bloco por linha (o ano pode ser corrigido)."""
    linhas = []
    for b in parcela.blocos:
        linhas.append({"bloco": b.indice, "rotulo": b.rotulo, "coluna": _letra_coluna(b.col_tipo),
                       "data": b.data.date() if b.data else None, "ano": b.ano,
                       "origem": b.origem_ano or "-",
                       "coleta_altura": (_letra_coluna(b.col_altura_ano)
                                         if b.col_altura_ano is not None else "-"),
                       "registros": sum(1 for i in parcela.individuos if b.indice in i.por_bloco)})
    return pd.DataFrame(linhas, columns=["bloco", "rotulo", "coluna", "data", "ano", "origem",
                                         "coleta_altura", "registros"])


def tabela_codigos(parcela):
    """Codigos encontrados (um por individuo e bloco), com a classe de cada um."""
    linhas = [{"codigo": cod, "classe": classifica(cod, parcela.classes_manuais), "n": n}
              for cod, n in sorted(parcela.codigos.items(), key=lambda kv: -kv[1])]
    return pd.DataFrame(linhas, columns=["codigo", "classe", "n"])


def tabela_coortes(parcela):
    """Jovens por ano segundo a coorte (validos, sem coorte e com coorte impossivel) e
    individuos N1 e N2 (fora da densidade)."""
    t = tabela_individuos(parcela)
    if t.empty:
        return pd.DataFrame(columns=["ano", "j_valido", "j_sem_coorte", "j_coorte_impossivel",
                                     "n1", "n2"])
    j = t[t["classe"] == "jovem"]
    out = pd.DataFrame({"ano": sorted(t["ano"].unique())}).set_index("ano")
    for nome, cat in (("j_valido", "valida"), ("j_sem_coorte", "sem"),
                      ("j_coorte_impossivel", "impossivel")):
        out[nome] = j[j["categoria_coorte"] == cat].groupby("ano")["n_jovens"].sum()
    for nome, cod in (("n1", "N1"), ("n2", "N2")):
        out[nome] = t[t["codigo"] == cod].groupby("ano").size()
    return out.fillna(0).astype(int).reset_index()


def resumo(parcela):
    """Numeros da leitura de uma parcela, para a tela de verificacao."""
    return {"parcela": parcela.parcela, "arquivo": parcela.arquivo, "aba": parcela.aba,
            "individuos": len(parcela.individuos), "blocos": len(parcela.blocos),
            "anos": (min(parcela.anos()), max(parcela.anos())) if parcela.anos() else None,
            "excluidos": parcela.excluidos, "lacres_repetidos": len(parcela.lacres_repetidos),
            "anotacoes": len(parcela.linhas_anotacao),
            "sem_coorte": sum(1 for i in parcela.individuos
                              if i.por_bloco and rotulo_coorte(i.coorte) == SEM_COORTE),
            "especies": sorted({i.especie.strip().capitalize() for i in parcela.individuos
                                if i.por_bloco and i.especie.strip()}),
            "codigos_desconhecidos": sorted(c for c in parcela.codigos
                                            if classifica(c, parcela.classes_manuais) == "desconhecido")}


# --------------------------------------------------------------------------
# Tabela de referencia (Grafico de densidade da monografia de Motta, 2026)
# --------------------------------------------------------------------------

def le_tabela_densidade(origem):
    """Le uma tabela de densidades (ind/ha) com uma coluna "Ano" e uma coluna por
    parcela (letras minusculas), como a planilha "Grafico de densidade dinamica".
    Retorna {(parcela, ano): valor}."""
    wb = openpyxl.load_workbook(origem, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = [tuple(r) for r in ws.iter_rows(values_only=True)]
    ih = next((i for i, r in enumerate(rows) if any(_nome_campo(c) == "ano" for c in r)), None)
    if ih is None:
        raise ValueError("Nao encontrei a coluna 'Ano' na tabela de referencia.")
    col_ano = next(j for j, c in enumerate(rows[ih]) if _nome_campo(c) == "ano")
    cols = {j: _texto(c).upper() for j, c in enumerate(rows[ih])
            if isinstance(c, str) and re.fullmatch(r"[A-Za-z]{1,2}", c.strip()) and j != col_ano}
    ref = {}
    for r in rows[ih + 1:]:
        ano = _como_ano(r[col_ano]) if col_ano < len(r) else None
        if not isinstance(ano, int):
            continue
        for j, letra in cols.items():
            if j < len(r) and _como_numero(r[j]) is not None:
                ref[(letra, ano)] = _como_numero(r[j])
    return ref


def compara_com_referencia(densidade, referencia, tolerancia=1.0):
    """Compara a densidade calculada (DataFrame de ``densidade_jovens``) com a tabela de
    referencia. Retorna DataFrame: parcela, ano, calculado, referencia, diferenca, igual."""
    linhas = []
    for _, r in densidade.iterrows():
        k = (r["parcela"], int(r["ano"]))
        if k in referencia:
            d = r["ind_ha"] - referencia[k]
            linhas.append({"parcela": k[0], "ano": k[1], "calculado": r["ind_ha"],
                           "referencia": referencia[k], "diferenca": d,
                           "igual": abs(d) < tolerancia})
    return pd.DataFrame(linhas, columns=["parcela", "ano", "calculado", "referencia",
                                         "diferenca", "igual"])


# --------------------------------------------------------------------------
# Altura e densidade relativa
# --------------------------------------------------------------------------

#: limite (cm) dos "jovens com 1 m ou mais"
ALTURA_1M_CM = 100.0


def alturas_jovens(parcelas, incluir_sem_coorte=True, unidas=None, classes=("jovem",)):
    """Uma linha por individuo (por linha com J, no caso dos jovens) com altura medida:
    parcela, ano, especie, classe, altura (cm). A altura do ano e a da ultima coleta do
    bloco com altura medida. ``classes`` escolhe as classes (jovem, plantula, propagulo,
    morto...). ``unidas`` junta parcelas ({"A+B": ["A", "B"]}): os individuos entram juntos."""
    linhas = []
    for p in parcelas:
        t = tabela_individuos(p)
        t = t[t["classe"].isin(list(classes))]
        if not incluir_sem_coorte:
            t = t[t["categoria_coorte"] == "valida"]
        for r in t.itertuples():
            alturas = r.alturas_j if r.classe == "jovem" else [r.altura]
            for h in alturas:
                if h is not None and not pd.isna(h):
                    linhas.append({"parcela": r.parcela, "ano": r.ano, "especie": r.especie,
                                   "classe": r.classe, "altura": float(h)})
    df = pd.DataFrame(linhas, columns=["parcela", "ano", "especie", "classe", "altura"])
    for nome, membros in (unidas or {}).items():
        df.loc[df["parcela"].isin(membros), "parcela"] = nome
    return df


def _estatistica(g):
    h = g["altura"]
    return pd.Series({"n": int(h.count()), "media": h.mean(),
                      "dp": h.std(ddof=1) if h.count() > 1 else float("nan"),
                      "minimo": h.min(), "maximo": h.max()})


def estatistica_altura(parcelas, incluir_sem_coorte=True, unidas=None, por_especie=False,
                       minimo_cm=None, classes=("jovem",), por_classe=False):
    """Altura (cm) por parcela e ano: N, media, desvio padrao (amostral), minimo e maximo.
    Por padrao so os jovens; ``classes`` escolhe outras (plantula, propagulo, morto...) e
    ``por_classe`` separa cada uma. ``minimo_cm=100`` usa so os individuos com 1 m ou mais."""
    df = alturas_jovens(parcelas, incluir_sem_coorte, unidas, classes)
    if minimo_cm is not None:
        df = df[df["altura"] >= minimo_cm]
    chave = ["parcela", "ano"] + (["especie"] if por_especie else []) + (["classe"] if por_classe else [])
    cols = chave + ["n", "media", "dp", "minimo", "maximo"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    out = df.groupby(chave).apply(_estatistica, include_groups=False).reset_index()
    out["n"] = out["n"].astype(int)
    return out[cols]


def densidade_relativa(parcelas, incluir_sem_coorte=False, unidas=None, areas=None):
    """Densidade relativa (%) de cada especie = densidade da especie / densidade total x 100
    (Motta, 2026, eq. 1). Colunas: parcela, ano, especie, n, area_ha, ind_ha, total_ind_ha,
    relativa."""
    d = densidade_jovens(parcelas, incluir_sem_coorte=incluir_sem_coorte, unidas=unidas,
                         areas=areas, por_especie=True)
    if d.empty:
        return d.assign(total_ind_ha=[], relativa=[])
    tot = d.groupby(["parcela", "ano"])["ind_ha"].transform("sum")
    d = d.assign(total_ind_ha=tot)
    d["relativa"] = (d["ind_ha"] / d["total_ind_ha"] * 100).where(d["total_ind_ha"] > 0)
    return d


# --------------------------------------------------------------------------
# Exportacao limpa: um individuo por linha
# --------------------------------------------------------------------------

COLUNAS_LONGO = ["parcela", "individuo", "linha", "lado", "lacres", "especie", "coorte", "ano",
                 "coleta", "data", "codigo", "classe", "altura_cm", "troncos_vivos",
                 "n_jovens", "categoria_coorte", "usada_na_analise"]


def tabela_limpa(parcelas, formato="longo"):
    """Dados lidos em tabela limpa, sem as colunas de digitacao da planilha.

    ``formato="longo"``: uma linha por individuo e coleta (todas as coletas, mesmo as sem
    ano), com a coleta, a data, o ano de analise, o codigo, a classe e a altura. A coluna
    ``usada_na_analise`` marca a coleta que vale em cada ano (a ultima, se houver duas).
    ``formato="largo"``: uma linha por individuo, com o codigo e a altura de cada ano.
    A coorte e a de planilha ("<1998", "?" ou ano); ``individuo`` e parcela-numero do grupo
    e ``linha`` e a primeira linha do individuo na aba de digitacao.
    """
    linhas = []
    for p in parcelas:
        usada = {}                                  # ano -> indice do bloco que vale
        for b in p.blocos:
            if b.ano is not None:
                usada[b.ano] = b.indice
        for ind in p.individuos:
            for b in p.blocos:
                d = ind.por_bloco.get(b.indice)
                if not d:
                    continue
                linhas.append({
                    "parcela": p.parcela, "individuo": f"{p.parcela}-{ind.grupo + 1}",
                    "linha": ind.linhas[0], "lado": ind.lado,
                    "lacres": "; ".join(str(x) for x in ind.lacres),
                    "especie": ind.especie.strip().capitalize(), "coorte": ind.coorte,
                    "ano": b.ano, "coleta": b.rotulo, "data": b.data.date() if b.data else None,
                    "codigo": d["codigo"], "classe": d["classe"], "altura_cm": d["altura"],
                    "troncos_vivos": d["troncos_vivos"], "n_jovens": d["n_jovens"],
                    "categoria_coorte": (_categoria_coorte(ind.coorte, b.ano)
                                         if b.ano is not None else ""),
                    "usada_na_analise": b.ano is not None and usada.get(b.ano) == b.indice})
    longo = pd.DataFrame(linhas, columns=COLUNAS_LONGO)
    if formato == "longo":
        return longo
    if formato != "largo":
        raise ValueError("formato deve ser 'longo' ou 'largo'")
    d = longo[longo["usada_na_analise"].astype(bool)]
    chaves = ["parcela", "individuo", "linha", "lado", "lacres", "especie", "coorte"]
    if d.empty:
        return pd.DataFrame(columns=chaves)
    # pivot_table descarta chaves vazias: usa-se string/None neutras
    d = d.assign(coorte=d["coorte"].map(lambda v: "" if v is None else v), ano=d["ano"].astype(int))
    larg = d.pivot(index=chaves, columns="ano", values=["codigo", "altura_cm"])
    larg.columns = [f"{ano} {nome}" for nome, ano in larg.columns]
    ordem = sorted(larg.columns, key=lambda c: (int(c.split()[0]), c.split()[1] != "codigo"))
    return larg[ordem].reset_index()


# --------------------------------------------------------------------------
# Idade das parcelas e regressao log-linear
# --------------------------------------------------------------------------

def com_idade(densidade, inicio):
    """Acrescenta ``inicio`` (ano em que a parcela comecou a colonizar) e ``idade`` (anos)
    a tabela de ``densidade_jovens``. ``inicio`` e {parcela: ano}; parcelas sem ano ou com
    idade menor ou igual a zero ficam fora."""
    d = densidade.copy()
    d["inicio"] = d["parcela"].map(lambda p: inicio.get(p) or None)
    d = d[d["inicio"].notna()]
    d["idade"] = d["ano"] - d["inicio"]
    return d[d["idade"] > 0].reset_index(drop=True)


def regressao_log_linear(df, x="idade", y="ind_ha"):
    """Ajuste ln(y) = a + b ln(x) por minimos quadrados (so valores positivos).

    Retorna dict(a, b, r2, n, ep_b) ou None se houver menos de 3 pontos ou um unico x.
    ``ep_b`` e o erro padrao de b. Os pontos sao medidas repetidas das mesmas parcelas:
    n conta pontos, nao parcelas independentes.
    """
    d = df[(df[x] > 0) & (df[y] > 0)]
    if len(d) < 3 or d[x].nunique() < 2:
        return None
    lx, ly = np.log(d[x].to_numpy(float)), np.log(d[y].to_numpy(float))
    b, a = np.polyfit(lx, ly, 1)
    res = float(((ly - (a + b * lx)) ** 2).sum())
    tot = float(((ly - ly.mean()) ** 2).sum())
    sxx = float(((lx - lx.mean()) ** 2).sum())
    return {"a": float(a), "b": float(b), "r2": (1 - res / tot) if tot > 0 else float("nan"),
            "n": int(len(d)), "ep_b": float(np.sqrt(res / (len(d) - 2) / sxx))}


def curva_esquematica(n=200):
    """Esquema da densidade de troncos no tempo (Jimenez et al. 1985, Fig. 2): colonizacao,
    desenvolvimento inicial, maturidade e senescencia. Desenho qualitativo, sem escala e
    sem equacao (o artigo nao traz uma). Retorna (x, y, limites das fases) com x e y em
    0-1; limites = {fase: (inicio, fim)}."""
    fases = {"colonization": (0.0, 0.15), "early": (0.15, 0.5),
             "maturity": (0.5, 0.72), "senescence": (0.72, 0.95)}
    x = np.linspace(0.0, 0.95, n)
    y = np.empty_like(x)
    for i, t in enumerate(x):
        if t <= 0.15:
            y[i] = (t / 0.15) ** 2.2
        elif t <= 0.5:
            y[i] = 0.38 + 0.62 * np.exp(-(t - 0.15) / 0.09)
        elif t <= 0.72:
            y[i] = 0.3926 - (0.3926 - 0.37) * (t - 0.5) / 0.22
        else:
            y[i] = 0.15 + 0.22 * np.exp(-(t - 0.72) / 0.15)
    return x, y, fases


# --------------------------------------------------------------------------
# Verificacao ampliada, contagem por coorte e juncao livre de parcelas
# --------------------------------------------------------------------------

#: rotulo das coortes ausentes ("?" ou em branco) nas contagens
SEM_COORTE = "sem coorte"


def rotulo_coorte(coorte):
    """Rotulo de uma coorte: o ano, "<1998" ou SEM_COORTE."""
    if isinstance(coorte, int):
        return str(coorte)
    if isinstance(coorte, str) and coorte.startswith("<"):
        return coorte
    return SEM_COORTE


def ordem_coortes(rotulos):
    """Coortes anteriores ("<1998") primeiro, depois os anos e por ultimo SEM_COORTE."""
    def chave(r):
        if r == SEM_COORTE:
            return (2, 0, r)
        if r.isdigit():
            return (1, int(r), r)
        return (0, 0, r)
    return sorted(set(rotulos), key=chave)


def ano_estabelecimento(nome):
    """Ano de estabelecimento de uma parcela ou de uma uniao ("A+B": o mais antigo). 0 se
    nao houver informacao."""
    anos = [ANOS_ESTABELECIMENTO.get(p) for p in str(nome).split("+")]
    anos = [a for a in anos if a]
    return min(anos) if anos else 0


def monta_unidas(grupos, existentes):
    """Dicionario ``unidas`` ({"A+B": ["A", "B"]}) a partir de listas de parcelas.

    Cada grupo precisa de duas parcelas ou mais, entre as ``existentes``; uma parcela so
    entra no primeiro grupo em que aparece. Retorna (unidas, repetidas) com as parcelas
    que apareceram em mais de um grupo."""
    usados, repetidas, out = set(), [], {}
    for g in grupos:
        membros = [p for p in dict.fromkeys(g) if p in existentes]
        repetidas += [p for p in membros if p in usados]
        membros = sorted(p for p in membros if p not in usados)
        if len(membros) >= 2:
            out["+".join(membros)] = membros
            usados |= set(membros)
    return out, sorted(set(repetidas))


def contagem_por_ano(parcelas, selecao, por="classe", agrupar="coorte", unidas=None):
    """Individuos por ano, de uma selecao de classes ou de codigos, empilhados por um grupo.

    ``selecao`` e uma lista de classes (``por="classe"``: jovem, plantula, morto...) ou de
    codigos (``por="codigo"``: J, X, Y, M...); os itens escolhidos entram juntos na contagem.
    ``agrupar`` separa a contagem por "coorte", "especie", "codigo", "classe" ou "nenhum".
    Cada linha com J conta um jovem (como na densidade); as demais, um individuo.
    Retorna parcela, ano, grupo, n; ``unidas`` junta parcelas."""
    cols = ["parcela", "ano", "grupo", "n"]
    tabs = [tabela_individuos(p) for p in parcelas]
    tabs = pd.concat(tabs, ignore_index=True) if tabs else pd.DataFrame()
    if tabs.empty or not selecao:
        return pd.DataFrame(columns=cols)
    d = tabs[tabs["classe" if por == "classe" else "codigo"].isin(list(selecao))].copy()
    if d.empty:
        return pd.DataFrame(columns=cols)
    d["n"] = d["n_jovens"].where(d["classe"] == "jovem", 1)
    if agrupar == "coorte":
        d["grupo"] = d["coorte"].map(rotulo_coorte)
    elif agrupar in ("especie", "codigo", "classe"):
        d["grupo"] = d[agrupar]
    else:
        d["grupo"] = ""
    for nome, membros in (unidas or {}).items():
        d.loc[d["parcela"].isin(membros), "parcela"] = nome
    return d.groupby(["parcela", "ano", "grupo"], as_index=False)["n"].sum().astype(
        {"n": int})[cols]


def tabela_codigos_por_ano(parcela):
    """Individuos de cada codigo em cada ano (linhas: ano; colunas: codigos, do mais
    frequente ao menos)."""
    t = tabela_individuos(parcela)
    if t.empty:
        return pd.DataFrame(columns=["ano"])
    piv = t.pivot_table(index="ano", columns="codigo", values="linha", aggfunc="count",
                        fill_value=0)
    return piv[piv.sum().sort_values(ascending=False).index].reset_index()


def tabela_registros(parcela):
    """Por ano: individuos com registro, novos (primeiro ano em que aparecem) e ultimos
    (ultimo ano em que aparecem, sem contar o ultimo ano da parcela)."""
    t = tabela_individuos(parcela)
    cols = ["ano", "registros", "novos", "ultimos"]
    if t.empty:
        return pd.DataFrame(columns=cols)
    primeiro, ultimo = t.groupby("grupo")["ano"].min(), t.groupby("grupo")["ano"].max()
    anos = sorted(t["ano"].unique())
    return pd.DataFrame({"ano": anos,
                         "registros": [int((t["ano"] == a).sum()) for a in anos],
                         "novos": [int((primeiro == a).sum()) for a in anos],
                         "ultimos": [int(((ultimo == a) & (a < anos[-1])).sum())
                                     for a in anos]})[cols]


def tabela_especies(parcela):
    """Por especie: individuos, os que foram jovens em algum ano e os sem coorte."""
    linhas = {}
    for i in parcela.individuos:
        if not i.por_bloco or not i.especie.strip():
            continue
        r = linhas.setdefault(i.especie.strip().capitalize(),
                              {"individuos": 0, "ja_jovens": 0, "sem_coorte": 0})
        r["individuos"] += 1
        r["ja_jovens"] += any(d["classe"] == "jovem" for d in i.por_bloco.values())
        r["sem_coorte"] += rotulo_coorte(i.coorte) == SEM_COORTE
    out = pd.DataFrame(linhas).T.rename_axis("especie").reset_index()
    return out if not out.empty else pd.DataFrame(
        columns=["especie", "individuos", "ja_jovens", "sem_coorte"])


def tabela_alertas_altura(parcela, maximo_cm=600.0):
    """Por ano: linhas com J, as sem altura medida, a maior altura e as alturas suspeitas
    (zero, negativas ou acima de ``maximo_cm``)."""
    t = tabela_individuos(parcela)
    t = t[t["classe"] == "jovem"]
    linhas = []
    for ano, g in t.groupby("ano"):
        alturas = [h for lst in g["alturas_j"] for h in lst]
        medidas = [float(h) for h in alturas if h is not None and not pd.isna(h)]
        linhas.append({"ano": ano, "linhas_j": len(alturas),
                       "sem_altura": len(alturas) - len(medidas),
                       "altura_maxima": max(medidas) if medidas else float("nan"),
                       "suspeitas": sum(1 for h in medidas if h <= 0 or h > maximo_cm)})
    return pd.DataFrame(linhas, columns=["ano", "linhas_j", "sem_altura", "altura_maxima",
                                         "suspeitas"])
