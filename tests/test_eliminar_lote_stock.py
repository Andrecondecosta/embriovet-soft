"""Testes para a eliminação definitiva de um lote (separador "Eliminar"
em Stock Atual, só Administrador).

`deletar_stock` apaga a linha de `estoque_dono`; os registos ligados
mantêm-se mas perdem a ligação: `transferencias.estoque_id` via FK
`ON DELETE SET NULL`, `inseminacoes.estoque_id` (sem FK) posto a NULL
explicitamente na mesma transacção.
"""

from __future__ import annotations

import os
import time

import psycopg2
import pytest

from modules.repositories.stock_repo import contar_ligacoes_stock, deletar_stock


def _connect():
    url = os.getenv("DATABASE_URL", "").strip()
    assert url, "DATABASE_URL não configurada"
    return psycopg2.connect(url)


@pytest.fixture
def lote_com_ligacoes():
    nome = f"_TEST_DEL_{int(time.time() * 1_000_000)}"
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO estoque_dono (garanhao, existencia_atual) VALUES (%s, 5) RETURNING id",
        (nome,),
    )
    lote_id = int(cur.fetchone()[0])
    cur.execute(
        "INSERT INTO inseminacoes (garanhao, data_inseminacao, egua, palhetas_gastas, estoque_id) "
        "VALUES (%s, CURRENT_DATE, %s, 1, %s) RETURNING id",
        (nome, nome, lote_id),
    )
    insem_id = int(cur.fetchone()[0])
    cur.execute(
        "INSERT INTO transferencias (estoque_id, quantidade) VALUES (%s, 1) RETURNING id",
        (lote_id,),
    )
    transf_id = int(cur.fetchone()[0])
    conn.commit()

    yield conn, lote_id, insem_id, transf_id

    cur.execute("DELETE FROM inseminacoes WHERE id = %s", (insem_id,))
    cur.execute("DELETE FROM transferencias WHERE id = %s", (transf_id,))
    cur.execute("DELETE FROM estoque_dono WHERE id = %s", (lote_id,))
    conn.commit()
    cur.close()
    conn.close()


def test_contar_ligacoes(lote_com_ligacoes):
    _, lote_id, _, _ = lote_com_ligacoes
    contagens = contar_ligacoes_stock([lote_id])
    assert contagens[lote_id] == {"inseminacoes": 1, "transferencias": 1}


def test_contar_ligacoes_lista_vazia():
    assert contar_ligacoes_stock([]) == {}


def test_deletar_stock_mantem_registos_sem_ligacao(lote_com_ligacoes):
    conn, lote_id, insem_id, transf_id = lote_com_ligacoes

    assert deletar_stock(lote_id) is True

    cur = conn.cursor()
    cur.execute("SELECT 1 FROM estoque_dono WHERE id = %s", (lote_id,))
    assert cur.fetchone() is None
    cur.execute("SELECT estoque_id FROM inseminacoes WHERE id = %s", (insem_id,))
    assert cur.fetchone() == (None,)
    cur.execute("SELECT estoque_id FROM transferencias WHERE id = %s", (transf_id,))
    assert cur.fetchone() == (None,)
    cur.close()
