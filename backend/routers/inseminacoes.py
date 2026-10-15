"""Registar inseminação — equivalente a `modules/pages/insemination_page.py`.

Criar usa `registar_inseminacao_completa` (uma transação: desconta as
palhetas dos lotes, liga à estadia ativa da égua, cria o acompanhamento e
as tarefas D+1 / D+14); editar usa `registrar_inseminacao_multiplas`, como a
app atual (repõe as palhetas antigas e grava as novas).
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.deps import get_current_user
from backend.serial import registos, valor
from modules.db import get_connection
from modules.repositories.insemination_repo import (
    InseminacaoError,
    listar_eguas_com_estadia_ativa,
    registar_inseminacao_completa,
    registrar_inseminacao_multiplas,
)
from modules.repositories.owner_repo import atualizar_status_proprietarios
from modules.repositories.stock_repo import carregar_stock

router = APIRouter(prefix="/api/inseminacoes", tags=["inseminacoes"])

COLS_LOTE = ["id", "garanhao_nome", "dono_id", "proprietario_nome", "data_embriovet", "origem_externa", "contentor_codigo",
             "local_armazenagem", "canister", "andar", "motilidade", "dose", "cor", "concentracao", "existencia_atual"]


def _erro(http_status: int, chave: str, **params):
    return HTTPException(http_status, {"code": chave, "params": params})


@router.get("/lotes")
def lotes(_user: dict = Depends(get_current_user)):
    """Lotes com palhetas (donos ativos ou sem dono), como a página atual."""
    return registos(carregar_stock(apenas_ativos=True), COLS_LOTE)


@router.get("/eguas")
def eguas(_user: dict = Depends(get_current_user)):
    """Éguas/receptoras com estadia ou visita aberta (só essas podem ser inseminadas)."""
    return [{k: valor(v) for k, v in e.items()} for e in listar_eguas_com_estadia_ativa()]


class Linha(BaseModel):
    stock_id: int
    palhetas: int = Field(gt=0)


class InseminacaoIn(BaseModel):
    animal_id_egua: int
    garanhao: str
    data_inseminacao: date
    linhas: list[Linha] = Field(min_length=1)
    observacoes: str | None = None
    criar_tarefa_d1: bool = True

    @field_validator("observacoes", "garanhao", mode="before")
    @classmethod
    def _limpar(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v


def _validar_linhas(linhas: list[Linha], extra: dict[int, int] | None = None):
    """Todos os lotes existem e têm palhetas que cheguem (`extra` = palhetas
    que a operação a editar já tinha gasto, e que voltam ao lote)."""
    ids = [l.stock_id for l in linhas]
    if len(set(ids)) != len(ids):
        raise _erro(422, "web.insem.error.duplicate_lot")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, existencia_atual FROM estoque_dono WHERE id = ANY(%s)", (ids,))
            exist = dict(cur.fetchall())
    for l in linhas:
        if l.stock_id not in exist:
            raise _erro(404, "web.insem.error.lot_not_found", id=l.stock_id)
        disponivel = int(exist[l.stock_id] or 0) + (extra or {}).get(l.stock_id, 0)
        if l.palhetas > disponivel:
            raise _erro(409, "web.insem.error.not_enough", id=l.stock_id, max=disponivel)


@router.post("", status_code=201)
def registar(d: InseminacaoIn, user: dict = Depends(get_current_user)):
    egua = next((e for e in listar_eguas_com_estadia_ativa() if e["animal_id"] == d.animal_id_egua), None)
    if not egua:
        raise _erro(409, "web.insem.error.mare_no_stay")
    if not d.garanhao:
        raise _erro(422, "warning.select_garanhao_first")
    _validar_linhas(d.linhas)
    try:
        ret = registar_inseminacao_completa(
            animal_id_egua=d.animal_id_egua,
            estadia_id=int(egua["estadia_id"]),
            dono_id=int(egua["dono_id"]),
            garanhao_nome=d.garanhao,
            data_inseminacao=d.data_inseminacao,
            registros=[{"stock_id": l.stock_id, "palhetas": l.palhetas, "garanhao": d.garanhao} for l in d.linhas],
            observacoes=d.observacoes,
            utilizador=user["username"],
            criar_tarefa_d1=d.criar_tarefa_d1,
        )
    except InseminacaoError as e:
        raise _erro(409, "web.insem.error.failed", detalhe=str(e)) from e
    try:
        atualizar_status_proprietarios()
    except Exception:  # noqa: BLE001 — como a app atual: não falha o registo por isto
        pass
    return {
        "egua": egua["nome"],
        "animal_id_egua": d.animal_id_egua,
        "garanhao": d.garanhao,
        "total_palhetas": ret["total_palhetas"],
        "num_lotes": len(ret["inseminacao_ids"]),
        "data_inseminacao": d.data_inseminacao.isoformat(),
        "data_ver_ovulacao": valor(ret.get("data_ver_ovulacao")) if ret.get("verificar_ovulacao_id") else None,
        "data_1o_diagnostico": valor(ret["data_1o_diagnostico"]),
    }


# ── Editar (a partir da Atividade) ────────────────────────────────────────

def _linhas_da_operacao(ref: str) -> list[tuple]:
    """`ref` = operation_id (UUID) ou "id-<n>" para linhas antigas sem operação."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            onde = "i.id = %s" if ref.startswith("id-") else "i.operation_id = %s::uuid"
            par = int(ref[3:]) if ref.startswith("id-") else ref
            cur.execute(
                f"""
                SELECT i.id, i.estoque_id, i.palhetas_gastas, i.data_inseminacao, i.observacoes,
                       i.animal_id_egua, i.egua, i.garanhao, ed.existencia_atual
                FROM inseminacoes i
                LEFT JOIN estoque_dono ed ON ed.id = i.estoque_id
                WHERE {onde}
                ORDER BY i.id
                """,
                (par,),
            )
            return cur.fetchall()


@router.get("/operacao/{ref}")
def operacao(ref: str, _user: dict = Depends(get_current_user)):
    try:
        rows = _linhas_da_operacao(ref)
    except Exception as e:  # UUID inválido
        raise _erro(404, "web.insem.error.not_found") from e
    if not rows:
        raise _erro(404, "web.insem.error.not_found")
    r0 = rows[0]
    return {
        "ref": ref,
        "animal_id_egua": r0[5],
        "egua": r0[6],
        "garanhao": r0[7],
        "data_inseminacao": valor(r0[3]),
        "observacoes": r0[4],
        # Disponível = o que o lote tem + o que esta operação já gastou dele.
        "linhas": [{"stock_id": r[1], "palhetas": r[2], "max": int(r[8] or 0) + int(r[2] or 0)} for r in rows if r[1]],
    }


@router.put("/operacao/{ref}")
def editar(ref: str, d: InseminacaoIn, _user: dict = Depends(get_current_user)):
    atual = operacao(ref)
    _validar_linhas(d.linhas, extra={l["stock_id"]: int(l["palhetas"] or 0) for l in atual["linhas"]})
    # Cada linha leva o dono do lote (como a app atual).
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, dono_id FROM estoque_dono WHERE id = ANY(%s)", ([l.stock_id for l in d.linhas],))
            donos = dict(cur.fetchall())
    ok = registrar_inseminacao_multiplas(
        [{"stock_id": l.stock_id, "palhetas": l.palhetas, "garanhao": d.garanhao, "dono_id": donos.get(l.stock_id)} for l in d.linhas],
        d.data_inseminacao,
        atual["egua"],
        int(ref[3:]) if ref.startswith("id-") else None,
        observacoes=d.observacoes,
        edit_operation_id=None if ref.startswith("id-") else ref,
        animal_id_egua=atual["animal_id_egua"] or d.animal_id_egua,
    )
    if not ok:
        raise _erro(409, "web.insem.error.edit_failed")
    return {"ok": True}
