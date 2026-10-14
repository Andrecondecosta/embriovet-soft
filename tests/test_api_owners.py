"""API nova (FastAPI): login/sessão e Proprietários — contra a base de TESTE.

Cria um utilizador e proprietários próprios (prefixo `__api_test__`) e
apaga-os no fim, para não deixar lixo na base de teste.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from modules.db import get_connection
from modules.services.auth_service import criar_hash_password

PREFIXO = "__api_test__"


@pytest.fixture
def utilizador():
    username = f"{PREFIXO}{uuid.uuid4().hex[:8]}"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo, must_change_password)
                VALUES (%s, 'Teste API', %s, 'Gestor', TRUE, FALSE) RETURNING id
                """,
                (username, criar_hash_password("segredo123")),
            )
            user_id = cur.fetchone()[0]
        conn.commit()
    yield {"id": user_id, "username": username, "password": "segredo123"}
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_sessions WHERE username LIKE %s", (f"{PREFIXO}%",))
            cur.execute("DELETE FROM usuarios WHERE id = %s", (user_id,))
        conn.commit()


@pytest.fixture
def client(utilizador):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"username": utilizador["username"], "password": utilizador["password"]})
    assert r.status_code == 200
    yield c
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM dono WHERE nome LIKE %s", (f"{PREFIXO}%",))
        conn.commit()


def _nome():
    return f"{PREFIXO}{uuid.uuid4().hex[:8]}"


# ── Autenticação ──────────────────────────────────────────────────────────

def test_sem_sessao_nao_acede():
    assert TestClient(app).get("/api/owners").status_code == 401


def test_password_errada(utilizador):
    r = TestClient(app).post("/api/auth/login", json={"username": utilizador["username"], "password": "x"})
    assert r.status_code == 401
    assert r.json()["detail"] == "login.invalid"


def test_login_me_logout(client, utilizador):
    assert client.get("/api/auth/me").json()["user"]["username"] == utilizador["username"]
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_utilizador_desativado_perde_acesso(client, utilizador):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET ativo = FALSE WHERE id = %s", (utilizador["id"],))
        conn.commit()
    assert client.get("/api/owners").status_code == 401


def test_obrigado_a_mudar_credenciais(client, utilizador):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET must_change_password = TRUE WHERE id = %s", (utilizador["id"],))
        conn.commit()
    r = client.get("/api/owners")
    assert r.status_code == 403 and r.json()["detail"] == "must_change_password"

    r = client.post("/api/auth/change-credentials",
                    json={"username": utilizador["username"], "password": "a", "confirm_password": "b"})
    assert r.json()["detail"] == "error.passwords_mismatch"

    r = client.post("/api/auth/change-credentials",
                    json={"username": utilizador["username"], "password": "nova1234", "confirm_password": "nova1234"})
    assert r.status_code == 200
    assert client.get("/api/owners").status_code == 200


# ── Proprietários ─────────────────────────────────────────────────────────

def test_criar_editar_e_listar(client):
    nome = _nome()
    r = client.post("/api/owners", json={"nome": f"  {nome}  ", "email": "", "cidade": "Évora"})
    assert r.status_code == 201
    owner = r.json()
    assert owner["nome"] == nome and owner["ativo"] is True
    assert owner["email"] is None and owner["cidade"] == "Évora"

    r = client.put(f"/api/owners/{owner['id']}", json={"nome": nome, "nif": "123456789"})
    assert r.status_code == 200 and r.json()["nif"] == "123456789"

    r = client.get("/api/owners", params={"q": nome})
    assert r.json()["total"] == 1 and r.json()["items"][0]["id"] == owner["id"]

    r = client.get("/api/owners", params={"q": "123456789"})
    assert any(o["id"] == owner["id"] for o in r.json()["items"])


def test_nome_obrigatorio(client):
    assert client.post("/api/owners", json={"nome": "   "}).status_code == 422


def test_nome_duplicado_ignora_maiusculas(client):
    nome = _nome()
    client.post("/api/owners", json={"nome": nome})
    r = client.post("/api/owners", json={"nome": nome.upper()})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "web.owners.error.duplicate"


def test_editar_para_nome_de_outro(client):
    a, b = _nome(), _nome()
    client.post("/api/owners", json={"nome": a})
    id_b = client.post("/api/owners", json={"nome": b}).json()["id"]
    r = client.put(f"/api/owners/{id_b}", json={"nome": a})
    assert r.status_code == 409


def test_alternar_estado_e_filtro(client):
    nome = _nome()
    owner_id = client.post("/api/owners", json={"nome": nome}).json()["id"]
    assert client.post(f"/api/owners/{owner_id}/alternar-estado").json()["ativo"] is False

    inativos = client.get("/api/owners", params={"q": nome, "estado": "inativos"}).json()
    ativos = client.get("/api/owners", params={"q": nome, "estado": "ativos"}).json()
    assert inativos["total"] == 1 and ativos["total"] == 0

    assert client.post(f"/api/owners/{owner_id}/alternar-estado").json()["ativo"] is True


def test_paginacao(client):
    ids = [client.post("/api/owners", json={"nome": f"{PREFIXO}pag{i:02d}"}).json()["id"] for i in range(5)]
    p1 = client.get("/api/owners", params={"q": f"{PREFIXO}pag", "por_pagina": 2, "pagina": 1}).json()
    p3 = client.get("/api/owners", params={"q": f"{PREFIXO}pag", "por_pagina": 2, "pagina": 3}).json()
    assert p1["total"] == 5
    assert [o["id"] for o in p1["items"]] == ids[:2]
    assert [o["id"] for o in p3["items"]] == ids[4:]


def test_apagar(client):
    owner_id = client.post("/api/owners", json={"nome": _nome()}).json()["id"]
    assert client.delete(f"/api/owners/{owner_id}").status_code == 200
    assert client.get(f"/api/owners/{owner_id}").status_code == 404


def test_nao_apaga_com_stock(client):
    owner_id = client.post("/api/owners", json={"nome": _nome()}).json()["id"]
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO estoque_dono (garanhao, dono_id, existencia_atual) VALUES (%s, %s, 3)",
                (f"{PREFIXO}garanhao", owner_id),
            )
        conn.commit()
    try:
        r = client.delete(f"/api/owners/{owner_id}")
        assert r.status_code == 409
        assert r.json()["detail"] == {"code": "web.owners.error.has_stock", "params": {"count": 1}}
    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM estoque_dono WHERE dono_id = %s", (owner_id,))
            conn.commit()
