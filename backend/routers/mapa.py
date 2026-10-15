"""Mapa dos contentores (separador do Stock de sémen) — equivalente a
`modules/pages/map_page.py`.

Escritas pelos mesmos repositórios (`container_repo`, `mover_palhetas_localizacao`)
e exportação pelo mesmo `mapa_export` (PDF/Excel iguais aos da app atual).

Diferenças deliberadas em relação à página atual:
- A lista do mapa vem numa só consulta (a atual fazia uma por contentor).
- As validações que lá eram só `st.error` (código vazio/duplicado, contentor
  com stock, destino igual à origem) são feitas aqui antes, para o ecrã
  poder dizer o motivo.

Permissões iguais à app atual: qualquer utilizador.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator

from backend.deps import get_current_user
from modules.db import get_connection
from modules.mapa_export import gerar_excel_inventario, gerar_pdf_inventario
from modules.mapa_layout import (
    CONTENTOR_LADO_VIRTUAL,
    MAPA_VIRTUAL_H,
    MAPA_VIRTUAL_W,
    chave_natural,
    posicoes_em_grelha,
)
from modules.repositories.container_repo import (
    adicionar_contentor,
    atualizar_posicao_contentor,
    atualizar_posicoes_contentores,
    deletar_contentor,
    editar_contentor,
    inverter_andares,
)
from modules.repositories.stock_repo import mover_palhetas_localizacao, obter_inventario_contentores

router = APIRouter(prefix="/api/mapa", tags=["mapa"])


def _erro(http_status: int, chave: str, **params):
    return HTTPException(http_status, {"code": chave, "params": params})


def _contentor(cid: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, codigo, descricao, x, y, w, h FROM contentores WHERE id = %s AND ativo = TRUE", (cid,))
            r = cur.fetchone()
    return dict(zip(["id", "codigo", "descricao", "x", "y", "w", "h"], r)) if r else None


def _codigo_em_uso(codigo: str, excluir_id: int | None = None) -> bool:
    # Contra todos os contentores (também inativos): `codigo` é UNIQUE na BD.
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM contentores WHERE codigo = %s AND id <> %s", (codigo, excluir_id or -1))
            return cur.fetchone() is not None


# ── Mapa ──────────────────────────────────────────────────────────────────

@router.get("/contentores")
def listar(_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.id, c.codigo, c.descricao, c.x, c.y,
                       COALESCE(SUM(e.existencia_atual), 0)::int AS palhetas,
                       COUNT(e.id)::int AS lotes
                FROM contentores c
                LEFT JOIN estoque_dono e ON e.contentor_id = c.id AND e.existencia_atual > 0
                WHERE c.ativo = TRUE
                GROUP BY c.id
                """
            )
            rows = cur.fetchall()
    itens = [
        {"id": r[0], "codigo": r[1], "descricao": r[2], "x": int(r[3] or 0), "y": int(r[4] or 0),
         "palhetas": r[5], "lotes": r[6]}
        for r in rows
    ]
    itens.sort(key=lambda c: chave_natural(c["codigo"]))
    return {
        "contentores": itens,
        "virtual": {"w": MAPA_VIRTUAL_W, "h": MAPA_VIRTUAL_H, "lado": CONTENTOR_LADO_VIRTUAL},
    }


class ContentorIn(BaseModel):
    codigo: str
    descricao: str | None = None

    @field_validator("codigo", mode="before")
    @classmethod
    def _codigo(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("map.container_code_required_error")
        return v

    @field_validator("descricao", mode="before")
    @classmethod
    def _descricao(cls, v):
        return (v or "").strip()


@router.post("/contentores", status_code=status.HTTP_201_CREATED)
def criar(body: ContentorIn, _user: dict = Depends(get_current_user)):
    if _codigo_em_uso(body.codigo):
        raise _erro(409, "map.container_code_exists", code=body.codigo)
    # Sem x/y: fica ao lado do último criado (`_posicao_novo_contentor`).
    novo = adicionar_contentor({"codigo": body.codigo, "descricao": body.descricao})
    if not novo:
        raise _erro(500, "web.error.generic")
    return _contentor(int(novo))


@router.put("/contentores/{cid}")
def editar(cid: int, body: ContentorIn, _user: dict = Depends(get_current_user)):
    c = _contentor(cid)
    if not c:
        raise _erro(404, "web.map.error.not_found")
    if _codigo_em_uso(body.codigo, excluir_id=cid):
        raise _erro(409, "map.container_code_exists", code=body.codigo)
    if not editar_contentor(cid, {**c, "codigo": body.codigo, "descricao": body.descricao}):
        raise _erro(500, "web.error.generic")
    return _contentor(cid)


class PosicaoIn(BaseModel):
    x: float
    y: float


@router.patch("/contentores/{cid}/posicao")
def mover_contentor(cid: int, body: PosicaoIn, _user: dict = Depends(get_current_user)):
    if not _contentor(cid):
        raise _erro(404, "web.map.error.not_found")
    # Mesmos limites da app atual: a caixa (70) tem de caber no mapa (900×550).
    x = max(0, min(MAPA_VIRTUAL_W - CONTENTOR_LADO_VIRTUAL, round(body.x)))
    y = max(0, min(MAPA_VIRTUAL_H - CONTENTOR_LADO_VIRTUAL, round(body.y)))
    if not atualizar_posicao_contentor(cid, x, y):
        raise _erro(500, "map.save_failed")
    return {"id": cid, "x": x, "y": y}


class TrocaIn(BaseModel):
    a: int
    b: int


@router.post("/trocar")
def trocar(body: TrocaIn, _user: dict = Depends(get_current_user)):
    """Troca dois contentores de lugar no mapa (arrastar um para cima do
    outro na lista). As duas posições mudam na mesma transação."""
    if body.a == body.b:
        raise _erro(422, "web.error.generic")
    ca, cb = _contentor(body.a), _contentor(body.b)
    if not ca or not cb:
        raise _erro(404, "web.map.error.not_found")
    if not atualizar_posicoes_contentores({ca["id"]: (cb["x"], cb["y"]), cb["id"]: (ca["x"], ca["y"])}):
        raise _erro(500, "web.error.generic")
    return {"a": {"id": ca["id"], "x": cb["x"], "y": cb["y"]}, "b": {"id": cb["id"], "x": ca["x"], "y": ca["y"]}}


@router.post("/organizar")
def organizar(_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, codigo FROM contentores WHERE ativo = TRUE")
            rows = cur.fetchall()
    posicoes = posicoes_em_grelha(rows)
    if posicoes and not atualizar_posicoes_contentores(posicoes):
        raise _erro(500, "web.error.generic")
    return {"count": len(posicoes)}


@router.delete("/contentores/{cid}")
def apagar(cid: int, _user: dict = Depends(get_current_user)):
    if not _contentor(cid):
        raise _erro(404, "web.map.error.not_found")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(existencia_atual), 0), COUNT(*) FROM estoque_dono WHERE contentor_id = %s",
                (cid,),
            )
            palhetas, registos = cur.fetchone()
    if palhetas:
        raise _erro(409, "web.map.error.has_stock", count=int(palhetas))
    # Lotes vazios (0 palhetas) ainda apontam para o contentor e a BD não
    # deixa apagar (FK RESTRICT). Na app atual dava um erro técnico.
    if registos:
        raise _erro(409, "web.map.error.has_empty_lots", count=int(registos))
    if not deletar_contentor(cid):
        raise _erro(500, "web.error.generic")
    return {"ok": True}


# ── Interior do contentor ─────────────────────────────────────────────────

@router.get("/contentores/{cid}/stock")
def stock_contentor(cid: int, _user: dict = Depends(get_current_user)):
    """Lotes com palhetas do contentor (`obter_stock_contentor`)."""
    c = _contentor(cid)
    if not c:
        raise _erro(404, "web.map.error.not_found")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.id, COALESCE(a.nome, e.garanhao), e.dono_id, d.nome, e.canister, e.andar,
                       e.existencia_atual, e.qualidade, e.data_embriovet, e.origem_externa,
                       e.motilidade, e.concentracao
                FROM estoque_dono e
                LEFT JOIN dono d ON e.dono_id = d.id
                LEFT JOIN animais a ON a.id = e.animal_id
                WHERE e.contentor_id = %s AND e.existencia_atual > 0
                ORDER BY e.canister, e.andar, 2
                """,
                (cid,),
            )
            cols = ["id", "garanhao", "dono_id", "proprietario_nome", "canister", "andar", "existencia_atual",
                    "qualidade", "data_embriovet", "origem_externa", "motilidade", "concentracao"]
            lotes = [dict(zip(cols, r)) for r in cur.fetchall()]
    return {"contentor": c, "lotes": lotes, "palhetas": sum(int(l["existencia_atual"] or 0) for l in lotes)}


@router.post("/contentores/{cid}/inverter-andares")
def inverter(cid: int, _user: dict = Depends(get_current_user)):
    if not _contentor(cid):
        raise _erro(404, "web.map.error.not_found")
    n = inverter_andares(cid)
    if n is False:
        raise _erro(500, "web.error.generic")
    return {"count": n}


class MoverIn(BaseModel):
    lote_id: int
    quantidade: int = Field(gt=0)
    contentor_id: int
    canister: int = Field(ge=1, le=10)
    andar: int = Field(ge=1, le=2)


@router.post("/mover")
def mover(body: MoverIn, _user: dict = Depends(get_current_user)):
    """Arrumação física: muda palhetas de canister/andar/contentor. O dono
    não muda e não fica registo em `transferencias` (igual à app atual)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT existencia_atual, contentor_id, canister, andar FROM estoque_dono WHERE id = %s",
                (body.lote_id,),
            )
            lote = cur.fetchone()
    if not lote:
        raise _erro(404, "web.stock.error.not_found")
    if not _contentor(body.contentor_id):
        raise _erro(404, "web.map.error.not_found")
    disponivel = int(lote[0] or 0)
    if body.quantidade > disponivel:
        raise _erro(409, "web.map.error.insufficient", disponivel=disponivel)
    if (lote[1], lote[2], lote[3]) == (body.contentor_id, body.canister, body.andar):
        raise _erro(409, "web.map.error.same_place")
    if not mover_palhetas_localizacao(
        body.lote_id, body.quantidade, body.canister, body.andar, contentor_destino_id=body.contentor_id,
    ):
        raise _erro(500, "web.error.generic")
    return {"ok": True}


# ── Exportar ──────────────────────────────────────────────────────────────

@router.get("/exportar")
def exportar(
    formato: str = Query(pattern="^(pdf|xlsx)$"),
    ids: list[int] = Query(default=[]),
    _user: dict = Depends(get_current_user),
):
    """Inventário por contentor, canister e andar — os mesmos ficheiros que
    o botão Exportar da app atual gera."""
    df = obter_inventario_contentores(ids or None)
    data = datetime.now().strftime("%Y%m%d")
    if formato == "pdf":
        conteudo, mime = gerar_pdf_inventario(df), "application/pdf"
    else:
        conteudo = gerar_excel_inventario(df)
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    nome = f"inventario_contentores_{data}.{formato}"
    return Response(conteudo, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{nome}"'})
