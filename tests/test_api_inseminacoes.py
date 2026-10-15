"""API nova (FastAPI): Registar inseminação — contra a base de TESTE.

Cria um dono, um garanhão com um lote, e uma égua com visita aberta
(prefixo `__api_test__`); apaga tudo no fim.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from modules.db import get_connection
from modules.services.auth_service import criar_hash_password

P = "__api_test__"


def _um(sql, params=()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone() if cur.description else None
        conn.commit()
    return row


@pytest.fixture
def ctx():
    username = f"{P}{uuid.uuid4().hex[:8]}"
    _um(
        """INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo, must_change_password)
           VALUES (%s, 'Teste API', %s, 'Gestor', TRUE, FALSE)""",
        (username, criar_hash_password("segredo123")),
    )
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"username": username, "password": "segredo123"}).status_code == 200
    dono = _um("INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id", (f"{P}dono{uuid.uuid4().hex[:6]}",))[0]
    nome_g = f"{P}Gar{uuid.uuid4().hex[:6]}"
    gar = _um("INSERT INTO animais (nome, tipo, ativo) VALUES (%s, 'garanhao', TRUE) RETURNING id", (nome_g,))[0]
    lote = _um(
        """INSERT INTO estoque_dono (garanhao, animal_id, dono_id, existencia_atual, quantidade_inicial, origem_externa)
           VALUES (%s, %s, %s, 10, 10, %s) RETURNING id""",
        (nome_g, gar, dono, f"{P}L"),
    )[0]
    egua = _um("INSERT INTO animais (nome, tipo, dono_id, ativo) VALUES (%s, 'egua', %s, TRUE) RETURNING id", (f"{P}Egua{uuid.uuid4().hex[:6]}", dono))[0]
    _um(
        """INSERT INTO estadias (tipo_registo, animal_id, dono_id, data_entrada, motivo, estado)
           VALUES ('visita', %s, %s, CURRENT_DATE, 'inseminacao', 'visitante')""",
        (egua, dono),
    )
    yield {"c": c, "dono": dono, "gar": nome_g, "lote": lote, "egua": egua, "user": username}
    sub = "SELECT id FROM animais WHERE nome LIKE %s"
    for sql in (
        f"DELETE FROM trabalho_diario WHERE animal_id IN ({sub})",
        f"DELETE FROM acompanhamento_inseminacao WHERE animal_id IN ({sub})",
        f"DELETE FROM inseminacoes WHERE animal_id_egua IN ({sub})",
        f"DELETE FROM estadias WHERE animal_id IN ({sub})",
    ):
        _um(sql, (f"{P}%",))
    _um("DELETE FROM historico_edicoes WHERE utilizador_nome = %s", (username,))
    _um("DELETE FROM estoque_dono WHERE dono_id = %s", (dono,))
    _um("DELETE FROM animais WHERE nome LIKE %s", (f"{P}%",))
    _um("DELETE FROM dono WHERE id = %s", (dono,))
    _um("DELETE FROM user_sessions WHERE username = %s", (username,))
    _um("DELETE FROM usuarios WHERE username = %s", (username,))


def _stock(lote):
    return _um("SELECT existencia_atual FROM estoque_dono WHERE id = %s", (lote,))[0]


def _corpo(x, palhetas, **extra):
    return {
        "animal_id_egua": x["egua"],
        "garanhao": x["gar"],
        "data_inseminacao": date.today().isoformat(),
        "linhas": [{"stock_id": x["lote"], "palhetas": palhetas}],
        **extra,
    }


def test_listas(ctx):
    c = ctx["c"]
    assert any(l["id"] == ctx["lote"] for l in c.get("/api/inseminacoes/lotes").json())
    assert any(e["animal_id"] == ctx["egua"] for e in c.get("/api/inseminacoes/eguas").json())


def test_registar_desconta_stock_e_cria_tarefas(ctx):
    c = ctx["c"]
    r = c.post("/api/inseminacoes", json=_corpo(ctx, 3, observacoes="  teste  "))
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["total_palhetas"] == 3 and d["num_lotes"] == 1
    assert d["data_ver_ovulacao"] == (date.today() + timedelta(days=1)).isoformat()
    assert d["data_1o_diagnostico"] == (date.today() + timedelta(days=14)).isoformat()
    assert _stock(ctx["lote"]) == 7
    tipos = {t for (t,) in _tarefas(ctx["egua"])}
    assert {"verificar_ovulacao", "diagnostico_gestacao"} <= tipos

    # Editar: passa para 5 palhetas (as 3 antigas voltam ao lote).
    op = _um("SELECT operation_id::text FROM inseminacoes WHERE animal_id_egua = %s", (ctx["egua"],))[0]
    atual = c.get(f"/api/inseminacoes/operacao/{op}").json()
    assert atual["linhas"] == [{"stock_id": ctx["lote"], "palhetas": 3, "max": 10}]
    assert c.put(f"/api/inseminacoes/operacao/{op}", json=_corpo(ctx, 5)).status_code == 200
    assert _stock(ctx["lote"]) == 5
    # Não pode pedir mais do que o lote tinha antes desta operação.
    r = c.put(f"/api/inseminacoes/operacao/{op}", json=_corpo(ctx, 11))
    assert r.json()["detail"]["code"] == "web.insem.error.not_enough"


def _tarefas(egua):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT tipo FROM trabalho_diario WHERE animal_id = %s", (egua,))
            return cur.fetchall()


def test_validacoes(ctx):
    c = ctx["c"]
    assert c.post("/api/inseminacoes", json=_corpo(ctx, 11)).json()["detail"]["code"] == "web.insem.error.not_enough"
    corpo = _corpo(ctx, 1)
    corpo["linhas"] *= 2
    assert c.post("/api/inseminacoes", json=corpo).json()["detail"]["code"] == "web.insem.error.duplicate_lot"
    assert c.post("/api/inseminacoes", json=_corpo(ctx, 1, linhas=[])).status_code == 422
    # Égua sem estadia aberta não pode ser inseminada.
    _um("UPDATE estadias SET data_saida = CURRENT_DATE, estado = 'alta' WHERE animal_id = %s", (ctx["egua"],))
    assert c.post("/api/inseminacoes", json=_corpo(ctx, 1)).json()["detail"]["code"] == "web.insem.error.mare_no_stay"
    assert _stock(ctx["lote"]) == 10
    assert c.get("/api/inseminacoes/operacao/nao-e-uuid").status_code == 404


def test_receptora_nao_e_inseminada(ctx):
    _um("UPDATE animais SET tipo = 'receptora' WHERE id = %s", (ctx["egua"],))
    assert not any(e["animal_id"] == ctx["egua"] for e in ctx["c"].get("/api/inseminacoes/eguas").json())
    r = ctx["c"].post("/api/inseminacoes", json=_corpo(ctx, 1))
    assert r.json()["detail"]["code"] == "web.insem.error.recipient"
