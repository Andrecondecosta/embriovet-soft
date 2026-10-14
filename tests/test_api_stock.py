"""API nova: Stock de sémen (Lotes, Garanhões, Adicionar lote) — base de TESTE.

Cria dono, contentor e garanhão próprios (prefixo `__api_stock__`) e apaga
tudo no fim.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from modules.db import get_connection
from modules.services.auth_service import criar_hash_password

P = "__api_stock__"


def _exec(sql, params=()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone() if cur.description else None
        conn.commit()
    return row


def _login(nivel: str) -> TestClient:
    username = f"{P}{nivel}{uuid.uuid4().hex[:6]}"
    _exec(
        "INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo, must_change_password)"
        " VALUES (%s, 'Teste', %s, %s, TRUE, FALSE)",
        (username, criar_hash_password("x123"), nivel),
    )
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"username": username, "password": "x123"}).status_code == 200
    return c


@pytest.fixture
def ctx():
    sufixo = uuid.uuid4().hex[:8]
    dono = _exec("INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id", (f"{P}dono{sufixo}",))[0]
    dono_inativo = _exec("INSERT INTO dono (nome, ativo) VALUES (%s, FALSE) RETURNING id", (f"{P}inativo{sufixo}",))[0]
    contentor = _exec(
        "INSERT INTO contentores (codigo, ativo) VALUES (%s, TRUE) RETURNING id", (f"{P}C{sufixo}",)
    )[0]
    yield {
        "admin": _login("Administrador"),
        "gestor": _login("Gestor"),
        "dono": dono,
        "dono_inativo": dono_inativo,
        "contentor": contentor,
        "garanhao": f"{P}Garanhão {sufixo}",
    }
    _exec(
        "DELETE FROM estoque_dono WHERE dono_id IN (%s, %s) OR contentor_id = %s",
        (dono, dono_inativo, contentor),
    )
    _exec("DELETE FROM animais WHERE nome LIKE %s", (f"{P}%",))
    _exec("DELETE FROM dono WHERE id IN (%s, %s)", (dono, dono_inativo))
    _exec("DELETE FROM contentores WHERE id = %s", (contentor,))
    _exec("DELETE FROM user_sessions WHERE username LIKE %s", (f"{P}%",))
    _exec("DELETE FROM usuarios WHERE username LIKE %s", (f"{P}%",))


def _novo(ctx, **extra):
    body = {
        "garanhao": ctx["garanhao"],
        "dono_id": ctx["dono"],
        "palhetas": 10,
        "contentor_id": ctx["contentor"],
        "canister": 3,
        "andar": 2,
        "qualidade": "80",
        "motilidade": 60,
        "concentracao": 200,
        "data_embriovet": "2026-05",
        **extra,
    }
    return ctx["gestor"].post("/api/stock/lotes", json=body)


def test_adicionar_lote_cria_garanhao_e_regista_utilizador(ctx):
    r = _novo(ctx)
    assert r.status_code == 201, r.text
    lote = r.json()
    assert lote["garanhao_nome"] == ctx["garanhao"]
    assert lote["animal_id"] is not None
    assert lote["existencia_atual"] == 10 and lote["quantidade_inicial"] == 10
    assert lote["criado_por"].startswith(f"{P}Gestor")
    assert (lote["contentor_id"], lote["canister"], lote["andar"]) == (ctx["contentor"], 3, 2)


def test_adicionar_lote_validacoes(ctx):
    assert _novo(ctx, palhetas=0).status_code == 422
    assert _novo(ctx, garanhao="  ").status_code == 422
    assert _novo(ctx, canister=11).status_code == 422
    assert _novo(ctx, andar=3).status_code == 422
    assert _novo(ctx, contentor_id=-1).status_code == 422


def test_lotes_kpis_e_resumo(ctx):
    _novo(ctx, palhetas=10, qualidade="80")
    _novo(ctx, palhetas=5, qualidade="60")
    r = ctx["gestor"].get("/api/stock/lotes", params={"garanhao": ctx["garanhao"]}).json()
    assert r["kpis"] == {"lotes": 2, "palhetas": 15, "proprietarios": 1, "qualidade_media": 70.0}
    assert r["por_proprietario"] == [{"dono_id": ctx["dono"], "proprietario_nome": r["items"][0]["proprietario_nome"], "palhetas": 15}]
    # Ligações só para Administrador (como na app atual).
    assert r["ligacoes"] == {}


def test_lotes_de_dono_inativo_nao_aparecem(ctx):
    _novo(ctx)
    _novo(ctx, dono_id=ctx["dono_inativo"])
    r = ctx["gestor"].get("/api/stock/lotes", params={"garanhao": ctx["garanhao"]}).json()
    assert [l["dono_id"] for l in r["items"]] == [ctx["dono"]]


def test_filtros(ctx):
    _novo(ctx, palhetas=10)
    _novo(ctx, palhetas=2)
    g = ctx["garanhao"]
    c = ctx["gestor"]
    assert len(c.get("/api/stock/lotes", params={"garanhao": g, "min_palhetas": 5}).json()["items"]) == 1
    assert len(c.get("/api/stock/lotes", params={"garanhao": g, "donos": [ctx["dono"]]}).json()["items"]) == 2
    assert len(c.get("/api/stock/lotes", params={"garanhao": g, "sem_dono": True}).json()["items"]) == 0


def test_garanhoes(ctx):
    _novo(ctx, palhetas=4)
    lista = ctx["gestor"].get("/api/stock/garanhoes").json()
    g = next(x for x in lista if x["garanhao"] == ctx["garanhao"])
    assert (g["palhetas"], g["lotes"], g["donos"], g["no_seletor"]) == (4, 1, 1, True)


def test_editar_e_apagar_so_admin(ctx):
    lote = _novo(ctx).json()
    body = {
        "garanhao": lote["garanhao"], "dono_id": ctx["dono"], "contentor_id": ctx["contentor"],
        "canister": 5, "andar": 1, "palhetas_produzidas": 10, "existencia_atual": 7,
        "certificado": "Não", "motilidade": 50,
    }
    assert ctx["gestor"].put(f"/api/stock/lotes/{lote['id']}", json=body).status_code == 403
    assert ctx["gestor"].delete(f"/api/stock/lotes/{lote['id']}").status_code == 403

    r = ctx["admin"].put(f"/api/stock/lotes/{lote['id']}", json=body)
    assert r.status_code == 200
    assert (r.json()["existencia_atual"], r.json()["canister"], r.json()["certificado"]) == (7, 5, "Não")

    admin_lotes = ctx["admin"].get("/api/stock/lotes", params={"garanhao": ctx["garanhao"]}).json()
    assert admin_lotes["items"][0]["id"] == lote["id"]

    assert ctx["admin"].delete(f"/api/stock/lotes/{lote['id']}").status_code == 200
    assert ctx["admin"].get(f"/api/stock/lotes/{lote['id']}").status_code == 404


def test_editar_muda_o_garanhao_a_serio(ctx):
    """Trocar o garanhão ao editar muda a ligação à ficha (animal_id) —
    o lote passa a aparecer no garanhão novo."""
    lote = _novo(ctx).json()
    novo_nome = ctx["garanhao"] + " B"
    body = {
        "garanhao": novo_nome, "dono_id": ctx["dono"], "contentor_id": ctx["contentor"],
        "canister": 3, "andar": 2, "palhetas_produzidas": 10, "existencia_atual": 10,
    }
    r = ctx["admin"].put(f"/api/stock/lotes/{lote['id']}", json=body)
    assert r.status_code == 200
    editado = r.json()
    assert editado["garanhao_nome"] == novo_nome
    assert editado["animal_id"] != lote["animal_id"]

    antigo = ctx["admin"].get("/api/stock/lotes", params={"garanhao": ctx["garanhao"]}).json()
    novo = ctx["admin"].get("/api/stock/lotes", params={"garanhao": novo_nome}).json()
    assert antigo["items"] == [] and [l["id"] for l in novo["items"]] == [lote["id"]]

    # Escrever o nome de um garanhão que já existe (outras maiúsculas) não
    # cria duplicado: volta para o primeiro.
    r = ctx["admin"].put(f"/api/stock/lotes/{lote['id']}", json={**body, "garanhao": ctx["garanhao"].upper()})
    assert r.json()["animal_id"] == lote["animal_id"]
