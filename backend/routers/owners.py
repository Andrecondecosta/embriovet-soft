"""Proprietários (tabela `dono`) — equivalente a `modules/pages/owners_view.py`.

As escritas passam pelos mesmos repositórios que a app Streamlit usa
(`modules/repositories/owner_repo.py`). As validações que lá só davam um
`st.error` (nome duplicado, proprietário com stock…) são feitas aqui antes,
para a API poder devolver o motivo exato ao ecrã.

A listagem é nova: paginada e filtrada na BD, em vez de carregar todos os
proprietários de uma vez (ver nota sobre os 1774 proprietários de teste).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator

from backend.deps import get_current_user
from modules.db import get_connection
from modules.repositories.owner_repo import (
    adicionar_proprietario,
    alternar_status_proprietario,
    deletar_proprietario,
    editar_proprietario,
)

router = APIRouter(prefix="/api/owners", tags=["owners"])

COLUNAS = ["id", "nome", "ativo", "email", "telemovel", "nome_completo",
           "nif", "morada", "codigo_postal", "cidade"]

_ORDENACAO = {
    "nome": "LOWER(nome), id",
    "id": "id",
    "status": "ativo DESC NULLS LAST, LOWER(nome), id",
}


class OwnerIn(BaseModel):
    nome: str
    email: str | None = None
    telemovel: str | None = None
    nome_completo: str | None = None
    nif: str | None = None
    morada: str | None = None
    codigo_postal: str | None = None
    cidade: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _limpar(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v

    @field_validator("nome", mode="after")
    @classmethod
    def _nome_obrigatorio(cls, v):
        if not v:
            raise ValueError("error.name_required")
        return v


def _erro(http_status: int, code: str, **params):
    return HTTPException(http_status, {"code": code, "params": params})


def _linha(row) -> dict:
    return dict(zip(COLUNAS, row))


def _obter(owner_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {', '.join(COLUNAS)} FROM dono WHERE id = %s", (owner_id,))
            row = cur.fetchone()
    return _linha(row) if row else None


def _nome_em_uso(nome: str, excluir_id: int | None = None) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM dono WHERE LOWER(nome) = LOWER(%s) AND id <> %s",
                (nome, excluir_id or -1),
            )
            return cur.fetchone() is not None


@router.get("")
def listar(
    q: str = "",
    estado: Literal["todos", "ativos", "inativos"] = "todos",
    ordem: Literal["nome", "id", "status"] = "nome",
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(25, ge=1, le=200),
    _user: dict = Depends(get_current_user),
):
    where, params = [], []
    termo = q.strip()
    if termo:
        where.append(
            "(nome ILIKE %s OR nome_completo ILIKE %s OR email ILIKE %s"
            " OR nif ILIKE %s OR cidade ILIKE %s OR telemovel ILIKE %s)"
        )
        params += [f"%{termo}%"] * 6
    if estado == "ativos":
        where.append("ativo = TRUE")
    elif estado == "inativos":
        where.append("ativo = FALSE")
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM dono {where_sql}", params)
            total = cur.fetchone()[0]
            cur.execute(
                f"SELECT {', '.join(COLUNAS)} FROM dono {where_sql}"
                f" ORDER BY {_ORDENACAO[ordem]} LIMIT %s OFFSET %s",
                [*params, por_pagina, (pagina - 1) * por_pagina],
            )
            items = [_linha(r) for r in cur.fetchall()]

    return {"items": items, "total": total, "pagina": pagina, "por_pagina": por_pagina}


@router.get("/{owner_id}")
def obter(owner_id: int, _user: dict = Depends(get_current_user)):
    owner = _obter(owner_id)
    if not owner:
        raise _erro(404, "web.owners.error.not_found")
    return owner


@router.post("", status_code=status.HTTP_201_CREATED)
def criar(body: OwnerIn, _user: dict = Depends(get_current_user)):
    if _nome_em_uso(body.nome):
        raise _erro(409, "web.owners.error.duplicate", name=body.nome)
    novo_id = adicionar_proprietario(body.model_dump())
    if not novo_id:
        raise _erro(500, "web.error.generic")
    return _obter(novo_id)


@router.put("/{owner_id}")
def editar(owner_id: int, body: OwnerIn, _user: dict = Depends(get_current_user)):
    if not _obter(owner_id):
        raise _erro(404, "web.owners.error.not_found")
    if _nome_em_uso(body.nome, excluir_id=owner_id):
        raise _erro(409, "web.owners.error.duplicate", name=body.nome)
    if not editar_proprietario(owner_id, body.model_dump()):
        raise _erro(500, "web.error.generic")
    return _obter(owner_id)


@router.post("/{owner_id}/alternar-estado")
def alternar_estado(owner_id: int, _user: dict = Depends(get_current_user)):
    if not _obter(owner_id):
        raise _erro(404, "web.owners.error.not_found")
    novo = alternar_status_proprietario(owner_id)
    if novo is None:
        raise _erro(500, "web.error.generic")
    return _obter(owner_id)


# Tudo o que impede apagar. As duas primeiras são as que a app atual já
# verifica; animais e estadias têm FK para `dono` sem ON DELETE, por isso
# o DELETE falhava com um erro genérico — aqui diz-se o motivo.
_DEPENDENCIAS = [
    ("web.owners.error.has_stock", "SELECT COUNT(*) FROM estoque_dono WHERE dono_id = %(id)s"),
    ("web.owners.error.has_inseminations", "SELECT COUNT(*) FROM inseminacoes WHERE dono_id = %(id)s"),
    ("web.owners.error.has_animals", "SELECT COUNT(*) FROM animais WHERE dono_id = %(id)s"),
    ("web.owners.error.has_stays",
     "SELECT COUNT(*) FROM estadias WHERE dono_id = %(id)s OR dono_doadora_id = %(id)s"),
]


def _primeira_dependencia(owner_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            for code, sql in _DEPENDENCIAS:
                cur.execute(sql, {"id": owner_id})
                count = cur.fetchone()[0] or 0
                if count:
                    return code, count
    return None


@router.delete("/{owner_id}")
def apagar(owner_id: int, _user: dict = Depends(get_current_user)):
    if not _obter(owner_id):
        raise _erro(404, "web.owners.error.not_found")
    dependencia = _primeira_dependencia(owner_id)
    if dependencia:
        code, count = dependencia
        raise _erro(409, code, count=count)
    if not deletar_proprietario(owner_id):
        raise _erro(500, "web.error.generic")
    return {"ok": True}
