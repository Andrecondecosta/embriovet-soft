"""Página de Trabalho diário — agenda semanal de tarefas pendentes.

Mostra uma vista de 7 colunas (segunda → domingo) com cartões coloridos
por urgência. Permite navegar entre semanas e abrir a ficha do animal.
A query carrega tarefas da semana seleccionada com `data_tarefa BETWEEN
segunda_feira AND domingo AND concluida = FALSE`.
"""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from modules.db import get_connection


# ────────────────────────────────────────────────────────────────────────────
# Constantes
# ────────────────────────────────────────────────────────────────────────────
URGENCIAS = {
    "urgente":    {"label": "Urgente",    "icon": "🔴", "color": "#dc2626", "bg": "#fee2e2", "border": "#fca5a5"},
    "hoje":       {"label": "Hoje",       "icon": "🟡", "color": "#ca8a04", "bg": "#fef3c7", "border": "#fde68a"},
    "amanha":     {"label": "Amanhã",     "icon": "🟢", "color": "#16a34a", "bg": "#dcfce7", "border": "#bbf7d0"},
    "observacao": {"label": "Observação", "icon": "⚪", "color": "#475569", "bg": "#f1f5f9", "border": "#e2e8f0"},
}

DIAS_ABREV = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
MESES_ABREV = [
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
]


# ────────────────────────────────────────────────────────────────────────────
# Helpers DB
# ────────────────────────────────────────────────────────────────────────────
def _gerar_tarefas_primeira_observacao() -> int:
    """Cria automaticamente tarefas 'primeira_observacao' para animais em
    estadias activas que ainda não têm registo no diário clínico —
    apenas se ainda não existir uma tarefa do mesmo tipo para hoje.
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


def _carregar_tarefas_semana(seg: date, dom: date) -> pd.DataFrame:
    sql = """
        SELECT
            td.id,
            td.animal_id,
            a.nome    AS animal,
            td.tipo,
            td.motivo,
            td.urgencia,
            td.data_tarefa,
            td.concluida,
            td.data_conclusao,
            td.observacoes_conclusao
        FROM trabalho_diario td
        JOIN animais a ON a.id = td.animal_id
        WHERE td.data_tarefa BETWEEN %s AND %s
        ORDER BY td.data_tarefa ASC, td.concluida ASC, td.created_at DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=(seg, dom))


def _contar_total_proximos_7_dias() -> int:
    sql = """
        SELECT COUNT(*) FROM trabalho_diario
        WHERE data_tarefa BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
          AND concluida = FALSE
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql)
        n = cur.fetchone()[0]
        cur.close()
        return int(n or 0)


def _contar_concluidas_hoje() -> int:
    sql = """
        SELECT COUNT(*) FROM trabalho_diario
        WHERE concluida = TRUE AND data_conclusao = CURRENT_DATE
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql)
        n = cur.fetchone()[0]
        cur.close()
        return int(n or 0)


def _concluir_tarefa(tarefa_id: int, observacoes: str | None) -> None:
    sql = """
        UPDATE trabalho_diario
        SET concluida = TRUE,
            data_conclusao = CURRENT_DATE,
            observacoes_conclusao = %s
        WHERE id = %s
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (observacoes, tarefa_id))
        conn.commit()
        cur.close()


# ────────────────────────────────────────────────────────────────────────────
# Helpers de período
# ────────────────────────────────────────────────────────────────────────────
def _segunda_da_semana(referencia: date) -> date:
    """Devolve a segunda-feira da semana a que `referencia` pertence."""
    return referencia - timedelta(days=referencia.weekday())


def _formatar_intervalo(seg: date, dom: date) -> str:
    if seg.month == dom.month and seg.year == dom.year:
        return f"{seg.day} — {dom.day} {MESES_ABREV[dom.month - 1]} {dom.year}"
    if seg.year == dom.year:
        return (
            f"{seg.day} {MESES_ABREV[seg.month - 1]} — "
            f"{dom.day} {MESES_ABREV[dom.month - 1]} {dom.year}"
        )
    return (
        f"{seg.day} {MESES_ABREV[seg.month - 1]} {seg.year} — "
        f"{dom.day} {MESES_ABREV[dom.month - 1]} {dom.year}"
    )


# ────────────────────────────────────────────────────────────────────────────
# UI helpers
# ────────────────────────────────────────────────────────────────────────────
def _badge_pequeno(urgencia: str) -> str:
    cfg = URGENCIAS.get(urgencia, {"label": urgencia, "icon": "•", "color": "#94a3b8"})
    return (
        f"<span style='display:inline-block;padding:1px 7px;border-radius:999px;"
        f"background:{cfg['color']}26;color:{cfg['color']};font-size:.62rem;"
        f"font-weight:700;text-transform:uppercase;letter-spacing:.4px;'>"
        f"{cfg['icon']} {cfg['label']}</span>"
    )


def _resumir(texto: str | None, max_chars: int = 30) -> str:
    if not texto:
        return "—"
    texto = texto.strip()
    if len(texto) <= max_chars:
        return texto
    return texto[: max_chars - 1] + "…"


def _render_cabecalho_dia(dia: date) -> None:
    is_today = dia == date.today()
    bg = "#fef3c7" if is_today else "#f8fafc"
    border = "#fde68a" if is_today else "#e2e8f0"
    nome = DIAS_ABREV[dia.weekday()]
    st.markdown(
        f"<div style='background:{bg};border:1px solid {border};border-radius:8px;"
        f"padding:8px 6px;text-align:center;margin-bottom:8px;'>"
        f"<div style='font-size:.7rem;color:#64748b;font-weight:700;text-transform:uppercase;"
        f"letter-spacing:.6px;'>{nome}</div>"
        f"<div style='font-size:1.05rem;font-weight:700;color:#0f172a;'>"
        f"{dia.day}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_cartao_tarefa(row: dict, key_prefix: str) -> None:
    motivo = _resumir(row.get("motivo"), 30)
    tid = int(row["id"])

    # ── Tarefa concluída ───────────────────────────────────────────────
    if bool(row.get("concluida")):
        obs_concl = (row.get("observacoes_conclusao") or "").strip()
        obs_html = (
            f"<div style='font-size:.68rem;color:#94a3b8;font-style:italic;"
            f"line-height:1.25;margin-top:2px;'>{obs_concl}</div>"
            if obs_concl else ""
        )
        dt_concl = row.get("data_conclusao")
        dt_concl_txt = dt_concl.strftime("%d/%m") if dt_concl else ""
        st.markdown(
            f"<div style='background:#f1f5f9;border:1px solid #e2e8f0;"
            f"border-left:3px solid #cbd5e1;border-radius:6px;"
            f"padding:8px 10px;margin-bottom:6px;opacity:.95;'>"
            f"<div style='font-weight:700;color:#64748b;font-size:.85rem;"
            f"line-height:1.2;margin-bottom:3px;text-decoration:line-through;'>"
            f"{row['animal']}</div>"
            f"<div style='font-size:.72rem;color:#94a3b8;line-height:1.25;"
            f"margin-bottom:6px;'>{motivo}</div>"
            f"{obs_html}"
            f"<div style='margin:6px 0 4px;'>"
            f"<span style='display:inline-block;padding:1px 8px;border-radius:999px;"
            f"background:#dcfce7;color:#15803d;font-size:.62rem;font-weight:700;"
            f"text-transform:uppercase;letter-spacing:.4px;'>✓ Feito</span>"
            f"</div>"
            f"<div style='font-size:.66rem;color:#94a3b8;margin-top:4px;'>"
            f"Concluído em {dt_concl_txt}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        return

    # ── Tarefa pendente (mantém aspecto actual) ────────────────────────
    cfg = URGENCIAS.get(row["urgencia"], URGENCIAS["observacao"])
    concluir_key = f"concluir_{tid}"

    with st.container():
        st.markdown(
            f"<div style='background:{cfg['bg']};border:1px solid {cfg['border']};"
            f"border-left:3px solid {cfg['color']};border-radius:6px;"
            f"padding:8px 10px;margin-bottom:6px;'>"
            f"<div style='font-weight:700;color:#0f172a;font-size:.85rem;"
            f"line-height:1.2;margin-bottom:3px;'>{row['animal']}</div>"
            f"<div style='font-size:.72rem;color:#475569;line-height:1.25;"
            f"margin-bottom:6px;'>{motivo}</div>"
            f"<div style='margin-bottom:4px;'>{_badge_pequeno(row['urgencia'])}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # Botões: Ver | ✓ Concluir
        bcol1, bcol2 = st.columns(2)
        with bcol1:
            if st.button(
                "Ver",
                key=f"{key_prefix}_ver_{tid}",
                width="stretch",
            ):
                st.session_state["ver_animal_id"] = int(row["animal_id"])
                st.session_state["ver_animal_tab"] = 0
                st.rerun()
        with bcol2:
            if st.button(
                "✓ Concluir",
                key=f"{key_prefix}_concluir_btn_{tid}",
                width="stretch",
            ):
                st.session_state[concluir_key] = not st.session_state.get(concluir_key, False)
                st.rerun()

        # Form inline de conclusão (só renderiza quando aberto)
        if st.session_state.get(concluir_key, False):
            with st.form(f"{key_prefix}_form_concluir_{tid}", clear_on_submit=False):
                obs = st.text_area(
                    "Notas",
                    key=f"{key_prefix}_obs_{tid}",
                    placeholder="Notas sobre a conclusão...",
                    label_visibility="collapsed",
                    height=68,
                )
                fcol1, fcol2 = st.columns(2)
                with fcol1:
                    confirmar = st.form_submit_button(
                        "Confirmar", type="primary", width="stretch",
                    )
                with fcol2:
                    cancelar = st.form_submit_button("Cancelar", width="stretch")

                if cancelar:
                    st.session_state[concluir_key] = False
                    st.rerun()
                if confirmar:
                    try:
                        _concluir_tarefa(tid, (obs or "").strip() or None)
                        st.session_state[concluir_key] = False
                        st.toast(f"Tarefa concluída: {row['animal']}", icon="✅")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")


def _render_coluna_dia(dia: date, df_dia: pd.DataFrame, idx: int) -> None:
    _render_cabecalho_dia(dia)
    if df_dia.empty:
        st.markdown(
            "<div style='color:#94a3b8;font-style:italic;font-size:.72rem;"
            "text-align:center;padding:8px 0;'>— sem tarefas —</div>",
            unsafe_allow_html=True,
        )
        return
    for _, row in df_dia.iterrows():
        _render_cartao_tarefa(row.to_dict(), key_prefix=f"sem_d{idx}")


# ────────────────────────────────────────────────────────────────────────────
# Página principal
# ────────────────────────────────────────────────────────────────────────────
def run_trabalho_diario_page(context: dict):
    """Trabalho diário — agenda semanal."""

    # Drill-down para ficha do animal
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

    # Cabeçalho com data
    hoje = date.today()
    st.markdown(
        f"## Trabalho diário "
        f"<span style='font-size:1.05rem;color:#94a3b8;font-weight:500;'>"
        f"· {hoje.strftime('%d/%m/%Y')}</span>",
        unsafe_allow_html=True,
    )

    # KPIs: próximos 7 dias + concluídas hoje
    total = _contar_total_proximos_7_dias()
    concluidas = _contar_concluidas_hoje()
    kpi1, kpi2 = st.columns(2)
    with kpi1:
        st.metric(label="Tarefas nos próximos 7 dias", value=total)
    with kpi2:
        st.metric(label="Concluídas hoje", value=concluidas)

    st.markdown("---")

    # Inicializar offset de semana
    if "semana_offset" not in st.session_state:
        st.session_state["semana_offset"] = 0

    # Calcular semana visível
    seg_hoje = _segunda_da_semana(hoje)
    seg = seg_hoje + timedelta(weeks=int(st.session_state["semana_offset"]))
    dom = seg + timedelta(days=6)

    # Navegação de semana
    col_prev, col_title, col_next = st.columns([1, 3, 1])
    with col_prev:
        if st.button("◀ Semana anterior", key="btn_sem_ant", width="stretch"):
            st.session_state["semana_offset"] -= 1
            st.rerun()
    with col_title:
        sufixo = ""
        if st.session_state["semana_offset"] == 0:
            sufixo = " · Esta semana"
        elif st.session_state["semana_offset"] == 1:
            sufixo = " · Próxima semana"
        elif st.session_state["semana_offset"] == -1:
            sufixo = " · Semana anterior"
        st.markdown(
            f"<div style='text-align:center;padding:6px 0;'>"
            f"<div style='font-size:1.05rem;font-weight:700;color:#0f172a;'>"
            f"{_formatar_intervalo(seg, dom)}</div>"
            f"<div style='font-size:.75rem;color:#94a3b8;'>{sufixo}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col_next:
        if st.button("Semana seguinte ▶", key="btn_sem_seg", width="stretch"):
            st.session_state["semana_offset"] += 1
            st.rerun()

    # Botão extra: voltar a hoje
    if st.session_state["semana_offset"] != 0:
        if st.button("⌂ Voltar a esta semana", key="btn_sem_hoje"):
            st.session_state["semana_offset"] = 0
            st.rerun()

    st.markdown(
        "<hr style='border:none;border-top:1px solid #e2e8f0;margin:6px 0 12px;'>",
        unsafe_allow_html=True,
    )

    # Carregar tarefas da semana
    df = _carregar_tarefas_semana(seg, dom)
    if not df.empty:
        df["dia"] = pd.to_datetime(df["data_tarefa"]).dt.date

    # 7 colunas — uma por dia
    cols = st.columns(7, gap="small")
    for i in range(7):
        dia = seg + timedelta(days=i)
        df_dia = df[df["dia"] == dia] if not df.empty else df
        with cols[i]:
            _render_coluna_dia(dia, df_dia, idx=i)
