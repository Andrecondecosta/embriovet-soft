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


@st.cache_resource(show_spinner=False)
def build_connection_pool():
    """Constrói (uma única vez) o pool de conexões."""
    database_url = (os.getenv("DATABASE_URL") or "").strip()

    if database_url:
        database_url = ensure_sslmode_require(database_url)
        pool_obj = psycopg2.pool.SimpleConnectionPool(
            1, 10,
            dsn=database_url
        )
        logger.info("✅ Pool criado com DATABASE_URL (sslmode=require)")
        return pool_obj

    pool_obj = psycopg2.pool.SimpleConnectionPool(
        1, 10,
        dbname=os.getenv("DB_NAME", "embriovet"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "123"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
    )
    logger.info("✅ Pool criado localmente")
    return pool_obj


@contextmanager
def get_connection():
    """Context manager para gestão segura de conexões."""
    pool = build_connection_pool()
    conn = None
    try:
        conn = pool.getconn()
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Erro na conexão: {e}")
        raise
    finally:
        if conn:
            pool.putconn(conn)


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
