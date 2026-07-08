"""Testes das validações + constraint (Pedido 4b + item 3).

Uma égua só pode ter uma estadia em aberto em simultâneo. Validado em
2 camadas:
- **BD**: UNIQUE INDEX PARCIAL `estadias_uma_aberta_por_animal`
  (migration 029) — rejeita a nível de PostgreSQL.
- **Aplicação**: `_criar_estadia_apenas` faz raise `ValueError` com
  mensagem amigável antes de a constraint disparar.
"""

from __future__ import annotations

import os
import time
from datetime import date, timedelta

import psycopg2
import pytest


def _connect():
    return psycopg2.connect(os.environ["DATABASE_URL"])


@pytest.fixture(scope="module")
def db():
    conn = _connect()
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def _rollback_before(db):
    try:
        db.rollback()
    except Exception:
        pass
    yield


@pytest.fixture()
def animal_egua(db):
    suf = int(time.time() * 1000)
    cur = db.cursor()
    cur.execute(
        "INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id",
        (f"_TEST_DONO_EST_{suf}",),
    )
    dono_id = int(cur.fetchone()[0])
    cur.execute(
        "INSERT INTO animais (nome, tipo, dono_id, ativo) "
        "VALUES (%s, 'egua', %s, TRUE) RETURNING id",
        (f"_TEST_EGUA_EST_{suf}", dono_id),
    )
    animal_id = int(cur.fetchone()[0])
    cur.execute(
        "INSERT INTO alojamentos (nome, tipo, capacidade, ativo) "
        "VALUES (%s, 'box', 1, TRUE) RETURNING id",
        (f"_TEST_BOX_EST_{suf}",),
    )
    aloj_id = int(cur.fetchone()[0])
    db.commit()
    cur.close()
    yield {"animal_id": animal_id, "dono_id": dono_id, "alojamento_id": aloj_id}
    cur = db.cursor()
    cur.execute("DELETE FROM estadias WHERE animal_id = %s", (animal_id,))
    cur.execute("DELETE FROM animais WHERE id = %s", (animal_id,))
    cur.execute("DELETE FROM dono WHERE id = %s", (dono_id,))
    cur.execute("DELETE FROM alojamentos WHERE id = %s", (aloj_id,))
    db.commit()
    cur.close()


def _payload(animal, tipo_registo="estadia", motivo="inseminacao",
             data_saida=None):
    return {
        "tipo_registo": tipo_registo,
        "animal_id": animal["animal_id"],
        "alojamento_id": animal["alojamento_id"],
        "dono_id": animal["dono_id"],
        "data_entrada": date.today() - timedelta(days=1),
        "data_saida": data_saida,
        "motivo": motivo,
        "estado": "internado" if data_saida is None else "saiu",
        "observacoes_entrada": None,
    }


def test_criar_estadia_apenas_valida_estadia_aberta(db, animal_egua):
    """Se já existir estadia aberta, `_criar_estadia_apenas` faz raise
    `ValueError` com mensagem amigável, antes de a UNIQUE INDEX disparar."""
    from modules.pages.estadias_page import _criar_estadia_apenas

    id1 = _criar_estadia_apenas(_payload(animal_egua))
    assert id1 > 0

    with pytest.raises(ValueError, match="já tem uma estadia em aberto"):
        _criar_estadia_apenas(_payload(animal_egua))

    # Fechada primeiro → depois pode criar nova aberta
    cur = db.cursor()
    cur.execute(
        "UPDATE estadias SET data_saida = CURRENT_DATE WHERE id = %s",
        (id1,),
    )
    db.commit()
    cur.close()

    id2 = _criar_estadia_apenas(_payload(animal_egua))
    assert id2 != id1


def test_constraint_bd_rejeita_segunda_estadia_aberta(db, animal_egua):
    """A UNIQUE INDEX PARCIAL da migration 029 rejeita mesmo em bypass
    da validação Python (INSERT directo)."""
    cur = db.cursor()
    cur.execute(
        "INSERT INTO estadias ("
        "  tipo_registo, animal_id, alojamento_id, dono_id, "
        "  data_entrada, motivo, estado) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
        ("estadia", animal_egua["animal_id"], animal_egua["alojamento_id"],
         animal_egua["dono_id"], date.today(), "inseminacao", "internado"),
    )
    id1 = int(cur.fetchone()[0])
    db.commit()

    with pytest.raises(psycopg2.errors.UniqueViolation):
        cur.execute(
            "INSERT INTO estadias ("
            "  tipo_registo, animal_id, alojamento_id, dono_id, "
            "  data_entrada, motivo, estado) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            ("estadia", animal_egua["animal_id"], animal_egua["alojamento_id"],
             animal_egua["dono_id"], date.today(), "inseminacao", "internado"),
        )
    db.rollback()

    # Confirma que a original sobreviveu.
    cur.execute("SELECT COUNT(*) FROM estadias WHERE animal_id = %s",
                (animal_egua["animal_id"],))
    assert cur.fetchone()[0] == 1
    cur.execute("DELETE FROM estadias WHERE id = %s", (id1,))
    db.commit()
    cur.close()


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s"]))
