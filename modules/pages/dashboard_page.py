"""Dashboard — visão do dia (100% leitura).

Toda a lógica de escrita (anulação de transferências / inseminações) foi
movida para `modules/repositories/transfer_repo.py` e é usada a partir
do histórico da Transfer Page. Este módulo não faz nenhum
UPDATE/DELETE/INSERT — validado por
`tests/test_dashboard_page_readonly.py::test_dashboard_nao_contem_writes`.

Estrutura:
1. Cabeçalho.
2. KPIs de stock (4 cards).
3. KPIs clínicos (4 cards) — estadias, tarefas de hoje (+ urgentes),
   gestações confirmadas, inseminações do mês (DISTINCT operation_id).
4. "Hoje na clínica": tarefas do dia do Trabalho Diário + atalho.
5. "Stock a precisar de atenção": lotes com existência <= 5.
6. Gráficos de distribuição (contentor / proprietário).
7. Atividade recente — agrupada por `operation_id` (1 linha por
   operação), com atalho para a página de transferências.
8. Ações rápidas.
"""

from __future__ import annotations

from datetime import date, datetime
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

from modules.i18n import t
from modules.repositories.dashboard_repo import (
    carregar_atividade_recente_agrupada,
    carregar_kpis_clinicos,
    carregar_kpis_stock,
    carregar_partos_previstos,
    carregar_stock_atencao,
    carregar_stock_por_contentor,
    carregar_stock_por_proprietario,
    carregar_tarefas_hoje,
)
from modules.repositories.settings_repo import get_app_settings
from modules.ui_kit import (
    DEFAULT_PRIMARY_COLOR,
    inject_design_tokens,
    render_kpi_row,
    render_page_header,
    render_status_pill,
    render_zone_title,
)

# Labels curtas para o tipo de tarefa (mais legíveis que o valor bruto).
_LABEL_TIPO_TAREFA = {
    "primeira_observacao": "1ª observação",
    "verificar_ovulacao": "Verificar ovulação",
    "diagnostico_gestacao": "Diagnóstico de gestação",
    "confirmacao_gestacao": "Confirmação de gestação",
    "segunda_confirmacao": "2ª confirmação",
    "pre_parto": "Pré-parto",
    "parto_previsto": "Parto previsto",
}


def _label_tipo(tipo: str) -> str:
    return _LABEL_TIPO_TAREFA.get(tipo, tipo or "—")


def _fmt_ts(val) -> str:
    if not val:
        return "—"
    if isinstance(val, datetime):
        return val.strftime("%d/%m/%Y %H:%M")
    if isinstance(val, date):
        return val.strftime("%d/%m/%Y")
    return str(val)


def _inject_local_css() -> None:
    """CSS específico do Dashboard não coberto pelos componentes base do
    design system (`inject_design_tokens`) — lista de tarefas de "Hoje
    na clínica" (linhas com pill de urgência) e o ajuste do pill quando
    embutido dentro de um valor de KPI."""
    st.markdown(
        """
        <style>
            .dash-task-list {
                display: flex;
                flex-direction: column;
            }
            .dash-task-row {
                display: flex;
                align-items: center;
                gap: var(--ds-space-3);
                padding: var(--ds-space-2) 0;
                border-bottom: 1px solid var(--ds-gray-200);
                font-size: var(--ds-text-sm);
            }
            .dash-task-row:last-child {
                border-bottom: none;
            }
            .dash-task-animal {
                font-weight: 600;
                color: var(--ds-gray-900);
                min-width: 160px;
            }
            .dash-task-detail {
                color: var(--ds-gray-600);
                flex: 1;
            }
            .ds-kpi-value .ds-pill {
                margin-left: 6px;
                vertical-align: middle;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_kpis_stock(kpis: dict) -> None:
    render_zone_title("Stock", "ds-zone-title")
    render_kpi_row([
        (t("dashboard.kpi.total"), kpis["total_palhetas"]),
        (t("dashboard.kpi.active"), kpis["lotes_ativos"]),
        (t("dashboard.kpi.critical"), kpis["stock_critico"]),
    ])


def _render_kpis_clinicos(kpis: dict) -> None:
    render_zone_title("Clínica", "ds-zone-title")
    urgentes = kpis["tarefas_urgentes"]
    tarefas_valor = str(kpis["tarefas_hoje"])
    if urgentes:
        tarefas_valor += " " + render_status_pill(f"{urgentes} urgente(s)", "critico")
    render_kpi_row([
        ("Estadias ativas", kpis["estadias_ativas"]),
        ("Tarefas de hoje", tarefas_valor),
        ("Gestações confirmadas", kpis["gestacoes_confirmadas"]),
        ("Inseminações do mês · por operação", kpis["insem_mes_operacoes"]),
    ])


_PILL_LEVEL_URGENCIA = {"urgente": "critico", "hoje": "aviso"}


def _render_hoje_na_clinica(df: pd.DataFrame) -> None:
    render_zone_title("Hoje na clínica", "ds-zone-title")
    if df.empty:
        st.caption("Sem tarefas para hoje.")
    else:
        rows_html = "".join(
            "<div class='dash-task-row'>"
            f"<span class='dash-task-animal'>{escape(str(row['animal'] or '—'))}</span>"
            "<span class='dash-task-detail'>"
            f"{escape(_label_tipo(row['tipo']))}"
            + (f" · {escape(str(row['motivo']))}" if row["motivo"] else "")
            + "</span>"
            + render_status_pill(
                str(row["urgencia"]).capitalize(),
                _PILL_LEVEL_URGENCIA.get(row["urgencia"], "ok"),
            )
            + "</div>"
            for _, row in df.iterrows()
        )
        st.markdown(f"<div class='dash-task-list'>{rows_html}</div>", unsafe_allow_html=True)

    if st.button(
        "Abrir Trabalho Diário",
        key="dashboard-open-trabalho-diario",
        width="stretch",
    ):
        st.session_state["aba_selecionada"] = "Trabalho diário"
        st.rerun()


def _render_partos_previstos(df: pd.DataFrame, dias: int) -> None:
    """Widget de partos previstos nos próximos `dias` dias (só leitura).

    Só mostra operações com `resultado = 'gestacao_confirmada'` — nunca
    gestações falhadas. Ordenado do mais próximo para o mais distante.
    """
    render_zone_title(f"Partos previstos — próximos {dias} dias", "ds-zone-title")
    if df.empty:
        st.caption("Sem partos previstos neste horizonte.")
        return

    def _fmt_dias(n: int) -> str:
        n = int(n)
        if n == 0:
            return "hoje"
        if n == 1:
            return "amanhã"
        return f"em {n} dias"

    display = pd.DataFrame({
        "Égua": df["egua"].fillna("—"),
        "Data prevista": df["data_parto_previsto"].apply(
            lambda d: d.strftime("%d/%m/%Y") if d else "—"
        ),
        "Dias restantes": df["dias_restantes"].apply(_fmt_dias),
    })
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        height=min(220, 40 + 35 * len(display)),
    )


def _render_stock_atencao(df: pd.DataFrame, limite: int) -> None:
    render_zone_title(f"Stock a precisar de atenção (≤ {limite})", "ds-zone-title")
    if df.empty:
        st.caption("Todos os lotes acima do limite.")
        return

    display = pd.DataFrame({
        "Garanhão": df["garanhao_nome"].fillna("—"),
        "Proprietário": df["proprietario"].fillna("—"),
        "Contentor": df["contentor"].fillna("—"),
        "Can/Andar": df.apply(
            lambda r: f"C{int(r['canister']) if pd.notna(r['canister']) else '?'}"
                      f" / A{int(r['andar']) if pd.notna(r['andar']) else '?'}",
            axis=1,
        ),
        "Existência": df["existencia_atual"].astype(int),
    })
    st.dataframe(display, use_container_width=True, hide_index=True, height=220)


def _render_graficos(primary_color: str) -> None:
    df_cont = carregar_stock_por_contentor(limit=10)
    df_prop = carregar_stock_por_proprietario(limit=8)

    if df_cont.empty and df_prop.empty:
        return

    render_zone_title("Distribuição de Stock", "ds-zone-title")
    col_g1, col_g2 = st.columns([1, 1])

    with col_g1:
        if not df_cont.empty:
            _df_c = df_cont[df_cont["Palhetas"] > 0].copy()
            if not _df_c.empty:
                chart = (
                    alt.Chart(_df_c)
                    .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                    .encode(
                        x=alt.X("Contentor:N", sort=None,
                                axis=alt.Axis(labelAngle=-30, title=None)),
                        y=alt.Y("Palhetas:Q",
                                axis=alt.Axis(title="Palhetas"),
                                scale=alt.Scale(zero=True)),
                        color=alt.value(primary_color),
                        tooltip=["Contentor:N", "Palhetas:Q"],
                    )
                    .properties(title="Palhetas por Contentor", height=220)
                )
                st.altair_chart(chart, use_container_width=True)
            else:
                st.caption("Sem stock em contentores")
        else:
            st.caption("Sem dados de contentores")

    with col_g2:
        if not df_prop.empty:
            _df_p = df_prop[df_prop["Palhetas"] > 0].copy()
            if not _df_p.empty:
                chart = (
                    alt.Chart(_df_p)
                    .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                    .encode(
                        x=alt.X("Proprietário:N", sort=None,
                                axis=alt.Axis(labelAngle=-30, title=None)),
                        y=alt.Y("Palhetas:Q",
                                axis=alt.Axis(title="Palhetas"),
                                scale=alt.Scale(zero=True)),
                        color=alt.value(primary_color),
                        tooltip=["Proprietário:N", "Palhetas:Q"],
                    )
                    .properties(title="Palhetas por Proprietário", height=220)
                )
                st.altair_chart(chart, use_container_width=True)
            else:
                st.caption("Sem stock por proprietário")
        else:
            st.caption("Sem dados de proprietários")


def _render_atividade_recente(ops: list[dict]) -> None:
    render_zone_title(t("dashboard.activity"), "ds-zone-title")
    if not ops:
        st.caption("Sem atividade recente registada.")
        return

    df = pd.DataFrame([
        {
            "Hora": _fmt_ts(op["ts"]),
            "Utilizador": op["usuario"] or "—",
            "Ação": op["acao"] or "—",
            "Detalhe": op["detalhe"],
            "Lotes": op["num_lotes"],
        }
        for op in ops
    ])
    st.dataframe(df, use_container_width=True, hide_index=True, height=220)

    st.caption(
        "Para editar ou anular uma operação, use o histórico em "
        "**Transferências → Histórico**."
    )


def _render_acoes_rapidas() -> None:
    render_zone_title(t("dashboard.actions"), "ds-zone-title")
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        if st.button(t("dashboard.action.new_insem"), width="stretch",
                     key="dashboard-action-new-insem"):
            st.session_state['aba_selecionada'] = t("menu.register_insemination")
            st.rerun()
    with a2:
        if st.button(t("dashboard.action.new_transfer"), width="stretch",
                     key="dashboard-action-new-transfer"):
            st.session_state['aba_selecionada'] = t("menu.transfers")
            st.rerun()
    with a3:
        if st.button(t("dashboard.action.import"), width="stretch",
                     key="dashboard-action-import"):
            st.session_state['aba_selecionada'] = t("menu.import")
            st.rerun()
    with a4:
        if st.button(t("dashboard.action.map"), width="stretch",
                     key="dashboard-action-map"):
            st.session_state['aba_selecionada'] = t("menu.map")
            st.rerun()


def run_dashboard_page(ctx: dict) -> None:
    """Entry-point da página (chamado pelo router).

    Pedido 9 · Fase 2: `ctx` já não é usado. `app_settings` vem via
    `get_app_settings()` (cacheado em `settings_repo`).
    """
    del ctx
    app_settings = get_app_settings() or {}
    company_name = app_settings.get("company_name") or "Sistema"
    primary_color = app_settings.get("primary_color") or DEFAULT_PRIMARY_COLOR

    inject_design_tokens()
    _inject_local_css()
    today_str = date.today().strftime("%d/%m/%Y")
    render_page_header(t("dashboard.title"), f"{company_name} · {today_str}")

    # KPIs
    try:
        kpis_stock = carregar_kpis_stock()
    except Exception as e:
        st.error(f"Erro ao carregar KPIs de stock: {e}")
        kpis_stock = {"total_palhetas": 0, "lotes_ativos": 0, "stock_critico": 0}
    try:
        kpis_clin = carregar_kpis_clinicos()
    except Exception as e:
        st.error(f"Erro ao carregar KPIs clínicos: {e}")
        kpis_clin = {
            "estadias_ativas": 0, "tarefas_hoje": 0, "tarefas_urgentes": 0,
            "gestacoes_confirmadas": 0, "insem_mes_operacoes": 0,
        }

    _render_kpis_stock(kpis_stock)
    _render_kpis_clinicos(kpis_clin)

    # Hoje na clínica
    try:
        df_hoje = carregar_tarefas_hoje()
    except Exception as e:
        st.error(f"Erro ao carregar tarefas de hoje: {e}")
        df_hoje = pd.DataFrame()
    _render_hoje_na_clinica(df_hoje)

    # Widget partos previstos (secção "Hoje na clínica")
    DIAS_PARTOS = 30
    try:
        df_partos = carregar_partos_previstos(dias=DIAS_PARTOS)
    except Exception as e:
        st.error(f"Erro ao carregar partos previstos: {e}")
        df_partos = pd.DataFrame()
    _render_partos_previstos(df_partos, DIAS_PARTOS)

    # Stock a precisar de atenção
    LIMITE_STOCK_ATENCAO = int(app_settings.get("stock_atencao_limite") or 5)
    try:
        df_atencao = carregar_stock_atencao(limite=LIMITE_STOCK_ATENCAO, top=10)
    except Exception as e:
        st.error(f"Erro ao carregar stock com pouca existência: {e}")
        df_atencao = pd.DataFrame()
    _render_stock_atencao(df_atencao, LIMITE_STOCK_ATENCAO)

    # Gráficos + atividade + ações
    _render_graficos(primary_color)

    try:
        ops = carregar_atividade_recente_agrupada(limit=10)
    except Exception as e:
        st.error(f"Erro ao carregar atividade recente: {e}")
        ops = []
    _render_atividade_recente(ops)

    _render_acoes_rapidas()
