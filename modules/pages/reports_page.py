import logging

import datetime as dt
import pandas as pd
import streamlit as st

from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from modules.db import to_py
from modules.i18n import t
from modules.repositories.stock_repo import (
    carregar_contentores, carregar_inseminacoes, carregar_proprietarios,
    carregar_stock, carregar_transferencias, carregar_transferencias_externas,
)
from modules.ui_kit import (
    inject_design_tokens, render_kpi_row, render_page_header,
    render_zone_title, safe_pick,
)

logger = logging.getLogger(__name__)


def _contar_operacoes(df: pd.DataFrame) -> int:
    """Conta operações de inseminação DISTINTAS num DataFrame já
    carregado, não linhas — uma operação multi-lote (várias linhas em
    `inseminacoes` com o mesmo `operation_id`) conta como 1.

    Mesmo padrão de `dashboard_repo.carregar_kpis_clinicos`
    (`insem_mes_operacoes`) e `animal_page` (histórico reprodutivo):
    `COALESCE(operation_id, 'solo_'||id)` para agrupar também as linhas
    legadas sem `operation_id`, cada uma a sua própria operação.
    """
    if df.empty:
        return 0
    op_key = df["operation_id"].astype(str).where(
        df["operation_id"].notna(), "solo_" + df["id"].astype(str)
    )
    return int(op_key.nunique())


def _filtrar_stock_por_periodo(df, data_inicio, data_fim):
    if df.empty:
        return df

    col_data = "data_criacao" if "data_criacao" in df.columns else "data_embriovet"
    if col_data not in df.columns:
        return df

    out = df.copy()
    out[col_data] = pd.to_datetime(out[col_data], errors="coerce")
    if data_inicio:
        out = out[out[col_data] >= pd.to_datetime(data_inicio)]
    if data_fim:
        out = out[out[col_data] <= pd.to_datetime(data_fim)]
    return out


def aplicar_filtro_data(df, coluna_data, data_inicio=None, data_fim=None):
    """Aplica filtro de data em um DataFrame.

    Extraído de `app.py` no Pedido 9 · Fase 2 (bit-for-bit). Só usado por
    esta página, portanto vive aqui em vez de num utils partilhado.
    """
    if df.empty:
        return df

    if coluna_data not in df.columns:
        return df

    df_filtrado = df.copy()

    try:
        if not pd.api.types.is_datetime64_any_dtype(df_filtrado[coluna_data]):
            df_filtrado[coluna_data] = pd.to_datetime(
                df_filtrado[coluna_data], errors="coerce",
            )

        if data_inicio:
            df_filtrado = df_filtrado[
                df_filtrado[coluna_data] >= pd.Timestamp(data_inicio)
            ]

        if data_fim:
            df_filtrado = df_filtrado[
                df_filtrado[coluna_data] <= pd.Timestamp(data_fim)
            ]

        return df_filtrado
    except Exception as e:
        logger.error(f"Erro ao aplicar filtro de data: {e}")
        return df


def gerar_pdf_garanhao(
    garanhao_nome, dados_stock, dados_insem, dados_transf_int, dados_transf_ext,
):
    """Gera PDF com histórico completo do garanhão.

    Extraído de `app.py` no Pedido 9 · Fase 2 (bit-for-bit).
    """
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        )
        elements = []
        styles = getSampleStyleSheet()

        titulo_style = ParagraphStyle(
            'CustomTitle', parent=styles['Heading1'], fontSize=18,
            textColor=colors.HexColor('#1f4788'), spaceAfter=12, alignment=1,
        )
        subtitulo_style = ParagraphStyle(
            'CustomSubtitle', parent=styles['Heading2'], fontSize=14,
            textColor=colors.HexColor('#2e5c9a'), spaceAfter=10,
        )

        elements.append(Paragraph(
            f"Relatório Completo: {garanhao_nome}", titulo_style,
        ))
        elements.append(Paragraph(
            f"Gerado em: {dt.datetime.now().strftime('%d/%m/%Y %H:%M')}",
            styles['Normal'],
        ))
        elements.append(Spacer(1, 0.5 * cm))

        if not dados_stock.empty:
            elements.append(Paragraph("📦 Stock Atual", subtitulo_style))
            stock_data = [['Proprietário', 'Data', 'Existência', 'Qualidade', 'Local']]
            for _, row in dados_stock.iterrows():
                stock_data.append([
                    str(row.get('proprietario_nome', 'N/A'))[:30],
                    str(row.get('data_embriovet', 'N/A'))[:10],
                    str(int(row.get('existencia_atual', 0))),
                    str(row.get('qualidade', '—')),
                    str(row.get('local_armazenagem', 'N/A'))[:20],
                ])
            tbl = Table(stock_data, colWidths=[4 * cm, 3 * cm, 2.5 * cm, 2.5 * cm, 4 * cm])
            tbl.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(tbl)
            elements.append(Spacer(1, 0.5 * cm))

        if not dados_insem.empty:
            elements.append(Paragraph("📝 Histórico de Inseminações", subtitulo_style))
            insem_data = [['Data', 'Égua', 'Proprietário', 'Palhetas']]
            for _, row in dados_insem.iterrows():
                insem_data.append([
                    str(row.get('data_inseminacao', 'N/A'))[:10],
                    str(row.get('egua_nome') or row.get('egua', 'N/A'))[:25],
                    str(row.get('proprietario_nome', 'N/A'))[:25],
                    str(int(row.get('palhetas_gastas', 0))),
                ])
            tbl = Table(insem_data, colWidths=[3 * cm, 5 * cm, 5 * cm, 3 * cm])
            tbl.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e5c9a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(tbl)
            elements.append(Spacer(1, 0.5 * cm))

        if not dados_transf_int.empty:
            elements.append(Paragraph("🔄 Transferências Internas", subtitulo_style))
            transf_data = [['Data', 'De', 'Para', 'Palhetas']]
            for _, row in dados_transf_int.iterrows():
                transf_data.append([
                    str(row.get('data_transferencia', 'N/A'))[:10],
                    str(row.get('proprietario_origem', 'N/A'))[:20],
                    str(row.get('proprietario_destino', 'N/A'))[:20],
                    str(int(row.get('quantidade', 0))),
                ])
            tbl = Table(transf_data, colWidths=[3 * cm, 4.5 * cm, 4.5 * cm, 3 * cm])
            tbl.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e5c9a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(tbl)
            elements.append(Spacer(1, 0.5 * cm))

        if not dados_transf_ext.empty:
            elements.append(Paragraph(
                "📤 Transferências Externas (Vendas/Doações)", subtitulo_style,
            ))
            for _, row in dados_transf_ext.iterrows():
                transf_ext_data = [['Data', 'De', 'Para', 'Palhetas', 'Tipo']]
                transf_ext_data.append([
                    str(row.get('data_transferencia', 'N/A'))[:10],
                    str(row.get('proprietario_origem', 'N/A'))[:18],
                    str(row.get('destinatario_externo', 'N/A'))[:18],
                    str(int(row.get('quantidade', 0))),
                    str(row.get('tipo', 'N/A'))[:15],
                ])
                tbl = Table(
                    transf_ext_data,
                    colWidths=[2.5 * cm, 3.5 * cm, 3.5 * cm, 2.5 * cm, 3 * cm],
                )
                tbl.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e5c9a')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                elements.append(tbl)

                obs = row.get('observacoes', '')
                if obs and str(obs) != 'nan' and str(obs).strip():
                    obs_style = ParagraphStyle(
                        'Obs', parent=styles['Normal'], fontSize=9, leftIndent=10,
                    )
                    elements.append(Paragraph(
                        f"<b>Observações:</b> {str(obs)}", obs_style,
                    ))

                elements.append(Spacer(1, 0.3 * cm))

        doc.build(elements)
        buffer.seek(0)
        return buffer

    except Exception as e:
        logger.error(f"Erro ao gerar PDF: {e}")
        return None


def run_reports_page(ctx: dict):
    # Pedido 9 · Fase 2: `ctx` mantido na assinatura por compatibilidade
    # com o router mas as dependências vêm todas por import explícito no
    # topo do módulo. Nenhum `ctx["..."]`.
    del ctx

    inject_design_tokens()
    render_page_header(t("reports.title"))

    stock = carregar_stock()
    insem = carregar_inseminacoes()
    transf = carregar_transferencias()
    transf_ext = carregar_transferencias_externas()
    proprietarios = carregar_proprietarios()
    contentores = carregar_contentores()

    render_zone_title(t("reports.zone.selection"), "ds-zone-title")
    modo = st.radio(
        t("reports.analysis_type"),
        [t("reports.mode.stallion"), t("reports.mode.owner"), t("reports.mode.container"), t("reports.mode.history")],
        horizontal=True,
        label_visibility="collapsed",
        key="rel_modo",
    )

    garanhao_sel = None
    prop_sel = None
    contentor_sel = None
    tipo_hist = None

    if modo == t("reports.mode.stallion") and not stock.empty:
        garanhao_sel = st.selectbox(t("reports.select_stallion"), sorted(stock["garanhao_nome"].dropna().unique()), key="rel_sel_g")
    elif modo == t("reports.mode.owner") and not proprietarios.empty:
        prop_sel = st.selectbox(
            t("reports.select_owner"),
            proprietarios["id"].tolist(),
            format_func=lambda x: proprietarios[proprietarios["id"] == x]["nome"].values[0],
            key="rel_sel_p",
        )
    elif modo == t("reports.mode.container") and not contentores.empty:
        contentor_sel = st.selectbox(
            t("reports.select_container"),
            contentores["id"].tolist(),
            format_func=lambda x: contentores[contentores["id"] == x]["codigo"].values[0],
            key="rel_sel_c",
        )
    elif modo == t("reports.mode.history"):
        tipo_hist = st.radio(
            t("reports.history_type"),
            [t("reports.history.inseminations"), t("reports.history.transfer_internal"), t("reports.history.transfer_external"), t("reports.history.full_stock")],
            horizontal=True,
            label_visibility="collapsed",
            key="rel_tipo_hist",
        )

    render_zone_title(t("reports.zone.filters"), "ds-zone-title")
    filtros = {}
    with st.expander(t("reports.filters_title"), expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            usar_periodo = st.checkbox(t("reports.apply_period"), value=False, key="rel_periodo_flag")
        with c2:
            data_inicio = st.date_input(t("reports.date_start"), value=None, key="rel_periodo_ini") if usar_periodo else None
        with c3:
            data_fim = st.date_input(t("reports.date_end"), value=None, key="rel_periodo_fim") if usar_periodo else None

        if data_inicio and data_fim and data_inicio > data_fim:
            st.warning(t("reports.invalid_period"))
            data_inicio, data_fim = None, None

        if modo == t("reports.mode.stallion") and garanhao_sel:
            base = stock[stock["garanhao_nome"] == garanhao_sel]
            filtros["prop"] = st.multiselect(t("reports.owners"), sorted(base["proprietario_nome"].dropna().unique()) if not base.empty else [], key="rel_f_g_prop")
        elif modo == t("reports.mode.owner") and prop_sel:
            base = stock[stock["dono_id"] == prop_sel] if not stock.empty else pd.DataFrame()
            filtros["gar"] = st.multiselect(t("reports.stallions"), sorted(base["garanhao_nome"].dropna().unique()) if not base.empty else [], key="rel_f_p_gar")
        elif modo == t("reports.mode.container") and contentor_sel:
            base = stock[stock["contentor_id"] == contentor_sel] if (not stock.empty and "contentor_id" in stock.columns) else pd.DataFrame()
            f1, f2, f3, f4 = st.columns(4)
            with f1:
                filtros["gar"] = st.multiselect(t("reports.stallions"), sorted(base["garanhao_nome"].dropna().unique()) if not base.empty else [], key="rel_f_c_gar")
            with f2:
                filtros["prop"] = st.multiselect(t("reports.owners"), sorted(base["proprietario_nome"].dropna().unique()) if not base.empty else [], key="rel_f_c_prop")
            with f3:
                filtros["can"] = st.multiselect(t("reports.canister"), sorted(base["canister"].dropna().unique()) if (not base.empty and "canister" in base.columns) else [], key="rel_f_c_can")
            with f4:
                filtros["and"] = st.multiselect(t("reports.floor"), sorted(base["andar"].dropna().unique()) if (not base.empty and "andar" in base.columns) else [], key="rel_f_c_and")

    if usar_periodo and (data_inicio or data_fim):
        if not insem.empty:
            insem = aplicar_filtro_data(insem, "data_inseminacao", data_inicio, data_fim)
        if not transf.empty:
            transf = aplicar_filtro_data(transf, "data_transferencia", data_inicio, data_fim)
        if not transf_ext.empty:
            transf_ext = aplicar_filtro_data(transf_ext, "data_transferencia", data_inicio, data_fim)
        stock = _filtrar_stock_por_periodo(stock, data_inicio, data_fim)

    render_zone_title(t("reports.zone.results"), "ds-zone-title")

    if modo == t("reports.mode.stallion") and garanhao_sel:
        s = stock[stock["garanhao_nome"] == garanhao_sel] if not stock.empty else pd.DataFrame()
        if filtros.get("prop"):
            s = s[s["proprietario_nome"].isin(filtros["prop"])]
        i = insem[insem["garanhao_nome"] == garanhao_sel] if not insem.empty else pd.DataFrame()
        transf_sel = transf[transf["garanhao"] == garanhao_sel] if not transf.empty else pd.DataFrame()
        te = transf_ext[transf_ext["garanhao"] == garanhao_sel] if not transf_ext.empty else pd.DataFrame()

        left, right = st.columns([6, 2])
        with left:
            st.markdown(f"<div class='reports-results-head'><strong>{t('label.garanhao')}:</strong> {garanhao_sel}</div>", unsafe_allow_html=True)
        with right:
            csv = f"=== {t('label.garanhao').upper()}: {garanhao_sel} ===\n\n"
            for nome, df in {
                t("reports.section.stock"): safe_pick(s, ["proprietario_nome", "data_embriovet", "existencia_atual", "qualidade"]),
                t("reports.section.inseminations"): safe_pick(i, ["data_inseminacao", "egua_nome", "proprietario_nome", "palhetas_gastas"]),
                t("reports.section.transfers_in"): safe_pick(transf_sel, ["data_transferencia", "proprietario_origem", "proprietario_destino", "quantidade"]),
                t("reports.section.transfers_out"): safe_pick(te, ["data_transferencia", "proprietario_origem", "destinatario_externo", "quantidade", "tipo"]),
            }.items():
                if not df.empty:
                    csv += f"\n{nome}:\n{df.to_csv(index=False)}\n"
            st.download_button(t("btn.csv"), csv.encode("utf-8"), f"garanhao_{garanhao_sel}.csv", "text/csv", width="stretch", key="rel_csv_g")
            pdf = gerar_pdf_garanhao(garanhao_sel, s, i, transf_sel, te)
            if pdf:
                st.download_button(t("btn.pdf"), pdf, f"garanhao_{garanhao_sel}.pdf", "application/pdf", width="stretch", key="rel_pdf_g")

        render_kpi_row([
            (t("reports.kpi.straws_stock"), int(to_py(s["existencia_atual"].sum()) or 0) if not s.empty else 0),
            (t("reports.kpi.inseminations"), _contar_operacoes(i)),
            (t("reports.kpi.transfers_in"), len(transf_sel)),
            (t("reports.kpi.transfers_out"), len(te)),
        ])
        if not s.empty:
            st.dataframe(safe_pick(s, ["proprietario_nome", "data_embriovet", "existencia_atual", "qualidade"]).sort_values("existencia_atual", ascending=False), width="stretch", hide_index=True, height=350)
        if not i.empty:
            st.dataframe(safe_pick(i, ["data_inseminacao", "egua_nome", "proprietario_nome", "palhetas_gastas"]).sort_values("data_inseminacao", ascending=False), width="stretch", hide_index=True, height=300)

    elif modo == t("reports.mode.owner") and prop_sel:
        nome = proprietarios[proprietarios["id"] == prop_sel]["nome"].values[0]
        s = stock[stock["dono_id"] == prop_sel] if not stock.empty else pd.DataFrame()
        if filtros.get("gar"):
            s = s[s["garanhao_nome"].isin(filtros["gar"])] if not s.empty else s
        i = insem[insem["dono_id"] == prop_sel] if not insem.empty else pd.DataFrame()
        t_in = transf[transf["proprietario_destino_id"] == prop_sel] if not transf.empty else pd.DataFrame()
        t_out = transf[transf["proprietario_origem_id"] == prop_sel] if not transf.empty else pd.DataFrame()

        left, right = st.columns([6, 2])
        with left:
            st.markdown(f"<div class='reports-results-head'><strong>{t('label.owner')}:</strong> {nome}</div>", unsafe_allow_html=True)
        with right:
            csv = safe_pick(s, ["garanhao_nome", "existencia_atual", "qualidade", "data_embriovet"])
            st.download_button(t("btn.csv"), csv.to_csv(index=False).encode("utf-8"), f"proprietario_{nome}.csv", "text/csv", width="stretch", key="rel_csv_p")

        render_kpi_row([
            (t("reports.kpi.straws_stock"), int(to_py(s["existencia_atual"].sum()) or 0) if not s.empty else 0),
            (t("reports.kpi.inseminations"), _contar_operacoes(i)),
            (t("reports.kpi.transfers_received"), len(t_in)),
            (t("reports.kpi.transfers_sent"), len(t_out)),
        ])
        if not s.empty:
            st.dataframe(safe_pick(s, ["garanhao_nome", "data_embriovet", "existencia_atual", "qualidade"]).sort_values("existencia_atual", ascending=False), width="stretch", hide_index=True, height=350)

    elif modo == t("reports.mode.container") and contentor_sel:
        s = stock[stock["contentor_id"] == contentor_sel].copy() if (not stock.empty and "contentor_id" in stock.columns) else pd.DataFrame()
        if filtros.get("gar"):
            s = s[s["garanhao_nome"].isin(filtros["gar"])] if not s.empty else s
        if filtros.get("prop"):
            s = s[s["proprietario_nome"].isin(filtros["prop"])] if not s.empty else s
        if filtros.get("can") and "canister" in s.columns:
            s = s[s["canister"].isin(filtros["can"])]
        if filtros.get("and") and "andar" in s.columns:
            s = s[s["andar"].isin(filtros["and"])]

        info = contentores[contentores["id"] == contentor_sel].iloc[0]
        st.markdown(f"<div class='reports-results-head'><strong>{t('label.container')}:</strong> {info['codigo']} | <strong>{t('label.description')}:</strong> {info.get('descricao') or '—'}</div>", unsafe_allow_html=True)
        render_kpi_row([
            (t("reports.kpi.lots"), len(s)),
            (t("reports.kpi.straws"), int(to_py(s["existencia_atual"].sum()) or 0) if not s.empty else 0),
            (t("reports.kpi.canisters"), s["canister"].nunique() if (not s.empty and "canister" in s.columns) else 0),
        ])
        if not s.empty:
            st.dataframe(safe_pick(s, ["proprietario_nome", "garanhao_nome", "existencia_atual", "canister", "andar", "data_embriovet", "data_criacao"]), width="stretch", hide_index=True, height=420)
        else:
            st.info(t("reports.no_data_filters"))

    elif modo == t("reports.mode.history") and tipo_hist:
        if tipo_hist == t("reports.history.inseminations"):
            d = insem.copy()
            st.dataframe(safe_pick(d, ["data_inseminacao", "garanhao_nome", "egua_nome", "proprietario_nome", "palhetas_gastas"]).sort_values("data_inseminacao", ascending=False) if not d.empty else d, width="stretch", hide_index=True, height=620)
        elif tipo_hist == t("reports.history.transfer_internal"):
            d = transf.copy()
            st.dataframe(safe_pick(d, ["data_transferencia", "garanhao", "proprietario_origem", "proprietario_destino", "quantidade"]).sort_values("data_transferencia", ascending=False) if not d.empty else d, width="stretch", hide_index=True, height=620)
        elif tipo_hist == t("reports.history.transfer_external"):
            d = transf_ext.copy()
            st.dataframe(safe_pick(d, ["data_transferencia", "garanhao", "proprietario_origem", "destinatario_externo", "tipo", "quantidade", "observacoes"]).sort_values("data_transferencia", ascending=False) if not d.empty else d, width="stretch", hide_index=True, height=620)
        else:
            d = stock.copy()
            st.dataframe(safe_pick(d, ["proprietario_nome", "garanhao_nome", "data_embriovet", "data_criacao", "existencia_atual", "qualidade", "local_armazenagem"]).sort_values("existencia_atual", ascending=False) if not d.empty else d, width="stretch", hide_index=True, height=620)
