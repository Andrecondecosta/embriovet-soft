"""API nova (FastAPI): ficha do animal — contra a base de TESTE.

Cria animais, estadias e tarefas próprios (prefixo `__api_test__`) e
apaga-os no fim.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from modules.db import get_connection
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
                VALUES (%s, 'Teste API', %s, 'Gestor', TRUE, FALSE)
                """,
                (username, criar_hash_password("segredo123")),
            )
        conn.commit()
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"username": username, "password": "segredo123"}).status_code == 200
    yield c
    with get_connection() as conn:
        with conn.cursor() as cur:
            sub = "SELECT id FROM animais WHERE nome LIKE %s"
            cur.execute(f"DELETE FROM trabalho_diario WHERE animal_id IN ({sub})", (f"{PREFIXO}%",))
            cur.execute(f"DELETE FROM diario_clinico WHERE animal_id IN ({sub})", (f"{PREFIXO}%",))
            cur.execute(f"DELETE FROM acompanhamento_inseminacao WHERE animal_id IN ({sub})", (f"{PREFIXO}%",))
            cur.execute(f"DELETE FROM estadias WHERE animal_id IN ({sub})", (f"{PREFIXO}%",))
            cur.execute("DELETE FROM animais WHERE nome LIKE %s", (f"{PREFIXO}%",))
            cur.execute("DELETE FROM dono WHERE nome LIKE %s", (f"{PREFIXO}%",))
            cur.execute("DELETE FROM user_sessions WHERE username = %s", (username,))
            cur.execute("DELETE FROM usuarios WHERE username = %s", (username,))
        conn.commit()


def _animal(tipo="egua", estadia=True):
    """Animal de teste; com estadia de inseminação aberta e uma tarefa de hoje."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id", (f"{PREFIXO}d{uuid.uuid4().hex[:6]}",))
            dono = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO animais (nome, tipo, dono_id, ativo) VALUES (%s, %s, %s, TRUE) RETURNING id",
                (f"{PREFIXO}{uuid.uuid4().hex[:6]}", tipo, dono),
            )
            aid = cur.fetchone()[0]
            if estadia:
                cur.execute(
                    """
                    INSERT INTO estadias (tipo_registo, animal_id, dono_id, data_entrada, motivo, estado)
                    VALUES ('visita', %s, %s, CURRENT_DATE, 'inseminacao', 'visitante') RETURNING id
                    """,
                    (aid, dono),
                )
                eid = cur.fetchone()[0]
                cur.execute(
                    """
                    INSERT INTO trabalho_diario (animal_id, estadia_id, data_tarefa, tipo, motivo, urgencia)
                    VALUES (%s, %s, CURRENT_DATE, 'verificar_ovulacao', 'teste', 'hoje')
                    """,
                    (aid, eid),
                )
        conn.commit()
    return aid


def _tarefas(aid):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT data_tarefa, concluida FROM trabalho_diario WHERE animal_id = %s ORDER BY data_tarefa", (aid,))
            return cur.fetchall()


def test_ficha_e_editar(client):
    aid = _animal()
    f = client.get(f"/api/animais/{aid}").json()
    assert f["tipo"] == "egua" and f["estadia_ativa"] and f["estadia_inseminacao"]
    r = client.put(f"/api/animais/{aid}", json={"nome": f["nome"], "tipo": "egua", "raca": " Lusitano ", "altura": 0})
    assert r.json()["raca"] == "Lusitano" and r.json()["altura"] is None
    assert client.put(f"/api/animais/{aid}", json={"nome": " "}).json()["detail"]["code"] == "web.stays.error.animal_name_required"
    assert client.get("/api/animais/999999999").status_code == 404


def test_diario_conclui_tarefas_e_agenda_proxima(client):
    aid = _animal()
    amanha = date.today() + timedelta(days=1)
    r = client.post(
        f"/api/animais/{aid}/diario",
        json={"data_registo": date.today().isoformat(), "foliculo_mm": 35, "edema_grau": 2, "comportamento": "cio_ativo", "proxima_observacao": amanha.isoformat()},
    )
    assert r.status_code == 201 and r.json()["tarefas_concluidas"] == 1
    assert _tarefas(aid) == [(date.today(), True), (amanha, False)]

    rid = r.json()["id"]
    assert client.put(f"/api/animais/{aid}/diario/{rid}", json={"data_registo": date.today().isoformat(), "foliculo_mm": 40}).status_code == 200
    assert client.get(f"/api/animais/{aid}/diario").json()[0]["foliculo_mm"] == 40
    assert client.delete(f"/api/animais/{aid}/diario/{rid}").status_code == 200
    assert client.get(f"/api/animais/{aid}/diario").json() == []
    # Registos de outro animal não se mexem por esta ficha.
    assert client.delete(f"/api/animais/{aid}/diario/{rid}").status_code == 404


def test_diario_sem_estadia(client):
    aid = _animal(estadia=False)
    r = client.post(f"/api/animais/{aid}/diario", json={"data_registo": date.today().isoformat()})
    assert r.json()["detail"]["code"] == "web.animal.error.no_active_stay"


def test_reprodutivo_e_acompanhamento(client):
    aid = _animal()
    rep = client.get(f"/api/animais/{aid}/reprodutivo").json()
    assert rep["total"] == 0 and rep["taxa"] is None
    r = client.post(f"/api/animais/{aid}/resultado", json={"op_key": "nao-existe", "resultado": "positivo"})
    assert r.json()["detail"]["code"] == "web.animal.error.result_not_allowed"

    hoje = date.today().isoformat()
    r = client.put(f"/api/animais/{aid}/acompanhamento", json={"garanhao": "Zeus", "data_inseminacao": hoje})
    a = r.json()["acompanhamento"]
    assert a["garanhao"] == "Zeus" and a["data_inseminacao"] == hoje
    assert len(r.json()["estadias"]) == 1


def test_garanhao_alertas_e_colheitas(client):
    gid = _animal(tipo="garanhao", estadia=False)
    assert client.get(f"/api/animais/{gid}/producao").json()["kpis"]["palhetas"] == 0
    assert client.get(f"/api/animais/{gid}/fertilidade").json()["total"] == 0
    chaves = [a["chave"] for a in client.get(f"/api/animais/{gid}/alertas").json()]
    assert chaves == ["web.animal.alert.stock_critical", "web.animal.alert.no_production"]

    ontem = (date.today() - timedelta(days=1)).isoformat()
    assert client.post(f"/api/animais/{gid}/colheitas", json={"data": ontem}).json()["detail"]["code"] == "web.animal.error.collection_past"
    amanha = (date.today() + timedelta(days=1)).isoformat()
    tid = client.post(f"/api/animais/{gid}/colheitas", json={"data": amanha}).json()["id"]
    assert [c["id"] for c in client.get(f"/api/animais/{gid}/colheitas").json()] == [tid]
    assert client.delete(f"/api/animais/{gid}/colheitas/{tid}").status_code == 200
    assert client.get(f"/api/animais/{gid}/colheitas").json() == []
