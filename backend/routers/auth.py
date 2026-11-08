"""Login, sessão e alteração obrigatória de credenciais.

Usa a mesma tabela `user_sessions` e o mesmo bcrypt que a app Streamlit:
as contas e passwords são exatamente as mesmas nas duas apps.
"""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from backend.config import IS_RENDER, SESSION_COOKIE, SESSION_MAX_AGE
from backend.deps import get_current_user_any, get_session_token
from modules.db import get_connection
from modules.repositories.settings_repo import update_show_initial_credentials
from modules.services.auth_service import (
    autenticar_usuario,
    criar_hash_password,
    delete_session_db,
    save_session_db,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class ChangeCredentialsIn(BaseModel):
    username: str
    password: str
    confirm_password: str


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=IS_RENDER,
        samesite="lax",
        path="/",
    )


# Tentativas falhadas por utilizador (memória do processo): 5 seguidas
# bloqueiam esse utilizador 15 minutos — trava quem tenta adivinhar a
# password.
MAX_FALHAS = 5
BLOQUEIO_SEG = 15 * 60
_falhas: dict[str, list[float]] = {}


def _bloqueado(chave: str) -> bool:
    agora = time.monotonic()
    recentes = [t for t in _falhas.get(chave, []) if agora - t < BLOQUEIO_SEG]
    _falhas[chave] = recentes
    return len(recentes) >= MAX_FALHAS


@router.post("/login")
def login(body: LoginIn, response: Response):
    username = body.username.strip()
    if not username or not body.password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "login.missing")
    chave = username.lower()
    if _bloqueado(chave):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "login.too_many")
    user = autenticar_usuario(username, body.password)
    if not user:
        _falhas.setdefault(chave, []).append(time.monotonic())
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "login.invalid")
    _falhas.pop(chave, None)
    token = str(uuid.uuid4())
    save_session_db(token, user)
    _set_cookie(response, token)
    return {"user": user}


@router.post("/logout")
def logout(response: Response, token: str = Depends(get_session_token)):
    delete_session_db(token)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(get_current_user_any)):
    return {"user": user}


@router.post("/change-credentials")
def change_credentials(body: ChangeCredentialsIn, user: dict = Depends(get_current_user_any), token: str = Depends(get_session_token)):
    """Equivalente a `render_change_credentials` em `app.py`."""
    novo_username = body.username.strip()
    if not novo_username:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "error.username_required")
    if not body.password or not body.confirm_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "error.password_required")
    if body.password != body.confirm_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "error.passwords_mismatch")
    if len(body.password) < 6:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "users.password_min_error")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM usuarios WHERE username = %s AND id <> %s",
                (novo_username, user["id"]),
            )
            em_uso = cur.fetchone() is not None
    if em_uso:
        raise HTTPException(status.HTTP_409_CONFLICT, "security.username_exists")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE usuarios
                SET username = %s,
                    password_hash = %s,
                    must_change_password = FALSE,
                    updated_at = now()
                WHERE id = %s
                """,
                (novo_username, criar_hash_password(body.password), user["id"]),
            )
            # Password nova: as outras sessões deste utilizador terminam.
            cur.execute(
                "DELETE FROM user_sessions WHERE username IN (%s, %s) AND token <> %s",
                (user["username"], novo_username, token),
            )
        conn.commit()

    update_show_initial_credentials(False)
    return {"user": {**user, "username": novo_username, "must_change_password": False}}
