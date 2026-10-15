"""Definições — equivalente a `modules/pages/definicoes_page.py`.

Separadores e permissões como na app atual:
- Marca, Idioma e Alojamentos: qualquer utilizador com sessão;
- Utilizadores e Cópia de segurança: só Administrador.

A marca e o idioma vivem na mesma linha de `app_settings` e gravam-se com
`update_branding_settings`, como na app atual (lá partilhavam o painel).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, field_validator

from backend.deps import get_current_user, require_nivel
from modules.db import get_connection
from modules.repositories.settings_repo import get_app_settings, update_branding_settings
from modules.services.auth_service import (
    adicionar_usuario,
    alterar_password,
    ativar_usuario,
    desativar_usuario,
)
from modules.ui_kit import DEFAULT_PRIMARY_COLOR

router = APIRouter(prefix="/api/definicoes", tags=["definicoes"])

IDIOMAS = ("pt-PT", "en", "fr", "de")
NIVEIS = ("Administrador", "Gestor", "Visualizador")
TIPOS_ALOJAMENTO = ("box", "paddock", "outro")
# Logótipo guardado como data URI na BD (como a app atual): só PNG/JPEG e
# com um limite, para não pesar em cada página.
_LOGO_RE = re.compile(r"^data:image/(png|jpe?g);base64,[A-Za-z0-9+/=]+$")
LOGO_MAX = 1_500_000
_COR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _erro(http_status: int, chave: str, **params):
    return HTTPException(http_status, {"code": chave, "params": params})


def _texto(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


# ── Marca e idioma ──────────────────────────────────────────────────────────

class MarcaIn(BaseModel):
    company_name: str | None = None
    logo_base64: str | None = None
    primary_color: str | None = None
    language: Literal["pt-PT", "en", "fr", "de"] = "pt-PT"

    @field_validator("company_name", "logo_base64", "primary_color", mode="before")
    @classmethod
    def _limpar(cls, v):
        return _texto(v)


def _marca() -> dict:
    s = get_app_settings() or {}
    return {
        "company_name": s.get("company_name") or "Sistema",
        "logo_base64": s.get("logo_base64"),
        "primary_color": s.get("primary_color") or DEFAULT_PRIMARY_COLOR,
        "language": s.get("language") or "pt-PT",
    }


@router.get("/marca")
def obter_marca(_user: dict = Depends(get_current_user)):
    return _marca()


@router.put("/marca")
def gravar_marca(dados: MarcaIn, _user: dict = Depends(get_current_user)):
    if not dados.company_name:
        raise _erro(422, "web.settings.error.company_required")
    if dados.primary_color and not _COR_RE.match(dados.primary_color):
        raise _erro(422, "web.settings.error.color_invalid")
    if dados.logo_base64:
        if not _LOGO_RE.match(dados.logo_base64):
            raise _erro(422, "web.settings.error.logo_type")
        if len(dados.logo_base64) > LOGO_MAX:
            raise _erro(422, "web.settings.error.logo_size")
    update_branding_settings(dados.company_name, dados.logo_base64, dados.language, dados.primary_color)
    return _marca()


@router.post("/marca/repor")
def repor_marca(_user: dict = Depends(get_current_user)):
    """"Repor predefinições" da app atual: nome "Sistema", sem logótipo,
    português e a cor de origem."""
    update_branding_settings("Sistema", None, "pt-PT", DEFAULT_PRIMARY_COLOR)
    return _marca()


# ── Alojamentos ─────────────────────────────────────────────────────────────

class AlojamentoIn(BaseModel):
    nome: str | None = None
    tipo: Literal["box", "paddock", "outro"] = "box"
    capacidade: int = 1
    observacoes: str | None = None

    @field_validator("nome", "observacoes", mode="before")
    @classmethod
    def _limpar(cls, v):
        return _texto(v)


_COL_ALOJ = ["id", "tipo", "nome", "capacidade", "ativo", "observacoes"]


def _validar_alojamento(d: AlojamentoIn):
    if not d.nome:
        raise _erro(422, "error.name_required")
    if not 1 <= d.capacidade <= 999:
        raise _erro(422, "web.settings.error.capacity", min=1, max=999)


def _obter_alojamento(cur, aid: int) -> dict:
    cur.execute(f"SELECT {', '.join(_COL_ALOJ)} FROM alojamentos WHERE id = %s", (aid,))
    row = cur.fetchone()
    if not row:
        raise _erro(404, "web.settings.error.housing_not_found")
    return dict(zip(_COL_ALOJ, row))


@router.get("/alojamentos")
def listar_alojamentos(_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {', '.join(_COL_ALOJ)} FROM alojamentos ORDER BY ativo DESC, tipo, nome")
            return [dict(zip(_COL_ALOJ, r)) for r in cur.fetchall()]


@router.post("/alojamentos", status_code=201)
def criar_alojamento(d: AlojamentoIn, _user: dict = Depends(get_current_user)):
    _validar_alojamento(d)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO alojamentos (tipo, nome, capacidade, observacoes, ativo)
                VALUES (%s, %s, %s, %s, TRUE) RETURNING id
                """,
                (d.tipo, d.nome, d.capacidade, d.observacoes),
            )
            aid = cur.fetchone()[0]
            conn.commit()
            return _obter_alojamento(cur, aid)


@router.put("/alojamentos/{aid}")
def editar_alojamento(aid: int, d: AlojamentoIn, _user: dict = Depends(get_current_user)):
    _validar_alojamento(d)
    with get_connection() as conn:
        with conn.cursor() as cur:
            _obter_alojamento(cur, aid)
            cur.execute(
                "UPDATE alojamentos SET tipo = %s, nome = %s, capacidade = %s, observacoes = %s WHERE id = %s",
                (d.tipo, d.nome, d.capacidade, d.observacoes, aid),
            )
            conn.commit()
            return _obter_alojamento(cur, aid)


@router.post("/alojamentos/{aid}/alternar")
def alternar_alojamento(aid: int, _user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        with conn.cursor() as cur:
            _obter_alojamento(cur, aid)
            cur.execute("UPDATE alojamentos SET ativo = NOT ativo WHERE id = %s", (aid,))
            conn.commit()
            return _obter_alojamento(cur, aid)


# ── Utilizadores (só Administrador) ─────────────────────────────────────────

class UtilizadorIn(BaseModel):
    username: str | None = None
    nome_completo: str | None = None
    nivel: Literal["Administrador", "Gestor", "Visualizador"]
    password: str

    @field_validator("username", "nome_completo", mode="before")
    @classmethod
    def _limpar(cls, v):
        return _texto(v)


class PasswordIn(BaseModel):
    password: str


_COL_USR = ["id", "username", "nome_completo", "nivel", "ativo", "created_at", "last_login"]


def _validar_password(p: str):
    # As mesmas regras da app atual.
    if not p:
        raise _erro(422, "users.password_required")
    if len(p) < 6:
        raise _erro(422, "users.password_min_error")


def _obter_utilizador(uid: int) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {', '.join(_COL_USR)} FROM usuarios WHERE id = %s", (uid,))
            row = cur.fetchone()
    if not row:
        raise _erro(404, "web.settings.error.user_not_found")
    return dict(zip(_COL_USR, row))


@router.get("/utilizadores")
def listar_utilizadores(_user: dict = Depends(require_nivel("Administrador"))):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {', '.join(_COL_USR)} FROM usuarios ORDER BY nivel, nome_completo")
            return [dict(zip(_COL_USR, r)) for r in cur.fetchall()]


@router.post("/utilizadores", status_code=201)
def criar_utilizador(d: UtilizadorIn, user: dict = Depends(require_nivel("Administrador"))):
    if not d.username or not d.nome_completo:
        raise _erro(422, "users.fill_required")
    if " " in d.username:
        raise _erro(422, "users.username_no_spaces")
    _validar_password(d.password)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM usuarios WHERE LOWER(username) = LOWER(%s)", (d.username,))
            if cur.fetchone():
                raise _erro(409, "error.username_exists")
    # O nível guarda-se sempre com o nome em português (é o que as
    # permissões comparam), seja qual for o idioma da app.
    if not adicionar_usuario(d.username, d.nome_completo, d.password, d.nivel, user["id"]):
        raise _erro(500, "web.error.generic")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM usuarios WHERE username = %s", (d.username,))
            return _obter_utilizador(cur.fetchone()[0])


@router.post("/utilizadores/{uid}/ativar")
def ativar(uid: int, _user: dict = Depends(require_nivel("Administrador"))):
    _obter_utilizador(uid)
    ativar_usuario(uid)
    return _obter_utilizador(uid)


@router.post("/utilizadores/{uid}/desativar")
def desativar(uid: int, user: dict = Depends(require_nivel("Administrador"))):
    _obter_utilizador(uid)
    # Desativar-se a si próprio fechava a porta a quem está a usar a app.
    if uid == user["id"]:
        raise _erro(409, "web.settings.error.self_deactivate")
    desativar_usuario(uid)
    return _obter_utilizador(uid)


@router.post("/utilizadores/{uid}/password")
def mudar_password(uid: int, d: PasswordIn, _user: dict = Depends(require_nivel("Administrador"))):
    _obter_utilizador(uid)
    _validar_password(d.password)
    if not alterar_password(uid, d.password):
        raise _erro(500, "web.error.generic")
    return {"ok": True}


# ── Cópia de segurança (só Administrador) ───────────────────────────────────

@router.get("/backup")
def resumo_backup(_user: dict = Depends(require_nivel("Administrador"))):
    from modules.backup import contar_linhas

    with get_connection() as conn:
        linhas = contar_linhas(conn)
    return {
        "lotes": linhas.get("estoque_dono", 0),
        "proprietarios": linhas.get("dono", 0),
        "animais": linhas.get("animais", 0),
        "inseminacoes": linhas.get("inseminacoes", 0),
        "estadias": linhas.get("estadias", 0),
        "tabelas": len(linhas),
    }


@router.get("/backup/zip")
def descarregar_backup(user: dict = Depends(require_nivel("Administrador"))):
    from modules.backup import gerar_backup_zip

    with get_connection() as conn:
        dados = gerar_backup_zip(conn, criado_por=user["username"])
    nome = f"embriovet_backup_{datetime.now():%Y%m%d_%H%M}.zip"
    return Response(dados, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{nome}"'})
