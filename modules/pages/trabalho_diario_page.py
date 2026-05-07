"""Página de Trabalho diário — listagem de tarefas pendentes do dia.

Mostra três secções (Urgente · Hoje · Observação) com tarefas da tabela
`trabalho_diario` WHERE concluida = FALSE AND data_tarefa = CURRENT_DATE.
Ao arrancar a página garante a existência de tarefas automáticas
'primeira_observacao' para animais em estadias activas sem registo clínico.
"""

from datetime import date

import pandas as pd
import streamlit as st

from modules.db import get_connection


# ────────────────────────────────────────────────────────────────────────────
# Constantes
# ────────────────────────────────────────────────────────────────────────────
URGENCIAS = {
    "urgente":     {"label": "Urgente",     "icon": "🔴", "color": "#dc2626"},
    "hoje":        {"label": "Hoje",        "icon": "🟡", "color": "#ca8a04"},
    "amanha":      {"label": "Amanhã",      "icon": "🟢", "color": "#16a34a"},
    "observacao":  {"label": "Observação",  "icon": "⚪", "color": "#64748b"},
}


# ────────────────────────────────────────────────────────────────────────────
# Helpers DB
# ────────────────────────────────────────────────────────────────────────────
def _gerar_tarefas_primeira_observacao() -> int:
    """Cria automaticamente tarefas 'primeira_observacao' para animais em
    estadias activas que ainda não têm registo no diário clínico —
    apenas se ainda não existir uma tarefa do mesmo tipo para hoje.
    Devolve quantas tarefas foram criadas.
    """
    sql = """
        INSERT INTO trabalho_diario (
            animal_id, estadia_id, data_tarefa, tipo,
            motivo, urgencia, criado_automaticamente
        )
        SELECT
            e.animal_id, e.id, CURRENT_DATE, 'primeira_observacao',
            '1ª observação — sem registo clínico ainda', 'hoje', TRUE
        FROM estadias e
        WHERE e.data_saida IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM diario_clinico dc
              WHERE dc.animal_id = e.animal_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM trabalho_diario td
              WHERE td.animal_id = e.animal_id
                AND td.estadia_id = e.id
                AND td.data_tarefa = CURRENT_DATE
                AND td.tipo = 'primeira_observacao'
          )
        RETURNING id
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql)
        n = cur.rowcount
        conn.commit()
        cur.close()
        return n or 0


def _carregar_tarefas(urgencia: str) -> pd.DataFrame:
    sql = """
        SELECT
            td.id,
            td.animal_id,
            a.nome      AS animal,
            td.tipo,
            td.motivo,
            td.urgencia,
            e.motivo    AS motivo_estadia,
            td.data_tarefa
        FROM trabalho_diario td
        JOIN animais  a ON a.id = td.animal_id
        JOIN estadias e ON e.id = td.estadia_id
        WHERE td.data_tarefa = CURRENT_DATE
          AND td.concluida = FALSE
          AND td.urgencia = %s
        ORDER BY td.created_at DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=(urgencia,))


def _contar_total_tarefas_hoje() -> int:
    sql = """
        SELECT COUNT(*) FROM trabalho_diario
        WHERE data_tarefa = CURRENT_DATE AND concluida = FALSE
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql)
        n = cur.fetchone()[0]
        cur.close()
        return int(n or 0)


# ────────────────────────────────────────────────────────────────────────────
# UI helpers
# ────────────────────────────────────────────────────────────────────────────
def _badge_urgencia(urgencia: str) -> str:
    cfg = URGENCIAS.get(urgencia, {"label": urgencia, "icon": "•", "color": "#94a3b8"})
    return (
        f"<span style='display:inline-block;padding:2px 10px;border-radius:999px;"
        f"background:{cfg['color']}1A;color:{cfg['color']};font-size:.7rem;"
        f"font-weight:700;text-transform:uppercase;letter-spacing:.5px;'>"
        f"{cfg['icon']} {cfg['label']}</span>"
    )


def _render_tarefa(row: dict, key_prefix: str) -> None:
    cols = st.columns([3.5, 4, 2, 1.5, 1.3])

    cols[0].markdown(
        f"<div style='font-weight:600;color:#0f172a;'>{row['animal']}</div>"
        f"<div style='font-size:.75rem;color:#94a3b8;'>{row['tipo']}</div>",
        unsafe_allow_html=True,
    )
    cols[1].markdown(
        f"<div style='color:#334155;font-size:.9rem;'>{row['motivo']}</div>",
        unsafe_allow_html=True,
    )
    cols[2].markdown(
        f"<div style='font-size:.78rem;color:#64748b;'>Estadia: <b>{row['motivo_estadia']}</b></div>",
        unsafe_allow_html=True,
    )
    cols[3].markdown(_badge_urgencia(row["urgencia"]), unsafe_allow_html=True)

    with cols[4]:
        if st.button(
            "Ver animal",
            key=f"{key_prefix}_ver_{int(row['id'])}",
            width="stretch",
        ):
            st.session_state["ver_animal_id"] = int(row["animal_id"])
            st.session_state["ver_animal_tab"] = 0
            st.rerun()


def _render_seccao(titulo: str, urgencia: str, key_prefix: str) -> None:
    st.subheader(titulo)
    df = _carregar_tarefas(urgencia)
    if df.empty:
        st.markdown(
            "<div style='color:#94a3b8;font-style:italic;padding:6px 0 14px;'>"
            "Sem tarefas nesta categoria.</div>",
            unsafe_allow_html=True,
        )
        return
    for _, row in df.iterrows():
        _render_tarefa(row.to_dict(), key_prefix)
        st.markdown(
            "<hr style='border:none;border-top:1px dashed #e2e8f0;margin:8px 0;'>",
            unsafe_allow_html=True,
        )


# ────────────────────────────────────────────────────────────────────────────
# Página principal
# ────────────────────────────────────────────────────────────────────────────
def run_trabalho_diario_page(context: dict):
    """Trabalho diário — tarefas do dia agrupadas por urgência."""

    # Drill-down para ficha do animal (mesma lógica do estadias_page)
    if st.session_state.get("ver_animal_id") is not None:
        if st.button("← Voltar ao trabalho diário", key="btn_voltar_trab_diario"):
            st.session_state.pop("ver_animal_id", None)
            st.session_state.pop("ver_animal_tab", None)
            st.rerun()
        from modules.pages.animal_page import run_animal_page
        run_animal_page(
            st.session_state["ver_animal_id"],
            context,
            st.session_state.get("ver_animal_tab", 0),
        )
        return

    # Geração automática de tarefas (idempotente)
    try:
        criadas = _gerar_tarefas_primeira_observacao()
        if criadas > 0:
            st.toast(f"Criadas {criadas} tarefas automáticas de 1ª observação.", icon="🆕")
    except Exception as e:
        st.warning(f"Não foi possível gerar tarefas automáticas: {e}")

    # Cabeçalho
    hoje = date.today()
    st.markdown(
        f"## Trabalho diário "
        f"<span style='font-size:1.05rem;color:#94a3b8;font-weight:500;'>"
        f"· {hoje.strftime('%d/%m/%Y')}</span>",
        unsafe_allow_html=True,
    )

    # KPI total de tarefas para hoje
    total = _contar_total_tarefas_hoje()
    st.metric(label="Tarefas pendentes hoje", value=total)

    st.markdown("---")

    # Secções
    _render_seccao("🔴 Urgente",     "urgente",    key_prefix="td_urg")
    _render_seccao("🟡 Hoje",        "hoje",       key_prefix="td_hoje")
    _render_seccao("⚪ Observação",  "observacao", key_prefix="td_obs")
