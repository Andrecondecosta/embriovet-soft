"""Módulo de acesso à base de dados — pool de conexões PostgreSQL.

Centraliza a criação do pool, o context manager `get_connection()` e
helpers de conversão de tipos (numpy/pandas → Python nativo) usados
em todo o codebase.
"""

import os
import logging
import datetime as dt
from contextlib import contextmanager
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import numpy as np
import pandas as pd
import psycopg2
import psycopg2.pool
import streamlit as st

logger = logging.getLogger(__name__)


def to_py(v):
    """Converte tipos numpy/pandas para tipos Python aceites pelo psycopg2."""
    if v is None:
        return None

    try:
        if pd.isna(v):
            return None
    except Exception:
        pass

    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)

    if isinstance(v, (pd.Timestamp,)):
        return v.to_pydatetime()

    if isinstance(v, (dt.date, dt.datetime)):
        return v

    return v


def ensure_sslmode_require(url: str) -> str:
    """Garante que o URL contém sslmode=require (obrigatório p/ Render PG)."""
    if not url:
        return url
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "sslmode" not in qs:
        qs["sslmode"] = ["require"]
        parsed = parsed._replace(query=urlencode(qs, doseq=True))
    return urlunparse(parsed)


def is_production_database_url(url: str) -> bool:
    """True se `url` apontar para a base gerida pelo Render (produção) —
    identificado pelo host, não por qual variável de ambiente o trouxe.
    Usado para mostrar um aviso visível caso a app alguma vez fique
    ligada à produção sem ser o próprio deployment no Render (ver
    `app.py`, onde localmente `DATABASE_URL` é sempre substituída por
    `TEST_DATABASE_URL` — isto é só uma rede de segurança adicional)."""
    if not url:
        return False
    return "render.com" in (urlparse(url).hostname or "")


# TCP keepalives: o servidor/rede deixa de fechar tão facilmente ligações
# paradas no pool (e quando fecha, `_ligacao_valida` substitui-as).
_KEEPALIVES = dict(keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=5)


@st.cache_resource(show_spinner=False)
def build_connection_pool():
    """Constrói (uma única vez) o pool de conexões.

    `ThreadedConnectionPool` (com lock) e não `SimpleConnectionPool`: o
    Streamlit corre cada sessão na sua thread, e os `st.download_button`
    com callable (exportações, cópia de segurança) geram o ficheiro
    noutra — o pool é partilhado entre todas."""
    database_url = (os.getenv("DATABASE_URL") or "").strip()

    if database_url:
        database_url = ensure_sslmode_require(database_url)
        pool_obj = psycopg2.pool.ThreadedConnectionPool(
            1, 10,
            dsn=database_url,
            **_KEEPALIVES,
        )
        logger.info("✅ Pool criado com DATABASE_URL (sslmode=require)")
        return pool_obj

    pool_obj = psycopg2.pool.ThreadedConnectionPool(
        1, 10,
        dbname=os.getenv("DB_NAME", "embriovet"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "123"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        **_KEEPALIVES,
    )
    logger.info("✅ Pool criado localmente")
    return pool_obj


def _ligacao_valida(conn) -> bool:
    """True se a ligação ainda está viva. O pool não sabe quando o
    servidor fecha uma ligação parada (inactividade, reinício, rede):
    continuaria a entregá-la e o primeiro uso falhava."""
    if conn.closed:
        return False
    try:
        if conn.info.transaction_status != psycopg2.extensions.TRANSACTION_STATUS_IDLE:
            conn.rollback()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.rollback()
        return True
    except psycopg2.Error:
        return False


def _obter_ligacao_valida(pool, tentativas: int = 3):
    """Ligação do pool, descartando (e substituindo) as que já morreram."""
    for _ in range(tentativas):
        conn = pool.getconn()
        if _ligacao_valida(conn):
            return conn
        logger.warning("Ligação à BD fechada pelo servidor — a abrir uma nova")
        pool.putconn(conn, close=True)
    return pool.getconn()


@contextmanager
def get_connection():
    """Context manager para gestão segura de conexões."""
    pool = build_connection_pool()
    conn = None
    try:
        conn = _obter_ligacao_valida(pool)
        yield conn
    except Exception as e:
        # Se a ligação morreu a meio, o rollback também falha — não pode
        # esconder o erro original (antes aparecia só "connection already
        # closed", sem dizer o que tinha falhado).
        if conn and not conn.closed:
            try:
                conn.rollback()
            except psycopg2.Error:
                pass
        logger.error(f"Erro na conexão: {e}")
        raise
    finally:
        if conn:
            pool.putconn(conn, close=bool(conn.closed))


def invalidate_data_cache():
    """Limpa o `st.cache_data` (todas as vistas com cache).

    Deve ser chamado após qualquer COMMIT que altere tabelas cujas
    leituras estejam decoradas com `@st.cache_data` — nomeadamente
    `estoque_dono`, `dono`, `contentores`, `transferencias`,
    `transferencias_externas` e `animais`.

    É seguro chamar fora de um contexto Streamlit (ex: testes pytest);
    nesses casos actua como no-op.
    """
    try:
        st.cache_data.clear()
    except Exception:
        # Fora de contexto Streamlit ou runtime não inicializado.
        pass
