"""API nova (FastAPI): Trabalho diário — contra a base de TESTE."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from modules.db import get_connection
from modules.repositories.dashboard_repo import carregar_resumo_tarefas_hoje
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
            cur.execute("DELETE FROM trabalho_diario WHERE animal_id IN (SELECT id FROM animais WHERE nome LIKE %s)", (f"{PREFIXO}%",))
            cur.execute("DELETE FROM estadias WHERE animal_id IN (SELECT id FROM animais WHERE nome LIKE %s)", (f"{PREFIXO}%",))
            cur.execute("DELETE FROM animais WHERE nome LIKE %s", (f"{PREFIXO}%",))
            cur.execute("DELETE FROM dono WHERE nome LIKE %s", (f"{PREFIXO}%",))
            cur.execute("DELETE FROM user_sessions WHERE username = %s", (username,))
            cur.execute("DELETE FROM usuarios WHERE username = %s", (username,))
        conn.commit()


def _tarefa(dias_atras: int) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO animais (nome, tipo, ativo) VALUES (%s, 'egua', TRUE) RETURNING id", (f"{PREFIXO}{uuid.uuid4().hex[:6]}",))
            aid = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO trabalho_diario (animal_id, data_tarefa, tipo, motivo, urgencia)
                VALUES (%s, %s, 'verificar_ovulacao', 'teste', 'hoje') RETURNING id
                """,
                (aid, date.today() - timedelta(days=dias_atras)),
            )
            tid = cur.fetchone()[0]
        conn.commit()
    return tid


def test_lista_do_dia_e_atrasadas(client):
    hoje, atrasada = _tarefa(0), _tarefa(3)
    r = client.get("/api/trabalho").json()
    assert r["resumo"] == carregar_resumo_tarefas_hoje()
    assert any(x["tarefa_id"] == hoje for x in r["por_fazer"])
    linha = next(x for x in r["atrasadas"] if x["tarefa_id"] == atrasada)
    assert linha["dias_atraso"] == 3
    assert not any(x["tarefa_id"] == atrasada for x in r["por_fazer"])
    # Um dia anterior à tarefa atrasada já não a mostra.
    antes = client.get("/api/trabalho", params={"dia": (date.today() - timedelta(days=5)).isoformat()}).json()
    assert not any(x["tarefa_id"] in (hoje, atrasada) for x in antes["por_fazer"] + antes["atrasadas"])


def test_gerar_primeira_observacao_e_idempotente(client):
    client.post("/api/trabalho/gerar")
    assert client.post("/api/trabalho/gerar").json()["criadas"] == 0


def _internado(tipo: str, registo_novo: bool = False) -> int:
    """Animal com estadia aberta (visita); opcionalmente com um registo clínico novo."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO animais (nome, tipo, ativo) VALUES (%s, %s, TRUE) RETURNING id", (f"{PREFIXO}{uuid.uuid4().hex[:6]}", tipo))
            aid = cur.fetchone()[0]
            cur.execute("INSERT INTO dono (nome) VALUES (%s) RETURNING id", (f"{PREFIXO}{uuid.uuid4().hex[:6]}",))
            dono = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO estadias (tipo_registo, animal_id, dono_id, data_entrada, motivo, estado)
                   VALUES ('visita', %s, %s, CURRENT_DATE, %s, 'visitante') RETURNING id""",
                (aid, dono, "colheita" if tipo == "garanhao" else "diagnostico"),
            )
            eid = cur.fetchone()[0]
            if registo_novo:
                cur.execute(
                    "INSERT INTO registo_clinico (animal_id, estadia_id, data_registo, dados) VALUES (%s, %s, NOW(), '{}')",
                    (aid, eid),
                )
        conn.commit()
    return aid


def _primeiras_observacoes(aid: int) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM trabalho_diario WHERE animal_id = %s AND tipo = 'primeira_observacao'", (aid,))
            return cur.fetchone()[0]


def test_primeira_observacao_nao_inclui_garanhoes_nem_eguas_com_registo_novo(client):
    garanhao = _internado("garanhao")
    egua_com_registo = _internado("egua", registo_novo=True)
    egua_sem_registo = _internado("egua")
    client.post("/api/trabalho/gerar")
    try:
        assert _primeiras_observacoes(garanhao) == 0
        assert _primeiras_observacoes(egua_com_registo) == 0
        assert _primeiras_observacoes(egua_sem_registo) == 1
    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM registo_clinico WHERE animal_id = %s", (egua_com_registo,))
            conn.commit()
