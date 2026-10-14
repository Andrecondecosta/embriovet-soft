"""API nova: Transferências (internas, externas, editar, anular, histórico)
— base de TESTE. Dados próprios com prefixo `__api_transf__`, apagados no fim.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from modules.db import get_connection
from modules.repositories.animal_repo import get_or_create_garanhao
from modules.services.auth_service import criar_hash_password

P = "__api_transf__"


def _exec(sql, params=()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall() if cur.description else None
        conn.commit()
    return rows


def _um(sql, params=()):
    return _exec(sql, params)[0]


@pytest.fixture
def ctx():
    s = uuid.uuid4().hex[:8]
    username = f"{P}{s}"
    _exec(
        "INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo, must_change_password)"
        " VALUES (%s, 'Teste', %s, 'Gestor', TRUE, FALSE)",
        (username, criar_hash_password("x123")),
    )
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"username": username, "password": "x123"}).status_code == 200

    a = _um("INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id", (f"{P}A{s}",))[0]
    b = _um("INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id", (f"{P}B{s}",))[0]
    cont = _um("INSERT INTO contentores (codigo, ativo) VALUES (%s, TRUE) RETURNING id", (f"{P}C{s}",))[0]
    cont2 = _um("INSERT INTO contentores (codigo, ativo) VALUES (%s, TRUE) RETURNING id", (f"{P}D{s}",))[0]
    nome_g = f"{P}G{s}"
    animal = get_or_create_garanhao(nome_g)

    def lote(dono, qtd, ref):
        return _um(
            """INSERT INTO estoque_dono (garanhao, animal_id, dono_id, existencia_atual, quantidade_inicial,
                   origem_externa, contentor_id, canister, andar)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 1, 1) RETURNING id""",
            (nome_g, animal, dono, qtd, qtd, ref, cont),
        )[0]

    l1 = lote(a, 10, f"{P}L1")
    l2 = lote(a, 6, f"{P}L2")
    yield {"c": c, "user": username, "a": a, "b": b, "cont": cont, "cont2": cont2, "l1": l1, "l2": l2}

    ids = (a, b)
    _exec("DELETE FROM transferencias WHERE proprietario_origem_id = ANY(%s) OR proprietario_destino_id = ANY(%s)",
          (list(ids), list(ids)))
    _exec("DELETE FROM transferencias_externas WHERE proprietario_origem_id = ANY(%s)", (list(ids),))
    _exec("DELETE FROM historico_edicoes WHERE utilizador_nome = %s", (username,))
    _exec("DELETE FROM estoque_dono WHERE dono_id = ANY(%s)", (list(ids),))
    _exec("DELETE FROM animais WHERE nome LIKE %s", (f"{P}%",))
    _exec("DELETE FROM dono WHERE id = ANY(%s)", (list(ids),))
    _exec("DELETE FROM contentores WHERE id = ANY(%s)", ([cont, cont2],))
    _exec("DELETE FROM user_sessions WHERE username = %s", (username,))
    _exec("DELETE FROM usuarios WHERE username = %s", (username,))


def _exist(lote_id):
    return _um("SELECT existencia_atual FROM estoque_dono WHERE id = %s", (lote_id,))[0]


def _lotes_de(dono):
    return _exec(
        "SELECT existencia_atual, contentor_id, canister, andar FROM estoque_dono WHERE dono_id = %s ORDER BY id",
        (dono,),
    )


def test_interna_multi_lote_mesmo_local(ctx):
    r = ctx["c"].post("/api/transferencias", json={
        "tipo": "interna", "destino_id": ctx["b"],
        "linhas": [{"stock_id": ctx["l1"], "quantidade": 4}, {"stock_id": ctx["l2"], "quantidade": 6}],
    })
    assert r.status_code == 201, r.text
    op = r.json()["operation_id"]
    assert (_exist(ctx["l1"]), _exist(ctx["l2"])) == (6, 0)
    # Mesmo garanhão e mesma localização no destino → um só lote com 10.
    assert _lotes_de(ctx["b"]) == [(10, ctx["cont"], 1, 1)]
    regs = _exec("SELECT utilizador, operation_id::text FROM transferencias WHERE operation_id = %s::uuid", (op,))
    assert len(regs) == 2 and all(u == ctx["user"] for u, _ in regs)


def test_interna_nova_localizacao(ctx):
    r = ctx["c"].post("/api/transferencias", json={
        "tipo": "interna", "destino_id": ctx["b"], "linhas": [{"stock_id": ctx["l1"], "quantidade": 3}],
        "nova_localizacao": {"contentor_id": ctx["cont2"], "canister": 7, "andar": 2},
    })
    assert r.status_code == 201
    assert _lotes_de(ctx["b"]) == [(3, ctx["cont2"], 7, 2)]


def test_validacoes_nao_mexem_em_nada(ctx):
    c = ctx["c"]
    # Quantidade a mais num dos lotes: nenhum lote é tocado.
    r = c.post("/api/transferencias", json={
        "tipo": "interna", "destino_id": ctx["b"],
        "linhas": [{"stock_id": ctx["l1"], "quantidade": 2}, {"stock_id": ctx["l2"], "quantidade": 99}],
    })
    assert r.status_code == 409 and r.json()["detail"]["code"] == "web.transfer.error.insufficient"
    assert (_exist(ctx["l1"]), _exist(ctx["l2"])) == (10, 6)
    # Para o próprio dono.
    r = c.post("/api/transferencias", json={
        "tipo": "interna", "destino_id": ctx["a"], "linhas": [{"stock_id": ctx["l1"], "quantidade": 1}],
    })
    assert r.json()["detail"]["code"] == "web.transfer.error.same_owner"
    # Externa sem destinatário; interna sem destino.
    assert c.post("/api/transferencias", json={
        "tipo": "externa", "linhas": [{"stock_id": ctx["l1"], "quantidade": 1}]}).status_code == 422
    assert c.post("/api/transferencias", json={
        "tipo": "interna", "linhas": [{"stock_id": ctx["l1"], "quantidade": 1}]}).status_code == 422
    assert _exist(ctx["l1"]) == 10


def test_externa_editar_e_anular(ctx):
    c = ctx["c"]
    r = c.post("/api/transferencias", json={
        "tipo": "externa", "destinatario": "Haras X", "motivo": "Venda", "observacoes": "fatura 12",
        "linhas": [{"stock_id": ctx["l1"], "quantidade": 4}],
    })
    assert r.status_code == 201
    assert _exist(ctx["l1"]) == 6
    action_id = _um("SELECT id FROM transferencias_externas WHERE estoque_id = %s", (ctx["l1"],))[0]

    op = c.get(f"/api/transferencias/operacao/transfer_external/{action_id}").json()
    assert op["destinatario"] == "Haras X" and op["motivo"] == "Venda"
    # O disponível para editar já conta com as 4 palhetas que voltam.
    assert op["linhas"][0]["existencia_atual"] == 10 and op["linhas"][0]["quantidade"] == 4

    r = c.put(f"/api/transferencias/operacao/transfer_external/{action_id}", json={
        "tipo": "externa", "destinatario": "Haras Y", "motivo": "Doação",
        "linhas": [{"stock_id": ctx["l1"], "quantidade": 10}],
    })
    assert r.status_code == 200, r.text
    assert _exist(ctx["l1"]) == 0
    reg = _exec("SELECT destinatario_externo, tipo, quantidade, atualizado FROM transferencias_externas"
                " WHERE estoque_id = %s", (ctx["l1"],))
    assert reg == [("Haras Y", "Doação", 10, True)]
    assert _exec("SELECT COUNT(*) FROM historico_edicoes WHERE utilizador_nome = %s", (ctx["user"],))[0][0] == 1

    hist = c.get("/api/transferencias/historico", params={"dia": date.today().isoformat()}).json()
    linha = next(h for h in hist if h["tipo"] == "transfer_external" and "Haras Y" in (h["detalhe"] or ""))
    r = c.post("/api/transferencias/anular", json={
        "tipo": linha["tipo"], "action_id": linha["action_id"], "operation_id": linha["operation_id"]})
    assert r.status_code == 200
    assert _exist(ctx["l1"]) == 10


def test_editar_interna_mudar_destino(ctx):
    c = ctx["c"]
    c.post("/api/transferencias", json={
        "tipo": "interna", "destino_id": ctx["b"], "linhas": [{"stock_id": ctx["l1"], "quantidade": 5}]})
    action_id = _um("SELECT id FROM transferencias WHERE estoque_id = %s", (ctx["l1"],))[0]
    # Passa a externa: a interna antiga é anulada (B fica sem o lote).
    r = c.put(f"/api/transferencias/operacao/transfer_internal/{action_id}", json={
        "tipo": "externa", "destinatario": "Fora", "linhas": [{"stock_id": ctx["l1"], "quantidade": 2}]})
    assert r.status_code == 200, r.text
    assert _exist(ctx["l1"]) == 8
    assert _lotes_de(ctx["b"]) == []
    assert _exec("SELECT COUNT(*) FROM transferencias WHERE estoque_id = %s", (ctx["l1"],))[0][0] == 0
