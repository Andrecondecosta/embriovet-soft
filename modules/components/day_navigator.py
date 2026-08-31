"""Navegador de dia reutilizável — setas ◀/▶, botão "Hoje" (só quando
não está no dia actual) e um `st.date_input` compacto como
mini-calendário.

Genérico: recebe uma `key_prefix` própria para não colidir entre
páginas que o usem em simultâneo (ex.: Atividade e, mais tarde,
Trabalho Diário).

Uso típico:
    from modules.components.day_navigator import render_day_navigator

    dia = render_day_navigator("atividade")
"""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st


def render_day_navigator(key_prefix: str, default: date | None = None) -> date:
    """Renderiza o navegador e devolve a data seleccionada.

    O estado vive em `st.session_state[f"{key_prefix}_date_input"]` — a
    mesma key do próprio widget `st.date_input`, para que os botões
    ◀/▶/Hoje e a escolha directa no calendário fiquem sempre em
    sincronia (nunca se passa `value=` ao date_input a par de uma key
    já presente em session_state — o Streamlit ignoraria o `value` e
    isso desalinhava os dois).
    """
    widget_key = f"{key_prefix}_date_input"
    if widget_key not in st.session_state:
        st.session_state[widget_key] = default or date.today()

    dia_atual: date = st.session_state[widget_key]
    is_hoje = dia_atual == date.today()

    col_prev, col_date, col_next, col_hoje = st.columns(
        [0.08, 0.32, 0.08, 0.16], gap="small", vertical_alignment="bottom",
    )
    with col_prev:
        if st.button("◀", key=f"{key_prefix}_dia_anterior", width="stretch"):
            st.session_state[widget_key] = dia_atual - timedelta(days=1)
            st.rerun()
    with col_next:
        if st.button("▶", key=f"{key_prefix}_dia_seguinte", width="stretch"):
            st.session_state[widget_key] = dia_atual + timedelta(days=1)
            st.rerun()
    with col_hoje:
        if not is_hoje:
            if st.button("Hoje", key=f"{key_prefix}_ir_para_hoje", width="stretch"):
                st.session_state[widget_key] = date.today()
                st.rerun()
    with col_date:
        st.date_input("Dia", key=widget_key, label_visibility="collapsed")

    return st.session_state[widget_key]
