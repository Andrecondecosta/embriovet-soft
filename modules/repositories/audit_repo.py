"""Auditoria de edições — extraído de `app.py` no Pedido 9 · Fase 2.

Contém `registar_historico_edicao`, usada por `insemination_repo` e por
`transfer_page` para registar deltas em `historico_edicoes`. Extração
pura (bit-for-bit) — nenhuma alteração de lógica.
"""

from __future__ import annotations

import json
import logging

import streamlit as st

from modules.db import get_connection

logger = logging.getLogger(__name__)


def registar_historico_edicao(tabela, record_id, dados_antigos, dados_novos):
    """Regista uma edição no histórico de auditoria."""
    try:
        utilizador = st.session_state.get("user", {}).get("username", "—")
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO historico_edicoes (
                    tabela_nome, record_id, dados_antigos, dados_novos,
                    utilizador_nome
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    tabela,
                    record_id,
                    json.dumps(dados_antigos, default=str),
                    json.dumps(dados_novos, default=str),
                    utilizador,
                ),
            )
            conn.commit()
            cur.close()
    except Exception as e:
        logger.error(f"Erro ao registar histórico de edição: {e}")
