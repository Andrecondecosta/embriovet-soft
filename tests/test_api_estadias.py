"""API nova (FastAPI): Estadias e visitas — contra a base de TESTE.

Cria animais e estadias próprios (prefixo `__api_test__`) e apaga-os no fim.
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
            cur.execute("DELETE FROM estadias WHERE animal_id IN (SELECT id FROM animais WHERE nome LIKE %s)", (f"{PREFIXO}%",))
            cur.execute("DELETE FROM animais WHERE nome LIKE %s", (f"{PREFIXO}%",))
            cur.execute("DELETE FROM alojamentos WHERE nome LIKE %s", (f"{PREFIXO}%",))
            cur.execute("DELETE FROM dono WHERE nome LIKE %s", (f"{PREFIXO}%",))
            cur.execute("DELETE FROM user_sessions WHERE username = %s", (username,))
            cur.execute("DELETE FROM usuarios WHERE username = %s", (username,))
        conn.commit()


@pytest.fixture
def base(client):
    """Um dono e um alojamento de teste."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id", (f"{PREFIXO}dono{uuid.uuid4().hex[:6]}",))
            dono = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO alojamentos (tipo, nome, capacidade, ativo) VALUES ('box', %s, 1, TRUE) RETURNING id",
                (f"{PREFIXO}box{uuid.uuid4().hex[:6]}",),
            )
            aloj = cur.fetchone()[0]
        conn.commit()
    return {"dono": dono, "aloj": aloj}


def _nova(client, base, **extra):
    corpo = {
        "animal": {"nome": f"{PREFIXO}{uuid.uuid4().hex[:6]}", "tipo": "egua"},
        "tipo_registo": "estadia",
        "motivo": "inseminacao",
        "dono_id": base["dono"],
        "data_entrada": date.today().isoformat(),
        "alojamento_id": base["aloj"],
        **extra,
    }
    return client.post("/api/estadias", json=corpo)


def test_nova_estadia_com_animal_novo_e_saida(client, base):
    r = _nova(client, base)
    assert r.status_code == 201
    eid, aid = r.json()["id"], r.json()["animal_id"]

    inter = client.get("/api/estadias/internadas").json()
    linha = next(x for x in inter["itens"] if x["id"] == eid)
    assert linha["estado"] == "internado" and linha["animal_id"] == aid
    assert client.get("/api/estadias/internadas", params={"tipo_animal": "garanhao"}).json()["total"] == inter["total"]
    assert any(x["id"] == eid for x in client.get("/api/estadias/movimentos").json()["entram"])

    # O mesmo animal não pode ter duas estadias abertas.
    r = _nova(client, base, animal=None, animal_id=aid)
    assert r.json()["detail"]["code"] == "web.stays.error.already_open"

    # "Outro" exige observações; a saída não pode ser antes da entrada.
    hoje = date.today()
    r = client.post(f"/api/estadias/{eid}/saida", json={"data_saida": hoje.isoformat(), "estado": "sem_resultado"})
    assert r.json()["detail"]["code"] == "web.stays.error.exit_notes_required"
    r = client.post(f"/api/estadias/{eid}/saida", json={"data_saida": (hoje - timedelta(days=1)).isoformat(), "estado": "alta"})
    assert r.json()["detail"]["code"] == "web.stays.error.exit_before_entry"

    assert client.post(f"/api/estadias/{eid}/saida", json={"data_saida": hoje.isoformat(), "estado": "transferido"}).status_code == 200
    assert not any(x["id"] == eid for x in client.get("/api/estadias/internadas").json()["itens"])
    hist = client.get("/api/estadias/historico", params={"ano": hoje.year, "mes": hoje.month}).json()
    assert next(x for x in hist["itens"] if x["id"] == eid)["estado"] == "transferido"
    r = client.post(f"/api/estadias/{eid}/saida", json={"data_saida": hoje.isoformat(), "estado": "alta"})
    assert r.json()["detail"]["code"] == "web.stays.error.already_closed"


def test_validacoes_nova(client, base):
    assert _nova(client, base, alojamento_id=None).json()["detail"]["code"] == "web.stays.error.housing_required"
    assert _nova(client, base, dono_id=None).json()["detail"]["code"] == "web.stays.error.owner_required"
    assert _nova(client, base, animal={"nome": " "}).json()["detail"]["code"] == "web.stays.error.animal_name_required"
    r = _nova(client, base, animal=None)
    assert r.json()["detail"]["code"] == "web.stays.error.animal_required"


def test_animal_repetido_do_mesmo_dono(client, base):
    nome = f"{PREFIXO}{uuid.uuid4().hex[:6]}"
    assert _nova(client, base, animal={"nome": nome}).status_code == 201
    r = _nova(client, base, animal={"nome": nome.upper()})
    assert r.json()["detail"]["code"] == "web.stays.error.animal_exists"


def test_visita_e_externo_sem_alojamento(client, base):
    assert _nova(client, base, tipo_registo="visita", alojamento_id=None).status_code == 201
    r = _nova(client, base, tipo_registo="externo")
    assert r.status_code == 201
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT estado, alojamento_id FROM estadias WHERE id = %s", (r.json()["id"],))
            assert cur.fetchone() == ("externo", None)


def test_pesquisa_animais(client, base):
    nome = f"{PREFIXO}Pesq{uuid.uuid4().hex[:6]}"
    _nova(client, base, animal={"nome": nome})
    r = client.get("/api/animais/pesquisa", params={"q": nome.lower()}).json()
    assert len(r) == 1 and r[0]["em_aberto"] == "estadia" and r[0]["dono_id"] == base["dono"]
