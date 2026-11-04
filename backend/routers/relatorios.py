"""Relatórios — equivalente a `modules/pages/reports_page.py`.

Os mesmos 4 modos (garanhão, proprietário, contentor, histórico), o mesmo
filtro de período e os mesmos ficheiros (PDF/CSV do garanhão, CSV do
proprietário, PDF/CSV/Excel do stock completo). A lógica é a da página
atual, reaproveitada: os números têm de bater com os que os clientes já
conhecem.

A mais do que a app antiga: PDF, Excel e CSV em todos (os que não tinham
ficheiro próprio usam
`modules/relatorio_export.py`, a partir das mesmas tabelas do ecrã).

As etiquetas (KPIs, títulos, colunas) vão como chaves de tradução; o ecrã
traduz.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from backend.deps import get_current_user
from backend.i18n_web import WEB_TRANSLATIONS
from backend.serial import anexo, registos
from modules.db import to_py
from modules.i18n import TRANSLATIONS
from modules.pages.reports_page import (
    _contar_operacoes,
    _filtrar_stock_por_periodo,
    aplicar_filtro_data,
    gerar_pdf_garanhao,
)
from modules.repositories.settings_repo import get_app_settings
from modules.repositories.stock_repo import (
    carregar_contentores,
    carregar_inseminacoes,
    carregar_proprietarios,
    carregar_stock,
    carregar_transferencias,
    carregar_transferencias_externas,
)
from modules.relatorio_export import gerar_csv, gerar_excel, gerar_pdf
from modules.stock_export import gerar_csv_stock, gerar_excel_stock, gerar_pdf_stock
from modules.ui_kit import safe_pick

router = APIRouter(prefix="/api/relatorios", tags=["relatorios"])

Modo = Literal["garanhao", "proprietario", "contentor", "historico"]
Hist = Literal["insem", "transf_int", "transf_ext", "stock"]

# Colunas de cada tabela, pela ordem da página atual.
COL_STOCK_G = ["proprietario_nome", "data_embriovet", "existencia_atual", "motilidade"]
COL_INSEM_G = ["data_inseminacao", "egua_nome", "proprietario_nome", "palhetas_gastas"]
COL_TRANSF_G = ["data_transferencia", "proprietario_origem", "proprietario_destino", "quantidade"]
COL_EXT_G = ["data_transferencia", "proprietario_origem", "destinatario_externo", "quantidade", "tipo"]
COL_STOCK_P = ["garanhao_nome", "data_embriovet", "existencia_atual", "motilidade"]
COL_CSV_P = ["garanhao_nome", "existencia_atual", "motilidade", "data_embriovet"]
COL_STOCK_C = ["proprietario_nome", "garanhao_nome", "existencia_atual", "canister", "andar", "data_embriovet", "data_criacao"]
COL_H_INSEM = ["data_inseminacao", "garanhao_nome", "egua_nome", "proprietario_nome", "palhetas_gastas"]
COL_H_TRANSF = ["data_transferencia", "garanhao", "proprietario_origem", "proprietario_destino", "quantidade"]
COL_H_EXT = ["data_transferencia", "garanhao", "proprietario_origem", "destinatario_externo", "tipo", "quantidade", "observacoes"]
COL_H_STOCK = ["proprietario_nome", "garanhao_nome", "data_embriovet", "data_criacao", "existencia_atual", "motilidade", "local_armazenagem"]

# Colunas que se podem acrescentar no ficheiro (Exportar → Colunas), além das do ecrã.
EXTRA_STOCK = [
    "garanhao_nome", "proprietario_nome", "data_embriovet", "origem_externa", "palhetas_produzidas", "quantidade_inicial",
    "existencia_atual", "qualidade", "cor", "concentracao", "motilidade", "certificado", "dose", "contentor_codigo",
    "canister", "andar", "local_armazenagem", "observacoes", "criado_por", "data_criacao",
]
EXTRA_INSEM = ["protocolo", "resultado", "observacoes", "utilizador"]
EXTRA_TRANSF = ["utilizador"]


def _erro(http_status: int, chave: str, **params):
    return HTTPException(http_status, {"code": chave, "params": params})


def _soma(df, col="existencia_atual") -> int:
    return int(to_py(df[col].sum()) or 0) if not df.empty else 0


def _ordenar(df, col, desc=True):
    return df.sort_values(col, ascending=not desc) if not df.empty and col in df.columns else df


def _tabela(titulo: str, df, colunas: list[str], extra: list[str] | None = None) -> dict:
    """`colunas` são as do ecrã; `disponiveis` as que se podem pôr no
    ficheiro. Cada linha leva o `_id` do registo, para escolher linhas."""
    disponiveis = colunas + [c for c in (extra or []) if c not in colunas]
    mapa = {c: c for c in disponiveis} | {"id": "_id"}
    return {"titulo": titulo, "colunas": colunas, "disponiveis": disponiveis, "linhas": registos(safe_pick(df, list(mapa)), mapa)}


def _unicos(df, col) -> list:
    if df.empty or col not in df.columns:
        return []
    return [to_py(v) for v in sorted(df[col].dropna().unique())]


class Pedido:
    """Parâmetros comuns ao relatório e à exportação."""

    def __init__(
        self,
        modo: Modo,
        garanhao: str | None = None,
        proprietario: int | None = None,
        contentor: int | None = None,
        hist: Hist = "insem",
        inicio: date | None = None,
        fim: date | None = None,
        f_prop: list[str] = Query(default=[]),
        f_gar: list[str] = Query(default=[]),
        f_can: list[int] = Query(default=[]),
        f_and: list[int] = Query(default=[]),
    ):
        if inicio and fim and inicio > fim:
            raise _erro(422, "reports.invalid_period")
        self.modo, self.garanhao, self.proprietario, self.contentor, self.hist = modo, garanhao, proprietario, contentor, hist
        self.inicio, self.fim = inicio, fim
        self.f_prop, self.f_gar, self.f_can, self.f_and = f_prop, f_gar, f_can, f_and


def _dados(p: Pedido) -> dict:
    """Carrega tudo e aplica o período, como a página atual."""
    stock = carregar_stock()
    insem = carregar_inseminacoes()
    transf = carregar_transferencias()
    transf_ext = carregar_transferencias_externas()
    if p.inicio or p.fim:
        insem = aplicar_filtro_data(insem, "data_inseminacao", p.inicio, p.fim)
        transf = aplicar_filtro_data(transf, "data_transferencia", p.inicio, p.fim)
        transf_ext = aplicar_filtro_data(transf_ext, "data_transferencia", p.inicio, p.fim)
        stock = _filtrar_stock_por_periodo(stock, p.inicio, p.fim)
    return {"stock": stock, "insem": insem, "transf": transf, "transf_ext": transf_ext}


def _por_garanhao(p: Pedido, d: dict) -> dict:
    g = p.garanhao
    stock, insem, transf, ext = d["stock"], d["insem"], d["transf"], d["transf_ext"]
    base = stock[stock["garanhao_nome"] == g] if not stock.empty else pd.DataFrame()
    s = base[base["proprietario_nome"].isin(p.f_prop)] if p.f_prop and not base.empty else base
    i = insem[insem["garanhao_nome"] == g] if not insem.empty else pd.DataFrame()
    tr = transf[transf["garanhao"] == g] if not transf.empty else pd.DataFrame()
    te = ext[ext["garanhao"] == g] if not ext.empty else pd.DataFrame()
    return {
        "s": s, "i": i, "tr": tr, "te": te,
        "filtros": {"prop": _unicos(base, "proprietario_nome")},
        "kpis": [
            ["reports.kpi.straws_stock", _soma(s)],
            ["reports.kpi.inseminations", _contar_operacoes(i)],
            ["reports.kpi.transfers_in", len(tr)],
            ["reports.kpi.transfers_out", len(te)],
        ],
    }


def _por_proprietario(p: Pedido, d: dict) -> dict:
    stock, insem, transf = d["stock"], d["insem"], d["transf"]
    base = stock[stock["dono_id"] == p.proprietario] if not stock.empty else pd.DataFrame()
    s = base[base["garanhao_nome"].isin(p.f_gar)] if p.f_gar and not base.empty else base
    i = insem[insem["dono_id"] == p.proprietario] if not insem.empty else pd.DataFrame()
    t_in = transf[transf["proprietario_destino_id"] == p.proprietario] if not transf.empty else pd.DataFrame()
    t_out = transf[transf["proprietario_origem_id"] == p.proprietario] if not transf.empty else pd.DataFrame()
    return {
        "s": s,
        "filtros": {"gar": _unicos(base, "garanhao_nome")},
        "kpis": [
            ["reports.kpi.straws_stock", _soma(s)],
            ["reports.kpi.inseminations", _contar_operacoes(i)],
            ["reports.kpi.transfers_received", len(t_in)],
            ["reports.kpi.transfers_sent", len(t_out)],
        ],
    }


def _por_contentor(p: Pedido, d: dict) -> dict:
    stock = d["stock"]
    base = stock[stock["contentor_id"] == p.contentor].copy() if (not stock.empty and "contentor_id" in stock.columns) else pd.DataFrame()
    s = base
    if p.f_gar and not s.empty:
        s = s[s["garanhao_nome"].isin(p.f_gar)]
    if p.f_prop and not s.empty:
        s = s[s["proprietario_nome"].isin(p.f_prop)]
    if p.f_can and "canister" in s.columns:
        s = s[s["canister"].isin(p.f_can)]
    if p.f_and and "andar" in s.columns:
        s = s[s["andar"].isin(p.f_and)]
    return {
        "s": s,
        "filtros": {
            "gar": _unicos(base, "garanhao_nome"),
            "prop": _unicos(base, "proprietario_nome"),
            "can": _unicos(base, "canister"),
            "and": _unicos(base, "andar"),
        },
        "kpis": [
            ["reports.kpi.lots", len(s)],
            ["reports.kpi.straws", _soma(s)],
            ["reports.kpi.canisters", int(s["canister"].nunique()) if (not s.empty and "canister" in s.columns) else 0],
        ],
    }


@router.get("/opcoes")
def opcoes(_user: dict = Depends(get_current_user)):
    stock = carregar_stock()
    props = carregar_proprietarios()
    conts = carregar_contentores()
    return {
        "garanhoes": _unicos(stock, "garanhao_nome"),
        "proprietarios": registos(props, ["id", "nome"]),
        "contentores": registos(conts, ["id", "codigo", "descricao"]),
    }


FORMATOS: list[str] = ["pdf", "xlsx", "csv"]
VAZIO = {"kpis": [], "tabelas": [], "filtros": {}, "exportar": []}


def _montar(p: Pedido) -> dict:
    """O relatório que o ecrã mostra — e de onde saem os ficheiros."""
    d = _dados(p)
    if p.modo == "garanhao":
        if not p.garanhao:
            return VAZIO
        r = _por_garanhao(p, d)
        return {
            "kpis": r["kpis"],
            "filtros": r["filtros"],
            "titulo": ("reports.mode.stallion", p.garanhao),
            "tabelas": [
                _tabela("reports.section.stock", _ordenar(r["s"], "existencia_atual"), COL_STOCK_G, EXTRA_STOCK),
                _tabela("reports.section.inseminations", _ordenar(r["i"], "data_inseminacao"), COL_INSEM_G, EXTRA_INSEM),
            ],
        }
    if p.modo == "proprietario":
        if p.proprietario is None:
            return VAZIO
        r = _por_proprietario(p, d)
        props = carregar_proprietarios()
        nome = props.loc[props["id"] == p.proprietario, "nome"]
        i = d["insem"][d["insem"]["dono_id"] == p.proprietario] if not d["insem"].empty else pd.DataFrame()
        return {
            "kpis": r["kpis"],
            "filtros": r["filtros"],
            "titulo": ("reports.mode.owner", nome.iloc[0] if not nome.empty else str(p.proprietario)),
            "tabelas": [_tabela("reports.section.stock", _ordenar(r["s"], "existencia_atual"), COL_STOCK_P, EXTRA_STOCK)],
        }
    if p.modo == "contentor":
        if p.contentor is None:
            return VAZIO
        r = _por_contentor(p, d)
        conts = carregar_contentores()
        cod = conts.loc[conts["id"] == p.contentor, "codigo"]
        return {
            "kpis": r["kpis"],
            "filtros": r["filtros"],
            "titulo": ("reports.mode.container", cod.iloc[0] if not cod.empty else str(p.contentor)),
            "tabelas": [_tabela("reports.section.stock", r["s"], COL_STOCK_C, EXTRA_STOCK)],
        }
    # Histórico
    if p.hist == "insem":
        tab = _tabela("reports.history.inseminations", _ordenar(d["insem"], "data_inseminacao"), COL_H_INSEM, EXTRA_INSEM)
    elif p.hist == "transf_int":
        tab = _tabela("reports.history.transfer_internal", _ordenar(d["transf"], "data_transferencia"), COL_H_TRANSF, EXTRA_TRANSF)
    elif p.hist == "transf_ext":
        tab = _tabela("reports.history.transfer_external", _ordenar(d["transf_ext"], "data_transferencia"), COL_H_EXT, EXTRA_TRANSF)
    else:
        tab = _tabela("reports.history.full_stock", _ordenar(d["stock"], "existencia_atual"), COL_H_STOCK, EXTRA_STOCK)
    return {"kpis": [], "filtros": {}, "titulo": ("reports.mode.history", tab["titulo"]), "tabelas": [tab]}


@router.get("")
def relatorio(p: Pedido = Depends(), _user: dict = Depends(get_current_user)):
    r = _montar(p)
    if not r["tabelas"]:
        return VAZIO
    return {k: r[k] for k in ("kpis", "filtros", "tabelas")} | {"exportar": FORMATOS}


def _ficheiro(dados: bytes, nome: str, tipo: str) -> Response:
    return Response(dados, media_type=tipo, headers=anexo(nome))


def _t(chave: str, **params) -> str:
    """Texto na língua da app (os ficheiros são gerados no servidor)."""
    lang = (get_app_settings() or {}).get("language") or "pt-PT"
    texto = (
        WEB_TRANSLATIONS.get(lang, {}).get(chave)
        or TRANSLATIONS.get(lang, {}).get(chave)
        or WEB_TRANSLATIONS["pt-PT"].get(chave)
        or TRANSLATIONS["pt-PT"].get(chave, chave)
    )
    return texto.format(**params) if params else texto


TIPOS = {
    "csv": "text/csv",
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@router.get("/exportar")
def exportar(formato: Literal["csv", "pdf", "xlsx"], p: Pedido = Depends(), _user: dict = Depends(get_current_user)):
    d = _dados(p)
    if p.modo == "garanhao" and p.garanhao and formato in ("csv", "pdf"):
        r = _por_garanhao(p, d)
        if formato == "pdf":
            pdf = gerar_pdf_garanhao(p.garanhao, r["s"], r["i"], r["tr"], r["te"])
            if not pdf:
                raise _erro(500, "web.error.generic")
            return _ficheiro(pdf.getvalue(), f"garanhao_{p.garanhao}.pdf", TIPOS["pdf"])
        # O mesmo CSV "por secções" da página atual.
        csv = f"=== {_t('label.garanhao').upper()}: {p.garanhao} ===\n\n"
        for chave, df in {
            "reports.section.stock": safe_pick(r["s"], COL_STOCK_G),
            "reports.section.inseminations": safe_pick(r["i"], COL_INSEM_G),
            "reports.section.transfers_in": safe_pick(r["tr"], COL_TRANSF_G),
            "reports.section.transfers_out": safe_pick(r["te"], COL_EXT_G),
        }.items():
            if not df.empty:
                csv += f"\n{_t(chave)}:\n{df.to_csv(index=False)}\n"
        return _ficheiro(csv.encode("utf-8"), f"garanhao_{p.garanhao}.csv", TIPOS["csv"])

    if p.modo == "proprietario" and p.proprietario is not None and formato == "csv":
        r = _por_proprietario(p, d)
        props = carregar_proprietarios()
        nome = props.loc[props["id"] == p.proprietario, "nome"]
        nome = nome.iloc[0] if not nome.empty else p.proprietario
        return _ficheiro(safe_pick(r["s"], COL_CSV_P).to_csv(index=False).encode("utf-8"), f"proprietario_{nome}.csv", TIPOS["csv"])

    if p.modo == "historico" and p.hist == "stock":
        stock = d["stock"]
        nome = f"stock_completo_{datetime.now():%Y%m%d}.{formato}"
        if formato == "pdf":
            periodo = ""
            if p.inicio or p.fim:
                periodo = _t(
                    "reports.export_period",
                    ini=p.inicio.strftime("%d/%m/%Y") if p.inicio else "…",
                    fim=p.fim.strftime("%d/%m/%Y") if p.fim else "…",
                )
            return _ficheiro(gerar_pdf_stock(stock, periodo), nome, TIPOS["pdf"])
        if formato == "csv":
            return _ficheiro(gerar_csv_stock(stock), nome, TIPOS["csv"])
        return _ficheiro(gerar_excel_stock(stock), nome, TIPOS["xlsx"])

    return _exportar_generico(formato, p)


def _valor_ficheiro(v):
    """Datas como no ecrã (dd/mm/aaaa); números ficam números."""
    if isinstance(v, str) and len(v) >= 10 and v[4] == "-" and v[7] == "-":
        try:
            dt = datetime.fromisoformat(v)
        except ValueError:
            return v
        return f"{dt:%d/%m/%Y}" if len(v) == 10 or (dt.hour, dt.minute) == (0, 0) else f"{dt:%d/%m/%Y %H:%M}"
    return v


class EscolhaTabela(BaseModel):
    titulo: str
    colunas: list[str]
    ids: list[int] | None = None  # None = todas as linhas


class Escolha(BaseModel):
    formato: Literal["csv", "pdf", "xlsx"]
    resumo: bool = True
    tabelas: list[EscolhaTabela]


@router.post("/exportar")
def exportar_escolha(e: Escolha, p: Pedido = Depends(), _user: dict = Depends(get_current_user)):
    """Ficheiro com só as partes, colunas e linhas escolhidas."""
    return _exportar_generico(e.formato, p, e)


def _aplicar_escolha(r: dict, e: Escolha) -> dict:
    por_titulo = {tab["titulo"]: tab for tab in r["tabelas"]}
    tabelas = []
    for et in e.tabelas:
        tab = por_titulo.get(et.titulo)
        colunas = [c for c in (tab or {}).get("disponiveis", []) if c in et.colunas]
        if not tab or not colunas:
            continue
        ids = set(et.ids) if et.ids is not None else None
        linhas = [l for l in tab["linhas"] if ids is None or l.get("_id") in ids]
        tabelas.append(tab | {"colunas": colunas, "linhas": linhas})
    if not tabelas and not (e.resumo and r["kpis"]):
        raise _erro(400, "web.reports.error.nothing_to_export")
    return r | {"tabelas": tabelas, "kpis": r["kpis"] if e.resumo else []}


def _exportar_generico(formato: str, p: Pedido, e: Escolha | None = None) -> Response:
    r = _montar(p)
    if not r["tabelas"]:
        raise _erro(400, "web.reports.error.export_unavailable")
    if e is not None:
        r = _aplicar_escolha(r, e)
    modo, nome = r["titulo"]
    titulo = f"{_t(modo)}: {_t(nome)}"
    kpis = [(_t(label), n) for label, n in r["kpis"]]
    tabelas = [
        (_t(tab["titulo"]), [_t(f"web.reports.col.{c}") for c in tab["colunas"]], [[_valor_ficheiro(l[c]) for c in tab["colunas"]] for l in tab["linhas"]])
        for tab in r["tabelas"]
    ]
    periodo = ""
    if p.inicio or p.fim:
        periodo = _t(
            "reports.export_period",
            ini=p.inicio.strftime("%d/%m/%Y") if p.inicio else "…",
            fim=p.fim.strftime("%d/%m/%Y") if p.fim else "…",
        )
    ficheiro = f"relatorio_{_t(nome)}_{datetime.now():%Y%m%d}.{formato}".replace(" ", "_").replace("/", "-")
    if formato == "pdf":
        dados = gerar_pdf(titulo, periodo, kpis, tabelas, sem_dados=_t("reports.no_data_filters"))
    elif formato == "xlsx":
        dados = gerar_excel(titulo, kpis, tabelas)
    else:
        dados = gerar_csv(titulo, kpis, tabelas)
    return _ficheiro(dados, ficheiro, TIPOS[formato])
