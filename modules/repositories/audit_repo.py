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


def registar_historico_edicao(tabela, record_id, dados_antigos, dados_novos, utilizador=None):
    """Regista uma edição no histórico de auditoria."""
    try:
        if not utilizador:
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


def auditar_apagadas(cur, tabela: str, where: str, params: tuple, utilizador: str | None, motivo: str = "apagado") -> int:
    """Antes de um DELETE: guarda em `historico_edicoes` uma cópia de cada
    linha que vai ser apagada (e quem apagou), na MESMA transação do
    DELETE — se o apagar falhar, a cópia também não fica; se ficar, há
    rasto do que estava lá. `tabela`/`where` são fixos no código (nunca
    input do utilizador)."""
    cur.execute(f"SELECT id, to_jsonb(t) FROM {tabela} t WHERE {where}", params)
    linhas = cur.fetchall()
    for rid, dados in linhas:
        cur.execute(
            """INSERT INTO historico_edicoes (tabela_nome, record_id, dados_antigos, dados_novos, utilizador_nome)
               VALUES (%s, %s, %s, %s, %s)""",
            (tabela, rid, json.dumps(dados, default=str), json.dumps({"acao": motivo}), (utilizador or "—")[:255]),
        )
    return len(linhas)
