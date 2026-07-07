"""Testes de integração para `modules.components.modal_animal`.

Valida que `_criar_animal_e_estadia` cria correctamente um garanhão em
`animais` e uma estadia associada, mantendo o FK `estadias.animal_id`
→ `animais.id`.

Requer acesso à base de dados PostgreSQL configurada em `.env`
(`DATABASE_URL` no Render). Todos os registos criados são apagados no
final de cada teste (fixture com cleanup automático).
"""

from __future__ import annotations

import os
import time
from datetime import date

import psycopg2
import pytest

# Garante que `conftest.py` já carregou .env e configurou sys.path
from modules.components.modal_animal import _criar_animal_e_estadia


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

def _connect():
    url = os.getenv("DATABASE_URL", "").strip()
    assert url, "DATABASE_URL não configurada — verifique .env"
    return psycopg2.connect(url)


def _get_or_create_dono_ativo(conn) -> int:
    """Devolve o `id` de um dono activo (cria um temporário se preciso)."""
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM dono WHERE ativo = TRUE ORDER BY id LIMIT 1"
    )
    row = cur.fetchone()
    if row:
        cur.close()
        return int(row[0])

    nome = f"_TEST_DONO_{int(time.time())}"
    cur.execute(
        "INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id",
        (nome,),
    )
    dono_id = int(cur.fetchone()[0])
    conn.commit()
    cur.close()
    return dono_id


def _cleanup(conn, animal_id: int | None, estadia_id: int | None) -> None:
    cur = conn.cursor()
    if estadia_id is not None:
        cur.execute("DELETE FROM estadias WHERE id = %s", (estadia_id,))
    if animal_id is not None:
        cur.execute("DELETE FROM animais WHERE id = %s", (animal_id,))
    conn.commit()
    cur.close()


# ────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db_conn():
    conn = _connect()
    yield conn
    conn.close()


@pytest.fixture()
def dono_id(db_conn) -> int:
    return _get_or_create_dono_ativo(db_conn)


# ────────────────────────────────────────────────────────────────────
# Testes
# ────────────────────────────────────────────────────────────────────

def test_criar_garanhao_gera_fk_correcto_em_estadias(db_conn, dono_id):
    """Cria um garanhão + visita e valida o FK `estadias.animal_id`."""
    nome_unico = f"_TEST_GARANHAO_{int(time.time() * 1000)}"

    animal_payload = {
        "nome": nome_unico,
        "tipo": "garanhao",
        "raca": "Lusitano",
        "pelagem": "castanho",
        "data_nascimento": None,
        "numero_registo": None,
        "chip": None,
        "altura": None,
        "peso": None,
        "dono_id": dono_id,
        "pai": None,
        "mae": None,
        "avo_paterno": None,
        "avo_materno": None,
        "observacoes": "criado pelo teste automático",
        "is_receptora": False,
    }
    estadia_payload = {
        "tipo_registo": "visita",
        "alojamento_id": None,
        "dono_id": dono_id,
        "data_entrada": date.today(),
        "data_saida": None,
        "motivo": "colheita",
        "estado": "visitante",
        "observacoes_entrada": None,
    }

    animal_id: int | None = None
    estadia_id: int | None = None
    try:
        animal_id, estadia_id = _criar_animal_e_estadia(
            animal_payload, estadia_payload,
        )

        assert animal_id and animal_id > 0, "animal_id devolvido inválido"
        assert estadia_id and estadia_id > 0, "estadia_id devolvido inválido"

        # (1) O animal existe em `animais` com o tipo/dono correctos.
        cur = db_conn.cursor()
        cur.execute(
            "SELECT nome, tipo, dono_id, ativo FROM animais WHERE id = %s",
            (animal_id,),
        )
        row = cur.fetchone()
        assert row is not None, "Animal não foi criado em `animais`"
        nome_db, tipo_db, dono_db, ativo_db = row
        assert nome_db == nome_unico
        assert tipo_db == "garanhao"
        assert int(dono_db) == int(dono_id)
        assert ativo_db is True

        # (2) A estadia existe com `animal_id` a apontar para o novo animal.
        cur.execute(
            "SELECT animal_id, tipo_registo, motivo, estado "
            "FROM estadias WHERE id = %s",
            (estadia_id,),
        )
        row = cur.fetchone()
        assert row is not None, "Estadia não foi criada"
        animal_fk, tipo_reg, motivo, estado = row
        assert int(animal_fk) == int(animal_id), (
            "estadias.animal_id não aponta para o animal criado (FK "
            "incorrecta)"
        )
        assert tipo_reg == "visita"
        assert motivo == "colheita"
        assert estado == "visitante"

        # (3) O JOIN pela FK funciona (integridade referencial completa).
        cur.execute(
            "SELECT a.id, a.nome, e.id "
            "FROM animais a "
            "JOIN estadias e ON e.animal_id = a.id "
            "WHERE a.id = %s AND e.id = %s",
            (animal_id, estadia_id),
        )
        join_row = cur.fetchone()
        assert join_row is not None, (
            "JOIN animais↔estadias falhou — FK não está a funcionar"
        )
        assert join_row[0] == animal_id
        assert join_row[1] == nome_unico
        assert join_row[2] == estadia_id
        cur.close()
    finally:
        _cleanup(db_conn, animal_id, estadia_id)


def test_fk_estadias_animal_id_impede_orfao(db_conn):
    """A FK deve impedir inserir uma estadia com `animal_id` inexistente."""
    cur = db_conn.cursor()
    try:
        cur.execute(
            "INSERT INTO estadias ("
            "  tipo_registo, animal_id, dono_id, data_entrada, "
            "  motivo, estado"
            ") VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            ("visita", -999999, 1, date.today(), "colheita", "visitante"),
        )
        pytest.fail("Insert de estadia com animal_id inexistente devia falhar")
    except psycopg2.errors.ForeignKeyViolation:
        db_conn.rollback()
    finally:
        cur.close()


if __name__ == "__main__":
    # Permite `python tests/test_modal_animal.py` para uma execução rápida
    # sem pytest.
    import sys

    sys.exit(pytest.main([__file__, "-v", "-s"]))
