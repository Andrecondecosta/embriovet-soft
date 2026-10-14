"""Dependências partilhadas pelos routers: utilizador da sessão e permissões."""

from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException, status

from backend.config import SESSION_COOKIE
from modules.db import get_connection
from modules.services.auth_service import load_session_db

NIVEIS = {"Visualizador": 1, "Gestor": 2, "Administrador": 3}


def _utilizador_atual(user_id: int):
    """Dados frescos do utilizador — a sessão guarda uma cópia do momento
    do login, mas um utilizador desativado entretanto não deve continuar
    a entrar, e um nível alterado tem efeito logo."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, username, nome_completo, nivel, must_change_password
                FROM usuarios
                WHERE id = %s AND ativo = TRUE
                """,
                (user_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "username": row[1],
        "nome": row[2],
        "nivel": row[3],
        "must_change_password": bool(row[4]),
    }


def get_session_token(
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> str:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not_authenticated")
    return token


def get_current_user_any(token: str = Depends(get_session_token)) -> dict:
    """Utilizador autenticado, mesmo que ainda tenha de mudar credenciais."""
    sessao = load_session_db(token)
    if not sessao or "id" not in sessao:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not_authenticated")
    user = _utilizador_atual(int(sessao["id"]))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not_authenticated")
    return user


def get_current_user(user: dict = Depends(get_current_user_any)) -> dict:
    """Utilizador autenticado e com as credenciais iniciais já alteradas
    (como em `app.py`, nada fica acessível antes disso)."""
    if user["must_change_password"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "must_change_password")
    return user


def require_nivel(nivel_minimo: str):
    def _dep(user: dict = Depends(get_current_user)) -> dict:
        if NIVEIS.get(user["nivel"], 0) < NIVEIS.get(nivel_minimo, 0):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
        return user

    return _dep
