"""API nova (FastAPI): registo clínico das éguas (desenho OE/OD/UT/CER,
DG, TX) — contra a base de TESTE. Apaga tudo o que cria."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from modules.db import get_connection
from modules.services.auth_service import criar_hash_password

P = "__api_test__"


def _exec(sql, params=()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone() if cur.description else None
        conn.commit()
    return row


def _todas(sql, params=()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


@pytest.fixture
def ctx():
    username = f"{P}{uuid.uuid4().hex[:8]}"
    _exec(
        """INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo, must_change_password)
           VALUES (%s, 'Teste API', %s, 'Gestor', TRUE, FALSE)""",
        (username, criar_hash_password("segredo123")),
    )
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"username": username, "password": "segredo123"}).status_code == 200
    dono = _exec("INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id", (f"{P}d{uuid.uuid4().hex[:6]}",))[0]

    def animal(tipo="egua", estadia=True, tarefa="observacao_clinica"):
        aid = _exec("INSERT INTO animais (nome, tipo, dono_id, ativo) VALUES (%s, %s, %s, TRUE) RETURNING id", (f"{P}{uuid.uuid4().hex[:6]}", tipo, dono))[0]
        if estadia:
            eid = _exec(
                """INSERT INTO estadias (tipo_registo, animal_id, dono_id, data_entrada, motivo, estado, garanhao)
                   VALUES ('visita', %s, %s, CURRENT_DATE, 'inseminacao', 'visitante', 'Zeus') RETURNING id""",
                (aid, dono),
            )[0]
            _exec(
                """INSERT INTO trabalho_diario (animal_id, estadia_id, data_tarefa, tipo, motivo, urgencia)
                   VALUES (%s, %s, CURRENT_DATE, %s, 'teste', 'hoje')""",
                (aid, eid, tarefa),
            )
        return aid

    yield {"c": c, "animal": animal}
    sub = "SELECT id FROM animais WHERE nome LIKE %s"
    for sql in (
        f"DELETE FROM diagnosticos_gestacao WHERE animal_id IN ({sub})",
        f"DELETE FROM inseminacoes WHERE animal_id_egua IN ({sub})",
        f"DELETE FROM acompanhamento_inseminacao WHERE animal_id IN ({sub})",
        f"DELETE FROM registo_clinico WHERE animal_id IN ({sub})",
        f"DELETE FROM trabalho_diario WHERE animal_id IN ({sub})",
        f"DELETE FROM estadias WHERE animal_id IN ({sub})",
    ):
        _exec(sql, (f"{P}%",))
    _exec("DELETE FROM opcoes_clinicas WHERE valor LIKE %s", (f"{P}%",))
    _exec("DELETE FROM animais WHERE nome LIKE %s", (f"{P}%",))
    _exec("DELETE FROM dono WHERE id = %s", (dono,))
    _exec("DELETE FROM user_sessions WHERE username = %s", (username,))
    _exec("DELETE FROM usuarios WHERE username = %s", (username,))


def _registo(**dados):
    return {"data_registo": datetime.now().isoformat(timespec="minutes"), "dados": dados, "prioritario": False}


def test_registar_e_historico(ctx):
    c, aid = ctx["c"], ctx["animal"]()
    lista = c.get(f"/api/animais/{aid}/registos").json()
    assert lista["historico"] == [] and lista["pede"] == {"ovulacao": False, "dg": False}
    assert lista["garanhao"] == "Zeus" and lista["estadia_ativa"] is True

    r = c.post(
        f"/api/animais/{aid}/registos",
        json=_registo(
            OE={"foliculos": [{"tamanho": 35, "achados": ["OV"]}, {"tamanho": 20}], "comentario": " ok "},
            UT={"edema": 2, "liquido": 1},
            CER={"grau": 2},
        ),
    )
    assert r.status_code == 201, r.text
    # Concluiu a tarefa de hoje, como o registo antigo.
    assert r.json()["tarefas_concluidas"] == 1

    lista = c.get(f"/api/animais/{aid}/registos").json()
    h = lista["historico"][0]
    assert h["dados"]["OE"]["foliculos"][0] == {"tamanho": 35, "achados": ["OV"]}
    assert h["dados"]["OE"]["comentario"] == "ok"

    # Corrigir e apagar.
    rid = h["id"]
    assert c.put(f"/api/animais/{aid}/registos/{rid}", json=_registo(CER={"grau": 3})).status_code == 200
    assert c.get(f"/api/animais/{aid}/registos").json()["historico"][0]["dados"] == {"CER": {"grau": 3}}
    assert c.delete(f"/api/animais/{aid}/registos/{rid}").status_code == 200
    assert c.get(f"/api/animais/{aid}/registos").json()["historico"] == []


def test_tratamento_marca_tarefas_e_guarda_opcoes(ctx):
    c, aid = ctx["c"], ctx["animal"]()
    outro = f"{P}Amicacina"
    inducao = (datetime.now() + timedelta(days=2)).replace(hour=20, minute=0, second=0, microsecond=0)
    r = c.post(
        f"/api/animais/{aid}/registos",
        json=_registo(
            TX={
                "ocitocina": {"vezes": 2, "hora": "8h"},
                "infusao": {"ab": ["Genta"], "abOutro": outro},
                "inducao": {"data": inducao.isoformat()},
                "marcar": {"dias": "2"},
            }
        ),
    )
    assert r.json()["tarefas_criadas"] == 3  # 2 dias de tratamento + inseminar (da indução)
    tarefas = _todas("SELECT data_tarefa, motivo FROM trabalho_diario WHERE animal_id = %s AND tipo = 'tratamento' ORDER BY id", (aid,))
    hoje = date.today()
    assert [t[0] for t in tarefas] == [hoje + timedelta(days=1), hoje + timedelta(days=2)]
    assert "Ocitocina 2× 8h" in tarefas[0][1] and "Genta" in tarefas[0][1]
    # A indução deixa a tarefa "inseminar" para o dia seguinte (passagem de turno).
    ins = _todas("SELECT data_tarefa, motivo FROM trabalho_diario WHERE animal_id = %s AND tipo = 'inseminar'", (aid,))
    assert ins == [(inducao.date() + timedelta(days=1), f"Inseminar — indução a {inducao:%d/%m} 20:00")]
    lista = c.get(f"/api/animais/{aid}/registos").json()
    assert outro in lista["antibioticos"]
    assert lista["tratamentos_anteriores"][0]["texto"].startswith("Ocitocina 2× 8h")


def test_registo_nao_fecha_tarefa_inseminar(ctx):
    # A égua tem hoje "Inseminar": um exame qualquer não a dá por inseminada.
    c, aid = ctx["c"], ctx["animal"](tarefa="inseminar")
    r = c.post(f"/api/animais/{aid}/registos", json=_registo(CER={"grau": 2}))
    assert r.status_code == 201, r.text
    assert r.json()["tarefas_concluidas"] == 0
    assert _todas("SELECT concluida FROM trabalho_diario WHERE animal_id = %s AND tipo = 'inseminar'", (aid,)) == [(False,)]


def test_prioritario_passa_proxima_tarefa_a_urgente(ctx):
    c, aid = ctx["c"], ctx["animal"]()
    corpo = _registo(TX={"lavagem": 1, "marcar": {"dias": "1"}})
    corpo["prioritario"] = True
    c.post(f"/api/animais/{aid}/registos", json=corpo)
    assert _todas("SELECT urgencia FROM trabalho_diario WHERE animal_id = %s AND concluida = FALSE", (aid,)) == [("urgente",)]


def test_validacoes(ctx):
    c = ctx["c"]
    aid = ctx["animal"]()
    assert c.post(f"/api/animais/{aid}/registos", json=_registo()).json()["detail"]["code"] == "web.registo.error.empty"
    r = c.post(f"/api/animais/{aid}/registos", json=_registo(TX={"pg": 1, "marcar": {"dias": "agenda"}}))
    assert r.json()["detail"]["code"] == "web.registo.error.agenda_date"
    assert c.post(f"/api/animais/{aid}/registos", json=_registo(OE={"foliculos": [{"tamanho": 80}]})).status_code == 422
    sem = ctx["animal"](estadia=False)
    assert c.post(f"/api/animais/{sem}/registos", json=_registo(CER={"grau": 1})).json()["detail"]["code"] == "web.animal.error.no_active_stay"
    gar = ctx["animal"](tipo="garanhao")
    assert c.get(f"/api/animais/{gar}/registos").json()["detail"]["code"] == "web.animal.error.no_diary_stallion"


def test_dg_sem_inseminacao_fica_so_registado(ctx):
    c, aid = ctx["c"], ctx["animal"]()
    assert c.post(f"/api/animais/{aid}/registos", json=_registo(DG="Positivo")).json()["resultado"] == "sem_inseminacao"


def _inseminada_ha(aid, dias):
    """Inseminação (uma operação) feita há `dias` dias."""
    op = str(uuid.uuid4())
    eid = _exec("SELECT id FROM estadias WHERE animal_id = %s", (aid,))[0]
    _exec(
        """INSERT INTO inseminacoes (garanhao, data_inseminacao, egua, palhetas_gastas, operation_id, animal_id_egua, estadia_id, resultado)
           VALUES ('Zeus', %s, 'x', 1, %s::uuid, %s, %s, 'pendente')""",
        (date.today() - timedelta(days=dias), op, aid, eid),
    )
    return op


def test_ovulacao_obrigatoria_com_tarefa_d1(ctx):
    c, aid = ctx["c"], ctx["animal"](tarefa="verificar_ovulacao")
    assert c.get(f"/api/animais/{aid}/registos").json()["pede"] == {"ovulacao": True, "dg": False}
    r = c.post(f"/api/animais/{aid}/registos", json=_registo(CER={"grau": 1}))
    assert r.json()["detail"]["code"] == "web.registo.error.ovulation_required"
    r = c.post(f"/api/animais/{aid}/registos", json=_registo(OVU={"ovulacao": "nao_avaliado", "fh": "nao"}))
    assert r.status_code == 201 and r.json()["tarefas_concluidas"] == 1
    assert c.get(f"/api/animais/{aid}/registos").json()["historico"][0]["dados"]["OVU"] == {"ovulacao": "nao_avaliado", "fh": "nao"}
    assert c.post(f"/api/animais/{aid}/registos", json=_registo(OVU={"ovulacao": "talvez", "fh": "nao"})).status_code == 422


def test_dg_obrigatorio_com_tarefa_e_guardado_por_etapa(ctx):
    c, aid = ctx["c"], ctx["animal"](tarefa="diagnostico_gestacao")
    op = _inseminada_ha(aid, 14)
    r = c.post(f"/api/animais/{aid}/registos", json=_registo(CER={"grau": 2}))
    assert r.json()["detail"]["code"] == "web.registo.error.dg_required"
    exame = datetime.now().replace(second=0, microsecond=0)
    corpo = _registo(DG="Positivo")
    corpo["data_registo"] = exame.isoformat()
    assert c.post(f"/api/animais/{aid}/registos", json=corpo).json()["resultado"] == "registado"
    diag = _todas("SELECT operation_id::text, etapa, resultado, data_exame FROM diagnosticos_gestacao WHERE animal_id = %s", (aid,))
    assert diag == [(op, "D+14", "positivo", exame)]
    assert _exec("SELECT resultado FROM inseminacoes WHERE operation_id = %s::uuid", (op,))[0] == "gestacao_confirmada"


def test_d45_depois_de_positivo_e_sem_exame(ctx):
    c, aid = ctx["c"], ctx["animal"]()
    op = _inseminada_ha(aid, 45)
    _exec("UPDATE inseminacoes SET resultado = 'gestacao_confirmada' WHERE operation_id = %s::uuid", (op,))
    # Perda embrionária: negativo no D+45 depois de positivo no D+14.
    assert c.post(f"/api/animais/{aid}/registos", json=_registo(DG="Sem exame")).json()["resultado"] == "registado"
    assert c.post(f"/api/animais/{aid}/registos", json=_registo(DG="Negativo")).json()["resultado"] == "registado"
    diag = _todas("SELECT etapa, resultado FROM diagnosticos_gestacao WHERE animal_id = %s ORDER BY id", (aid,))
    assert diag == [("D+45", "sem_exame"), ("D+45", "negativo")]
    assert _exec("SELECT resultado FROM inseminacoes WHERE operation_id = %s::uuid", (op,))[0] == "falhou"


def test_dg_nao_reescreve_inseminacao_fechada(ctx):
    c, aid = ctx["c"], ctx["animal"]()
    op = _inseminada_ha(aid, 30)
    eid = _exec("SELECT id FROM estadias WHERE animal_id = %s", (aid,))[0]
    _exec("UPDATE inseminacoes SET resultado = 'falhou' WHERE operation_id = %s::uuid", (op,))
    _exec("INSERT INTO acompanhamento_inseminacao (estadia_id, animal_id, resultado) VALUES (%s, %s, 'falhou')", (eid, aid))
    assert c.post(f"/api/animais/{aid}/registos", json=_registo(DG="Positivo")).json()["resultado"] == "sem_inseminacao"
    assert _exec("SELECT resultado FROM inseminacoes WHERE operation_id = %s::uuid", (op,))[0] == "falhou"
    assert _todas("SELECT id FROM diagnosticos_gestacao WHERE animal_id = %s", (aid,)) == []


def test_resultado_na_ficha_com_data_do_exame(ctx):
    c, aid = ctx["c"], ctx["animal"]()
    op = _inseminada_ha(aid, 30)
    dia = date.today() - timedelta(days=2)  # 1.º diagnóstico, feito tarde: continua a ser D+14
    r = c.post(f"/api/animais/{aid}/resultado", json={"op_key": op, "resultado": "inconclusivo", "data_exame": dia.isoformat()})
    assert r.status_code == 200, r.text
    r = c.post(f"/api/animais/{aid}/resultado", json={"op_key": op, "resultado": "positivo", "data_exame": dia.isoformat()})
    assert r.json()["resultado"] == "gestacao_confirmada"
    diag = _todas("SELECT etapa, resultado, data_exame::date FROM diagnosticos_gestacao WHERE animal_id = %s ORDER BY id", (aid,))
    assert diag == [("D+14", "inconclusivo", dia), ("D+14", "positivo", dia)]
    # Depois de positivo ainda se pode registar (confirmações seguintes).
    assert c.get(f"/api/animais/{aid}/reprodutivo").json()["inseminacoes"][0]["pode_resultado"] is True
    futuro = (date.today() + timedelta(days=1)).isoformat()
    r = c.post(f"/api/animais/{aid}/resultado", json={"op_key": op, "resultado": "positivo", "data_exame": futuro})
    assert r.json()["detail"]["code"] == "web.animal.error.result_bad_date"


def test_registo_fecha_observacoes_em_atraso_mas_nao_tratamentos(ctx):
    c, aid = ctx["c"], ctx["animal"]()
    eid = _exec("SELECT id FROM estadias WHERE animal_id = %s", (aid,))[0]
    for tipo in ("observacao_clinica", "tratamento", "verificar_ovulacao"):
        _exec(
            """INSERT INTO trabalho_diario (animal_id, estadia_id, data_tarefa, tipo, motivo)
               VALUES (%s, %s, CURRENT_DATE - 3, %s, 'atraso')""",
            (aid, eid, tipo),
        )
    # D+1 em atraso: a ovulação também é pedida.
    assert c.get(f"/api/animais/{aid}/registos").json()["pede"]["ovulacao"] is True
    r = c.post(f"/api/animais/{aid}/registos", json=_registo(OVU={"ovulacao": "sim", "fh": "nao"}))
    assert r.status_code == 201, r.text
    abertas = _todas("SELECT tipo FROM trabalho_diario WHERE animal_id = %s AND concluida = FALSE", (aid,))
    assert abertas == [("tratamento",)]


def test_exame_ao_dia_16_depois_de_positivo_nao_e_d28(ctx):
    c, aid = ctx["c"], ctx["animal"]()
    op = _inseminada_ha(aid, 16)
    _exec("UPDATE inseminacoes SET resultado = 'gestacao_confirmada' WHERE operation_id = %s::uuid", (op,))
    assert c.post(f"/api/animais/{aid}/registos", json=_registo(DG="Positivo")).json()["resultado"] == "registado"
    assert _todas("SELECT etapa FROM diagnosticos_gestacao WHERE animal_id = %s", (aid,)) == [("D+14",)]
    # O ecrã continua a mostrar o D+28 como próxima etapa.
    assert c.get(f"/api/animais/{aid}/reprodutivo").json()["inseminacoes"][0]["etapa"] == "D+28"


def test_inconclusivo_repete_no_maximo_3_vezes(ctx):
    c, aid = ctx["c"], ctx["animal"]()
    _inseminada_ha(aid, 22)
    # Exames inconclusivos nos dias 14, 16, 18, 20 e 22 (cada um no dia da repetição marcada).
    for atras in (8, 6, 4, 2, 0):
        corpo = _registo(DG="Inconclusivo")
        corpo["data_registo"] = (datetime.now() - timedelta(days=atras)).isoformat(timespec="minutes")
        assert c.post(f"/api/animais/{aid}/registos", json=corpo).status_code == 201
    repetir = _todas("SELECT concluida FROM trabalho_diario WHERE animal_id = %s AND motivo LIKE 'Repetir DG%%'", (aid,))
    assert repetir == [(True,)] * 3
    assert _todas("SELECT id FROM trabalho_diario WHERE animal_id = %s AND concluida = FALSE", (aid,)) == []


def test_dg_cedo_demais_nao_grava_o_registo(ctx):
    c, aid = ctx["c"], ctx["animal"]()
    _inseminada_ha(aid, 5)
    r = c.post(f"/api/animais/{aid}/registos", json=_registo(DG="Positivo"))
    assert r.json()["detail"]["code"] == "web.registo.error.dg_too_early"
    assert _todas("SELECT id FROM registo_clinico WHERE animal_id = %s", (aid,)) == []


def test_apagar_registo_deixa_rasto(ctx):
    c, aid = ctx["c"], ctx["animal"]()
    rid = c.post(f"/api/animais/{aid}/registos", json=_registo(CER={"grau": 2})).json()["id"]
    assert c.delete(f"/api/animais/{aid}/registos/{rid}").status_code == 200
    rasto = _todas("SELECT dados_antigos->'dados', dados_novos FROM historico_edicoes WHERE tabela_nome = 'registo_clinico' AND record_id = %s", (rid,))
    assert rasto == [({"CER": {"grau": 2}}, {"acao": "apagado"})]
    _exec("DELETE FROM historico_edicoes WHERE tabela_nome = 'registo_clinico' AND record_id = %s", (rid,))


def test_registo_com_dg_nao_muda_o_dg_nem_apaga_resultado(ctx):
    c, aid = ctx["c"], ctx["animal"]()
    op = _inseminada_ha(aid, 14)
    corpo = _registo(DG="Positivo", CER={"grau": 1})
    rid = c.post(f"/api/animais/{aid}/registos", json=corpo).json()["id"]
    # Corrigir o resto do registo pode; mudar o DG não.
    assert c.put(f"/api/animais/{aid}/registos/{rid}", json={**corpo, "dados": {"DG": "Positivo", "CER": {"grau": 2}}}).status_code == 200
    r = c.put(f"/api/animais/{aid}/registos/{rid}", json={**corpo, "dados": {"DG": "Negativo"}})
    assert r.json()["detail"]["code"] == "web.registo.error.dg_locked"
    r = c.delete(f"/api/animais/{aid}/registos/{rid}")
    assert r.json()["detail"]["code"] == "web.registo.error.dg_locked_delete"
    assert _exec("SELECT resultado FROM inseminacoes WHERE operation_id = %s::uuid", (op,))[0] == "gestacao_confirmada"


def test_apagar_registo_com_dg_inconclusivo_leva_o_dg(ctx):
    c, aid = ctx["c"], ctx["animal"]()
    _inseminada_ha(aid, 14)
    rid = c.post(f"/api/animais/{aid}/registos", json=_registo(DG="Inconclusivo")).json()["id"]
    assert c.delete(f"/api/animais/{aid}/registos/{rid}").status_code == 200
    assert _todas("SELECT id FROM diagnosticos_gestacao WHERE animal_id = %s", (aid,)) == []


def test_pg_em_egua_gestante_ou_inseminada_pede_confirmacao(ctx):
    c, aid = ctx["c"], ctx["animal"]()
    op = _inseminada_ha(aid, 5)
    r = c.post(f"/api/animais/{aid}/registos", json=_registo(TX={"pg": 1}))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "web.registo.confirm_pg_inseminated"
    _exec("UPDATE inseminacoes SET resultado = 'gestacao_confirmada' WHERE operation_id = %s::uuid", (op,))
    r = c.post(f"/api/animais/{aid}/registos", json=_registo(TX={"pg": 1}))
    assert r.json()["detail"]["code"] == "web.registo.confirm_pg_pregnant"
    assert _todas("SELECT id FROM registo_clinico WHERE animal_id = %s", (aid,)) == []
    # Confirmado no ecrã: grava.
    assert c.post(f"/api/animais/{aid}/registos", json={**_registo(TX={"pg": 1}), "confirmar_pg": True}).status_code == 201


def test_pg_sem_inseminacao_nao_pergunta(ctx):
    c, aid = ctx["c"], ctx["animal"]()
    assert c.post(f"/api/animais/{aid}/registos", json=_registo(TX={"pg": 1})).status_code == 201


def test_dg_repetido_no_mesmo_dia_avisa(ctx):
    c, aid = ctx["c"], ctx["animal"]()
    _inseminada_ha(aid, 14)
    assert c.post(f"/api/animais/{aid}/registos", json=_registo(DG="Inconclusivo")).json()["dg_mesmo_dia"] is False
    assert c.post(f"/api/animais/{aid}/registos", json=_registo(DG="Positivo")).json()["dg_mesmo_dia"] is True
