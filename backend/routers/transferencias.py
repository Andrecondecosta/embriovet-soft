"""Transferências (separador do Stock de sémen) — equivalente a
`modules/pages/transfer_page.py`.

- Criar uma operação (vários lotes de uma vez) interna (para outro
  proprietário, mantendo ou mudando a localização) ou externa (venda,
  doação, exportação, outro).
- Editar uma operação: anula a antiga e cria a nova com o mesmo
  `operation_id`, marcada como editada — como a app atual. A anulação usa
  `reverter_operacao` (localiza o lote destino por animal + dono +
  localização, numa transação), em vez do SQL por nome do garanhão que a
  página atual tinha.
- Histórico de operações por dia (transferências e inseminações) com
  anulação.

As escritas por lote são as mesmas funções do repositório que a app atual
usa. Antes de mexer em qualquer coisa, a operação inteira é validada
(lotes existem, quantidades chegam, destino diferente da origem), para não
ficar meia operação gravada.

Permissões iguais à app atual: qualquer utilizador.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.deps import get_current_user
from modules.db import get_connection, invalidate_data_cache
from modules.repositories.audit_repo import registar_historico_edicao
from modules.repositories.dashboard_repo import carregar_atividade_do_dia
from modules.repositories.stock_repo import (
    transferir_palhetas_externo,
    transferir_palhetas_parcial,
    transferir_stock_interno_com_localizacao,
)
from modules.repositories.transfer_repo import reverter_operacao

router = APIRouter(prefix="/api/transferencias", tags=["transferencias"])

TipoOp = Literal["transfer_internal", "transfer_external", "insemination"]
MOTIVOS = ("Venda", "Doação", "Exportação", "Outro")


def _erro(http_status: int, code: str, **params):
    return HTTPException(http_status, {"code": code, "params": params})


# ── Modelos ───────────────────────────────────────────────────────────────

class Linha(BaseModel):
    stock_id: int
    quantidade: int = Field(gt=0)


class NovaLocalizacao(BaseModel):
    contentor_id: int
    # Mesmos limites da página atual (number_input 1–20).
    canister: int = Field(ge=1, le=20)
    andar: int = Field(ge=1, le=20)


class OperacaoIn(BaseModel):
    tipo: Literal["interna", "externa"]
    linhas: list[Linha] = Field(min_length=1)
    destino_id: int | None = None
    nova_localizacao: NovaLocalizacao | None = None
    destinatario: str | None = None
    motivo: Literal["Venda", "Doação", "Exportação", "Outro"] = "Venda"
    observacoes: str | None = None

    @field_validator("destinatario", "observacoes", mode="before")
    @classmethod
    def _limpar(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v

    @model_validator(mode="after")
    def _coerente(self):
        if self.tipo == "interna" and not self.destino_id:
            raise ValueError("transfer.error_no_destination")
        if self.tipo == "externa" and not self.destinatario:
            raise ValueError("transfer.error_no_recipient")
        ids = [l.stock_id for l in self.linhas]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_lot")
        return self


# ── Validação da operação inteira ─────────────────────────────────────────

def _carregar_lotes(ids: list[int]) -> dict[int, dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.id, e.dono_id, d.nome, e.existencia_atual,
                       COALESCE(e.origem_externa, e.data_embriovet, 'Lote #' || e.id)
                FROM estoque_dono e LEFT JOIN dono d ON d.id = e.dono_id
                WHERE e.id = ANY(%s)
                """,
                (ids,),
            )
            return {
                r[0]: {"dono_id": r[1], "dono": r[2], "existencia": int(r[3] or 0), "ref": r[4]}
                for r in cur.fetchall()
            }


def _validar(body: OperacaoIn, devolvido: dict[int, int] | None = None) -> dict[int, dict]:
    """`devolvido`: palhetas que voltam a cada lote ao anular a operação
    que está a ser editada (contam como disponíveis)."""
    devolvido = devolvido or {}
    lotes = _carregar_lotes([l.stock_id for l in body.linhas])
    for l in body.linhas:
        lote = lotes.get(l.stock_id)
        if not lote:
            raise _erro(404, "web.stock.error.not_found")
        disponivel = lote["existencia"] + devolvido.get(l.stock_id, 0)
        if l.quantidade > disponivel:
            raise _erro(409, "web.transfer.error.insufficient", ref=lote["ref"], disponivel=disponivel)
        if body.tipo == "interna" and lote["dono_id"] == body.destino_id:
            raise _erro(409, "web.transfer.error.same_owner", ref=lote["ref"], owner=lote["dono"] or "—")

    with get_connection() as conn:
        with conn.cursor() as cur:
            if body.tipo == "interna":
                cur.execute("SELECT 1 FROM dono WHERE id = %s AND ativo = TRUE", (body.destino_id,))
                if not cur.fetchone():
                    raise _erro(422, "transfer.error_no_destination")
            if body.nova_localizacao:
                cur.execute(
                    "SELECT 1 FROM contentores WHERE id = %s AND ativo = TRUE",
                    (body.nova_localizacao.contentor_id,),
                )
                if not cur.fetchone():
                    raise _erro(422, "transfer.error_no_container")
    return lotes


def _executar(body: OperacaoIn, lotes: dict[int, dict], op_id: str, utilizador: str) -> None:
    for l in body.linhas:
        if body.tipo == "interna":
            if body.nova_localizacao:
                ok = transferir_stock_interno_com_localizacao(
                    lotes[l.stock_id]["dono_id"], body.destino_id, l.stock_id, l.quantidade,
                    body.nova_localizacao.contentor_id, body.nova_localizacao.canister,
                    body.nova_localizacao.andar, operation_id=op_id, utilizador=utilizador,
                )
            else:
                ok = transferir_palhetas_parcial(
                    l.stock_id, body.destino_id, l.quantidade, operation_id=op_id, utilizador=utilizador,
                )
        else:
            ok = transferir_palhetas_externo(
                l.stock_id, body.destinatario, l.quantidade, body.motivo, body.observacoes or "",
                operation_id=op_id, utilizador=utilizador,
            )
        if not ok:
            raise _erro(500, "web.transfer.error.partial", ref=lotes[l.stock_id]["ref"])


# ── Criar ─────────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
def criar(body: OperacaoIn, user: dict = Depends(get_current_user)):
    lotes = _validar(body)
    op_id = str(uuid.uuid4())
    _executar(body, lotes, op_id, user["username"])
    return {"operation_id": op_id}


# ── Editar ────────────────────────────────────────────────────────────────

def _registos_da_operacao(tipo: str, action_id: int):
    """Linhas (estoque_id, quantidade) e dados da operação a que pertence
    `action_id`. Devolve (operation_id, linhas, dados)."""
    tabela = "transferencias" if tipo == "transfer_internal" else "transferencias_externas"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT operation_id::text FROM {tabela} WHERE id = %s", (action_id,))
            row = cur.fetchone()
            if not row:
                return None
            op_id = row[0]
            filtro, param = ("operation_id = %s::uuid", op_id) if op_id else ("id = %s", action_id)
            if tipo == "transfer_internal":
                cur.execute(
                    f"""SELECT id, estoque_id, quantidade, proprietario_destino_id, NULL, NULL, NULL
                        FROM transferencias WHERE {filtro} ORDER BY id""",
                    (param,),
                )
            else:
                cur.execute(
                    f"""SELECT id, estoque_id, quantidade, NULL, destinatario_externo, tipo, observacoes
                        FROM transferencias_externas WHERE {filtro} ORDER BY id""",
                    (param,),
                )
            rows = cur.fetchall()
    return op_id, rows


@router.get("/operacao/{tipo}/{action_id}")
def obter_operacao(
    tipo: Literal["transfer_internal", "transfer_external"],
    action_id: int,
    _user: dict = Depends(get_current_user),
):
    """Dados de uma operação para a editar: os lotes (com o disponível já a
    contar com as palhetas que voltam ao anular) e o destino."""
    reg = _registos_da_operacao(tipo, action_id)
    if not reg:
        raise _erro(404, "web.transfer.error.not_found")
    op_id, rows = reg
    ids = [r[1] for r in rows if r[1]]
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.id, COALESCE(a.nome, e.garanhao), e.dono_id, d.nome, e.existencia_atual,
                       e.origem_externa, e.data_embriovet, c.codigo, e.local_armazenagem,
                       e.canister, e.andar, e.qualidade, e.concentracao, e.motilidade
                FROM estoque_dono e
                LEFT JOIN animais a ON a.id = e.animal_id
                LEFT JOIN dono d ON d.id = e.dono_id
                LEFT JOIN contentores c ON c.id = e.contentor_id
                WHERE e.id = ANY(%s)
                """,
                (ids,),
            )
            info = {r[0]: r for r in cur.fetchall()}
    linhas = []
    for r in rows:
        e = info.get(r[1])
        if not e:
            continue  # lote entretanto eliminado
        linhas.append({
            "stock_id": e[0], "garanhao": e[1], "dono_id": e[2], "proprietario_nome": e[3],
            "existencia_atual": int(e[4] or 0) + int(r[2] or 0), "quantidade": int(r[2] or 0),
            "origem_externa": e[5], "data_embriovet": e[6], "contentor_codigo": e[7],
            "local_armazenagem": e[8], "canister": e[9], "andar": e[10],
            "qualidade": e[11], "concentracao": e[12], "motilidade": e[13],
        })
    primeira = rows[0]
    return {
        "tipo": tipo,
        "action_id": action_id,
        "operation_id": op_id,
        "linhas": linhas,
        "destino_id": primeira[3],
        "destinatario": primeira[4],
        "motivo": primeira[5],
        "observacoes": primeira[6],
    }


@router.put("/operacao/{tipo}/{action_id}")
def editar_operacao(
    tipo: Literal["transfer_internal", "transfer_external"],
    action_id: int,
    body: OperacaoIn,
    user: dict = Depends(get_current_user),
):
    reg = _registos_da_operacao(tipo, action_id)
    if not reg:
        raise _erro(404, "web.transfer.error.not_found")
    op_antigo, rows = reg

    # Validar a operação nova contando com as palhetas que voltam ao anular
    # a antiga — só depois se mexe na BD.
    devolvido: dict[int, int] = {}
    for r in rows:
        if r[1]:
            devolvido[r[1]] = devolvido.get(r[1], 0) + int(r[2] or 0)
    lotes = _validar(body, devolvido)

    if not reverter_operacao(tipo=tipo, action_id=action_id, operation_id=op_antigo):
        raise _erro(500, "web.error.generic")

    op_id = op_antigo or str(uuid.uuid4())
    _executar(body, lotes, op_id, user["username"])

    tabela = "transferencias" if body.tipo == "interna" else "transferencias_externas"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE {tabela} SET atualizado = TRUE WHERE operation_id = %s::uuid", (op_id,))
            cur.execute(f"SELECT id FROM {tabela} WHERE operation_id = %s::uuid ORDER BY id LIMIT 1", (op_id,))
            novo = cur.fetchone()
        conn.commit()
    invalidate_data_cache()

    # Auditoria, como a página atual faz para as externas.
    if tipo == "transfer_external" and body.tipo == "externa" and novo:
        registar_historico_edicao(
            "transferencias_externas", novo[0],
            {"Destinatário": rows[0][4], "Quantidade": sum(int(r[2] or 0) for r in rows), "Motivo": rows[0][5]},
            {"Destinatário": body.destinatario, "Quantidade": sum(l.quantidade for l in body.linhas),
             "Motivo": body.motivo},
            utilizador=user["username"],
        )
    return {"operation_id": op_id}


# ── Histórico e anulação ──────────────────────────────────────────────────

@router.get("/historico")
def historico(dia: date, _user: dict = Depends(get_current_user)):
    ops = carregar_atividade_do_dia(dia)
    return [
        {
            "ts": o["ts"].isoformat() if o.get("ts") else None,
            "usuario": o.get("usuario"),
            "acao": o.get("acao"),
            "detalhe": o.get("detalhe"),
            "tipo": o["tipo"],
            "action_id": o["action_id"],
            "operation_id": o.get("operation_id"),
            "num_lotes": o.get("num_lotes", 1),
            "quantidade": o.get("quantidade", 0),
        }
        for o in ops
    ]


class AnularIn(BaseModel):
    tipo: TipoOp
    action_id: int
    operation_id: str | None = None


@router.post("/anular")
def anular(body: AnularIn, _user: dict = Depends(get_current_user)):
    if not reverter_operacao(tipo=body.tipo, action_id=body.action_id, operation_id=body.operation_id):
        raise _erro(500, "web.transfer.error.undo_failed")
    return {"ok": True}
