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
    assert r["exportar"] == ["pdf", "xlsx", "csv"]


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


def test_exportar_sem_escolha(client):
    # Sem garanhão escolhido não há relatório, logo não há ficheiro.
    r = client.get("/api/relatorios/exportar", params={"modo": "garanhao", "formato": "xlsx"})
    assert r.status_code == 400


@pytest.mark.parametrize("formato, tipo", [("pdf", "application/pdf"), ("csv", "text/csv"), ("xlsx", "spreadsheetml")])
@pytest.mark.parametrize("modo", ["garanhao", "proprietario", "contentor", "insem", "transf_int", "transf_ext"])
def test_exportar_todos_os_relatorios(client, opcoes, modo, formato, tipo):
    params = {"formato": formato}
    if modo == "garanhao":
        if not opcoes["garanhoes"]:
            pytest.skip("sem stock na base de teste")
        params |= {"modo": "garanhao", "garanhao": opcoes["garanhoes"][0]}
    elif modo == "proprietario":
        params |= {"modo": "proprietario", "proprietario": opcoes["proprietarios"][0]["id"]}
    elif modo == "contentor":
        if not opcoes["contentores"]:
            pytest.skip("sem contentores na base de teste")
        params |= {"modo": "contentor", "contentor": opcoes["contentores"][0]["id"]}
    else:
        params |= {"modo": "historico", "hist": modo, "inicio": "2020-01-01"}
    r = client.get("/api/relatorios/exportar", params=params)
    assert r.status_code == 200, r.text
    assert tipo in r.headers["content-type"]
    assert r.content



def test_exportar_so_lotes_e_colunas_escolhidos(client):
    r = client.get("/api/relatorios", params={"modo": "historico", "hist": "stock"}).json()
    tab = r["tabelas"][0]
    if len(tab["linhas"]) < 3:
        pytest.skip("poucos lotes na base de teste")
    assert {"qualidade", "concentracao", "motilidade"} <= set(tab["disponiveis"])
    ids = [l["_id"] for l in tab["linhas"][:2]]
    escolha = {"formato": "csv", "resumo": False, "tabelas": [{"titulo": tab["titulo"], "colunas": ["garanhao_nome", "concentracao"], "ids": ids}]}
    f = client.post("/api/relatorios/exportar", params={"modo": "historico", "hist": "stock"}, json=escolha)
    assert f.status_code == 200, f.text
    linhas = f.content.decode("utf-8-sig").strip().splitlines()
    assert linhas[3] == "Garanhão,Concentração (M/ml)"
    assert len(linhas) == 4 + 2


def test_exportar_nada_escolhido(client):
    escolha = {"formato": "pdf", "resumo": False, "tabelas": []}
    f = client.post("/api/relatorios/exportar", params={"modo": "historico", "hist": "insem"}, json=escolha)
    assert f.status_code == 400
    assert f.json()["detail"]["code"] == "web.reports.error.nothing_to_export"


def test_resumo_so_dos_lotes_escolhidos_e_sem_zeros(client, opcoes):
    if not opcoes["garanhoes"]:
        pytest.skip("sem stock na base de teste")
    params = {"modo": "garanhao", "garanhao": opcoes["garanhoes"][0]}
    stock = client.get("/api/relatorios", params=params).json()["tabelas"][0]
    lotes = [l for l in stock["linhas"] if l["existencia_atual"]][:2]
    if not lotes:
        pytest.skip("garanhão sem palhetas")
    escolha = {
        "formato": "csv",
        "resumo": True,
        "tabelas": [{"titulo": stock["titulo"], "colunas": ["proprietario_nome"], "ids": [l["_id"] for l in lotes]}],
    }
    texto = client.post("/api/relatorios/exportar", params=params, json=escolha).content.decode("utf-8-sig")
    resumo = texto.split("\r\n\r\n")[0].splitlines()[1:]
    assert resumo[0].endswith(f",{sum(l['existencia_atual'] for l in lotes)}")
    assert all(not linha.endswith(",0") for linha in resumo)


@pytest.mark.parametrize("modo", ["linhas", "totais"])
def test_exportar_por_cavalo_com_totais(client, modo):
    params = {"modo": "historico", "hist": "stock"}
    tab = client.get("/api/relatorios", params=params).json()["tabelas"][0]
    linhas = [l for l in tab["linhas"] if l["existencia_atual"]][:6]
    if len({l["garanhao_nome"] for l in linhas}) < 2:
        pytest.skip("precisa de lotes de pelo menos dois garanhões")
    escolha = {"formato": "csv", "resumo": False, "tabelas": [{
        "titulo": tab["titulo"], "colunas": ["proprietario_nome", "garanhao_nome", "existencia_atual"],
        "ids": [l["_id"] for l in linhas], "modo": modo,
    }]}
    texto = client.post("/api/relatorios/exportar", params=params, json=escolha).content.decode("utf-8-sig")
    corpo = texto.strip().splitlines()[3:]
    assert corpo[-1].startswith("Total geral,") and corpo[-1].endswith(f",{sum(l['existencia_atual'] for l in linhas)}")
    if modo == "totais":
        assert corpo[0] == "Garanhão,Lotes,Palhetas"
        assert len(corpo) == 1 + len({l["garanhao_nome"] for l in linhas}) + 1
    else:
        assert corpo[0] == "Garanhão,Proprietário,Palhetas"
        assert sum(1 for c in corpo if c.startswith("Total ") and not c.startswith("Total geral")) == len({l["garanhao_nome"] for l in linhas})


def test_dados_estudo_so_admin_e_sem_nomes(client):
    # O cliente destes testes é Visualizador.
    assert client.get("/api/relatorios/estudo").status_code == 403


def test_dados_estudo_folhas():
    from modules.estudo_export import tabelas_estudo

    folhas = tabelas_estudo()
    assert [f[0] for f in folhas] == ["Éguas", "Exames", "Inseminações", "Diagnósticos", "Legenda"]
    insem = folhas[2]
    assert insem[1][:4] == ["egua", "inseminacao", "data", "hora"]
    # Códigos, não nomes.
    assert all(str(l[0]).startswith("E") for l in insem[2])
    assert all(l[4] is None or str(l[4]).startswith("G") for l in insem[2])
