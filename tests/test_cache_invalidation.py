"""Testes de invalidação do `st.cache_data` após COMMITs em tabelas com cache.

Contrato coberto (Correção ao Pedido 5):
- Qualquer função que faça COMMIT de escrita em tabelas cujas leituras
  estão decoradas com `@st.cache_data` (nomeadamente `estoque_dono`,
  `dono`, `contentores`, `transferencias`, `transferencias_externas`,
  `animais`) deve chamar `invalidate_data_cache()` no final da operação.

Estratégia: substituímos temporariamente `modules.db.invalidate_data_cache`
por um sentinel que conta as chamadas, executamos a operação real
contra a BD de teste e verificamos que o contador incrementou.
"""

from __future__ import annotations

import os
import time
from datetime import date, timedelta

import psycopg2
import pytest

from modules import db as db_module
from modules.repositories.animal_repo import get_or_create_garanhao
from modules.repositories.insemination_repo import (
    registar_inseminacao_completa,
    registar_resultado,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


class _CallCounter:
    def __init__(self) -> None:
        self.count = 0

    def __call__(self) -> None:
        self.count += 1


@pytest.fixture
def cache_spy(monkeypatch):
    """Substitui `invalidate_data_cache` em todos os módulos consumidores.

    Cada módulo faz `from modules.db import invalidate_data_cache`, o que
    cria um alias local. Se apenas fizermos patch em `modules.db`, os
    aliases já ligados não serão afectados — patchamos ambos.
    """
    counter = _CallCounter()
    monkeypatch.setattr(db_module, "invalidate_data_cache", counter)

    from modules.repositories import animal_repo, insemination_repo
    monkeypatch.setattr(animal_repo, "invalidate_data_cache", counter)
    monkeypatch.setattr(insemination_repo, "invalidate_data_cache", counter)

    return counter


@pytest.fixture()
def dono_id(db) -> int:
    cur = db.cursor()
    nome = f"_TEST_CACHE_DONO_{int(time.time() * 1000)}"
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
def egua_setup(db, dono_id):
    """Cria uma égua com estadia aberta pronta para inseminação."""
    cur = db.cursor()
    nome = f"_TEST_EGUA_{int(time.time() * 1000)}"
    cur.execute(
        "INSERT INTO animais (nome, tipo, ativo, dono_id) "
        "VALUES (%s, 'egua', TRUE, %s) RETURNING id",
        (nome, dono_id),
    )
    animal_id = int(cur.fetchone()[0])
    cur.execute(
        "INSERT INTO estadias (animal_id, dono_id, tipo_registo, data_entrada, motivo) "
        "VALUES (%s, %s, 'estadia', CURRENT_DATE, 'inseminacao') RETURNING id",
        (animal_id, dono_id),
    )
    estadia_id = int(cur.fetchone()[0])
    db.commit()
    cur.close()
    yield {"animal_id": animal_id, "estadia_id": estadia_id, "dono_id": dono_id}
    cur = db.cursor()
    # Limpeza em cascata manual (ordem inversa às FKs).
    cur.execute("DELETE FROM trabalho_diario WHERE estadia_id = %s", (estadia_id,))
    cur.execute("DELETE FROM acompanhamento_inseminacao WHERE estadia_id = %s", (estadia_id,))
    cur.execute("DELETE FROM inseminacoes WHERE estadia_id = %s", (estadia_id,))
    cur.execute("DELETE FROM estadias WHERE id = %s", (estadia_id,))
    cur.execute("DELETE FROM animais WHERE id = %s", (animal_id,))
    db.commit()
    cur.close()


@pytest.fixture()
def stock_lote(db, dono_id):
    gar_nome = f"_TEST_GAR_{int(time.time() * 1000)}"
    gar_id = get_or_create_garanhao(gar_nome)
    cur = db.cursor()
    cur.execute(
        """
        INSERT INTO estoque_dono (
            garanhao, dono_id, palhetas_produzidas,
            quantidade_inicial, existencia_atual, animal_id
        ) VALUES (
            (SELECT nome FROM animais WHERE id = %s),
            %s, 20, 20, 20, %s
        ) RETURNING id
        """,
        (gar_id, dono_id, gar_id),
    )
    stock_id = int(cur.fetchone()[0])
    db.commit()
    cur.close()
    yield {"stock_id": stock_id, "animal_id_garanhao": gar_id}
    cur = db.cursor()
    cur.execute("DELETE FROM inseminacoes WHERE estoque_id = %s", (stock_id,))
    cur.execute("DELETE FROM estoque_dono WHERE id = %s", (stock_id,))
    cur.execute("DELETE FROM animais WHERE id = %s", (gar_id,))
    db.commit()
    cur.close()


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

def test_get_or_create_garanhao_invalida_cache_quando_cria(cache_spy):
    """Ao criar um novo garanhão em `animais`, o cache deve ser limpo."""
    nome = f"_TEST_NOVO_GAR_{int(time.time() * 1000)}"
    before = cache_spy.count
    gar_id = get_or_create_garanhao(nome)
    assert gar_id is not None
    assert cache_spy.count > before, (
        "get_or_create_garanhao deve invalidar cache ao inserir novo animal"
    )


def test_get_or_create_garanhao_nao_invalida_quando_ja_existe(cache_spy):
    """Se o garanhão já existe (sem INSERT), o cache NÃO precisa ser limpo."""
    nome = f"_TEST_GAR_EXISTENTE_{int(time.time() * 1000)}"
    get_or_create_garanhao(nome)  # cria
    cache_spy.count = 0
    get_or_create_garanhao(nome)  # SELECT-only
    assert cache_spy.count == 0, (
        "get_or_create_garanhao não deve invalidar cache se apenas fez SELECT"
    )


def test_registar_inseminacao_completa_invalida_cache(
    cache_spy, egua_setup, stock_lote, db,
):
    """A função unificada de inseminação deve invalidar o cache no fim."""
    cache_spy.count = 0

    result = registar_inseminacao_completa(
        animal_id_egua=egua_setup["animal_id"],
        estadia_id=egua_setup["estadia_id"],
        dono_id=egua_setup["dono_id"],
        garanhao_nome=f"_TEST_GAR_INSEM_{int(time.time() * 1000)}",
        data_inseminacao=date.today(),
        registros=[{
            "stock_id": stock_lote["stock_id"],
            "palhetas": 3,
        }],
        utilizador="test",
    )
    assert result["inseminacao_ids"], "deveria ter criado inseminação"

    # Sanity: stock efectivamente descontado.
    cur = db.cursor()
    cur.execute(
        "SELECT existencia_atual FROM estoque_dono WHERE id = %s",
        (stock_lote["stock_id"],),
    )
    exist = int(cur.fetchone()[0])
    cur.close()
    assert exist == 17, f"stock esperado 17, obtido {exist}"

    assert cache_spy.count >= 1, (
        "registar_inseminacao_completa deve invalidar cache após COMMIT"
    )


def test_registar_resultado_invalida_cache(
    cache_spy, egua_setup, stock_lote,
):
    """`registar_resultado` deve invalidar o cache no fim (D+14 positivo)."""
    result = registar_inseminacao_completa(
        animal_id_egua=egua_setup["animal_id"],
        estadia_id=egua_setup["estadia_id"],
        dono_id=egua_setup["dono_id"],
        garanhao_nome=f"_TEST_GAR_RES_{int(time.time() * 1000)}",
        data_inseminacao=date.today() - timedelta(days=14),
        registros=[{"stock_id": stock_lote["stock_id"], "palhetas": 2}],
        utilizador="test",
    )

    cache_spy.count = 0
    registar_resultado(
        operation_id=result["operation_id"],
        resultado="positivo",
        tipo_tarefa="diagnostico_gestacao",
        data=date.today(),
        utilizador="test",
    )
    assert cache_spy.count >= 1, (
        "registar_resultado deve invalidar cache após COMMIT"
    )


def test_invalidate_data_cache_e_no_op_fora_streamlit():
    """Sanity: `invalidate_data_cache` real não rebenta em pytest."""
    db_module.invalidate_data_cache()  # não deve levantar
