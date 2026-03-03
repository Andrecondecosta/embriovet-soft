from datetime import date, datetime
import pandas as pd
import streamlit as st
from modules.i18n import t


def run_dashboard_page(ctx: dict):
    globals().update(ctx)

    company_name = (app_settings or {}).get("company_name") or "Sistema"
    today_str = date.today().strftime("%d/%m/%Y")

    st.markdown(
        """
        <style>
            .dash-header {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 10px 12px;
                background: #f8fafc;
                margin-bottom: 10px;
            }
            .dash-title {
                font-size: .9rem;
                font-weight: 700;
                color: #0f172a;
                margin: 0;
            }
            .dash-subtitle {
                font-size: .78rem;
                color: #64748b;
                margin-top: 4px;
            }
            .dash-alerts {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 8px 10px;
                background: #ffffff;
                font-size: .78rem;
                color: #1f2937;
            }
            .dash-alerts ul {
                margin: 0;
                padding-left: 16px;
            }
            .dash-actions button {
                font-size: .8rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Zona A — Cabeçalho
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
    motilidade_baixa = None

    try:
        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute(
                "SELECT COALESCE(SUM(existencia_atual),0) FROM estoque_dono WHERE existencia_atual > 0"
            )
            total_palhetas = cur.fetchone()[0] or 0

            cur.execute(
                "SELECT COUNT(*) FROM estoque_dono WHERE existencia_atual > 0"
            )
            lotes_ativos = cur.fetchone()[0] or 0

            cur.execute(
                "SELECT COUNT(*) FROM inseminacoes WHERE data_inseminacao = CURRENT_DATE"
            )
            inseminacoes_hoje = cur.fetchone()[0] or 0

            cur.execute(
                "SELECT COUNT(*) FROM estoque_dono WHERE existencia_atual <= 5"
            )
            stock_critico = cur.fetchone()[0] or 0

            cur.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name='estoque_dono' AND column_name='motilidade'
                """
            )
            if cur.fetchone():
                cur.execute(
                    "SELECT COUNT(*) FROM estoque_dono WHERE motilidade < 50"
                )
                motilidade_baixa = cur.fetchone()[0] or 0

            cur.close()
    except Exception as e:
        logger.error(f"Erro ao carregar KPIs do dashboard: {e}")

    # Zona B — KPI strip
    render_kpi_strip(
        [
            (t("dashboard.kpi.total"), int(total_palhetas)),
            (t("dashboard.kpi.active"), int(lotes_ativos)),
            (t("dashboard.kpi.today"), int(inseminacoes_hoje)),
            (t("dashboard.kpi.critical"), int(stock_critico)),
        ]
    )

    # Zona C — Atividade recente (Alertas removidos)
    render_zone_title(t("dashboard.activity"), "insem-zone-title")
    atividades = []
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema='public' AND table_name IN ('audit_logs','app_logs')
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if row:
                table = row[0]
                cur.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name=%s",
                    (table,),
                )
                cols = {r[0] for r in cur.fetchall()}
                ts_col = next((c for c in ["created_at", "data", "timestamp", "created_on"] if c in cols), None)
                action_col = next((c for c in ["acao", "action", "event", "tipo"] if c in cols), None)
                user_col = next((c for c in ["usuario", "user_name", "username", "created_by", "user"] if c in cols), None)
                detail_col = next((c for c in ["detalhe", "detail", "descricao", "message"] if c in cols), None)

                if ts_col and action_col:
                    user_expr = user_col if user_col else "'—'"
                    detail_expr = detail_col if detail_col else "''"
                    cur.execute(
                        f"SELECT {ts_col} AS ts, {user_expr} AS usuario, {action_col} AS acao, {detail_expr} AS detalhe "
                        f"FROM {table} ORDER BY {ts_col} DESC LIMIT 10"
                    )
                    atividades = cur.fetchall()

            if not atividades:
                cur.execute(
                    """
                    SELECT data_transferencia AS ts,
                           '—' AS usuario,
                           'Transferência interna' AS acao,
                           'Qtd ' || quantidade || ' | Origem ' || proprietario_origem_id || ' → Dest ' || proprietario_destino_id AS detalhe
                    FROM transferencias
                    UNION ALL
                    SELECT data_transferencia AS ts,
                           '—' AS usuario,
                           'Transferência externa' AS acao,
                           'Qtd ' || quantidade || ' | Dest ' || destinatario_externo AS detalhe
                    FROM transferencias_externas
                    UNION ALL
                    SELECT data_inseminacao AS ts,
                           '—' AS usuario,
                           'Inseminação' AS acao,
                           'Égua ' || egua || ' | Palhetas ' || palhetas_gastas AS detalhe
                    FROM inseminacoes
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

    rows = []
    for ts, usuario, acao, detalhe in atividades:
        rows.append(
            {
                "Hora": fmt_ts(ts),
                "Utilizador": usuario or "—",
                "Ação": acao or "—",
                "Detalhe": detalhe or "—",
            }
        )

    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", hide_index=True, height=260)

    # Zona E — Ações rápidas
    render_zone_title(t("dashboard.actions"), "insem-zone-title")
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        if st.button(t("dashboard.action.new_insem"), width="stretch"):
            st.session_state['aba_selecionada'] = t("menu.register_insemination")
            st.rerun()
    with a2:
        if st.button(t("dashboard.action.new_transfer"), width="stretch"):
            st.session_state['aba_selecionada'] = t("menu.stock")
            st.session_state['abrir_transferencias'] = True
            st.rerun()
    with a3:
        if st.button(t("dashboard.action.import"), width="stretch"):
            st.session_state['aba_selecionada'] = t("menu.import")
            st.rerun()
    with a4:
        if st.button(t("dashboard.action.map"), width="stretch"):
            st.session_state['aba_selecionada'] = t("menu.map")
            st.rerun()