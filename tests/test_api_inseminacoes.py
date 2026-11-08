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
        "hora_inseminacao": "10:30",
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


def test_hora_obrigatoria_e_gravada(ctx):
    c = ctx["c"]
    corpo = _corpo(ctx, 1)
    sem_hora = {k: v for k, v in corpo.items() if k != "hora_inseminacao"}
    r = c.post("/api/inseminacoes", json=sem_hora)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "web.insem.error.time_required"
    r = c.post("/api/inseminacoes", json=corpo)
    assert r.status_code == 201, r.text
    assert r.json()["hora_inseminacao"] == "10:30"
    ref = _um("SELECT operation_id::text FROM inseminacoes WHERE animal_id_egua = %s ORDER BY id DESC LIMIT 1", (ctx["egua"],))[0]
    assert c.get(f"/api/inseminacoes/operacao/{ref}").json()["hora_inseminacao"] == "10:30"
    # Editar mantém (ou muda) a hora.
    r = c.put(f"/api/inseminacoes/operacao/{ref}", json={**corpo, "hora_inseminacao": "16:05"})
    assert r.status_code == 200, r.text
    assert c.get(f"/api/inseminacoes/operacao/{ref}").json()["hora_inseminacao"] == "16:05"


def test_mesmo_envio_nao_grava_duas_vezes(ctx):
    import uuid

    c = ctx["c"]
    antes = _stock(ctx["lote"])
    corpo = _corpo(ctx, 1, pedido_id=str(uuid.uuid4()))
    assert c.post("/api/inseminacoes", json=corpo).status_code == 201
    r = c.post("/api/inseminacoes", json=corpo)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "web.insem.error.duplicate_submit"
    # Só descontou uma vez.
    assert _stock(ctx["lote"]) == antes - 1


# ── Acompanhamento: o resultado é de cada inseminação, não da estadia ──────

def _inseminar(x, dias_atras):
    corpo = _corpo(x, 1, data_inseminacao=(date.today() - timedelta(days=dias_atras)).isoformat())
    assert x["c"].post("/api/inseminacoes", json=corpo).status_code == 201
    return _um(
        "SELECT operation_id::text FROM inseminacoes WHERE animal_id_egua = %s ORDER BY id DESC LIMIT 1", (x["egua"],)
    )[0]


def _resultado(x, op, resultado):
    return x["c"].post(f"/api/animais/{x['egua']}/resultado", json={"op_key": op, "resultado": resultado})


def _historial(x):
    return {r["op_key"]: r for r in x["c"].get(f"/api/animais/{x['egua']}/reprodutivo").json()["inseminacoes"]}


def test_reinseminar_depois_de_negativo_na_mesma_estadia(ctx):
    a = _inseminar(ctx, 20)
    assert _resultado(ctx, a, "negativo").json()["resultado"] == "falhou"
    b = _inseminar(ctx, 0)
    h = _historial(ctx)
    assert h[a]["resultado"] == "falhou" and h[a]["pode_resultado"] is False
    assert h[b]["resultado"] == "pendente" and h[b]["pode_resultado"] is True
    # Editar a inseminação antiga não lhe apaga o resultado.
    corpo = _corpo(ctx, 2, data_inseminacao=(date.today() - timedelta(days=20)).isoformat())
    assert ctx["c"].put(f"/api/inseminacoes/operacao/{a}", json=corpo).status_code == 200
    assert _historial(ctx)[a]["resultado"] == "falhou"


def test_dg_vale_para_as_inseminacoes_do_mesmo_cio(ctx):
    a = _inseminar(ctx, 15)
    b = _inseminar(ctx, 14)
    assert _resultado(ctx, b, "positivo").json()["resultado"] == "gestacao_confirmada"
    h = _historial(ctx)
    assert h[a]["resultado"] == h[b]["resultado"] == "gestacao_confirmada"
    # Fica gravado em cada uma, não só no acompanhamento da estadia.
    assert _um("SELECT resultado FROM inseminacoes WHERE operation_id = %s::uuid", (a,))[0] == "gestacao_confirmada"


def test_primeiro_dg_feito_tarde_e_d14_e_agenda_confirmacoes(ctx):
    a = _inseminar(ctx, 29)
    assert _resultado(ctx, a, "positivo").json()["resultado"] == "gestacao_confirmada"
    assert _um("SELECT etapa FROM diagnosticos_gestacao WHERE operation_id = %s::uuid", (a,))[0] == "D+14"
    abertas = {t for (t,) in _tarefas(ctx["egua"])}
    assert {"confirmacao_gestacao", "segunda_confirmacao"} <= abertas
    assert _um(
        "SELECT concluida FROM trabalho_diario WHERE animal_id = %s AND tipo = 'diagnostico_gestacao'", (ctx["egua"],)
    )[0] is True
    # A seguir é a confirmação D+28.
    assert _historial(ctx)[a]["etapa"] == "D+28"


def test_inconclusivo_nao_faz_a_etapa_e_d45_positivo_fecha(ctx):
    b = _inseminar(ctx, 30)
    assert _resultado(ctx, b, "positivo").json()["resultado"] == "gestacao_confirmada"  # D+14
    assert _resultado(ctx, b, "sem_exame").status_code == 200  # D+28 sem exame
    assert _historial(ctx)[b]["etapa"] == "D+28"  # continua por fazer
    # Sem exame marca outra confirmação daqui a 2 dias.
    assert _um(
        "SELECT data_tarefa FROM trabalho_diario WHERE animal_id = %s AND tipo = 'confirmacao_gestacao' AND NOT concluida",
        (ctx["egua"],),
    )[0] == date.today() + timedelta(days=2)
    assert _resultado(ctx, b, "positivo").status_code == 200  # D+28 feito
    assert _historial(ctx)[b]["etapa"] == "D+45"
    assert _resultado(ctx, b, "positivo").status_code == 200  # D+45 positivo
    assert _historial(ctx)[b]["pode_resultado"] is False
    assert _resultado(ctx, b, "negativo").json()["detail"]["code"] == "web.animal.error.result_not_allowed"


def test_nova_inseminacao_fecha_o_ciclo_anterior_e_dg_cedo_recusado(ctx):
    a = _inseminar(ctx, 20)
    b = _inseminar(ctx, 0)
    h = _historial(ctx)
    assert h[a]["resultado"] == "falhou" and h[a]["pode_resultado"] is False
    # As tarefas de DG que eram de "a" ficam canceladas; fica só o D+14 de "b".
    abertas = _um(
        "SELECT array_agg(data_tarefa ORDER BY data_tarefa) FROM trabalho_diario WHERE animal_id = %s AND NOT concluida AND tipo = 'diagnostico_gestacao'",
        (ctx["egua"],),
    )[0]
    assert abertas == [date.today() + timedelta(days=14)]
    assert _resultado(ctx, b, "positivo").json()["detail"]["code"] == "web.registo.error.dg_too_early"


def test_inseminacao_fecha_a_tarefa_inseminar(ctx):
    eid = _um("SELECT id FROM estadias WHERE animal_id = %s", (ctx["egua"],))[0]
    _um(
        """INSERT INTO trabalho_diario (animal_id, estadia_id, data_tarefa, tipo, motivo)
           VALUES (%s, %s, CURRENT_DATE, 'inseminar', 'Inseminar — indução') RETURNING id""",
        (ctx["egua"], eid),
    )
    _inseminar(ctx, 0)
    assert _um("SELECT concluida, cancelada FROM trabalho_diario WHERE animal_id = %s AND tipo = 'inseminar'", (ctx["egua"],)) == (True, False)


def test_inseminar_egua_gestante_pede_confirmacao(ctx):
    a = _inseminar(ctx, 20)
    assert _resultado(ctx, a, "positivo").json()["resultado"] == "gestacao_confirmada"
    corpo = _corpo(ctx, 1)
    r = ctx["c"].post("/api/inseminacoes", json=corpo)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "web.insem.error.mare_pregnant"
    assert r.json()["detail"]["params"]["data"] == (date.today() - timedelta(days=20)).strftime("%d/%m/%Y")
    assert ctx["c"].post("/api/inseminacoes", json={**corpo, "confirmar_gestante": True}).status_code == 201
    assert _historial(ctx)[a]["resultado"] == "falhou"


def test_stock_nunca_negativo_com_pedidos_ao_mesmo_tempo(ctx):
    from concurrent.futures import ThreadPoolExecutor

    _um("UPDATE estoque_dono SET existencia_atual = 1 WHERE id = %s", (ctx["lote"],))
    with ThreadPoolExecutor(8) as ex:
        estados = list(ex.map(lambda _: ctx["c"].post("/api/inseminacoes", json=_corpo(ctx, 1)).status_code, range(8)))
    assert estados.count(201) == 1, estados
    assert _stock(ctx["lote"]) == 0
