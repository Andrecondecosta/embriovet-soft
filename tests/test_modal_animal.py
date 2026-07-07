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


# ────────────────────────────────────────────────────────────────────
# Índice único anti-duplicados (migration 025)
# ────────────────────────────────────────────────────────────────────

def test_indice_unico_impede_duplicados_nome_tipo(db_conn, dono_id):
    """A UNIQUE INDEX `animais_nome_tipo_uniq` deve bloquear inserts com
    o mesmo `(LOWER(TRIM(nome)), tipo)` — mesmo com case/espaços diferentes.
    """
    base = f"_TEST_UNIQ_{int(time.time() * 1000)}"
    variantes = [base, f"  {base.lower()}  ", base.upper()]

    ids_criados: list[int] = []
    cur = db_conn.cursor()
    try:
        # 1º INSERT — deve passar
        cur.execute(
            "INSERT INTO animais (nome, tipo, dono_id, ativo) "
            "VALUES (%s, 'garanhao', %s, TRUE) RETURNING id",
            (variantes[0], dono_id),
        )
        ids_criados.append(int(cur.fetchone()[0]))
        db_conn.commit()

        # 2º e 3º INSERTs — devem falhar com UniqueViolation
        for variante in variantes[1:]:
            try:
                cur.execute(
                    "INSERT INTO animais (nome, tipo, dono_id, ativo) "
                    "VALUES (%s, 'garanhao', %s, TRUE) RETURNING id",
                    (variante, dono_id),
                )
                dupe_id = int(cur.fetchone()[0])
                ids_criados.append(dupe_id)
                pytest.fail(
                    f"Insert duplicado ('{variante}') devia falhar mas "
                    f"criou id={dupe_id}"
                )
            except psycopg2.errors.UniqueViolation:
                db_conn.rollback()
    finally:
        cur.close()
        if ids_criados:
            c = db_conn.cursor()
            c.execute(
                "DELETE FROM animais WHERE id = ANY(%s)", (ids_criados,),
            )
            db_conn.commit()
            c.close()


def test_indice_unico_permite_mesmo_nome_tipos_diferentes(db_conn, dono_id):
    """O índice é `(nome_lc, tipo)` — mesmo nome com tipos diferentes
    deve continuar a ser permitido (ex.: "Tornado" égua + "Tornado" garanhão)."""
    base = f"_TEST_TIPOS_{int(time.time() * 1000)}"
    ids: list[int] = []
    cur = db_conn.cursor()
    try:
        for tipo in ("egua", "garanhao"):
            cur.execute(
                "INSERT INTO animais (nome, tipo, dono_id, ativo) "
                "VALUES (%s, %s, %s, TRUE) RETURNING id",
                (base, tipo, dono_id),
            )
            ids.append(int(cur.fetchone()[0]))
            db_conn.commit()
        assert len(ids) == 2
        assert ids[0] != ids[1]
    finally:
        cur.close()
        if ids:
            c = db_conn.cursor()
            c.execute("DELETE FROM animais WHERE id = ANY(%s)", (ids,))
            db_conn.commit()
            c.close()


# ────────────────────────────────────────────────────────────────────
# Ficha do garanhão via FK (`estoque_dono.animal_id`)
# ────────────────────────────────────────────────────────────────────

def test_carregar_stock_garanhao_usa_fk_animal_id(db_conn, dono_id):
    """`_carregar_stock_garanhao(animal_id)` devolve lotes cuja FK
    `estoque_dono.animal_id` coincide, ignorando lotes de outro garanhão
    com o mesmo nome legado.
    """
    from modules.pages.animal_page import _carregar_stock_garanhao

    nome = f"_TEST_STOCK_FK_{int(time.time() * 1000)}"

    animal_id: int | None = None
    lote_ids: list[int] = []
    cur = db_conn.cursor()
    try:
        # Cria o garanhão
        cur.execute(
            "INSERT INTO animais (nome, tipo, dono_id, ativo) "
            "VALUES (%s, 'garanhao', %s, TRUE) RETURNING id",
            (nome, dono_id),
        )
        animal_id = int(cur.fetchone()[0])

        # Cria dois lotes ligados por FK — um com data válida, outro sem data
        for palhetas in (10, 5):
            cur.execute(
                "INSERT INTO estoque_dono ("
                "  garanhao, dono_id, animal_id, palhetas_produzidas, "
                "  existencia_atual, data_embriovet"
                ") VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (nome, dono_id, animal_id, palhetas, palhetas, "2025-01-15"),
            )
            lote_ids.append(int(cur.fetchone()[0]))
        db_conn.commit()

        # Query via FK deve devolver ambos os lotes
        df = _carregar_stock_garanhao(animal_id)
        assert len(df) == 2, (
            f"esperado 2 lotes via FK, obtido {len(df)}"
        )
        assert set(df["palhetas_restantes"].tolist()) == {10, 5}

        # Garantir que a query filtra por FK e não por nome — se
        # inserirmos um lote com o mesmo nome mas `animal_id` diferente
        # (aponta para um segundo garanhão), NÃO deve aparecer.
        cur.execute(
            "INSERT INTO animais (nome, tipo, dono_id, ativo) "
            "VALUES (%s, 'egua', %s, TRUE) RETURNING id",
            (nome, dono_id),  # mesmo nome, tipo diferente — permitido
        )
        outro_animal_id = int(cur.fetchone()[0])
        cur.execute(
            "INSERT INTO estoque_dono ("
            "  garanhao, dono_id, animal_id, palhetas_produzidas, "
            "  existencia_atual"
            ") VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (nome, dono_id, outro_animal_id, 999, 999),
        )
        lote_outro = int(cur.fetchone()[0])
        lote_ids.append(lote_outro)
        db_conn.commit()

        df2 = _carregar_stock_garanhao(animal_id)
        assert len(df2) == 2, (
            "A query devia filtrar por animal_id (FK), não devia "
            "trazer lotes com o mesmo nome mas animal_id diferente"
        )
        assert 999 not in set(df2["palhetas_restantes"].tolist())

        # Cleanup do "outro" animal (apaga primeiro o lote — FK sem CASCADE)
        cur.execute("DELETE FROM estoque_dono WHERE id = %s", (lote_outro,))
        lote_ids.remove(lote_outro)
        cur.execute(
            "DELETE FROM animais WHERE id = %s", (outro_animal_id,),
        )
        db_conn.commit()
    finally:
        cur.close()
        # Se algo falhou a meio, rollback antes do cleanup para libertar
        # a transacção da ligação.
        try:
            db_conn.rollback()
        except Exception:
            pass
        c = db_conn.cursor()
        if lote_ids:
            c.execute(
                "DELETE FROM estoque_dono WHERE id = ANY(%s)", (lote_ids,),
            )
        if animal_id is not None:
            c.execute("DELETE FROM animais WHERE id = %s", (animal_id,))
        db_conn.commit()
        c.close()
