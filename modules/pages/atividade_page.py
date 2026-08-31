"""Página de Atividade — histórico único de operações (inseminações +
transferências), navegável por dia.

Parte 1 de 3 do redesign do histórico: só leitura aqui. A Parte 2
(editar/anular por linha) e a Parte 3 (remover o histórico redundante
de Transferências → Histórico, que passa a redirecionar para aqui)
ainda não estão feitas.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.components.day_navigator import render_day_navigator
from modules.repositories.dashboard_repo import carregar_atividade_do_dia
from modules.ui_kit import inject_design_tokens, render_page_header, render_zone_title


def _fmt_hora(ts) -> str:
    if not ts:
        return "—"
    return ts.strftime("%H:%M")


def run_atividade_page(context: dict) -> None:
    """Entry-point da página (chamado pelo router). `context` não é
    usado — mantido só por compatibilidade com a assinatura comum."""
    del context

    inject_design_tokens()
    render_page_header("Atividade", "Histórico de inseminações e transferências")

    dia = render_day_navigator("atividade")

    render_zone_title(
        f"Operações de {dia.strftime('%d/%m/%Y')}",
        "ds-zone-title ds-zone-title--first",
    )

    try:
        ops = carregar_atividade_do_dia(dia)
    except Exception as e:
        st.error(f"Erro ao carregar atividade do dia: {e}")
        return

    if not ops:
        st.caption("Sem operações registadas neste dia.")
        return

    display = pd.DataFrame({
        "Hora": [_fmt_hora(op["ts"]) for op in ops],
        "Utilizador": [op["usuario"] or "—" for op in ops],
        "Ação": [op["acao"] or "—" for op in ops],
        "Detalhe": [op["detalhe"] for op in ops],
    })
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        height=min(520, 40 + 35 * len(display)),
    )
