"""Testes para `modules.repositories.container_repo.inverter_andares`
(Passo 1/3 do redesign dos contentores).

Segue o mesmo padrão de `test_stock_fk_garanhao.py`: liga directamente
à BD de teste (já forçada por `conftest.py` via `TEST_DATABASE_URL`) e
cria/apaga os próprios dados.
"""

from __future__ import annotations

import os
import time

import psycopg2
import pytest

from modules.repositories.container_repo import inverter_andares


def _connect():
    url = os.getenv("DATABASE_URL", "").strip()
    assert url, "DATABASE_URL não configurada"
    return psycopg2.connect(url)


@pytest.fixture(scope="module")
def db_conn():
    conn = _connect()
    yield conn
    conn.close()


@pytest.fixture()
def contentor_id(db_conn) -> int:
    cur = db_conn.cursor()
    codigo = f"_TEST_CONT_{int(time.time() * 1000)}"
    cur.execute(
        "INSERT INTO contentores (codigo, descricao) VALUES (%s, %s) RETURNING id",
        (codigo, "Contentor de teste — inverter_andares"),
    )
    cid = int(cur.fetchone()[0])
    db_conn.commit()
    cur.close()
    yield cid

    cur = db_conn.cursor()
    cur.execute("DELETE FROM estoque_dono WHERE contentor_id = %s", (cid,))
    cur.execute("DELETE FROM contentores WHERE id = %s", (cid,))
    db_conn.commit()
    cur.close()


def _criar_lote(db_conn, contentor_id: int, canister: int, andar: int) -> int:
    cur = db_conn.cursor()
    nome = f"_TEST_GAR_{int(time.time() * 1_000_000)}_{canister}_{andar}"
    cur.execute(
        """
        INSERT INTO estoque_dono
            (garanhao, contentor_id, canister, andar, existencia_atual)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (nome, contentor_id, canister, andar, 5),
    )
    lote_id = int(cur.fetchone()[0])
    db_conn.commit()
    cur.close()
    return lote_id


def test_inverter_andares_troca_1_para_2_e_2_para_1(db_conn, contentor_id):
    lote_andar_1 = _criar_lote(db_conn, contentor_id, canister=1, andar=1)
    lote_andar_2 = _criar_lote(db_conn, contentor_id, canister=1, andar=2)

    total_antes = 2
    resultado = inverter_andares(contentor_id)

    assert resultado == total_antes

    cur = db_conn.cursor()
    cur.execute(
        "SELECT id, andar FROM estoque_dono WHERE contentor_id = %s ORDER BY id",
        (contentor_id,),
    )
    linhas = dict(cur.fetchall())
    cur.close()

    assert len(linhas) == total_antes
    assert linhas[lote_andar_1] == 2
    assert linhas[lote_andar_2] == 1


def test_inverter_andares_com_varios_lotes_por_andar(db_conn, contentor_id):
    ids_andar_1 = [
        _criar_lote(db_conn, contentor_id, canister=1, andar=1),
        _criar_lote(db_conn, contentor_id, canister=2, andar=1),
    ]
    ids_andar_2 = [
        _criar_lote(db_conn, contentor_id, canister=1, andar=2),
    ]

    resultado = inverter_andares(contentor_id)

    assert resultado == 3

    cur = db_conn.cursor()
    cur.execute(
        "SELECT id, andar FROM estoque_dono WHERE contentor_id = %s ORDER BY id",
        (contentor_id,),
    )
    linhas = dict(cur.fetchall())
    cur.close()

    assert len(linhas) == 3
    for lote_id in ids_andar_1:
        assert linhas[lote_id] == 2
    for lote_id in ids_andar_2:
        assert linhas[lote_id] == 1


def test_inverter_andares_contentor_vazio_devolve_zero(db_conn, contentor_id):
    resultado = inverter_andares(contentor_id)
    assert resultado == 0
