"""Listas curtas para preencher seletores (proprietários, contentores,
garanhões) — só id e nome, sem paginação."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.deps import get_current_user
from modules.db import get_connection

router = APIRouter(prefix="/api/opcoes", tags=["opcoes"])


def _lista(sql: str, params=()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [{"id": r[0], "nome": r[1]} for r in cur.fetchall()]


@router.get("/proprietarios")
def proprietarios(apenas_ativos: bool = False, _user: dict = Depends(get_current_user)):
    where = "WHERE ativo = TRUE" if apenas_ativos else ""
    return _lista(f"SELECT id, nome FROM dono {where} ORDER BY nome")


@router.get("/contentores")
def contentores(_user: dict = Depends(get_current_user)):
    return _lista("SELECT id, codigo FROM contentores WHERE ativo = TRUE ORDER BY codigo")


@router.get("/garanhoes")
def garanhoes(_user: dict = Depends(get_current_user)):
    return _lista(
        "SELECT id, nome FROM animais WHERE tipo = 'garanhao' AND ativo = TRUE ORDER BY LOWER(nome)"
    )
