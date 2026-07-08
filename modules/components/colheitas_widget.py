"""Painel reutilizável "Colheitas agendadas" (Pedido 8).

Usado em dois sítios:
- Ficha do garanhão (`animal_page.py`, tab Resumo)
- Tab "Garanhões" de Stock de sémen (link do "Ver ficha")

Só UI — toda a lógica vive em `modules.repositories.colheita_repo`.
"""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from modules.repositories.colheita_repo import (
    agendar_colheita,
    cancelar_colheita,
    listar_colheitas_futuras,
)


def _fmt_data(d: date) -> str:
    try:
        return d.strftime("%d/%m/%Y")
    except Exception:
        return str(d)


def render_colheitas_agendadas(animal_id: int, garanhao_nome: str) -> None:
    """Renderiza o painel completo — seletor + botão + lista."""
    st.markdown(
        "<div style='font-size:.8rem;font-weight:700;color:#0f172a;"
        "text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px;'>"
        "Colheitas agendadas</div>",
        unsafe_allow_html=True,
    )
    st.caption("Datas soltas, decididas pelo veterinário. A colheita "
               "aparece no Trabalho Diário na data marcada.")

    # ── Seletor + botão de agendar ──────────────────────────────
    col_dt, col_btn = st.columns([3, 1.4])
    with col_dt:
        nova_data = st.date_input(
            "Data da colheita",
            value=date.today() + timedelta(days=1),
            min_value=date.today(),
            key=f"colheita-nova-data-{animal_id}",
            label_visibility="collapsed",
        )
    with col_btn:
        if st.button(
            "Agendar colheita",
            key=f"colheita-btn-agendar-{animal_id}",
            type="primary",
            width="stretch",
        ):
            username = st.session_state.get("user", {}).get("username", "—")
            try:
                agendar_colheita(
                    animal_id=int(animal_id),
                    data_tarefa=nova_data,
                    utilizador=username,
                    motivo=f"Colheita — {garanhao_nome}",
                )
                st.success(f"Colheita agendada para {_fmt_data(nova_data)}.")
                st.rerun()
            except Exception as e:
                st.error(f"Não foi possível agendar: {e}")

    # ── Lista de futuras ────────────────────────────────────────
    try:
        df = listar_colheitas_futuras(int(animal_id))
    except Exception as e:
        st.error(f"Erro a carregar colheitas: {e}")
        return

    if df.empty:
        st.info("Sem colheitas futuras marcadas.")
        return

    st.markdown(
        "<div style='font-size:.7rem;color:#64748b;text-transform:uppercase;"
        "letter-spacing:.05em;font-weight:700;margin-top:12px;margin-bottom:4px;'>"
        f"Próximas colheitas ({len(df)})</div>",
        unsafe_allow_html=True,
    )
    for _, row in df.iterrows():
        c_data, c_urg, c_del = st.columns([2, 2, 1.2])
        with c_data:
            st.write(_fmt_data(row["data_tarefa"]))
        with c_urg:
            st.write((row.get("urgencia") or "").capitalize() or "—")
        with c_del:
            if st.button(
                "Cancelar",
                key=f"colheita-btn-cancel-{int(row['id'])}",
                width="stretch",
            ):
                ok = cancelar_colheita(int(row["id"]))
                if ok:
                    st.success("Colheita cancelada.")
                    st.rerun()
                else:
                    st.error("Não foi possível cancelar (já concluída?).")
