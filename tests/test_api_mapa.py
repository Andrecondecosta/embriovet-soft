"""API nova: Mapa dos contentores — base de TESTE. Dados próprios com
prefixo `__api_mapa__`, apagados no fim."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from modules.db import get_connection
from modules.repositories.animal_repo import get_or_create_garanhao
from modules.services.auth_service import criar_hash_password

P = "__api_mapa__"


def _exec(sql, params=()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall() if cur.description else None
        conn.commit()
    return rows


@pytest.fixture
def ctx():
    s = uuid.uuid4().hex[:8]
    username = f"{P}{s}"
    _exec(
        "INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo, must_change_password)"
        " VALUES (%s, 'Teste', %s, 'Visualizador', TRUE, FALSE)",
        (username, criar_hash_password("x123")),
    )
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"username": username, "password": "x123"}).status_code == 200
    dono = _exec("INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id", (f"{P}D{s}",))[0][0]
    animal = get_or_create_garanhao(f"{P}G{s}")
    yield {"c": c, "s": s, "dono": dono, "animal": animal}
    ids = [r[0] for r in _exec("SELECT id FROM contentores WHERE codigo LIKE %s", (f"{P}%",))]
    _exec("DELETE FROM estoque_dono WHERE dono_id = %s OR contentor_id = ANY(%s)", (dono, ids))
    _exec("DELETE FROM contentores WHERE id = ANY(%s)", (ids,))
    _exec("DELETE FROM animais WHERE nome LIKE %s", (f"{P}%",))
    _exec("DELETE FROM dono WHERE id = %s", (dono,))
    _exec("DELETE FROM user_sessions WHERE username = %s", (username,))
    _exec("DELETE FROM usuarios WHERE username = %s", (username,))


def _lote(ctx, cont, qtd, canister=1, andar=1):
    return _exec(
        """INSERT INTO estoque_dono (garanhao, animal_id, dono_id, existencia_atual, quantidade_inicial,
               contentor_id, canister, andar)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (f"{P}G{ctx['s']}", ctx["animal"], ctx["dono"], qtd, qtd, cont, canister, andar),
    )[0][0]


def test_criar_validar_editar_e_posicao(ctx):
    c = ctx["c"]
    cod = f"{P}A{ctx['s']}"
    r = c.post("/api/mapa/contentores", json={"codigo": f"  {cod} ", "descricao": "Sala 1"})
    assert r.status_code == 201, r.text
    cont = r.json()
    assert cont["codigo"] == cod and 0 <= cont["x"] <= 830

    assert c.post("/api/mapa/contentores", json={"codigo": cod}).status_code == 409
    assert c.post("/api/mapa/contentores", json={"codigo": "   "}).status_code == 422

    r = c.put(f"/api/mapa/contentores/{cont['id']}", json={"codigo": cod + "B", "descricao": "x"})
    assert r.json()["codigo"] == cod + "B" and r.json()["x"] == cont["x"]

    # Fora do mapa → encostado ao limite (900-70, 550-70).
    r = c.patch(f"/api/mapa/contentores/{cont['id']}/posicao", json={"x": 5000, "y": -3})
    assert r.json() == {"id": cont["id"], "x": 830, "y": 0}

    lista = c.get("/api/mapa/contentores").json()["contentores"]
    assert any(x["id"] == cont["id"] and x["x"] == 830 for x in lista)


def test_stock_mover_inverter_e_apagar(ctx):
    c = ctx["c"]
    a = c.post("/api/mapa/contentores", json={"codigo": f"{P}M{ctx['s']}"}).json()
    b = c.post("/api/mapa/contentores", json={"codigo": f"{P}N{ctx['s']}"}).json()
    lote = _lote(ctx, a["id"], 10, canister=2, andar=1)

    st = c.get(f"/api/mapa/contentores/{a['id']}/stock").json()
    assert st["palhetas"] == 10 and st["lotes"][0]["canister"] == 2

    # Mesmo sítio → recusado; mais do que há → recusado.
    assert c.post("/api/mapa/mover", json={"lote_id": lote, "quantidade": 1, "contentor_id": a["id"],
                                          "canister": 2, "andar": 1}).json()["detail"]["code"] == "web.map.error.same_place"
    assert c.post("/api/mapa/mover", json={"lote_id": lote, "quantidade": 11, "contentor_id": a["id"],
                                          "canister": 3, "andar": 1}).status_code == 409

    # Parte para outro contentor.
    r = c.post("/api/mapa/mover", json={"lote_id": lote, "quantidade": 4, "contentor_id": b["id"], "canister": 5, "andar": 2})
    assert r.status_code == 200
    assert c.get(f"/api/mapa/contentores/{a['id']}/stock").json()["palhetas"] == 6
    lotes_b = c.get(f"/api/mapa/contentores/{b['id']}/stock").json()["lotes"]
    assert [(l["canister"], l["andar"], l["existencia_atual"]) for l in lotes_b] == [(5, 2, 4)]

    # Inverter andares do contentor A: o lote passa ao 2º andar.
    assert c.post(f"/api/mapa/contentores/{a['id']}/inverter-andares").json()["count"] >= 1
    assert c.get(f"/api/mapa/contentores/{a['id']}/stock").json()["lotes"][0]["andar"] == 2

    # Apagar com stock → recusado com o nº de palhetas.
    r = c.delete(f"/api/mapa/contentores/{a['id']}")
    assert r.status_code == 409 and r.json()["detail"] == {"code": "web.map.error.has_stock", "params": {"count": 6}}

    # Contentor vazio de verdade → apaga.
    vazio = c.post("/api/mapa/contentores", json={"codigo": f"{P}V{ctx['s']}"}).json()
    assert c.delete(f"/api/mapa/contentores/{vazio['id']}").status_code == 200


def test_organizar_e_exportar(ctx):
    c = ctx["c"]
    cont = c.post("/api/mapa/contentores", json={"codigo": f"{P}E{ctx['s']}"}).json()
    _lote(ctx, cont["id"], 3)
    # "Organizar" mexe em todos os contentores: repor as posições no fim.
    antes = _exec("SELECT id, x, y FROM contentores")
    try:
        assert c.post("/api/mapa/organizar").json()["count"] >= 1
        assert c.get("/api/mapa/contentores").json()["contentores"][0]["x"] == 10
    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for cid, x, y in antes:
                    cur.execute("UPDATE contentores SET x = %s, y = %s WHERE id = %s", (x, y, cid))
            conn.commit()

    pdf = c.get("/api/mapa/exportar", params={"formato": "pdf", "ids": [cont["id"]]})
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    xlsx = c.get("/api/mapa/exportar", params={"formato": "xlsx", "ids": [cont["id"]]})
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"
    assert "inventario_contentores_" in xlsx.headers["content-disposition"]


def test_trocar_contentores_de_lugar(ctx):
    c = ctx["c"]
    a = c.post("/api/mapa/contentores", json={"codigo": f"{P}TA{ctx['s']}"}).json()
    b = c.post("/api/mapa/contentores", json={"codigo": f"{P}TB{ctx['s']}"}).json()
    c.patch(f"/api/mapa/contentores/{a['id']}/posicao", json={"x": 10, "y": 10})
    c.patch(f"/api/mapa/contentores/{b['id']}/posicao", json={"x": 460, "y": 190})

    r = c.post("/api/mapa/trocar", json={"a": a["id"], "b": b["id"]})
    assert r.status_code == 200
    pos = {x["id"]: (x["x"], x["y"]) for x in c.get("/api/mapa/contentores").json()["contentores"]}
    assert pos[a["id"]] == (460, 190) and pos[b["id"]] == (10, 10)

    assert c.post("/api/mapa/trocar", json={"a": a["id"], "b": a["id"]}).status_code == 422
