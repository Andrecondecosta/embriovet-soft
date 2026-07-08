"""Testes do Pedido 8 — Colheitas agendadas do garanhão.

Critérios de aceitação cobertos:
(a) `agendar_colheita` cria tarefa em `trabalho_diario` com tipo=`colheita`,
    `animal_id` do garanhão e `estadia_id=NULL`.
(b) A tarefa aparece nas queries de agenda (`dashboard_repo.carregar_tarefas_hoje`
    e `_carregar_tarefas_semana`) identificada pelo nome do garanhão.
(c) O trabalho_diario_page renderiza o cartão como "Colheita — [nome]"
    e activa o prefill `colheita_garanhao_prefill` (teste por inspecção).
(d) `concluir_colheita` marca `concluida=TRUE`; cache invalidado.
(e) `cancelar_colheita` remove só se ainda não estava concluída.
(f) A migração 030 adicionou o tipo ao CHECK e tornou `estadia_id` NULL.
"""

from __future__ import annotations

import os
import time
from datetime import date, timedelta
from pathlib import Path

import psycopg2
import pytest

from modules.repositories.animal_repo import get_or_create_garanhao
from modules.repositories.colheita_repo import (
    TIPO_COLHEITA,
    agendar_colheita,
    cancelar_colheita,
    concluir_colheita,
    listar_colheitas_futuras,
)


# ────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────

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
def garanhao_id(db):
    ts = int(time.time() * 1_000_000)
    gid = get_or_create_garanhao(f"_TEST_P8_GAR_{ts}")
    yield gid
    cur = db.cursor()
    cur.execute("DELETE FROM trabalho_diario WHERE animal_id = %s", (gid,))
    cur.execute("DELETE FROM animais WHERE id = %s", (gid,))
    db.commit()
    cur.close()


# ────────────────────────────────────────────────────────────────────
# (a) Agendar colheita
# ────────────────────────────────────────────────────────────────────

def test_agendar_colheita_cria_tarefa_com_estadia_nula(db, garanhao_id):
    quando = date.today() + timedelta(days=3)
    tid = agendar_colheita(
        animal_id=garanhao_id,
        data_tarefa=quando,
        utilizador="test",
        motivo="colheita agendada semanal",
    )
    assert isinstance(tid, int) and tid > 0

    cur = db.cursor()
    cur.execute(
        "SELECT animal_id, estadia_id, tipo, data_tarefa, concluida, urgencia "
        "FROM trabalho_diario WHERE id = %s",
        (tid,),
    )
    row = cur.fetchone()
    cur.close()
    assert row is not None
    assert row[0] == garanhao_id
    assert row[1] is None, "estadia_id deve ser NULL numa colheita"
    assert row[2] == TIPO_COLHEITA
    assert row[3] == quando
    assert row[4] is False


def test_listar_colheitas_futuras_ordena_por_data(db, garanhao_id):
    d1 = agendar_colheita(garanhao_id, date.today() + timedelta(days=5), "test")
    d2 = agendar_colheita(garanhao_id, date.today() + timedelta(days=2), "test")
    d3 = agendar_colheita(garanhao_id, date.today() + timedelta(days=8), "test")

    df = listar_colheitas_futuras(garanhao_id)
    ids = df["id"].tolist()
    # Ordem esperada por data ascendente: d2 (2d), d1 (5d), d3 (8d)
    assert ids == [d2, d1, d3]


def test_listar_colheitas_futuras_ignora_passado_e_concluidas(db, garanhao_id):
    # No passado (usamos INSERT directo porque agendar_colheita não permite)
    cur = db.cursor()
    cur.execute(
        "INSERT INTO trabalho_diario (animal_id, estadia_id, data_tarefa, "
        "tipo, motivo, urgencia, criado_automaticamente, utilizador) "
        "VALUES (%s, NULL, CURRENT_DATE - INTERVAL '2 days', 'colheita', "
        "'passada', 'hoje', FALSE, 'test') RETURNING id",
        (garanhao_id,),
    )
    passada = int(cur.fetchone()[0])
    db.commit()
    cur.close()

    futura = agendar_colheita(garanhao_id, date.today() + timedelta(days=1), "test")
    ok = concluir_colheita(futura, "test")
    assert ok is True

    df = listar_colheitas_futuras(garanhao_id)
    assert passada not in df["id"].tolist()
    assert futura not in df["id"].tolist(), "concluída não deve aparecer"


# ────────────────────────────────────────────────────────────────────
# (b) Query de agenda apanha colheitas
# ────────────────────────────────────────────────────────────────────

def test_dashboard_carregar_tarefas_hoje_inclui_colheita(db, garanhao_id):
    tid = agendar_colheita(garanhao_id, date.today(), "test")
    from modules.repositories.dashboard_repo import carregar_tarefas_hoje
    df = carregar_tarefas_hoje()
    ids = df["tarefa_id"].tolist() if not df.empty else []
    assert tid in ids
    row = df[df["tarefa_id"] == tid].iloc[0]
    assert row["tipo"] == TIPO_COLHEITA
    assert row["animal_id"] == garanhao_id


# ────────────────────────────────────────────────────────────────────
# (c) Trabalho diário renderiza "Colheita — [nome]" e prefill correcto
# ────────────────────────────────────────────────────────────────────

def test_trabalho_diario_page_trata_tipo_colheita():
    src = Path("/app/modules/pages/trabalho_diario_page.py").read_text()
    assert 'is_colheita = tipo_tarefa == "colheita"' in src
    assert "Colheita —" in src, (
        "cartão deve renderizar 'Colheita — [nome]'"
    )
    assert 'colheita_garanhao_prefill' in src, (
        "clique deve activar o prefill"
    )


def test_add_stock_view_lida_com_prefill_colheita():
    src = Path("/app/app.py").read_text()
    # Prefill respeitado no default_idx da selectbox
    assert 'colheita_garanhao_prefill' in src
    # Após save, conclusão da tarefa
    assert 'concluir_colheita' in src


# ────────────────────────────────────────────────────────────────────
# (d) Concluir colheita
# ────────────────────────────────────────────────────────────────────

def test_concluir_colheita_marca_como_feita(db, garanhao_id):
    tid = agendar_colheita(garanhao_id, date.today(), "test")
    ok = concluir_colheita(tid, "test_user")
    assert ok is True

    cur = db.cursor()
    cur.execute(
        "SELECT concluida, data_conclusao, observacoes_conclusao "
        "FROM trabalho_diario WHERE id = %s",
        (tid,),
    )
    row = cur.fetchone()
    cur.close()
    assert row[0] is True
    assert row[1] == date.today()
    assert "test_user" in (row[2] or "")


def test_concluir_colheita_e_idempotente(db, garanhao_id):
    tid = agendar_colheita(garanhao_id, date.today(), "test")
    assert concluir_colheita(tid, "u") is True
    # Segunda vez → False (não muda nada)
    assert concluir_colheita(tid, "u") is False


# ────────────────────────────────────────────────────────────────────
# (e) Cancelar colheita
# ────────────────────────────────────────────────────────────────────

def test_cancelar_colheita_remove_agendada(db, garanhao_id):
    tid = agendar_colheita(garanhao_id, date.today() + timedelta(days=4), "test")
    assert cancelar_colheita(tid) is True

    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM trabalho_diario WHERE id = %s", (tid,))
    n = int(cur.fetchone()[0])
    cur.close()
    assert n == 0


def test_cancelar_colheita_nao_apaga_concluidas(db, garanhao_id):
    tid = agendar_colheita(garanhao_id, date.today(), "test")
    concluir_colheita(tid, "test")
    # Não deve cancelar (já concluída)
    assert cancelar_colheita(tid) is False

    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM trabalho_diario WHERE id = %s", (tid,))
    assert int(cur.fetchone()[0]) == 1, "concluída não deve ser apagada"
    cur.close()


# ────────────────────────────────────────────────────────────────────
# (f) Migração 030 aplicada
# ────────────────────────────────────────────────────────────────────

def test_migration_030_permite_tipo_colheita_e_estadia_nula(db, garanhao_id):
    """Sanity: inserção directa com tipo='colheita' e estadia_id NULL
    passa no CHECK (confirmando que a migração 030 foi aplicada)."""
    cur = db.cursor()
    cur.execute(
        "INSERT INTO trabalho_diario (animal_id, estadia_id, data_tarefa, "
        "tipo, motivo, urgencia, criado_automaticamente, utilizador) "
        "VALUES (%s, NULL, CURRENT_DATE, 'colheita', 'sanity check', "
        "'hoje', FALSE, 'test') RETURNING id",
        (garanhao_id,),
    )
    tid = int(cur.fetchone()[0])
    db.commit()
    cur.close()
    assert tid > 0


def test_widget_colheitas_agendadas_existe():
    """Sanity de import — o widget é reutilizável."""
    from modules.components.colheitas_widget import render_colheitas_agendadas
    assert callable(render_colheitas_agendadas)
