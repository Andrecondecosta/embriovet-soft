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


def _injetar_css_cartoes() -> None:
    """Injecta o CSS que estiliza os botões-cartão conforme a urgência.

    Cada cartão pendente é criado com `st.button(key=...)` cuja key
    inclui a urgência. O Streamlit atribui a classe `st-key-<key>`
    ao `stElementContainer` desse botão; o CSS abaixo usa um selector
    de wildcard sobre essa classe.
    """
    css = """
    <style>
    /* Estado base — todos os cartões clicáveis ocupam altura suficiente
       para mostrar nome + motivo + badge alinhados à esquerda. */
    div[class*="st-key-tdcard-"] button,
    div[class*="st-key-tdcard-"] button[kind="secondary"] {
        text-align: left !important;
        white-space: normal !important;
        padding: 10px 12px !important;
        min-height: 92px !important;
        height: auto !important;
        border-radius: 6px !important;
        border-style: solid !important;
        border-width: 1px !important;
        border-left-width: 3px !important;
        font-weight: 400 !important;
        line-height: 1.25 !important;
    }
    div[class*="st-key-tdcard-"] button p,
    div[class*="st-key-tdcard-"] button div {
        text-align: left !important;
        margin: 0 !important;
    }

    /* URGENTE — vermelho claro */
    div.st-key-tdcard-urgente button,
    div[class*="st-key-tdcard-urgente-"] button {
        background: #fee2e2 !important;
        border-color: #fca5a5 !important;
        border-left-color: #dc2626 !important;
        color: #0f172a !important;
    }
    div.st-key-tdcard-urgente button:hover,
    div[class*="st-key-tdcard-urgente-"] button:hover {
        background: #fecaca !important;
        border-color: #f87171 !important;
    }

    /* HOJE — amarelo claro */
    div[class*="st-key-tdcard-hoje-"] button {
        background: #fef3c7 !important;
        border-color: #fde68a !important;
        border-left-color: #ca8a04 !important;
        color: #0f172a !important;
    }
    div[class*="st-key-tdcard-hoje-"] button:hover {
        background: #fde68a !important;
        border-color: #facc15 !important;
    }

    /* AMANHÃ — verde claro */
    div[class*="st-key-tdcard-amanha-"] button {
        background: #dcfce7 !important;
        border-color: #bbf7d0 !important;
        border-left-color: #16a34a !important;
        color: #0f172a !important;
    }
    div[class*="st-key-tdcard-amanha-"] button:hover {
        background: #bbf7d0 !important;
        border-color: #86efac !important;
    }

    /* OBSERVAÇÃO — cinza claro */
    div[class*="st-key-tdcard-observacao-"] button {
        background: #f1f5f9 !important;
        border-color: #e2e8f0 !important;
        border-left-color: #475569 !important;
        color: #0f172a !important;
    }
    div[class*="st-key-tdcard-observacao-"] button:hover {
        background: #e2e8f0 !important;
        border-color: #cbd5e1 !important;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def _render_painel_resultado() -> bool:
    """Painel inline para registar o resultado de uma tarefa de
    diagnóstico (D+14/D+28/D+45). Devolve True se foi renderizado."""
    task_id = st.session_state.get("resultado_task_id")
    if not task_id:
        return False

    from modules.repositories.insemination_repo import (
        InseminacaoError,
        find_operation_por_tarefa,
        registar_resultado,
    )

    info = find_operation_por_tarefa(int(task_id))
    if info is None:
        st.warning(
            "Esta tarefa não está ligada a uma inseminação registada. "
            "Marque como concluída manualmente na ficha do animal."
        )
        if st.button("← Voltar", key="btn_res_voltar_erro"):
            st.session_state.pop("resultado_task_id", None)
            st.session_state.pop("resultado_task_tipo", None)
            st.rerun()
        return True

    tipo = str(info["tipo"])
    label_etapa = {
        "diagnostico_gestacao": "1º diagnóstico (D+14)",
        "confirmacao_gestacao": "Confirmação (D+28)",
        "segunda_confirmacao": "2ª confirmação (D+45)",
    }.get(tipo, tipo)

    st.markdown(
        f"<div style='background:#fef3c7;border:1px solid #fde68a;"
        f"border-radius:12px;padding:20px;margin-bottom:16px;'>"
        f"<div style='font-size:.75rem;color:#78716c;text-transform:uppercase;"
        f"letter-spacing:.5px;font-weight:700;margin-bottom:4px;'>"
        f"Registar resultado — {label_etapa}</div>"
        f"<div style='font-size:1.35rem;font-weight:700;color:#0f172a;'>"
        f"{info['egua']} × {info['garanhao']}</div>"
        f"<div style='font-size:.85rem;color:#64748b;margin-top:2px;'>"
        f"Inseminação de {info['data_inseminacao'].strftime('%d/%m/%Y')} "
        f"· {int(info['total_palhetas'] or 0)} palhetas em "
        f"{int(info['num_lotes'] or 1)} lote(s)"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    obs = st.text_area(
        "Observações do exame",
        key=f"res_obs_{task_id}",
        placeholder="Ex.: reflexo positivo, útero vazio, presença de embrião...",
        height=90,
    )

    c1, c2, c3 = st.columns([1, 1, 0.6])
    with c1:
        clicked_pos = st.button(
            "✓ Positivo", key=f"res_pos_{task_id}",
            type="primary", width="stretch",
        )
    with c2:
        clicked_neg = st.button(
            "✗ Negativo", key=f"res_neg_{task_id}",
            width="stretch",
        )
    with c3:
        if st.button("Cancelar", key=f"res_cancel_{task_id}", width="stretch"):
            st.session_state.pop("resultado_task_id", None)
            st.session_state.pop("resultado_task_tipo", None)
            st.rerun()

    if clicked_pos or clicked_neg:
        resultado = "positivo" if clicked_pos else "negativo"
        try:
            _ret = registar_resultado(
                operation_id=str(info["operation_id"]),
                resultado=resultado,
                tipo_tarefa=tipo,
                data=date.today(),
                observacoes=obs or None,
                utilizador=st.session_state.get("user", {}).get("username", "—"),
                task_id=int(task_id),
            )
        except InseminacaoError as e:
            st.error(f"❌ {e}")
            return True

        if resultado == "negativo" and tipo == "diagnostico_gestacao":
            # Guardar dados para as opções pós-negativo (repetir / encerrar)
            st.session_state["resultado_pos_neg"] = {
                "animal_id": int(info["animal_id"]),
                "estadia_id": int(info["estadia_id"]),
                "dono_id": int(info["dono_id"]),
                "egua": info["egua"],
                "garanhao": info["garanhao"],
            }
            st.session_state.pop("resultado_task_id", None)
            st.session_state.pop("resultado_task_tipo", None)
            st.rerun()
        else:
            msg = "✓ Gestação confirmada — D+28 e D+45 adicionados à agenda." if resultado == "positivo" else "✗ Resultado negativo — ciclo encerrado."
            st.success(msg)
            st.session_state.pop("resultado_task_id", None)
            st.session_state.pop("resultado_task_tipo", None)
            st.rerun()

    return True


def _render_painel_pos_negativo() -> bool:
    """Painel de escolha após negativo em D+14: Repetir ou Encerrar."""
    dados = st.session_state.get("resultado_pos_neg")
    if not dados:
        return False

    st.markdown(
        f"<div style='background:#fee2e2;border:1px solid #fecaca;"
        f"border-radius:12px;padding:20px;margin-bottom:16px;'>"
        f"<div style='font-size:.75rem;color:#991b1b;text-transform:uppercase;"
        f"letter-spacing:.5px;font-weight:700;margin-bottom:4px;'>"
        f"Diagnóstico negativo</div>"
        f"<div style='font-size:1.2rem;font-weight:700;color:#0f172a;'>"
        f"{dados['egua']} × {dados['garanhao']} · não gestante</div>"
        f"<div style='font-size:.85rem;color:#7f1d1d;margin-top:4px;'>"
        f"O que quer fazer a seguir?</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔁 Repetir inseminação", key="btn_repetir_insem",
                     type="primary", width="stretch"):
            # Pré-preencher o formulário do menu de registo
            st.session_state["insem_egua_prefill"] = {
                "animal_id": dados["animal_id"],
                "estadia_id": dados["estadia_id"],
                "dono_id": dados["dono_id"],
                "nome": dados["egua"],
            }
            st.session_state["insem_show_success"] = False
            st.session_state.pop("resultado_pos_neg", None)
            # Navegar para o menu "Registar Inseminação" (mesma chave que
            # o dashboard usa em navigate-to-page).
            from modules.i18n import t as _t
            st.session_state["aba_selecionada"] = _t("menu.register_insemination")
            st.rerun()
    with c2:
        if st.button("🗑 Encerrar ciclo", key="btn_encerrar_ciclo",
                     width="stretch"):
            st.session_state.pop("resultado_pos_neg", None)
            st.success("Ciclo encerrado — operação marcada como falhada.")
            st.rerun()

    return True


def _render_cartao_tarefa(row: dict, key_prefix: str) -> None:
    motivo = _resumir(row.get("motivo"), 30)
    tid = int(row["id"])

    # ── Tarefa concluída — apenas visual, não clicável ─────────────────
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

    # ── Tarefa pendente — cartão inteiro clicável (st.button) ──────────
    cfg = URGENCIAS.get(row["urgencia"], URGENCIAS["observacao"])

    # Label markdown rico (negrito + duas linhas + emoji da urgência).
    # A key inclui a urgência para o CSS conseguir estilizar via `st-key-`.
    label = (
        f"**{row['animal']}**\n\n"
        f"{motivo}\n\n"
        f"{cfg['icon']} {cfg['label'].upper()}"
    )

    tipo_tarefa = row.get("tipo") or ""
    tarefas_diagnostico = {
        "diagnostico_gestacao",
        "confirmacao_gestacao",
        "segunda_confirmacao",
    }
    is_diagnostico = tipo_tarefa in tarefas_diagnostico

    if st.button(
        label,
        key=f"tdcard-{row['urgencia']}-{key_prefix}-{tid}",
        width="stretch",
    ):
        if is_diagnostico:
            # Abre o painel de registo de resultado por baixo do cartão.
            st.session_state["resultado_task_id"] = tid
            st.session_state["resultado_task_tipo"] = tipo_tarefa
        else:
            # Restantes tipos → drill-down para a ficha do animal.
            st.session_state["ver_animal_id"] = int(row["animal_id"])
            st.session_state["ver_animal_tab"] = 0
        st.rerun()


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

    # Painel de registo de resultado (D+14/D+28/D+45) — inline no topo
    if _render_painel_resultado():
        return
    if _render_painel_pos_negativo():
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

    # Estilos dos cartões clicáveis (cores por urgência)
    _injetar_css_cartoes()

    # 7 colunas — uma por dia
    cols = st.columns(7, gap="small")
    for i in range(7):
        dia = seg + timedelta(days=i)
        df_dia = df[df["dia"] == dia] if not df.empty else df
        with cols[i]:
            _render_coluna_dia(dia, df_dia, idx=i)
