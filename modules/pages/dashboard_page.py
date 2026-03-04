from datetime import date, datetime
import pandas as pd
import streamlit as st
import altair as alt
from modules.i18n import t


def run_dashboard_page(ctx: dict):
    globals().update(ctx)

    company_name = (app_settings or {}).get("company_name") or "Sistema"
    today_str = date.today().strftime("%d/%m/%Y")
    primary_color = (app_settings or {}).get("primary_color") or "#1D4ED8"

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
            .dash-kpi-value {{
                font-size: 1.8rem;
                font-weight: 800;
                color: {primary_color};
                line-height: 1;
                margin-bottom: 4px;
            }}
            .dash-kpi-label {{
                font-size: .72rem;
                font-weight: 600;
                color: #64748b;
                text-transform: uppercase;
                letter-spacing: .05em;
            }}
            .dash-section-title {{
                font-size: .78rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: .05em;
                color: #64748b;
                margin: 14px 0 8px 0;
            }}
            @media (max-width: 768px) {{
                .dash-kpi-grid {{
                    grid-template-columns: repeat(2, 1fr);
                }}
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Cabeçalho
    st.markdown(
        f"""
        <div class='dash-header'>
            <div class='dash-title'>{t("dashboard.title")}</div>
            <div class='dash-subtitle'>{company_name} · {today_str}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    total_palhetas = 0
    lotes_ativos = 0
    inseminacoes_hoje = 0
    stock_critico = 0
    df_por_contentor = pd.DataFrame()
    df_por_proprietario = pd.DataFrame()

    try:
        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("SELECT COALESCE(SUM(existencia_atual),0) FROM estoque_dono WHERE existencia_atual > 0")
            total_palhetas = cur.fetchone()[0] or 0

            cur.execute("SELECT COUNT(*) FROM estoque_dono WHERE existencia_atual > 0")
            lotes_ativos = cur.fetchone()[0] or 0

            cur.execute("SELECT COUNT(*) FROM inseminacoes WHERE data_inseminacao = CURRENT_DATE")
            inseminacoes_hoje = cur.fetchone()[0] or 0

            cur.execute("SELECT COUNT(*) FROM estoque_dono WHERE existencia_atual > 0 AND existencia_atual <= 5")
            stock_critico = cur.fetchone()[0] or 0

            # Dados para gráfico por contentor
            cur.execute("""
                SELECT c.codigo, COALESCE(SUM(e.existencia_atual), 0) AS palhetas
                FROM contentores c
                LEFT JOIN estoque_dono e ON c.id = e.contentor_id AND e.existencia_atual > 0
                GROUP BY c.codigo
                ORDER BY palhetas DESC
                LIMIT 10
            """)
            rows_cont = cur.fetchall()
            if rows_cont:
                df_por_contentor = pd.DataFrame(rows_cont, columns=["Contentor", "Palhetas"])

            # Dados para gráfico por proprietário
            cur.execute("""
                SELECT d.nome, COALESCE(SUM(e.existencia_atual), 0) AS palhetas
                FROM dono d
                JOIN estoque_dono e ON d.id = e.dono_id AND e.existencia_atual > 0
                GROUP BY d.nome
                ORDER BY palhetas DESC
                LIMIT 8
            """)
            rows_prop = cur.fetchall()
            if rows_prop:
                df_por_proprietario = pd.DataFrame(rows_prop, columns=["Proprietário", "Palhetas"])

            cur.close()
    except Exception as e:
        logger.error(f"Erro ao carregar KPIs do dashboard: {e}")

    # KPI Cards
    st.markdown(
        f"""
        <div class='dash-kpi-grid'>
            <div class='dash-kpi-card'>
                <div class='dash-kpi-value'>{int(total_palhetas)}</div>
                <div class='dash-kpi-label'>{t("dashboard.kpi.total")}</div>
            </div>
            <div class='dash-kpi-card'>
                <div class='dash-kpi-value'>{int(lotes_ativos)}</div>
                <div class='dash-kpi-label'>{t("dashboard.kpi.active")}</div>
            </div>
            <div class='dash-kpi-card'>
                <div class='dash-kpi-value'>{int(inseminacoes_hoje)}</div>
                <div class='dash-kpi-label'>{t("dashboard.kpi.today")}</div>
            </div>
            <div class='dash-kpi-card'>
                <div class='dash-kpi-value'>{int(stock_critico)}</div>
                <div class='dash-kpi-label'>{t("dashboard.kpi.critical")}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Gráficos
    if not df_por_contentor.empty or not df_por_proprietario.empty:
        st.markdown("<div class='dash-section-title'>Distribuição de Stock</div>", unsafe_allow_html=True)
        col_g1, col_g2 = st.columns([1, 1])

        with col_g1:
            if not df_por_contentor.empty:
                chart_cont = (
                    alt.Chart(df_por_contentor)
                    .mark_bar(color=primary_color, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                    .encode(
                        x=alt.X("Contentor:N", sort="-y", axis=alt.Axis(labelAngle=-30, title=None)),
                        y=alt.Y("Palhetas:Q", axis=alt.Axis(title="Palhetas")),
                        tooltip=["Contentor:N", "Palhetas:Q"],
                    )
                    .properties(title="Palhetas por Contentor", height=220)
                )
                st.altair_chart(chart_cont, use_container_width=True)
            else:
                st.info("Sem dados de contentores")

        with col_g2:
            if not df_por_proprietario.empty:
                chart_prop = (
                    alt.Chart(df_por_proprietario)
                    .mark_bar(color="#10b981", cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                    .encode(
                        x=alt.X("Proprietário:N", sort="-y", axis=alt.Axis(labelAngle=-30, title=None)),
                        y=alt.Y("Palhetas:Q", axis=alt.Axis(title="Palhetas")),
                        tooltip=["Proprietário:N", "Palhetas:Q"],
                    )
                    .properties(title="Palhetas por Proprietário", height=220)
                )
                st.altair_chart(chart_prop, use_container_width=True)
            else:
                st.info("Sem dados de proprietários")

    # Atividade recente
    st.markdown(f"<div class='dash-section-title'>{t('dashboard.activity')}</div>", unsafe_allow_html=True)
    atividades = []
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT data_transferencia AS ts,
                       '—' AS usuario,
                       'Transferência interna' AS acao,
                       'Qtd ' || t.quantidade || ' | ' || 
                       COALESCE(d1.nome, 'Origem ID ' || t.proprietario_origem_id) || ' → ' || 
                       COALESCE(d2.nome, 'Dest ID ' || t.proprietario_destino_id) AS detalhe,
                       'transfer_internal' AS tipo,
                       t.id AS action_id,
                       t.estoque_id,
                       t.proprietario_origem_id,
                       t.proprietario_destino_id,
                       t.quantidade
                FROM transferencias t
                LEFT JOIN dono d1 ON t.proprietario_origem_id = d1.id
                LEFT JOIN dono d2 ON t.proprietario_destino_id = d2.id
                UNION ALL
                SELECT data_transferencia AS ts,
                       '—' AS usuario,
                       'Transferência externa' AS acao,
                       'Qtd ' || te.quantidade || ' | ' || 
                       COALESCE(d.nome, 'Origem desconhecida') || ' → ' || te.destinatario_externo AS detalhe,
                       'transfer_external' AS tipo,
                       te.id AS action_id,
                       te.estoque_id,
                       te.proprietario_origem_id,
                       NULL::integer AS proprietario_destino_id,
                       te.quantidade
                FROM transferencias_externas te
                LEFT JOIN dono d ON te.proprietario_origem_id = d.id
                UNION ALL
                SELECT i.data_inseminacao AS ts,
                       '—' AS usuario,
                       'Inseminação' AS acao,
                       'Égua ' || i.egua || ' | ' || i.garanhao || ' | ' || 
                       COALESCE(d.nome, 'Proprietário ID ' || i.dono_id) || ' | ' ||
                       i.palhetas_gastas || ' palhetas' AS detalhe,
                       'insemination' AS tipo,
                       i.id AS action_id,
                       NULL::integer AS estoque_id,
                       i.dono_id AS proprietario_origem_id,
                       NULL::integer AS proprietario_destino_id,
                       i.palhetas_gastas AS quantidade
                FROM inseminacoes i
                LEFT JOIN dono d ON i.dono_id = d.id
                ORDER BY ts DESC
                LIMIT 10
                """
            )
            atividades = cur.fetchall()
            cur.close()
    except Exception as e:
        logger.error(f"Erro ao carregar atividade recente: {e}")

    def fmt_ts(val):
        if not val:
            return "—"
        if isinstance(val, (datetime, date)):
            return val.strftime("%d/%m/%Y %H:%M") if isinstance(val, datetime) else val.strftime("%d/%m/%Y")
        return str(val)

    rows_activity = []
    for ts, usuario, acao, detalhe in atividades:
        rows_activity.append({"Hora": fmt_ts(ts), "Utilizador": usuario or "—", "Ação": acao or "—", "Detalhe": detalhe or "—"})

    df_activity = pd.DataFrame(rows_activity)
    if df_activity.empty:
        st.info("Sem atividade recente registada.")
    else:
        st.dataframe(df_activity, use_container_width=True, hide_index=True, height=220)

    # Ações rápidas
    st.markdown(f"<div class='dash-section-title'>{t('dashboard.actions')}</div>", unsafe_allow_html=True)
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        if st.button(t("dashboard.action.new_insem"), use_container_width=True):
            st.session_state['aba_selecionada'] = t("menu.register_insemination")
            st.rerun()
    with a2:
        if st.button(t("dashboard.action.new_transfer"), use_container_width=True):
            st.session_state['aba_selecionada'] = t("menu.transfers")
            st.rerun()
    with a3:
        if st.button(t("dashboard.action.import"), use_container_width=True):
            st.session_state['aba_selecionada'] = t("menu.import")
            st.rerun()
    with a4:
        if st.button(t("dashboard.action.map"), use_container_width=True):
            st.session_state['aba_selecionada'] = t("menu.map")
            st.rerun()