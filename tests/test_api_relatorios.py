"""API nova (FastAPI): Relatórios — só leitura, contra a base de TESTE."""

from __future__ import annotations

import uuid
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from modules.db import get_connection
from modules.services.auth_service import criar_hash_password

PREFIXO = "__api_test__"


@pytest.fixture(scope="module")
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


@pytest.fixture(scope="module")
def opcoes(client):
    return client.get("/api/relatorios/opcoes").json()


def test_pede_sessao():
    assert TestClient(app).get("/api/relatorios/opcoes").status_code == 401


def test_garanhao_kpi_bate_com_a_tabela(client, opcoes):
    if not opcoes["garanhoes"]:
        pytest.skip("sem stock na base de teste")
    r = client.get("/api/relatorios", params={"modo": "garanhao", "garanhao": opcoes["garanhoes"][0]}).json()
    stock = r["tabelas"][0]
    assert stock["titulo"] == "reports.section.stock"
    assert r["kpis"][0] == ["reports.kpi.straws_stock", sum(l["existencia_atual"] for l in stock["linhas"])]
    assert r["exportar"] == ["csv", "pdf"]


def test_filtro_proprietario_no_garanhao(client, opcoes):
    if not opcoes["garanhoes"]:
        pytest.skip("sem stock na base de teste")
    g = opcoes["garanhoes"][0]
    tudo = client.get("/api/relatorios", params={"modo": "garanhao", "garanhao": g}).json()
    dono = tudo["filtros"]["prop"][0]
    r = client.get("/api/relatorios", params={"modo": "garanhao", "garanhao": g, "f_prop": [dono]}).json()
    assert all(l["proprietario_nome"] == dono for l in r["tabelas"][0]["linhas"])


@pytest.mark.parametrize("hist", ["insem", "transf_int", "transf_ext", "stock"])
def test_historicos(client, hist):
    r = client.get("/api/relatorios", params={"modo": "historico", "hist": hist})
    assert r.status_code == 200
    assert len(r.json()["tabelas"]) == 1


def test_periodo_invalido(client):
    r = client.get("/api/relatorios", params={"modo": "historico", "inicio": "2026-10-10", "fim": "2026-01-01"})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "reports.invalid_period"


@pytest.mark.parametrize("formato, tipo", [("pdf", "application/pdf"), ("csv", "text/csv"), ("xlsx", "spreadsheetml")])
def test_exportar_stock_completo(client, formato, tipo):
    r = client.get("/api/relatorios/exportar", params={"modo": "historico", "hist": "stock", "formato": formato})
    assert r.status_code == 200
    assert tipo in r.headers["content-type"]
    assert r.content


def test_exportar_nome_com_acentos(client):
    # Nome com acentos no ficheiro não pode partir o cabeçalho da descarga.
    r = client.get("/api/relatorios/exportar", params={"modo": "garanhao", "garanhao": "Falcão Ñ", "formato": "csv"})
    assert r.status_code == 200
    cd = r.headers["content-disposition"]
    assert 'filename="garanhao_Falcao N.csv"' in cd
    assert unquote(cd.split("filename*=UTF-8''")[1]) == "garanhao_Falcão Ñ.csv"


def test_exportar_combinacao_que_nao_existe(client):
    r = client.get("/api/relatorios/exportar", params={"modo": "contentor", "contentor": 1, "formato": "pdf"})
    assert r.status_code == 400
