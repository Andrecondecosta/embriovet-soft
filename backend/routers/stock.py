"""Stock de sémen — separadores Lotes e Garanhões + "Adicionar lote".

Equivalente a `modules/pages/stock_page.py`, `stock_semen_page.py`
(separador Garanhões) e `add_stock_view.py`. As escritas usam os mesmos
repositórios (`inserir_stock`, `editar_stock`, `deletar_stock`); as
leituras são consultas próprias, filtradas na BD, com o mesmo critério de
`carregar_stock(apenas_ativos=True)`.

Permissões iguais à app atual: todos veem e adicionam lotes; editar e
eliminar só Administrador.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from backend.deps import get_current_user, require_nivel
from modules.db import get_connection
from modules.repositories.animal_repo import get_or_create_garanhao
from modules.repositories.stock_repo import (
    contar_ligacoes_stock,
    deletar_stock,
    editar_stock,
    inserir_stock,
)

router = APIRouter(prefix="/api/stock", tags=["stock"])

_COLUNAS_LOTE = [
    "id", "garanhao", "garanhao_nome", "animal_id", "dono_id", "proprietario_nome",
    "data_embriovet", "origem_externa", "palhetas_produzidas", "qualidade",
    "concentracao", "motilidade", "local_armazenagem", "certificado", "dose",
    "observacoes", "quantidade_inicial", "existencia_atual", "data_criacao",
    "criado_por", "contentor_id", "contentor_codigo", "canister", "andar", "cor",
]

_SELECT_LOTE = """
    SELECT e.id, e.garanhao, COALESCE(a.nome, e.garanhao) AS garanhao_nome, e.animal_id,
           e.dono_id, d.nome AS proprietario_nome, e.data_embriovet, e.origem_externa,
           e.palhetas_produzidas, e.qualidade, e.concentracao, e.motilidade,
           e.local_armazenagem, e.certificado, e.dose, e.observacoes,
           e.quantidade_inicial, e.existencia_atual, e.data_criacao, e.criado_por,
           e.contentor_id, c.codigo AS contentor_codigo, e.canister, e.andar, e.cor
    FROM estoque_dono e
    LEFT JOIN dono d ON e.dono_id = d.id
    LEFT JOIN contentores c ON e.contentor_id = c.id
    LEFT JOIN animais a ON a.id = e.animal_id
"""

# Mesmo critério de `carregar_stock(apenas_ativos=True)`: lotes de donos
# inativos não aparecem; lotes sem dono sim.
_SO_DONOS_ATIVOS = "(d.ativo = TRUE OR e.dono_id IS NULL)"


def _erro(http_status: int, code: str, **params):
    return HTTPException(http_status, {"code": code, "params": params})


def _lote(row) -> dict:
    d = dict(zip(_COLUNAS_LOTE, row))
    if isinstance(d["data_criacao"], datetime):
        d["data_criacao"] = d["data_criacao"].isoformat()
    return d


def _obter_lote(lote_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_SELECT_LOTE + " WHERE e.id = %s", (lote_id,))
            row = cur.fetchone()
    return _lote(row) if row else None


def _qualidade_media(lotes: list[dict]) -> float | None:
    """Como `stock_kpis`: média das qualidades que são números."""
    valores = []
    for l in lotes:
        try:
            valores.append(float(str(l["qualidade"]).strip().rstrip("%").replace(",", ".")))
        except (TypeError, ValueError):
            pass
    return round(sum(valores) / len(valores), 1) if valores else None


# ── Leituras ──────────────────────────────────────────────────────────────

@router.get("/garanhoes")
def garanhoes(_user: dict = Depends(get_current_user)):
    """Garanhões com stock: alimenta o seletor dos Lotes e o separador
    Garanhões. `no_seletor` = tem stock visível na lista de Lotes (donos
    ativos ou sem dono), como o selectbox da app atual."""
    sql = f"""
        SELECT a.id AS animal_id,
               COALESCE(a.nome, e.garanhao) AS garanhao,
               SUM(e.existencia_atual)::int AS palhetas,
               COUNT(DISTINCT e.id)::int AS lotes,
               COUNT(DISTINCT e.dono_id)::int AS donos,
               BOOL_OR({_SO_DONOS_ATIVOS}) AS no_seletor
        FROM estoque_dono e
        LEFT JOIN animais a ON a.id = e.animal_id
        LEFT JOIN dono d ON d.id = e.dono_id
        WHERE e.existencia_atual > 0
        GROUP BY 1, 2
        ORDER BY LOWER(COALESCE(a.nome, e.garanhao)) ASC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    return [
        {"animal_id": r[0], "garanhao": r[1], "palhetas": r[2], "lotes": r[3],
         "donos": r[4], "no_seletor": bool(r[5])}
        for r in rows
    ]


@router.get("/lotes")
def lotes(
    garanhao: str,
    donos: list[int] = Query(default=[]),
    sem_dono: bool = False,
    min_palhetas: int = Query(0, ge=0),
    incluir_vazios: bool = False,
    user: dict = Depends(get_current_user),
):
    """Lotes de um garanhão, com os indicadores e o resumo por dono que a
    app atual mostra por cima da lista."""
    where = ["COALESCE(a.nome, e.garanhao) = %s", _SO_DONOS_ATIVOS]
    params: list = [garanhao]
    if not incluir_vazios:
        where.append("e.existencia_atual > 0")
    if min_palhetas:
        where.append("COALESCE(e.existencia_atual, 0) >= %s")
        params.append(min_palhetas)
    if donos or sem_dono:
        filtro = []
        if donos:
            filtro.append("e.dono_id = ANY(%s)")
            params.append(donos)
        if sem_dono:
            filtro.append("e.dono_id IS NULL")
        where.append(f"({' OR '.join(filtro)})")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_SELECT_LOTE + " WHERE " + " AND ".join(where) + " ORDER BY e.id", params)
            items = [_lote(r) for r in cur.fetchall()]
            # Opções do filtro de proprietários: os donos com stock deste
            # garanhão, independentemente dos outros filtros.
            cur.execute(
                f"""
                SELECT DISTINCT e.dono_id, d.nome
                FROM estoque_dono e
                LEFT JOIN dono d ON e.dono_id = d.id
                LEFT JOIN animais a ON a.id = e.animal_id
                WHERE COALESCE(a.nome, e.garanhao) = %s AND {_SO_DONOS_ATIVOS}
                  AND (e.existencia_atual > 0 OR %s)
                ORDER BY d.nome NULLS LAST
                """,
                (garanhao, incluir_vazios),
            )
            donos_disponiveis = [{"id": r[0], "nome": r[1]} for r in cur.fetchall()]

    resumo: dict[tuple, int] = {}
    for l in items:
        chave = (l["dono_id"], l["proprietario_nome"])
        resumo[chave] = resumo.get(chave, 0) + int(l["existencia_atual"] or 0)

    ligacoes = {}
    if user["nivel"] == "Administrador" and items:
        ligacoes = contar_ligacoes_stock([l["id"] for l in items])

    return {
        "items": items,
        "kpis": {
            "lotes": len(items),
            "palhetas": sum(int(l["existencia_atual"] or 0) for l in items),
            "proprietarios": len({l["dono_id"] for l in items if l["dono_id"] is not None}),
            "qualidade_media": _qualidade_media(items),
        },
        "por_proprietario": sorted(
            ({"dono_id": k[0], "proprietario_nome": k[1], "palhetas": v} for k, v in resumo.items()),
            key=lambda x: -x["palhetas"],
        ),
        "ligacoes": {str(k): v for k, v in ligacoes.items()},
        "donos_disponiveis": donos_disponiveis,
    }


@router.get("/lotes/{lote_id}")
def obter_lote(lote_id: int, _user: dict = Depends(get_current_user)):
    lote = _obter_lote(lote_id)
    if not lote:
        raise _erro(404, "web.stock.error.not_found")
    return lote


@router.get("/transferencias")
def transferencias(garanhao: str, _user: dict = Depends(get_current_user)):
    """Histórico de transferências de um garanhão (internas e externas).
    O ecrã filtra por dono/lote — como `filter_transfer_history` e
    `filter_lot_transfer_history`."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.id, t.data_transferencia, t.quantidade,
                       t.proprietario_origem_id, d1.nome, t.proprietario_destino_id, d2.nome
                FROM transferencias t
                LEFT JOIN estoque_dono e ON t.estoque_id = e.id
                LEFT JOIN animais a ON a.id = e.animal_id
                LEFT JOIN dono d1 ON t.proprietario_origem_id = d1.id
                LEFT JOIN dono d2 ON t.proprietario_destino_id = d2.id
                WHERE COALESCE(a.nome, e.garanhao) = %s
                ORDER BY t.data_transferencia DESC
                """,
                (garanhao,),
            )
            internas = [
                {"id": r[0], "data": r[1].isoformat() if r[1] else None, "quantidade": r[2],
                 "origem_id": r[3], "origem": r[4], "destino_id": r[5], "destino": r[6]}
                for r in cur.fetchall()
            ]
            cur.execute(
                """
                SELECT te.id, te.data_transferencia, te.quantidade, te.proprietario_origem_id,
                       d.nome, te.destinatario_externo, te.tipo, te.observacoes
                FROM transferencias_externas te
                LEFT JOIN estoque_dono e ON te.estoque_id = e.id
                LEFT JOIN animais a ON a.id = e.animal_id
                LEFT JOIN dono d ON te.proprietario_origem_id = d.id
                WHERE COALESCE(a.nome, e.garanhao, te.garanhao) = %s
                ORDER BY te.data_transferencia DESC
                """,
                (garanhao,),
            )
            externas = [
                {"id": r[0], "data": r[1].isoformat() if r[1] else None, "quantidade": r[2],
                 "origem_id": r[3], "origem": r[4], "destinatario": r[5], "tipo": r[6],
                 "observacoes": r[7]}
                for r in cur.fetchall()
            ]
    return {"internas": internas, "externas": externas}


# ── Escritas ──────────────────────────────────────────────────────────────

def _texto(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


class _LoteBase(BaseModel):
    data_embriovet: str | None = None
    origem_externa: str | None = None
    qualidade: str | None = None
    concentracao: int = Field(0, ge=0)
    motilidade: int = Field(0, ge=0, le=100)
    certificado: Literal["Sim", "Não"] = "Sim"
    dose: str | None = None
    cor: str | None = None
    contentor_id: int
    canister: int = Field(ge=1, le=10)
    andar: Literal[1, 2]
    observacoes: str | None = None

    @field_validator("data_embriovet", "origem_externa", "qualidade", "dose", "cor", "observacoes",
                     mode="before")
    @classmethod
    def _limpar(cls, v):
        return _texto(v)


class LoteNovo(_LoteBase):
    garanhao: str
    dono_id: int
    palhetas: int = Field(gt=0)

    @field_validator("garanhao", mode="before")
    @classmethod
    def _garanhao(cls, v):
        v = _texto(v)
        if not v:
            raise ValueError("error.stallion_required")
        return v


class LoteEdicao(_LoteBase):
    garanhao: str
    dono_id: int
    palhetas_produzidas: int = Field(0, ge=0)
    existencia_atual: int = Field(0, ge=0)


def _validar_refs(dono_id: int, contentor_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM dono WHERE id = %s", (dono_id,))
            dono_ok = cur.fetchone() is not None
            cur.execute("SELECT 1 FROM contentores WHERE id = %s AND ativo = TRUE", (contentor_id,))
            contentor_ok = cur.fetchone() is not None
    if not dono_ok:
        raise _erro(422, "web.owners.error.not_found")
    if not contentor_ok:
        raise _erro(422, "error.container_required")


@router.post("/lotes", status_code=status.HTTP_201_CREATED)
def criar_lote(body: LoteNovo, user: dict = Depends(get_current_user)):
    _validar_refs(body.dono_id, body.contentor_id)
    novo_id = inserir_stock(
        {
            "Garanhão": body.garanhao,
            "Proprietário": body.dono_id,
            "Data": body.data_embriovet,
            "Origem": body.origem_externa,
            "Palhetas": body.palhetas,
            "Qualidade": body.qualidade,
            "Concentração": body.concentracao,
            "Motilidade": body.motilidade,
            "Certificado": body.certificado,
            "Dose": body.dose,
            "Contentor": body.contentor_id,
            "Canister": body.canister,
            "Andar": body.andar,
            "Cor": body.cor,
            "Observações": body.observacoes,
        },
        username=user["username"],
    )
    if not novo_id:
        raise _erro(500, "web.error.generic")
    return _obter_lote(int(novo_id))


@router.put("/lotes/{lote_id}")
def editar_lote(lote_id: int, body: LoteEdicao, _user: dict = Depends(require_nivel("Administrador"))):
    if not _obter_lote(lote_id):
        raise _erro(404, "web.stock.error.not_found")
    _validar_refs(body.dono_id, body.contentor_id)
    # Trocar de garanhão a sério: muda a ligação à ficha (animal_id), não
    # só o texto antigo — na app atual o campo não tinha efeito visível.
    # Um nome novo cria o garanhão, como em "Adicionar lote".
    animal_id = get_or_create_garanhao(body.garanhao)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT nome FROM animais WHERE id = %s", (animal_id,))
            nome_garanhao = cur.fetchone()[0]
    ok = editar_stock(
        lote_id,
        {
            "animal_id": animal_id,
            "garanhao": nome_garanhao,
            "dono_id": body.dono_id,
            "data": body.data_embriovet,
            "origem": body.origem_externa,
            "palhetas_produzidas": body.palhetas_produzidas,
            "qualidade": body.qualidade,
            "concentracao": body.concentracao,
            "cor": body.cor,
            "motilidade": body.motilidade,
            "contentor_id": body.contentor_id,
            "canister": body.canister,
            "andar": body.andar,
            "certificado": body.certificado,
            "dose": body.dose,
            "observacoes": body.observacoes,
            "existencia": body.existencia_atual,
        },
    )
    if not ok:
        raise _erro(500, "web.error.generic")
    return _obter_lote(lote_id)


@router.delete("/lotes/{lote_id}")
def apagar_lote(lote_id: int, _user: dict = Depends(require_nivel("Administrador"))):
    if not _obter_lote(lote_id):
        raise _erro(404, "web.stock.error.not_found")
    if not deletar_stock(lote_id):
        raise _erro(500, "web.error.generic")
    return {"ok": True}
