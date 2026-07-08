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


def _inject_css(primary_color: str) -> None:
    st.markdown(
        f"""
        <style>
            .dash-header {{
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 14px 16px;
                background: linear-gradient(135deg, #f8fafc 0%, #ffffff 100%);
                margin-bottom: 12px;
                box-shadow: 0 2px 8px rgba(15,23,42,0.05);
            }}
            .dash-title {{
                font-size: 1.05rem;
                font-weight: 700;
                color: #0f172a;
                margin: 0;
            }}
            .dash-subtitle {{
                font-size: .78rem;
                color: #64748b;
                margin-top: 3px;
            }}
            .dash-kpi-grid {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 10px;
                margin-bottom: 14px;
            }}
            .dash-kpi-card {{
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 14px 16px;
                box-shadow: 0 2px 8px rgba(15,23,42,0.05);
                text-align: center;
            }}
            .dash-kpi-card--clinical {{
                background: linear-gradient(135deg, #ecfdf5 0%, #ffffff 60%);
                border-color: #a7f3d0;
            }}
            .dash-kpi-value {{
                font-size: 1.8rem;
                font-weight: 800;
                color: {primary_color};
                line-height: 1;
                margin-bottom: 4px;
            }}
            .dash-kpi-card--clinical .dash-kpi-value {{
                color: #047857;
            }}
            .dash-kpi-label {{
                font-size: .72rem;
                font-weight: 600;
                color: #64748b;
                text-transform: uppercase;
                letter-spacing: .05em;
            }}
            .dash-kpi-sub {{
                font-size: .68rem;
                color: #94a3b8;
                margin-top: 2px;
            }}
            .dash-kpi-sub--warn {{
                color: #dc2626;
                font-weight: 700;
            }}
            .dash-section-title {{
                font-size: .78rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: .05em;
                color: #64748b;
                margin: 14px 0 8px 0;
            }}
            .dash-urgency {{
                display:inline-block;
                padding:2px 8px;
                border-radius:999px;
                font-size:.68rem;
                font-weight:700;
                text-transform:uppercase;
                letter-spacing:.03em;
            }}
            .dash-urgency--urgente {{ background:#fee2e2; color:#b91c1c; }}
            .dash-urgency--hoje    {{ background:#fef3c7; color:#92400e; }}
            .dash-urgency--amanha  {{ background:#dbeafe; color:#1d4ed8; }}
            @media (max-width: 768px) {{
                .dash-kpi-grid {{
                    grid-template-columns: repeat(2, 1fr);
                }}
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header(company_name: str) -> None:
    today_str = date.today().strftime("%d/%m/%Y")
    st.markdown(
        f"""
        <div class='dash-header' data-testid='dashboard-header'>
            <div class='dash-title'>{t("dashboard.title")}</div>
            <div class='dash-subtitle'>{company_name} · {today_str}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_kpis_stock(kpis: dict) -> None:
    st.markdown(
        "<div class='dash-section-title'>Stock</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class='dash-kpi-grid' data-testid='dashboard-kpis-stock'>
            <div class='dash-kpi-card'>
                <div class='dash-kpi-value'>{kpis["total_palhetas"]}</div>
                <div class='dash-kpi-label'>{t("dashboard.kpi.total")}</div>
            </div>
            <div class='dash-kpi-card'>
                <div class='dash-kpi-value'>{kpis["lotes_ativos"]}</div>
                <div class='dash-kpi-label'>{t("dashboard.kpi.active")}</div>
            </div>
            <div class='dash-kpi-card'>
                <div class='dash-kpi-value'>{kpis["stock_critico"]}</div>
                <div class='dash-kpi-label'>{t("dashboard.kpi.critical")}</div>
            </div>
            <div class='dash-kpi-card'>
                <div class='dash-kpi-value'>—</div>
                <div class='dash-kpi-label'>&nbsp;</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_kpis_clinicos(kpis: dict) -> None:
    st.markdown(
        "<div class='dash-section-title'>Clínica</div>",
        unsafe_allow_html=True,
    )
    urgentes = kpis["tarefas_urgentes"]
    sub_urgentes = (
        f"<div class='dash-kpi-sub dash-kpi-sub--warn'>{urgentes} urgente(s)</div>"
        if urgentes else
        "<div class='dash-kpi-sub'>&nbsp;</div>"
    )
    st.markdown(
        f"""
        <div class='dash-kpi-grid' data-testid='dashboard-kpis-clinical'>
            <div class='dash-kpi-card dash-kpi-card--clinical'>
                <div class='dash-kpi-value'>{kpis["estadias_ativas"]}</div>
                <div class='dash-kpi-label'>Estadias ativas</div>
                <div class='dash-kpi-sub'>&nbsp;</div>
            </div>
            <div class='dash-kpi-card dash-kpi-card--clinical'>
                <div class='dash-kpi-value'>{kpis["tarefas_hoje"]}</div>
                <div class='dash-kpi-label'>Tarefas de hoje</div>
                {sub_urgentes}
            </div>
            <div class='dash-kpi-card dash-kpi-card--clinical'>
                <div class='dash-kpi-value'>{kpis["gestacoes_confirmadas"]}</div>
                <div class='dash-kpi-label'>Gestações confirmadas</div>
                <div class='dash-kpi-sub'>&nbsp;</div>
            </div>
            <div class='dash-kpi-card dash-kpi-card--clinical'>
                <div class='dash-kpi-value'>{kpis["insem_mes_operacoes"]}</div>
                <div class='dash-kpi-label'>Inseminações do mês</div>
                <div class='dash-kpi-sub'>por operação</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_hoje_na_clinica(df: pd.DataFrame) -> None:
    st.markdown(
        "<div class='dash-section-title'>Hoje na clínica</div>",
        unsafe_allow_html=True,
    )
    if df.empty:
        st.info("Sem tarefas para hoje. 🎉")
        return

    display = pd.DataFrame({
        "Égua": df["animal"].fillna("—"),
        "Motivo": df["tipo"].map(_label_tipo),
        "Detalhe": df["motivo"].fillna("—"),
        "Urgência": df["urgencia"].str.capitalize().fillna("—"),
    })
    st.dataframe(display, use_container_width=True, hide_index=True, height=220)

    if st.button(
        "📋 Abrir Trabalho Diário",
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
    st.markdown(
        f"<div class='dash-section-title'>Partos previstos — próximos "
        f"{dias} dias</div>",
        unsafe_allow_html=True,
    )
    if df.empty:
        st.info("Sem partos previstos neste horizonte.")
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
    st.markdown(
        f"<div class='dash-section-title'>Stock a precisar de atenção "
        f"(≤ {limite})</div>",
        unsafe_allow_html=True,
    )
    if df.empty:
        st.info("Todos os lotes acima do limite. 👍")
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

    st.markdown(
        "<div class='dash-section-title'>Distribuição de Stock</div>",
        unsafe_allow_html=True,
    )
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
                st.info("Sem stock em contentores")
        else:
            st.info("Sem dados de contentores")

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
                        color=alt.value("#10b981"),
                        tooltip=["Proprietário:N", "Palhetas:Q"],
                    )
                    .properties(title="Palhetas por Proprietário", height=220)
                )
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("Sem stock por proprietário")
        else:
            st.info("Sem dados de proprietários")


def _render_atividade_recente(ops: list[dict]) -> None:
    st.markdown(
        f"<div class='dash-section-title'>{t('dashboard.activity')}</div>",
        unsafe_allow_html=True,
    )
    if not ops:
        st.info("Sem atividade recente registada.")
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
    st.markdown(
        f"<div class='dash-section-title'>{t('dashboard.actions')}</div>",
        unsafe_allow_html=True,
    )
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

    NOTA: `ctx` é actualmente usado apenas para `app_settings`. Todos os
    dados vêm agora do repositório e não do contexto injectado (o que
    permitiu remover a dependência forte de `globals().update(ctx)`).
    """
    app_settings = (ctx or {}).get("app_settings") or {}
    company_name = app_settings.get("company_name") or "Sistema"
    primary_color = app_settings.get("primary_color") or "#1D4ED8"

    _inject_css(primary_color)
    _render_header(company_name)

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
