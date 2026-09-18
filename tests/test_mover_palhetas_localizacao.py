"""Testes de `mover_palhetas_localizacao` (stock_repo.py) — mover
palhetas de um lote para outro canister/andar dentro do MESMO
contentor (arrumação física, sem mudar de dono).

Cobre:
- Divisão correta ao mover parte de um lote (origem + destino com as
  quantidades certas, total inalterado).
- Mover o lote inteiro reposiciona o registo sem criar um "lote
  fantasma" com existência 0.
- Somar ao lote já existente no destino (mesmo garanhão, mesmo sítio).
- Validações: não deixa mover mais do que existe, nem para a mesma
  localização de origem.
"""

from __future__ import annotations

import time

import psycopg2
import pytest

from modules.repositories.stock_repo import mover_palhetas_localizacao


def _connect():
    import os
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
def dono_id(db) -> int:
    cur = db.cursor()
    nome = f"_TEST_DONO_MOVER_{int(time.time() * 1000)}"
    cur.execute(
        "INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id",
        (nome,),
    )
    did = int(cur.fetchone()[0])
    db.commit()
    cur.close()
    yield did
    cur = db.cursor()
    cur.execute("DELETE FROM dono WHERE id = %s", (did,))
    db.commit()
    cur.close()


@pytest.fixture()
def contentor_id(db) -> int:
    cur = db.cursor()
    codigo = f"_TEST_CONT_MOVER_{int(time.time() * 1000)}"
    cur.execute(
        "INSERT INTO contentores (codigo, descricao, x, y, w, h, ativo) "
        "VALUES (%s, %s, 0, 0, 100, 100, TRUE) RETURNING id",
        (codigo, "Contentor de teste — mover palhetas"),
    )
    cid = int(cur.fetchone()[0])
    db.commit()
    cur.close()
    yield cid
    cur = db.cursor()
    cur.execute("DELETE FROM estoque_dono WHERE contentor_id = %s", (cid,))
    cur.execute("DELETE FROM contentores WHERE id = %s", (cid,))
    db.commit()
    cur.close()


@pytest.fixture()
def lote_factory(db, dono_id, contentor_id):
    """Cria lotes em `estoque_dono` no contentor de teste. Devolve uma
    função `criar(garanhao, existencia, canister, andar)` -> lote_id."""
    criados: list[int] = []

    def criar(garanhao: str, existencia: int, canister: int, andar: int) -> int:
        cur = db.cursor()
        cur.execute(
            """
            INSERT INTO estoque_dono (
                garanhao, dono_id, existencia_atual, quantidade_inicial,
                palhetas_produzidas, contentor_id, canister, andar
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (garanhao, dono_id, existencia, existencia, existencia,
             contentor_id, canister, andar),
        )
        lote_id = int(cur.fetchone()[0])
        db.commit()
        cur.close()
        criados.append(lote_id)
        return lote_id

    yield criar

    cur = db.cursor()
    try:
        db.rollback()
    except Exception:
        pass
    if criados:
        cur.execute("DELETE FROM estoque_dono WHERE id = ANY(%s)", (criados,))
    db.commit()
    cur.close()


def _ler_lote(db, lote_id):
    cur = db.cursor()
    cur.execute(
        "SELECT existencia_atual, canister, andar, dono_id, garanhao "
        "FROM estoque_dono WHERE id = %s",
        (lote_id,),
    )
    row = cur.fetchone()
    cur.close()
    return row


def _ler_lote_localizacao(db, contentor_id, garanhao, canister, andar):
    """Lê o(s) lote(s) de um garanhão numa localização específica."""
    cur = db.cursor()
    cur.execute(
        "SELECT id, existencia_atual FROM estoque_dono "
        "WHERE contentor_id = %s AND garanhao = %s AND canister = %s AND andar = %s",
        (contentor_id, garanhao, canister, andar),
    )
    rows = cur.fetchall()
    cur.close()
    return rows


# ────────────────────────────────────────────────────────────────────
# Divisão correta ao mover parte de um lote
# ────────────────────────────────────────────────────────────────────

def test_mover_parcial_divide_lote_com_quantidades_certas_e_total_inalterado(
    db, dono_id, contentor_id, lote_factory,
):
    garanhao = f"_TEST_GAR_MOVER_{int(time.time() * 1000)}"
    lote_id = lote_factory(garanhao, 20, canister=1, andar=1)

    sucesso = mover_palhetas_localizacao(lote_id, 8, canister_destino=2, andar_destino=1)
    assert sucesso is True

    origem = _ler_lote(db, lote_id)
    assert origem is not None
    exist_origem, canister_origem, andar_origem, _, _ = origem
    assert exist_origem == 12
    assert (canister_origem, andar_origem) == (1, 1)

    destino_rows = _ler_lote_localizacao(db, contentor_id, garanhao, canister=2, andar=1)
    assert len(destino_rows) == 1
    destino_id, exist_destino = destino_rows[0]
    assert destino_id != lote_id
    assert exist_destino == 8

    # Total de palhetas do garanhão neste contentor não muda.
    assert exist_origem + exist_destino == 20


def test_mover_parcial_soma_a_lote_ja_existente_no_destino(
    db, dono_id, contentor_id, lote_factory,
):
    garanhao = f"_TEST_GAR_MOVER_{int(time.time() * 1000)}"
    lote_origem = lote_factory(garanhao, 20, canister=1, andar=1)
    lote_ja_no_destino = lote_factory(garanhao, 5, canister=2, andar=1)

    sucesso = mover_palhetas_localizacao(lote_origem, 8, canister_destino=2, andar_destino=1)
    assert sucesso is True

    origem = _ler_lote(db, lote_origem)
    assert origem[0] == 12

    destino_rows = _ler_lote_localizacao(db, contentor_id, garanhao, canister=2, andar=1)
    # Não duplica: continua a ser o MESMO registo do destino, só com mais existência.
    assert len(destino_rows) == 1
    assert destino_rows[0][0] == lote_ja_no_destino
    assert destino_rows[0][1] == 5 + 8

    assert origem[0] + destino_rows[0][1] == 20 + 5


# ────────────────────────────────────────────────────────────────────
# Mover o lote inteiro — sem lote fantasma
# ────────────────────────────────────────────────────────────────────

def test_mover_lote_inteiro_reposiciona_sem_criar_fantasma(
    db, dono_id, contentor_id, lote_factory,
):
    garanhao = f"_TEST_GAR_MOVER_{int(time.time() * 1000)}"
    lote_id = lote_factory(garanhao, 20, canister=1, andar=1)

    sucesso = mover_palhetas_localizacao(lote_id, 20, canister_destino=3, andar_destino=2)
    assert sucesso is True

    # O MESMO registo foi reposicionado — não foi criado nenhum novo.
    origem = _ler_lote(db, lote_id)
    exist, canister, andar, _, _ = origem
    assert exist == 20
    assert (canister, andar) == (3, 2)

    cur = db.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM estoque_dono WHERE contentor_id = %s AND garanhao = %s",
        (contentor_id, garanhao),
    )
    total_lotes = cur.fetchone()[0]
    cur.close()
    assert total_lotes == 1, "não deve sobrar nenhum lote fantasma na localização antiga"


def test_mover_lote_inteiro_soma_a_lote_existente_no_destino(
    db, dono_id, contentor_id, lote_factory,
):
    garanhao = f"_TEST_GAR_MOVER_{int(time.time() * 1000)}"
    lote_origem = lote_factory(garanhao, 20, canister=1, andar=1)
    lote_destino = lote_factory(garanhao, 5, canister=2, andar=1)

    sucesso = mover_palhetas_localizacao(lote_origem, 20, canister_destino=2, andar_destino=1)
    assert sucesso is True

    # A origem fica a 0 (fundida no destino) — não é apagada, só zerada.
    origem = _ler_lote(db, lote_origem)
    assert origem[0] == 0

    destino = _ler_lote(db, lote_destino)
    assert destino[0] == 25


# ────────────────────────────────────────────────────────────────────
# Validações
# ────────────────────────────────────────────────────────────────────

def test_mover_recusa_quantidade_maior_que_existente(db, dono_id, contentor_id, lote_factory):
    garanhao = f"_TEST_GAR_MOVER_{int(time.time() * 1000)}"
    lote_id = lote_factory(garanhao, 10, canister=1, andar=1)

    sucesso = mover_palhetas_localizacao(lote_id, 11, canister_destino=2, andar_destino=1)
    assert sucesso is False

    origem = _ler_lote(db, lote_id)
    assert origem[0] == 10, "nada deve mudar quando a quantidade pedida excede a existência"


def test_mover_recusa_mesma_localizacao_de_origem(db, dono_id, contentor_id, lote_factory):
    garanhao = f"_TEST_GAR_MOVER_{int(time.time() * 1000)}"
    lote_id = lote_factory(garanhao, 10, canister=1, andar=1)

    sucesso = mover_palhetas_localizacao(lote_id, 5, canister_destino=1, andar_destino=1)
    assert sucesso is False

    origem = _ler_lote(db, lote_id)
    assert origem[0] == 10, "nada deve mudar quando o destino é igual à origem"
