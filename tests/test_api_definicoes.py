"""API nova (FastAPI): Definições — marca/idioma, alojamentos, utilizadores
e cópia de segurança — contra a base de TESTE.

Cria utilizadores e alojamentos próprios (prefixo `__api_test__`) e apaga-os
no fim; a marca é reposta tal como estava.
"""

from __future__ import annotations

import io
import uuid
import zipfile

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from modules.db import get_connection
from modules.repositories.settings_repo import get_app_settings, update_branding_settings
from modules.services.auth_service import criar_hash_password

PREFIXO = "__api_test__"


def _criar_utilizador(nivel: str) -> dict:
    username = f"{PREFIXO}{uuid.uuid4().hex[:8]}"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo, must_change_password)
                VALUES (%s, 'Teste API', %s, %s, TRUE, FALSE) RETURNING id
                """,
                (username, criar_hash_password("segredo123"), nivel),
            )
            uid = cur.fetchone()[0]
        conn.commit()
    return {"id": uid, "username": username}


def _login(u: dict) -> TestClient:
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"username": u["username"], "password": "segredo123"}).status_code == 200
    return c


@pytest.fixture(autouse=True)
def limpar():
    marca = get_app_settings() or {}
    yield
    update_branding_settings(marca.get("company_name"), marca.get("logo_base64"), marca.get("language"), marca.get("primary_color"))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_sessions WHERE username LIKE %s", (f"{PREFIXO}%",))
            cur.execute("DELETE FROM usuarios WHERE username LIKE %s", (f"{PREFIXO}%",))
            cur.execute("DELETE FROM alojamentos WHERE nome LIKE %s", (f"{PREFIXO}%",))
        conn.commit()


@pytest.fixture
def admin():
    u = _criar_utilizador("Administrador")
    return {**u, "c": _login(u)}


@pytest.fixture
def gestor():
    return _login(_criar_utilizador("Gestor"))


# ── Marca e idioma ──────────────────────────────────────────────────────────

def test_marca_grava_e_repoe(gestor):
    r = gestor.put("/api/definicoes/marca", json={"company_name": "  Clínica X ", "primary_color": "#123abc", "language": "en"})
    assert r.status_code == 200
    assert r.json()["company_name"] == "Clínica X"
    assert r.json()["language"] == "en"
    # O ecrã de login vê logo a marca nova.
    assert gestor.get("/api/settings/public").json()["primary_color"] == "#123abc"

    r = gestor.post("/api/definicoes/marca/repor")
    assert r.json()["company_name"] == "Sistema"
    assert r.json()["language"] == "pt-PT"


@pytest.mark.parametrize(
    "dados, codigo",
    [
        ({"company_name": "  "}, "web.settings.error.company_required"),
        ({"company_name": "X", "primary_color": "vermelho"}, "web.settings.error.color_invalid"),
        ({"company_name": "X", "logo_base64": "data:text/html;base64,AAAA"}, "web.settings.error.logo_type"),
    ],
)
def test_marca_validacoes(gestor, dados, codigo):
    r = gestor.put("/api/definicoes/marca", json=dados)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == codigo


def test_marca_logo_grande_demais(gestor):
    logo = "data:image/png;base64," + "A" * 1_600_000
    r = gestor.put("/api/definicoes/marca", json={"company_name": "X", "logo_base64": logo})
    assert r.json()["detail"]["code"] == "web.settings.error.logo_size"


# ── Alojamentos ─────────────────────────────────────────────────────────────

def test_alojamentos_crud(gestor):
    nome = f"{PREFIXO}box"
    r = gestor.post("/api/definicoes/alojamentos", json={"nome": nome, "tipo": "box", "capacidade": 2})
    assert r.status_code == 201
    a = r.json()
    assert a["ativo"] is True and a["capacidade"] == 2

    r = gestor.put(f"/api/definicoes/alojamentos/{a['id']}", json={"nome": nome, "tipo": "paddock", "capacidade": 5, "observacoes": "x"})
    assert r.json()["tipo"] == "paddock" and r.json()["observacoes"] == "x"

    assert gestor.post(f"/api/definicoes/alojamentos/{a['id']}/alternar").json()["ativo"] is False
    assert any(x["id"] == a["id"] for x in gestor.get("/api/definicoes/alojamentos").json())


def test_alojamento_validacoes(gestor):
    assert gestor.post("/api/definicoes/alojamentos", json={"nome": " "}).json()["detail"]["code"] == "error.name_required"
    r = gestor.post("/api/definicoes/alojamentos", json={"nome": f"{PREFIXO}x", "capacidade": 0})
    assert r.json()["detail"]["code"] == "web.settings.error.capacity"
    assert gestor.post("/api/definicoes/alojamentos", json={"nome": f"{PREFIXO}x", "tipo": "garagem"}).status_code == 422


# ── Utilizadores ────────────────────────────────────────────────────────────

def test_utilizadores_so_administrador(gestor):
    assert gestor.get("/api/definicoes/utilizadores").status_code == 403
    assert gestor.get("/api/definicoes/backup").status_code == 403


def test_utilizadores_criar_ativar_password(admin):
    c = admin["c"]
    username = f"{PREFIXO}{uuid.uuid4().hex[:6]}"
    r = c.post("/api/definicoes/utilizadores", json={"username": username, "nome_completo": "Novo", "nivel": "Gestor", "password": "abcdef"})
    assert r.status_code == 201
    novo = r.json()
    assert novo["nivel"] == "Gestor" and novo["ativo"] is True

    # Username repetido (sem diferenciar maiúsculas).
    r = c.post("/api/definicoes/utilizadores", json={"username": username.upper(), "nome_completo": "X", "nivel": "Gestor", "password": "abcdef"})
    assert r.json()["detail"]["code"] == "error.username_exists"

    assert c.post(f"/api/definicoes/utilizadores/{novo['id']}/desativar").json()["ativo"] is False
    assert c.post(f"/api/definicoes/utilizadores/{novo['id']}/ativar").json()["ativo"] is True

    assert c.post(f"/api/definicoes/utilizadores/{novo['id']}/password", json={"password": "123"}).json()["detail"]["code"] == "users.password_min_error"
    assert c.post(f"/api/definicoes/utilizadores/{novo['id']}/password", json={"password": "novasenha"}).status_code == 200
    assert TestClient(app).post("/api/auth/login", json={"username": username, "password": "novasenha"}).status_code == 200


@pytest.mark.parametrize(
    "dados, codigo",
    [
        ({"username": "com espaco", "nome_completo": "X", "nivel": "Gestor", "password": "abcdef"}, "users.username_no_spaces"),
        ({"username": f"{PREFIXO}a", "nome_completo": " ", "nivel": "Gestor", "password": "abcdef"}, "users.fill_required"),
        ({"username": f"{PREFIXO}a", "nome_completo": "X", "nivel": "Gestor", "password": "123"}, "users.password_min_error"),
    ],
)
def test_utilizador_validacoes(admin, dados, codigo):
    assert admin["c"].post("/api/definicoes/utilizadores", json=dados).json()["detail"]["code"] == codigo


def test_nao_se_desativa_a_si_proprio(admin):
    r = admin["c"].post(f"/api/definicoes/utilizadores/{admin['id']}/desativar")
    assert r.json()["detail"]["code"] == "web.settings.error.self_deactivate"


# ── Cópia de segurança ──────────────────────────────────────────────────────

def test_backup(admin):
    c = admin["c"]
    resumo = c.get("/api/definicoes/backup").json()
    assert resumo["tabelas"] > 0
    r = c.get("/api/definicoes/backup/zip")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert zipfile.ZipFile(io.BytesIO(r.content)).namelist()
