"""Ligação parada no pool fechada pelo servidor (inactividade, reinício,
rede) — em produção aparecia "Falha ao aplicar migrations: connection
already closed" no arranque da página. `get_connection` tem de detectar
a ligação morta e entregar uma nova.
"""

from __future__ import annotations

import os

import psycopg2
import pytest

import modules.db as db
from modules.db import build_connection_pool, get_connection


def _matar(pid: int):
    admin = psycopg2.connect(os.getenv("DATABASE_URL", "").strip())
    admin.autocommit = True
    admin.cursor().execute("SELECT pg_terminate_backend(%s)", (pid,))
    admin.close()


def test_ligacao_morta_no_pool_e_substituida(monkeypatch):
    # Simula uma ligação parada há muito (só essas são testadas antes de
    # serem entregues — ver `_TESTAR_SE_PARADA_HA_S`).
    monkeypatch.setattr(db, "_TESTAR_SE_PARADA_HA_S", 0)
    with get_connection() as conn:
        pid = conn.get_backend_pid()
    # A ligação voltou ao pool; o servidor fecha-a enquanto está parada.
    _matar(pid)

    with get_connection() as conn:
        assert conn.get_backend_pid() != pid
        cur = conn.cursor()
        cur.execute("SELECT 1")
        assert cur.fetchone() == (1,)


def test_erro_original_nao_e_escondido_pelo_rollback():
    """Se a ligação morre a meio do bloco, o erro que sobe é o real (e
    não o "connection already closed" do rollback), e a ligação morta
    não volta ao pool."""
    with pytest.raises(psycopg2.OperationalError):
        with get_connection() as conn:
            _matar(conn.get_backend_pid())
            conn.cursor().execute("SELECT 1")

    with get_connection() as conn:
        conn.cursor().execute("SELECT 1")


def test_pool_e_thread_safe():
    assert isinstance(build_connection_pool(), psycopg2.pool.ThreadedConnectionPool)


def test_ligacao_usada_ha_pouco_nao_e_testada():
    """Uma ligação devolvida há instantes é entregue sem o SELECT 1 extra
    (testar sempre duplicava as idas à BD em cada página)."""
    with get_connection() as conn:
        pass
    assert db._ligacao_valida(conn) is True  # sem tocar na BD
