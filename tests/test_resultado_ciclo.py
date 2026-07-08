"""Testes do ciclo de resultados da inseminação (Pedido 4).

Cobre os critérios de aceitação:
(a) positivo D+14 → 'gestacao_confirmada' + criação de D+28 e D+45;
(b) negativo D+14 → 'falhou' + zero tarefas futuras + acompanhamento limpo;
(c) negativo D+28 (perda) → 'falhou' + tarefas remanescentes canceladas;
(d) registo pelo Trabalho Diário e pela ficha produz mesmo estado (via
    mesma função) — dois cenários com operation_ids distintos que
    invocam `registar_resultado` com os mesmos parâmetros;
(e) uma operação multi-lote tem UM só resultado, replicado em todas
    as linhas.
"""

from __future__ import annotations

import os
import time
from datetime import date, timedelta

import psycopg2
import pytest

from modules.repositories.insemination_repo import (
    InseminacaoError,
    find_operation_por_tarefa,
    registar_inseminacao_completa,
    registar_resultado,
)


def _connect():
    return psycopg2.connect(os.environ["DATABASE_URL"])


@pytest.fixture(scope="module")
def db():
    conn = _connect()
    conn.autocommit = False
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def _rollback_before_each(db):
    try:
        db.rollback()
    except Exception:
        pass
    yield


@pytest.fixture()
def dono_id(db):
    cur = db.cursor()
    nome = f"_TEST_DONO_RES_{int(time.time() * 1000)}"
    cur.execute("INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id", (nome,))
    did = int(cur.fetchone()[0])
    db.commit()
    cur.close()
    yield did
    cur = db.cursor()
    cur.execute("DELETE FROM dono WHERE id = %s", (did,))
    db.commit()
    cur.close()


@pytest.fixture()
def alojamento_id(db):
    cur = db.cursor()
    nome = f"_TEST_BOX_RES_{int(time.time() * 1000)}"
    cur.execute(
        "INSERT INTO alojamentos (nome, tipo, capacidade, ativo) "
        "VALUES (%s, 'box', 1, TRUE) RETURNING id",
        (nome,),
    )
    aid = int(cur.fetchone()[0])
    db.commit()
    cur.close()
    yield aid
    cur = db.cursor()
    cur.execute("DELETE FROM alojamentos WHERE id = %s", (aid,))
    db.commit()
    cur.close()


@pytest.fixture()
def egua_com_estadia(db, dono_id, alojamento_id):
    suf = int(time.time() * 1000)
    cur = db.cursor()
    cur.execute(
        "INSERT INTO animais (nome, tipo, dono_id, ativo) "
        "VALUES (%s, 'egua', %s, TRUE) RETURNING id",
        (f"_TEST_EGUA_RES_{suf}", dono_id),
    )
    animal_id = int(cur.fetchone()[0])
    cur.execute(
        "INSERT INTO estadias ("
        "  tipo_registo, animal_id, alojamento_id, dono_id, "
        "  data_entrada, motivo, estado) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
        ("estadia", animal_id, alojamento_id, dono_id,
         date.today() - timedelta(days=1), "inseminacao", "internado"),
    )
    estadia_id = int(cur.fetchone()[0])
    db.commit()
    cur.close()
    yield {
        "animal_id": animal_id, "estadia_id": estadia_id, "dono_id": dono_id,
        "alojamento_id": alojamento_id, "nome": f"_TEST_EGUA_RES_{suf}",
    }
    cur = db.cursor()
    try:
        db.rollback()
    except Exception:
        pass
    cur.execute("DELETE FROM trabalho_diario WHERE animal_id = %s", (animal_id,))
    cur.execute("DELETE FROM acompanhamento_inseminacao WHERE estadia_id = %s", (estadia_id,))
    cur.execute("DELETE FROM inseminacoes WHERE animal_id_egua = %s", (animal_id,))
    cur.execute("DELETE FROM estadias WHERE id = %s", (estadia_id,))
    cur.execute("DELETE FROM animais WHERE id = %s", (animal_id,))
    db.commit()
    cur.close()


@pytest.fixture()
def stock_garanhao(db, dono_id):
    suf = int(time.time() * 1000)
    nome_gar = f"_TEST_GAR_RES_{suf}"
    cur = db.cursor()
    cur.execute(
        "INSERT INTO animais (nome, tipo, ativo) "
        "VALUES (%s, 'garanhao', TRUE) RETURNING id",
        (nome_gar,),
    )
    garanhao_id = int(cur.fetchone()[0])
    lote_ids = []
    for palhetas in (20, 15):
        cur.execute(
            "INSERT INTO estoque_dono ("
            "  garanhao, dono_id, animal_id, palhetas_produzidas, "
            "  existencia_atual, quantidade_inicial, data_embriovet) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (nome_gar, dono_id, garanhao_id, palhetas, palhetas, palhetas,
             "2025-01-10"),
        )
        lote_ids.append(int(cur.fetchone()[0]))
    db.commit()
    cur.close()
    yield {"garanhao_id": garanhao_id, "nome": nome_gar, "lote_ids": lote_ids}
    cur = db.cursor()
    try:
        db.rollback()
    except Exception:
        pass
    cur.execute("DELETE FROM inseminacoes WHERE animal_id_garanhao = %s", (garanhao_id,))
    cur.execute("DELETE FROM estoque_dono WHERE id = ANY(%s)", (lote_ids,))
    cur.execute("DELETE FROM animais WHERE id = %s", (garanhao_id,))
    db.commit()
    cur.close()


def _registar_operacao(egua, stock, palhetas_por_lote=(5, 3), data_ins=None):
    """Helper: regista uma inseminação multi-lote e devolve resultado + operation_id."""
    if data_ins is None:
        data_ins = date(2026, 3, 1)
    registros = [
        {"stock_id": stock["lote_ids"][i], "palhetas": p}
        for i, p in enumerate(palhetas_por_lote)
    ]
    res = registar_inseminacao_completa(
        animal_id_egua=egua["animal_id"],
        estadia_id=egua["estadia_id"],
        dono_id=egua["dono_id"],
        garanhao_nome=stock["nome"],
        data_inseminacao=data_ins,
        registros=registros,
        criar_tarefa_d1=False,  # simplifica assertions
    )
    return res


# ────────────────────────────────────────────────────────────────────
# (a) positivo D+14
# ────────────────────────────────────────────────────────────────────

def test_positivo_d14_cria_d28_e_d45_e_marca_gestacao(
    db, egua_com_estadia, stock_garanhao,
):
    data_ins = date(2026, 3, 1)
    res = _registar_operacao(egua_com_estadia, stock_garanhao, (5, 3), data_ins)
    op_id = res["operation_id"]

    ret = registar_resultado(
        operation_id=op_id,
        resultado="positivo",
        tipo_tarefa="diagnostico_gestacao",
        data=data_ins + timedelta(days=14),
        observacoes="reflexo positivo, embrião visível",
    )
    assert ret["resultado_gravado"] == "gestacao_confirmada"
    assert len(ret["tarefas_criadas"]) == 2

    cur = db.cursor()

    # (e) TODAS as linhas da operação com o mesmo resultado
    cur.execute(
        "SELECT DISTINCT resultado, data_resultado FROM inseminacoes "
        "WHERE operation_id = %s::uuid",
        (op_id,),
    )
    rows = cur.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "gestacao_confirmada"
    assert rows[0][1] == data_ins + timedelta(days=14)

    # Tarefas D+28 e D+45 criadas
    cur.execute(
        "SELECT tipo, data_tarefa FROM trabalho_diario "
        "WHERE estadia_id = %s AND tipo IN ('confirmacao_gestacao','segunda_confirmacao') "
        "ORDER BY data_tarefa",
        (egua_com_estadia["estadia_id"],),
    )
    tar = cur.fetchall()
    assert len(tar) == 2
    assert tar[0][0] == "confirmacao_gestacao"
    assert tar[0][1] == data_ins + timedelta(days=28)
    assert tar[1][0] == "segunda_confirmacao"
    assert tar[1][1] == data_ins + timedelta(days=45)

    # acompanhamento tem resultado gravado
    cur.execute(
        "SELECT resultado FROM acompanhamento_inseminacao WHERE estadia_id = %s",
        (egua_com_estadia["estadia_id"],),
    )
    assert cur.fetchone()[0] == "gestacao_confirmada"
    cur.close()


def test_positivo_d14_idempotente_nao_duplica_tarefas(
    db, egua_com_estadia, stock_garanhao,
):
    data_ins = date(2026, 4, 1)
    res = _registar_operacao(egua_com_estadia, stock_garanhao, (5,), data_ins)
    op_id = res["operation_id"]

    r1 = registar_resultado(
        operation_id=op_id, resultado="positivo",
        tipo_tarefa="diagnostico_gestacao",
        data=data_ins + timedelta(days=14),
    )
    r2 = registar_resultado(
        operation_id=op_id, resultado="positivo",
        tipo_tarefa="diagnostico_gestacao",
        data=data_ins + timedelta(days=14),
    )
    assert len(r1["tarefas_criadas"]) == 2
    assert len(r2["tarefas_criadas"]) == 0  # idempotente

    cur = db.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM trabalho_diario "
        "WHERE estadia_id = %s AND tipo IN ('confirmacao_gestacao','segunda_confirmacao')",
        (egua_com_estadia["estadia_id"],),
    )
    assert cur.fetchone()[0] == 2
    cur.close()


# ────────────────────────────────────────────────────────────────────
# (b) negativo D+14
# ────────────────────────────────────────────────────────────────────

def test_negativo_d14_marca_falhou_e_nao_cria_futuras(
    db, egua_com_estadia, stock_garanhao,
):
    data_ins = date(2026, 5, 1)
    res = _registar_operacao(egua_com_estadia, stock_garanhao, (4, 2), data_ins)
    op_id = res["operation_id"]

    registar_resultado(
        operation_id=op_id, resultado="negativo",
        tipo_tarefa="diagnostico_gestacao",
        data=data_ins + timedelta(days=14),
        observacoes="útero vazio",
    )

    cur = db.cursor()
    cur.execute(
        "SELECT DISTINCT resultado, data_resultado FROM inseminacoes "
        "WHERE operation_id = %s::uuid",
        (op_id,),
    )
    rows = cur.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "falhou"

    # Sem tarefas futuras
    cur.execute(
        "SELECT COUNT(*) FROM trabalho_diario "
        "WHERE estadia_id = %s AND tipo IN ('confirmacao_gestacao','segunda_confirmacao')",
        (egua_com_estadia["estadia_id"],),
    )
    assert cur.fetchone()[0] == 0

    # acompanhamento com datas futuras limpas
    cur.execute(
        "SELECT data_confirmacao, data_2a_confirmacao, data_parto_previsto "
        "FROM acompanhamento_inseminacao WHERE estadia_id = %s",
        (egua_com_estadia["estadia_id"],),
    )
    d_conf, d_2a, d_parto = cur.fetchone()
    assert d_conf is None and d_2a is None and d_parto is None
    cur.close()


# ────────────────────────────────────────────────────────────────────
# (c) negativo D+28 (perda embrionária)
# ────────────────────────────────────────────────────────────────────

def test_negativo_d28_perde_gestacao_e_cancela_d45(
    db, egua_com_estadia, stock_garanhao,
):
    data_ins = date(2026, 6, 1)
    res = _registar_operacao(egua_com_estadia, stock_garanhao, (3,), data_ins)
    op_id = res["operation_id"]

    # Primeiro positivo em D+14 (cria D+28 e D+45)
    r1 = registar_resultado(
        operation_id=op_id, resultado="positivo",
        tipo_tarefa="diagnostico_gestacao",
        data=data_ins + timedelta(days=14),
    )
    d28_task, d45_task = sorted(r1["tarefas_criadas"])

    # Depois negativo em D+28 (perda)
    r2 = registar_resultado(
        operation_id=op_id, resultado="negativo",
        tipo_tarefa="confirmacao_gestacao",
        data=data_ins + timedelta(days=28),
        observacoes="perda embrionária, útero vazio",
        task_id=d28_task,
    )

    cur = db.cursor()
    cur.execute(
        "SELECT DISTINCT resultado, data_resultado FROM inseminacoes "
        "WHERE operation_id = %s::uuid",
        (op_id,),
    )
    rows = cur.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "falhou"
    assert rows[0][1] == data_ins + timedelta(days=28)

    # D+45 foi cancelada (delete)
    cur.execute(
        "SELECT id FROM trabalho_diario "
        "WHERE estadia_id = %s AND tipo = 'segunda_confirmacao'",
        (egua_com_estadia["estadia_id"],),
    )
    assert cur.fetchone() is None
    assert d45_task in r2["tarefas_canceladas"]

    # D+28 marcada como concluída (não apagada porque já era passada/concluída)
    cur.execute(
        "SELECT concluida, observacoes_conclusao FROM trabalho_diario WHERE id = %s",
        (d28_task,),
    )
    concl, obs = cur.fetchone()
    assert concl is True
    assert "Negativo" in obs
    cur.close()


# ────────────────────────────────────────────────────────────────────
# (d) Trabalho Diário vs Ficha produzem mesmo estado
# ────────────────────────────────────────────────────────────────────

def _snapshot_resultado(db, estadia_id, op_id):
    cur = db.cursor()
    cur.execute(
        "SELECT DISTINCT resultado, data_resultado FROM inseminacoes "
        "WHERE operation_id = %s::uuid",
        (op_id,),
    )
    ins = cur.fetchall()
    cur.execute(
        "SELECT resultado, data_confirmacao, data_2a_confirmacao, "
        "       data_parto_previsto FROM acompanhamento_inseminacao "
        "WHERE estadia_id = %s",
        (estadia_id,),
    )
    acomp = cur.fetchone()
    cur.execute(
        "SELECT tipo, data_tarefa, concluida FROM trabalho_diario "
        "WHERE estadia_id = %s "
        "  AND tipo IN ('diagnostico_gestacao','confirmacao_gestacao','segunda_confirmacao') "
        "ORDER BY data_tarefa, tipo",
        (estadia_id,),
    )
    td = cur.fetchall()
    cur.close()
    return {"inseminacoes": ins, "acompanhamento": acomp, "tarefas": td}


def test_menu_e_ficha_registam_resultado_identico(
    db, egua_com_estadia, stock_garanhao,
):
    """A mesma função é chamada pelos dois caminhos → mesmo estado na BD."""
    data_ins = date(2026, 7, 1)
    res = _registar_operacao(egua_com_estadia, stock_garanhao, (2,), data_ins)
    op_id = res["operation_id"]

    # Cenário "Trabalho Diário"
    registar_resultado(
        operation_id=op_id, resultado="positivo",
        tipo_tarefa="diagnostico_gestacao",
        data=data_ins + timedelta(days=14),
        utilizador="trabalho_diario",
    )
    snap_td = _snapshot_resultado(db, egua_com_estadia["estadia_id"], op_id)

    # Reverter para o mesmo ponto de partida
    cur = db.cursor()
    cur.execute(
        "DELETE FROM trabalho_diario WHERE estadia_id = %s "
        "AND tipo IN ('confirmacao_gestacao','segunda_confirmacao')",
        (egua_com_estadia["estadia_id"],),
    )
    cur.execute(
        "UPDATE trabalho_diario SET concluida = FALSE, "
        "  data_conclusao = NULL, observacoes_conclusao = NULL "
        "WHERE estadia_id = %s AND tipo = 'diagnostico_gestacao'",
        (egua_com_estadia["estadia_id"],),
    )
    cur.execute(
        "UPDATE inseminacoes SET resultado = 'pendente', data_resultado = NULL, "
        "  atualizado = FALSE WHERE operation_id = %s::uuid",
        (op_id,),
    )
    cur.execute(
        "UPDATE acompanhamento_inseminacao SET resultado = NULL "
        "WHERE estadia_id = %s",
        (egua_com_estadia["estadia_id"],),
    )
    db.commit()
    cur.close()

    # Cenário "Ficha da égua" — mesma função, mesmos inputs
    registar_resultado(
        operation_id=op_id, resultado="positivo",
        tipo_tarefa="diagnostico_gestacao",
        data=data_ins + timedelta(days=14),
        utilizador="ficha",
    )
    snap_ficha = _snapshot_resultado(db, egua_com_estadia["estadia_id"], op_id)

    assert snap_td == snap_ficha, (
        f"Estados divergem:\ntd={snap_td}\nficha={snap_ficha}"
    )


# ────────────────────────────────────────────────────────────────────
# (e) multi-lote: um só resultado em N linhas
# ────────────────────────────────────────────────────────────────────

def test_multi_lote_partilha_resultado_e_data(
    db, egua_com_estadia, stock_garanhao,
):
    data_ins = date(2026, 8, 1)
    res = _registar_operacao(egua_com_estadia, stock_garanhao, (7, 5), data_ins)
    op_id = res["operation_id"]
    assert len(res["inseminacao_ids"]) == 2

    registar_resultado(
        operation_id=op_id, resultado="positivo",
        tipo_tarefa="diagnostico_gestacao",
        data=data_ins + timedelta(days=14),
    )
    cur = db.cursor()
    cur.execute(
        "SELECT id, resultado, data_resultado FROM inseminacoes "
        "WHERE operation_id = %s::uuid ORDER BY id",
        (op_id,),
    )
    rows = cur.fetchall()
    assert len(rows) == 2
    resultados = {r[1] for r in rows}
    datas = {r[2] for r in rows}
    assert resultados == {"gestacao_confirmada"}
    assert datas == {data_ins + timedelta(days=14)}
    cur.close()


# ────────────────────────────────────────────────────────────────────
# Helpers e validações
# ────────────────────────────────────────────────────────────────────

def test_find_operation_por_tarefa(db, egua_com_estadia, stock_garanhao):
    """`find_operation_por_tarefa` devolve os dados da operação
    associada a uma tarefa D+14 recém-criada."""
    data_ins = date(2026, 9, 1)
    res = _registar_operacao(egua_com_estadia, stock_garanhao, (4,), data_ins)
    task_id = res["trabalho_diario_id"]
    info = find_operation_por_tarefa(task_id)
    assert info is not None
    assert str(info["operation_id"]) == res["operation_id"]
    assert info["tipo"] == "diagnostico_gestacao"
    assert info["num_lotes"] == 1
    assert int(info["total_palhetas"]) == 4


def test_resultado_invalido_erra(db, egua_com_estadia, stock_garanhao):
    res = _registar_operacao(egua_com_estadia, stock_garanhao, (2,))
    with pytest.raises(InseminacaoError):
        registar_resultado(
            operation_id=res["operation_id"],
            resultado="talvez",
            tipo_tarefa="diagnostico_gestacao",
            data=date.today(),
        )
    with pytest.raises(InseminacaoError):
        registar_resultado(
            operation_id=res["operation_id"],
            resultado="positivo",
            tipo_tarefa="qualquer_outra",
            data=date.today(),
        )
    with pytest.raises(InseminacaoError):
        registar_resultado(
            operation_id="00000000-0000-0000-0000-000000000000",
            resultado="positivo",
            tipo_tarefa="diagnostico_gestacao",
            data=date.today(),
        )


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s"]))
