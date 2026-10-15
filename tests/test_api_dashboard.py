"""API nova (FastAPI): Dashboard — só leitura, contra a base de TESTE."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from modules.db import get_connection
from modules.repositories.dashboard_repo import carregar_kpis_clinicos, carregar_kpis_stock
from modules.services.auth_service import criar_hash_password

PREFIXO = "__api_test__"


@pytest.fixture
def client():
    username = f"{PREFIXO}{uuid.uuid4().hex[:8]}"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo, must_change_password)
                VALUES (%s, 'Teste API', %s, 'Visualizador', TRUE, FALSE)
                """,
                (username, criar_hash_password("segredo123")),
            )
        conn.commit()
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"username": username, "password": "segredo123"}).status_code == 200
    yield c
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_sessions WHERE username = %s", (username,))
            cur.execute("DELETE FROM usuarios WHERE username = %s", (username,))
        conn.commit()


def test_dashboard_pede_sessao():
    assert TestClient(app).get("/api/dashboard").status_code == 401


def test_dashboard_bate_com_a_app_atual(client):
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    d = r.json()
    # Os mesmos números que a página atual mostra.
    assert d["stock"] == carregar_kpis_stock()
    assert d["clinica"] == carregar_kpis_clinicos()
    assert d["partos"]["dias"] == 30 and d["atencao"]["limite"] == 5
    assert all(0 < x["palhetas"] <= 5 for x in d["atencao"]["itens"])
    assert all(x["palhetas"] > 0 for x in d["por_contentor"] + d["por_proprietario"])
    assert len(d["atividade"]) <= 10
