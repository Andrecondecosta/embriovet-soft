import streamlit as st
import pandas as pd
import psycopg2
from psycopg2 import pool
import os
import uuid
import base64
import secrets
from pathlib import Path
from dotenv import load_dotenv
from contextlib import contextmanager
import logging
import numpy as np
import datetime as dt
import bcrypt
import hashlib
import time
import json
import unicodedata
import importlib.util
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
import warnings
from modules.ui_kit import (
    inject_all_css_consolidated,
    inject_design_system,
    inject_reports_css,
    inject_stock_css,
    inject_stepper_css,
    render_zone_title,
    render_kpi_strip,
    safe_pick,
    render_stepper,
    inject_shell_css,
    render_header,
    render_sidebar,
    inject_add_stock_form_css,
)
from migration_runner import run_migrations
from modules.stock_reporting import (
    filter_stock_view,
    summarize_stock_by_owner,
    stock_kpis,
    filter_transfer_history,
    filter_lot_transfer_history,
)
from modules.pages.map_page import run_map_page
from modules.pages.stock_page import run_stock_page
from modules.pages.reports_page import run_reports_page
from modules.pages.insemination_page import run_insemination_page
from modules.pages.transfer_page import run_transfer_page
from modules.pages.dashboard_page import run_dashboard_page
from modules.pages.settings_page import run_settings_page
from modules.pages.import_page import run_import_page
from modules.pages.estadias_page import run_estadias_page
from modules.pages.trabalho_diario_page import run_trabalho_diario_page
from modules.i18n import t, get_i18n_diagnostics
from modules.db import to_py, ensure_sslmode_require, build_connection_pool, get_connection, invalidate_data_cache
from modules.repositories.stock_repo import (
    carregar_proprietarios,
    carregar_stock,
    carregar_inseminacoes,
    carregar_transferencias,
    carregar_transferencias_externas,
    carregar_contentores,
    obter_stock_contentor,
    inserir_stock,
    editar_stock,
    deletar_stock,
    transferir_palhetas_parcial,
    transferir_stock_interno,
    transferir_stock_interno_com_localizacao,
    transferir_palhetas_externo,
    transferir_stock_externo,
)
from modules.services.auth_service import (
    criar_hash_password,
    ensure_admin_user_exists,
    verificar_password,
    autenticar_usuario,
    carregar_usuarios,
    adicionar_usuario,
    alterar_password,
    desativar_usuario,
    ativar_usuario,
    save_session_db,
    load_session_db,
    delete_session_db,
    verificar_permissao,
)

THEMES = {
    "blue": "#1D4ED8",
    "green": "#15803D",
    "wine": "#7C2D12",
    "teal": "#0F766E",
    "gray": "#374151",
    "purple": "#5B21B6",
}

# Suprimir avisos repetitivos do pandas para conexões DBAPI2 (psycopg2)
warnings.filterwarnings(
    "ignore",
    message="pandas only supports SQLAlchemy connectable*",
    category=UserWarning,
)

# ------------------------------------------------------------
# Configurar logging
# ------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# Carregar variáveis de ambiente
# ------------------------------------------------------------
load_dotenv("/app/.env", override=True)

# ------------------------------------------------------------
# DB connection pool — definido em modules/db.py.
# `to_py`, `ensure_sslmode_require`, `build_connection_pool` e `get_connection`
# são importados no topo deste ficheiro.
# ------------------------------------------------------------
try:
    build_connection_pool()  # garante que o pool é criado no arranque
except Exception as e:
    logger.error(f"❌ Erro ao criar pool de conexões: {e}")
    st.error(f"Erro de conexão com banco de dados: {e}")
    st.stop()

# ------------------------------------------------------------
# ✅ Migrations automáticas no arranque
# ------------------------------------------------------------
try:
    with get_connection() as conn:
        BASE_DIR = Path(__file__).resolve().parent
        MIGRATIONS_DIR = BASE_DIR / "migrations"
        run_migrations(conn, migrations_dir=str(MIGRATIONS_DIR))
except Exception as e:
    logger.error(f"❌ Falha ao aplicar migrations: {e}")
    st.error(f"Falha ao aplicar migrations: {e}")
    st.stop()

# ------------------------------------------------------------
# ⚙️ App Settings (white-label)
# ------------------------------------------------------------
# app_settings functions extraídas para modules.repositories.settings_repo
# (Pedido 9 — extração pura). Reimportadas no topo deste ficheiro.
from modules.repositories.settings_repo import (
    get_app_settings,
    ensure_app_settings,
    save_app_settings,
    finalize_app_settings,
    update_show_initial_credentials,
    update_language,
    update_branding_settings,
    update_welcome_completed,
)

from modules.repositories.owner_repo import (
    atualizar_status_proprietarios,
    alternar_status_proprietario,
    editar_proprietario,
    atualizar_proprietario_stock,
    adicionar_proprietario,
    deletar_proprietario,
)

from modules.repositories.container_repo import (
    adicionar_contentor,
    editar_contentor,
    atualizar_posicao_contentor,
    atualizar_andar_lote,
    mover_lotes_por_andar,
    deletar_contentor,
)

# Views extraídas para modules.pages (Pedido 9 · Fase 1)
from modules.pages.add_stock_view import _render_add_stock_view
from modules.pages.owners_view import _render_owners_view
from modules.pages.users_view import _render_users_view

from modules.repositories.owner_repo import (
    atualizar_status_proprietarios,
    alternar_status_proprietario,
    editar_proprietario,
    atualizar_proprietario_stock,
    adicionar_proprietario,
    deletar_proprietario,
)


# ------------------------------------------------------------
# 📥 Funções de carregamento de dados
# ------------------------------------------------------------
# `carregar_proprietarios` está em modules.repositories.stock_repo
# (importada no topo deste ficheiro).


def registar_historico_edicao(tabela, record_id, dados_antigos, dados_novos):
    """Regista uma edição no histórico de auditoria"""
    try:
        utilizador = st.session_state.get('user', {}).get('username', '—')
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO historico_edicoes (tabela_nome, record_id, dados_antigos, dados_novos, utilizador_nome)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                tabela, record_id,
                json.dumps(dados_antigos, default=str),
                json.dumps(dados_novos, default=str),
                utilizador
            ))
            conn.commit()
            cur.close()
    except Exception as e:
        logger.error(f"Erro ao registar histórico de edição: {e}")


def gerar_pdf_garanhao(garanhao_nome, dados_stock, dados_insem, dados_transf_int, dados_transf_ext):
    """Gera PDF com histórico completo do garanhão"""
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm)
        elements = []
        styles = getSampleStyleSheet()
        
        # Estilo customizado
        titulo_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=12,
            alignment=1  # Center
        )
        
        subtitulo_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2e5c9a'),
            spaceAfter=10
        )
        
        # Título
        elements.append(Paragraph(f"Relatório Completo: {garanhao_nome}", titulo_style))
        elements.append(Paragraph(f"Gerado em: {dt.datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
        elements.append(Spacer(1, 0.5*cm))
        
        # STOCK
        if not dados_stock.empty:
            elements.append(Paragraph("📦 Stock Atual", subtitulo_style))
            
            stock_data = [['Proprietário', 'Data', 'Existência', 'Qualidade', 'Local']]
            for _, row in dados_stock.iterrows():
                stock_data.append([
                    str(row.get('proprietario_nome', 'N/A'))[:30],
                    str(row.get('data_embriovet', 'N/A'))[:10],
                    str(int(row.get('existencia_atual', 0))),
                    str(row.get('qualidade', '—')),
                    str(row.get('local_armazenagem', 'N/A'))[:20]
                ])
            
            t = Table(stock_data, colWidths=[4*cm, 3*cm, 2.5*cm, 2.5*cm, 4*cm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(t)
            elements.append(Spacer(1, 0.5*cm))
        
        # INSEMINAÇÕES
        if not dados_insem.empty:
            elements.append(Paragraph("📝 Histórico de Inseminações", subtitulo_style))
            
            insem_data = [['Data', 'Égua', 'Proprietário', 'Palhetas']]
            for _, row in dados_insem.iterrows():
                insem_data.append([
                    str(row.get('data_inseminacao', 'N/A'))[:10],
                    str(row.get('egua', 'N/A'))[:25],
                    str(row.get('proprietario_nome', 'N/A'))[:25],
                    str(int(row.get('palhetas_gastas', 0)))
                ])
            
            t = Table(insem_data, colWidths=[3*cm, 5*cm, 5*cm, 3*cm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e5c9a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(t)
            elements.append(Spacer(1, 0.5*cm))
        
        # TRANSFERÊNCIAS INTERNAS
        if not dados_transf_int.empty:
            elements.append(Paragraph("🔄 Transferências Internas", subtitulo_style))
            
            transf_data = [['Data', 'De', 'Para', 'Palhetas']]
            for _, row in dados_transf_int.iterrows():
                transf_data.append([
                    str(row.get('data_transferencia', 'N/A'))[:10],
                    str(row.get('proprietario_origem', 'N/A'))[:20],
                    str(row.get('proprietario_destino', 'N/A'))[:20],
                    str(int(row.get('quantidade', 0)))
                ])
            
            t = Table(transf_data, colWidths=[3*cm, 4.5*cm, 4.5*cm, 3*cm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e5c9a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(t)
            elements.append(Spacer(1, 0.5*cm))
        
        # TRANSFERÊNCIAS EXTERNAS
        if not dados_transf_ext.empty:
            elements.append(Paragraph("📤 Transferências Externas (Vendas/Doações)", subtitulo_style))
            
            for _, row in dados_transf_ext.iterrows():
                transf_ext_data = [['Data', 'De', 'Para', 'Palhetas', 'Tipo']]
                transf_ext_data.append([
                    str(row.get('data_transferencia', 'N/A'))[:10],
                    str(row.get('proprietario_origem', 'N/A'))[:18],
                    str(row.get('destinatario_externo', 'N/A'))[:18],
                    str(int(row.get('quantidade', 0))),
                    str(row.get('tipo', 'N/A'))[:15]
                ])
                
                t = Table(transf_ext_data, colWidths=[2.5*cm, 3.5*cm, 3.5*cm, 2.5*cm, 3*cm])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e5c9a')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(t)
                
                # Adicionar observações se existirem
                obs = row.get('observacoes', '')
                if obs and str(obs) != 'nan' and str(obs).strip():
                    obs_style = ParagraphStyle('Obs', parent=styles['Normal'], fontSize=9, leftIndent=10)
                    elements.append(Paragraph(f"<b>Observações:</b> {str(obs)}", obs_style))
                
                elements.append(Spacer(1, 0.3*cm))
        
        # Gerar PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        logger.error(f"Erro ao gerar PDF: {e}")
        return None

def registrar_inseminacao(registro):
    """Registra uma inseminação e atualiza o stock"""
    try:
        palhetas_val = to_py(registro.get("palhetas")) or 0
        try:
            palhetas_int = int(palhetas_val)
        except Exception:
            st.error(t("error.straws_numeric"))
            return False

        if palhetas_int <= 0:
            st.error(t("error.straws_positive"))
            return False

        if not registro.get("egua"):
            st.error(t("error.mare_required"))
            return False

        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute(
                "SELECT existencia_atual FROM estoque_dono WHERE id = %s",
                (to_py(registro.get("stock_id")),),
            )
            result = cur.fetchone()

            if not result:
                st.error(t("error.stock_not_found"))
                return False

            existencia_atual = result[0] or 0
            try:
                existencia_atual = int(existencia_atual)
            except Exception:
                existencia_atual = 0

            if existencia_atual < palhetas_int:
                st.error(f"❌ Estoque insuficiente! Disponível: {existencia_atual} palhetas")
                return False

            cur.execute(
                """
                INSERT INTO inseminacoes (garanhao, dono_id, data_inseminacao, egua, protocolo, palhetas_gastas)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    to_py(registro.get("garanhao")),
                    to_py(registro.get("dono_id")),
                    to_py(registro.get("data")),
                    to_py(registro.get("egua")),
                    to_py(registro.get("protocolo")),
                    to_py(palhetas_int),
                ),
            )

            cur.execute(
                """
                UPDATE estoque_dono SET existencia_atual = existencia_atual - %s
                WHERE id = %s
                """,
                (to_py(palhetas_int), to_py(registro.get("stock_id"))),
            )

            conn.commit()
            cur.close()
            
            # Verificar e desativar proprietários com stock = 0
            atualizar_status_proprietarios()
            invalidate_data_cache()
            
            logger.info(f"Inseminação registrada: {registro.get('egua')} - {palhetas_int} palhetas")
            return True

    except Exception as e:
        logger.error(f"Erro ao registrar inseminação: {e}")
        st.error(f"Erro ao registrar inseminação: {e}")
        return False


def registrar_inseminacao_multiplas(registros, data_inseminacao, egua, insemination_id=None, observacoes=None, edit_operation_id=None):
    """Registra múltiplas linhas de inseminação ou atualiza uma operação existente.
    
    - edit_operation_id: UUID da operação a editar (apaga todos os lotes e re-insere)
    - insemination_id: ID da linha individual a editar (backward compat para operações antigas)
    """
    try:
        if not egua:
            st.error(t("error.mare_required"))
            return False
        if not registros:
            st.error(t("error.select_lot_line"))
            return False

        total_pal = sum(int(r.get("palhetas", 0)) for r in registros)

        with get_connection() as conn:
            cur = conn.cursor()

            # ─── MODO EDIÇÃO COM operation_id ────────────────────────────────────
            if edit_operation_id:
                # 1. Carregar dados antigos de TODOS os lotes da operação
                cur.execute("""
                    SELECT i.id, i.estoque_id, i.palhetas_gastas,
                           i.garanhao, i.dono_id, i.egua, i.data_inseminacao,
                           i.protocolo, i.observacoes, d.nome AS dono_nome
                    FROM inseminacoes i
                    LEFT JOIN dono d ON i.dono_id = d.id
                    WHERE i.operation_id = %s
                    ORDER BY i.id
                """, (edit_operation_id,))
                old_rows = cur.fetchall()

                if not old_rows:
                    # operation_id não encontrado → fallback para single-row edit
                    edit_operation_id = None
                else:
                    old_for_audit = old_rows[0]  # usar primeiro para auditoria

                    # 2. Devolver palhetas de TODOS os lotes antigos ao stock
                    for row in old_rows:
                        if row[1]:  # estoque_id not null
                            cur.execute(
                                "UPDATE estoque_dono SET existencia_atual = existencia_atual + %s WHERE id = %s",
                                (int(row[2] or 0), row[1])
                            )

                    # 3. Eliminar TODOS os registos antigos da operação
                    cur.execute(
                        "DELETE FROM inseminacoes WHERE operation_id = %s",
                        (edit_operation_id,)
                    )

                    # 4. Re-inserir todos os novos lotes com o mesmo operation_id
                    first_new_id = None
                    for reg in registros:
                        stock_id = to_py(reg.get("stock_id"))
                        palhetas = int(reg.get("palhetas", 0))
                        cur.execute("SELECT existencia_atual FROM estoque_dono WHERE id = %s", (stock_id,))
                        result = cur.fetchone()
                        if not result:
                            st.error(f"❌ Lote #{stock_id} não encontrado")
                            return False
                        if int(result[0] or 0) < palhetas:
                            st.error(f"❌ Estoque insuficiente no lote #{stock_id}! Disponível: {int(result[0] or 0)}")
                            return False
                        cur.execute("""
                            INSERT INTO inseminacoes (garanhao, dono_id, data_inseminacao, egua,
                                protocolo, palhetas_gastas, observacoes, utilizador, estoque_id, operation_id, atualizado)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::uuid, TRUE)
                            RETURNING id
                        """, (
                            to_py(reg.get("garanhao")), to_py(reg.get("dono_id")),
                            to_py(data_inseminacao), to_py(egua),
                            to_py(reg.get("protocolo")), palhetas,
                            to_py(observacoes), st.session_state.get('user', {}).get('username', '—'),
                            stock_id, edit_operation_id,
                        ))
                        new_row = cur.fetchone()
                        if first_new_id is None and new_row:
                            first_new_id = new_row[0]
                        cur.execute(
                            "UPDATE estoque_dono SET existencia_atual = existencia_atual - %s WHERE id = %s",
                            (palhetas, stock_id)
                        )

                    conn.commit()

                    # Auditoria - usar o ID do NOVO registo para que apareça no dashboard
                    first = old_for_audit
                    audit_record_id = first_new_id or first[0]
                    cur2 = conn.cursor()
                    cur2.execute("SELECT nome FROM dono WHERE id = %s", (to_py(registros[0].get("dono_id")),))
                    new_dono = (cur2.fetchone() or ['—'])[0]
                    cur2.close()
                    registar_historico_edicao('inseminacoes', audit_record_id, {
                        'Égua': str(first[5] or '—'), 'Garanhão': str(first[3] or '—'),
                        'Palhetas': int(first[2] or 0), 'Data': str(first[6] or ''),
                        'Proprietário': str(first[9] or '—'), 'Observações': str(first[8] or '—'),
                    }, {
                        'Égua': str(egua or '—'), 'Garanhão': str(registros[0].get("garanhao", '—')),
                        'Palhetas': total_pal, 'Data': str(data_inseminacao or ''),
                        'Proprietário': str(new_dono or '—'), 'Observações': str(observacoes or '—'),
                    })
                    logger.info(f"✏️ Operação ATUALIZADA (op={edit_operation_id}): égua={egua}, total={total_pal}")
                    cur.close()
                    atualizar_status_proprietarios()
                    invalidate_data_cache()
                    return True

            # ─── MODO EDIÇÃO SINGLE ROW (backward compat) ────────────────────────
            if insemination_id and not edit_operation_id:
                cur.execute("""
                    SELECT i.garanhao, i.dono_id, i.palhetas_gastas, i.egua,
                           i.data_inseminacao, i.protocolo,
                           d.nome AS dono_nome, i.observacoes, i.estoque_id
                    FROM inseminacoes i
                    LEFT JOIN dono d ON i.dono_id = d.id
                    WHERE i.id = %s
                """, (insemination_id,))
                old_data = cur.fetchone()

                if old_data:
                    old_garanhao, old_dono_id, old_palhetas, old_egua, old_data_insem, old_protocolo, old_dono_nome, old_observacoes, old_estoque_id = old_data
                    if old_estoque_id:
                        cur.execute(
                            "UPDATE estoque_dono SET existencia_atual = existencia_atual + %s WHERE id = %s",
                            (int(old_palhetas), old_estoque_id)
                        )

                primeiro_registro = registros[0]
                cur.execute("""
                    UPDATE inseminacoes
                    SET garanhao = %s, dono_id = %s, data_inseminacao = %s,
                        egua = %s, palhetas_gastas = %s, observacoes = %s,
                        atualizado = TRUE, utilizador = %s, estoque_id = %s
                    WHERE id = %s
                """, (
                    to_py(primeiro_registro.get("garanhao")), to_py(primeiro_registro.get("dono_id")),
                    to_py(data_inseminacao), to_py(egua), total_pal,
                    to_py(observacoes), st.session_state.get('user', {}).get('username', '—'),
                    to_py(primeiro_registro.get("stock_id")), insemination_id
                ))

                for reg in registros:
                    stock_id = to_py(reg.get("stock_id"))
                    palhetas = int(reg.get("palhetas", 0))
                    cur.execute("SELECT existencia_atual FROM estoque_dono WHERE id = %s", (stock_id,))
                    result = cur.fetchone()
                    if not result:
                        st.error(f"❌ Lote #{stock_id} não encontrado")
                        return False
                    if int(result[0] or 0) < palhetas:
                        st.error(f"❌ Estoque insuficiente! Disponível: {int(result[0] or 0)}")
                        return False
                    cur.execute(
                        "UPDATE estoque_dono SET existencia_atual = existencia_atual - %s WHERE id = %s",
                        (palhetas, stock_id)
                    )

                conn.commit()

                if old_data:
                    cur2 = conn.cursor()
                    cur2.execute("SELECT nome FROM dono WHERE id = %s", (to_py(primeiro_registro.get("dono_id")),))
                    new_dono_nome = (cur2.fetchone() or ['—'])[0]
                    cur2.close()
                    registar_historico_edicao('inseminacoes', insemination_id, {
                        'Égua': str(old_egua or '—'), 'Garanhão': str(old_garanhao or '—'),
                        'Palhetas': int(old_palhetas or 0), 'Data': str(old_data_insem or ''),
                        'Protocolo': str(old_protocolo or '—'), 'Proprietário': str(old_dono_nome or '—'),
                        'Observações': str(old_observacoes or '—'),
                    }, {
                        'Égua': str(egua or '—'), 'Garanhão': str(primeiro_registro.get("garanhao", '—')),
                        'Palhetas': total_pal, 'Data': str(data_inseminacao or ''),
                        'Protocolo': str(primeiro_registro.get("protocolo", '—')),
                        'Proprietário': str(new_dono_nome or '—'), 'Observações': str(observacoes or '—'),
                    })

                logger.info(f"✏️ Inseminação ATUALIZADA: ID {insemination_id}, égua={egua}")
                cur.close()
                atualizar_status_proprietarios()
                invalidate_data_cache()
                return True

            # ─── MODO CRIAÇÃO ─────────────────────────────────────────────────────
            import uuid as _uuid
            new_operation_id = str(_uuid.uuid4())

            for reg in registros:
                stock_id = to_py(reg.get("stock_id"))
                palhetas = int(reg.get("palhetas", 0))

                cur.execute("SELECT existencia_atual FROM estoque_dono WHERE id = %s", (stock_id,))
                result = cur.fetchone()
                if not result:
                    st.error(f"❌ Lote #{stock_id} não encontrado")
                    return False
                if int(result[0] or 0) < palhetas:
                    st.error(f"❌ Estoque insuficiente! Disponível: {int(result[0] or 0)}")
                    return False

                cur.execute("""
                    INSERT INTO inseminacoes (garanhao, dono_id, data_inseminacao, egua,
                        protocolo, palhetas_gastas, observacoes, utilizador, estoque_id, operation_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::uuid)
                """, (
                    to_py(reg.get("garanhao")), to_py(reg.get("dono_id")),
                    to_py(data_inseminacao), to_py(egua),
                    to_py(reg.get("protocolo")), palhetas,
                    to_py(observacoes), st.session_state.get('user', {}).get('username', '—'),
                    stock_id, new_operation_id,
                ))
                cur.execute(
                    "UPDATE estoque_dono SET existencia_atual = existencia_atual - %s WHERE id = %s",
                    (palhetas, stock_id)
                )

            conn.commit()
            cur.close()
            atualizar_status_proprietarios()
            invalidate_data_cache()
            logger.info(f"✅ Inseminação criada (op={new_operation_id}): {egua} - {total_pal} palhetas")
            return True

    except Exception as e:
        logger.error(f"Erro ao processar inseminação: {e}")
        st.error(f"Erro ao processar inseminação: {e}")
        return False

def registrar_inseminacao_linha(garanhao, dono_id, data_inseminacao, egua, protocolo, palhetas, stock_id):
    """Registra UMA linha de inseminação"""
    if not egua:
        st.error(t("error.mare_required"))
        return False

    if not stock_id:
        st.error(t("error.select_lot_line"))
        return False

    try:
        with get_connection() as conn:
            cur = conn.cursor()

            # Validar stock
            cur.execute("SELECT existencia_atual FROM estoque_dono WHERE id = %s", (stock_id,))
            result = cur.fetchone()

            if not result:
                st.error(f"❌ Lote #{stock_id} não encontrado")
                return False

            existencia = int(result[0] or 0)

            if existencia < palhetas:
                st.error(f"❌ Estoque insuficiente! Disponível: {existencia} palhetas")
                return False

            # Inserir inseminação
            cur.execute(
                """
                INSERT INTO inseminacoes (garanhao, dono_id, data_inseminacao, egua, protocolo, palhetas_gastas)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (garanhao, dono_id, data_inseminacao, egua, protocolo, palhetas),
            )

            # Descontar palhetas
            cur.execute(
                "UPDATE estoque_dono SET existencia_atual = existencia_atual - %s WHERE id = %s",
                (palhetas, stock_id),
            )

            conn.commit()
            cur.close()

            atualizar_status_proprietarios()
            invalidate_data_cache()
            return True

    except Exception as e:
        logger.error(f"Erro ao registrar inseminação: {e}")
        st.error(f"Erro ao registrar inseminação: {e}")
        return False

# ------------------------------------------------------------
# 👥 Funções de Gestão de Proprietários
# ------------------------------------------------------------

# Funções de contentores extraídas para modules.repositories.container_repo
# (Pedido 9 — extração pura). Reimportadas no topo deste ficheiro.


# `obter_stock_contentor` está em modules.repositories.stock_repo
# (importada no topo deste ficheiro).

def aplicar_filtro_data(df, coluna_data, data_inicio=None, data_fim=None):
    """Aplica filtro de data em um DataFrame"""
    if df.empty:
        return df
    
    if coluna_data not in df.columns:
        return df
    
    df_filtrado = df.copy()
    
    try:
        # Converter coluna para datetime se necessário
        if not pd.api.types.is_datetime64_any_dtype(df_filtrado[coluna_data]):
            df_filtrado[coluna_data] = pd.to_datetime(df_filtrado[coluna_data], errors='coerce')
        
        # Aplicar filtros
        if data_inicio:
            df_filtrado = df_filtrado[df_filtrado[coluna_data] >= pd.Timestamp(data_inicio)]
        
        if data_fim:
            df_filtrado = df_filtrado[df_filtrado[coluna_data] <= pd.Timestamp(data_fim)]
        
        return df_filtrado
    except Exception as e:
        logger.error(f"Erro ao aplicar filtro de data: {e}")
        return df


# As 3 funções de transferência (`transferir_palhetas_parcial`,
# `transferir_stock_interno_com_localizacao`, `transferir_palhetas_externo`)
# e os aliases (`transferir_stock_interno`, `transferir_stock_externo`)
# estão em modules.repositories.stock_repo (importados no topo deste
# ficheiro).


def atualizar_transferencia_interna(transfer_id, novo_estoque_id, novo_dest_id, nova_quantidade,
                                     contentor_id_novo=None, canister_novo=None, andar_novo=None):
    """Atualiza uma transferência interna existente revertendo a antiga e aplicando a nova"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            # 1. Carregar dados antigos da transferência
            cur.execute("""
                SELECT estoque_id, proprietario_origem_id, proprietario_destino_id, quantidade
                FROM transferencias WHERE id = %s
            """, (transfer_id,))
            old = cur.fetchone()
            if not old:
                st.error("Transferência não encontrada")
                return False

            old_estoque_id, old_origem_id, old_destino_id, old_quantidade = old
            old_quantidade = int(old_quantidade)

            # 2. Reverter: devolver palhetas ao lote de origem
            cur.execute("""
                UPDATE estoque_dono SET existencia_atual = existencia_atual + %s WHERE id = %s
            """, (old_quantidade, old_estoque_id))

            # 3. Reverter: remover palhetas do destino (procurar lote do destino com mesmo garanhão)
            cur.execute("""
                SELECT id, existencia_atual FROM estoque_dono
                WHERE dono_id = %s AND garanhao = (SELECT garanhao FROM estoque_dono WHERE id = %s)
                ORDER BY id DESC LIMIT 1
            """, (old_destino_id, old_estoque_id))
            lote_dest = cur.fetchone()
            if lote_dest:
                dest_lote_id, dest_exist = lote_dest
                nova_exist_dest = int(dest_exist) - old_quantidade
                if nova_exist_dest <= 0:
                    cur.execute("DELETE FROM estoque_dono WHERE id = %s", (dest_lote_id,))
                else:
                    cur.execute("UPDATE estoque_dono SET existencia_atual = %s WHERE id = %s",
                                (nova_exist_dest, dest_lote_id))

            # 4. Carregar dados do novo lote de origem
            cur.execute("""
                SELECT garanhao, dono_id, existencia_atual, data_embriovet, origem_externa,
                       qualidade, concentracao, motilidade, local_armazenagem, certificado,
                       dose, observacoes, cor, contentor_id, canister, andar, animal_id
                FROM estoque_dono WHERE id = %s
            """, (to_py(novo_estoque_id),))
            origem = cur.fetchone()
            if not origem:
                st.error("Lote de origem não encontrado")
                return False

            (garanhao, prop_orig_id, exist_atual, data_emb, orig_ext,
             qual, conc, mot, local, cert, dose, obs, cor, cont_id, can, andar, animal_id) = origem

            nova_quantidade_int = int(nova_quantidade)
            exist_atual_int = int(exist_atual or 0)

            if nova_quantidade_int <= 0:
                st.error(t("error.qty_positive"))
                return False

            if nova_quantidade_int > exist_atual_int:
                st.error(f"❌ Quantidade insuficiente! Disponível: {exist_atual_int}")
                return False

            # 5. Deduzir do novo lote de origem
            cur.execute("""
                UPDATE estoque_dono SET existencia_atual = existencia_atual - %s WHERE id = %s
            """, (nova_quantidade_int, to_py(novo_estoque_id)))

            # 6. Determinar localização final
            final_cont = to_py(contentor_id_novo) if contentor_id_novo else to_py(cont_id)
            final_can = to_py(canister_novo) if canister_novo else to_py(can)
            final_andar = to_py(andar_novo) if andar_novo else to_py(andar)

            # 7. Verificar se já existe lote do novo destino
            cur.execute("""
                SELECT id FROM estoque_dono
                WHERE garanhao = %s AND dono_id = %s AND id != %s
                AND COALESCE(contentor_id, 0) = COALESCE(%s, 0)
                AND COALESCE(canister, 0) = COALESCE(%s, 0)
                AND COALESCE(andar, 0) = COALESCE(%s, 0)
                LIMIT 1
            """, (to_py(garanhao), to_py(novo_dest_id), to_py(novo_estoque_id),
                  final_cont, final_can, final_andar))
            lote_destino = cur.fetchone()

            if lote_destino:
                cur.execute("UPDATE estoque_dono SET existencia_atual = existencia_atual + %s WHERE id = %s",
                            (nova_quantidade_int, lote_destino[0]))
            else:
                cur.execute("""
                    INSERT INTO estoque_dono (
                        garanhao, dono_id, data_embriovet, origem_externa,
                        palhetas_produzidas, qualidade, concentracao, motilidade,
                        local_armazenagem, certificado, dose, observacoes,
                        quantidade_inicial, existencia_atual, cor,
                        contentor_id, canister, andar, animal_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    to_py(garanhao), to_py(novo_dest_id), to_py(data_emb), to_py(orig_ext),
                    nova_quantidade_int, to_py(qual), to_py(conc), to_py(mot),
                    to_py(local), to_py(cert), to_py(dose), to_py(obs),
                    nova_quantidade_int, nova_quantidade_int, to_py(cor),
                    final_cont, final_can, final_andar, to_py(animal_id)
                ))

            # 8. Atualizar registo de transferência e marcar como editado
            cur.execute("""
                UPDATE transferencias
                SET estoque_id = %s, proprietario_origem_id = %s, proprietario_destino_id = %s,
                    quantidade = %s, data_transferencia = CURRENT_TIMESTAMP, atualizado = TRUE,
                    utilizador = %s
                WHERE id = %s
            """, (to_py(novo_estoque_id), to_py(prop_orig_id), to_py(novo_dest_id),
                  nova_quantidade_int, st.session_state.get('user', {}).get('username', '—'), transfer_id))

            conn.commit()
            cur.close()

            # 9. Registar auditoria (buscar nomes dos proprietários)
            try:
                with get_connection() as conn2:
                    cur2 = conn2.cursor()
                    cur2.execute("SELECT nome FROM dono WHERE id = %s", (old_destino_id,))
                    old_dest_nome = (cur2.fetchone() or ['—'])[0]
                    cur2.execute("SELECT nome FROM dono WHERE id = %s", (to_py(novo_dest_id),))
                    new_dest_nome = (cur2.fetchone() or ['—'])[0]
                    cur2.close()
                registar_historico_edicao('transferencias', transfer_id, {
                    'Quantidade': old_quantidade,
                    'Destino': str(old_dest_nome),
                }, {
                    'Quantidade': nova_quantidade_int,
                    'Destino': str(new_dest_nome),
                })
            except Exception as ae:
                logger.warning(f"Auditoria de transferência interna não registada: {ae}")

            atualizar_status_proprietarios()
            invalidate_data_cache()
            logger.info(f"✏️ Transferência interna ATUALIZADA: ID {transfer_id}")
            return True

    except Exception as e:
        logger.error(f"Erro ao atualizar transferência interna: {e}")
        st.error(f"Erro ao atualizar transferência: {e}")
        return False


def atualizar_transferencia_externa(transfer_id, novo_estoque_id, novo_destinatario,
                                     nova_quantidade, novo_tipo, novas_obs):
    """Atualiza uma transferência externa existente revertendo a antiga e aplicando a nova"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            # 1. Carregar dados antigos completos
            cur.execute("""
                SELECT estoque_id, proprietario_origem_id, quantidade, destinatario_externo, tipo
                FROM transferencias_externas WHERE id = %s
            """, (transfer_id,))
            old = cur.fetchone()
            if not old:
                st.error("Transferência não encontrada")
                return False

            old_estoque_id, old_origem_id, old_quantidade, old_destinatario, old_tipo = old
            old_quantidade = int(old_quantidade)

            # 2. Reverter: devolver palhetas ao lote de origem
            cur.execute("""
                UPDATE estoque_dono SET existencia_atual = existencia_atual + %s WHERE id = %s
            """, (old_quantidade, old_estoque_id))

            # 3. Carregar dados do novo lote de origem
            cur.execute("""
                SELECT dono_id, existencia_atual, garanhao
                FROM estoque_dono WHERE id = %s
            """, (to_py(novo_estoque_id),))
            origem = cur.fetchone()
            if not origem:
                st.error("Lote de origem não encontrado")
                return False

            prop_orig_id, exist_atual, garanhao = origem
            nova_quantidade_int = int(nova_quantidade)
            exist_atual_int = int(exist_atual or 0)

            if nova_quantidade_int <= 0:
                st.error(t("error.qty_positive"))
                return False

            if nova_quantidade_int > exist_atual_int:
                st.error(f"❌ Quantidade insuficiente! Disponível: {exist_atual_int}")
                return False

            # 4. Deduzir do novo lote de origem
            cur.execute("""
                UPDATE estoque_dono SET existencia_atual = existencia_atual - %s WHERE id = %s
            """, (nova_quantidade_int, to_py(novo_estoque_id)))

            # 5. Atualizar registo e marcar como editado
            cur.execute("""
                UPDATE transferencias_externas
                SET estoque_id = %s, proprietario_origem_id = %s, garanhao = %s,
                    destinatario_externo = %s, quantidade = %s, tipo = %s,
                    observacoes = %s, data_transferencia = CURRENT_TIMESTAMP, atualizado = TRUE,
                    utilizador = %s
                WHERE id = %s
            """, (to_py(novo_estoque_id), to_py(prop_orig_id), to_py(garanhao),
                  to_py(novo_destinatario), nova_quantidade_int,
                  to_py(novo_tipo), to_py(novas_obs), st.session_state.get('user', {}).get('username', '—'), transfer_id))

            conn.commit()
            cur.close()

            # 6. Registar auditoria
            registar_historico_edicao('transferencias_externas', transfer_id, {
                'Quantidade': old_quantidade,
                'Destinatário': str(old_destinatario or '—'),
                'Tipo': str(old_tipo or '—'),
            }, {
                'Quantidade': nova_quantidade_int,
                'Destinatário': str(novo_destinatario or '—'),
                'Tipo': str(novo_tipo or '—'),
            })

            atualizar_status_proprietarios()
            invalidate_data_cache()
            logger.info(f"✏️ Transferência externa ATUALIZADA: ID {transfer_id}")
            return True

    except Exception as e:
        logger.error(f"Erro ao atualizar transferência externa: {e}")
        st.error(f"Erro ao atualizar transferência: {e}")
        return False


# ------------------------------------------------------------
# 🖼️ Interface Streamlit
# ------------------------------------------------------------
st.set_page_config(
    page_title=os.getenv("APP_TITLE", "Sistema"),
    layout=os.getenv("APP_LAYOUT", "wide"),
    initial_sidebar_state="expanded",
    page_icon="🐴",
)

# CSS inicial limpo — apenas esconde o menu nativo do Streamlit
st.markdown(
    """
    <style>
    [data-testid="stMainMenu"] { display:none !important; }
    footer { display:none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Injetar TODO o CSS consolidado em um único bloco
inject_all_css_consolidated()

# ------------------------------------------------------------
# 🔐 Sistema de Login
# ------------------------------------------------------------

def mostrar_tela_login(app_settings):
    """Exibe tela de login com design limpo e sem artefactos visuais"""
    nome_empresa = (app_settings or {}).get("company_name") or "Sistema"
    logo_base64  = (app_settings or {}).get("logo_base64")
    cor          = (app_settings or {}).get("primary_color") or "#E85D4A"

    # Construir bloco do logo/título (HTML puro — sem widgets Streamlit)
    if logo_base64:
        # logo_base64 pode já ter o prefixo data:image/... completo
        img_src = logo_base64 if logo_base64.startswith("data:") else f"data:image/png;base64,{logo_base64}"
        logo_html = (
            f"<img src='{img_src}' "
            f"style='max-width:72px;height:auto;border-radius:10px;display:block;margin:0 auto 14px;'/>"
        )
    else:
        initials = "".join([p[0].upper() for p in nome_empresa.split()[:2] if p]) or "S"
        logo_html = (
            f"<div style='width:52px;height:52px;background:{cor};border-radius:12px;"
            f"display:flex;align-items:center;justify-content:center;color:#fff;"
            f"font-weight:700;font-size:1.2rem;margin:0 auto 14px;'>{initials}</div>"
        )

    # CSS da página de login
    st.markdown(
        f"""
        <style>
            #MainMenu, footer, [data-testid="stHeader"],
            [data-testid="stToolbar"] {{ display: none !important; }}

            .stApp {{
                background: #f1f5f9 !important;
            }}

            /* O formulário torna-se o card */
            [data-testid="stForm"] {{
                background: #ffffff !important;
                border-radius: 16px !important;
                padding: 32px 28px 24px !important;
                box-shadow: 0 4px 32px rgba(15,23,42,0.10) !important;
                border: 1px solid #e2e8f0 !important;
                margin-top: 0 !important;
            }}

            /* Inputs */
            [data-testid="stForm"] input {{
                border-radius: 9px !important;
                border: 1.5px solid #e2e8f0 !important;
                font-size: 0.95rem !important;
                transition: border-color 0.15s, box-shadow 0.15s !important;
            }}
            [data-testid="stForm"] input:focus {{
                border-color: {cor} !important;
                box-shadow: 0 0 0 3px {cor}22 !important;
            }}

            /* Botão de submeter — cor da app */
            button[data-testid="stBaseButton-primaryFormSubmit"] {{
                background: {cor} !important;
                border-color: {cor} !important;
                color: #ffffff !important;
                border-radius: 10px !important;
                height: 46px !important;
                font-weight: 700 !important;
                font-size: 1rem !important;
                letter-spacing: 0.02em;
                margin-top: 6px;
                transition: opacity 0.15s, transform 0.12s !important;
            }}
            button[data-testid="stBaseButton-primaryFormSubmit"]:hover {{
                opacity: 0.88 !important;
                transform: translateY(-1px) !important;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Usar colunas para centrar o card naturalmente
    _, col, _ = st.columns([1, 2, 1])

    with col:
        # Cabeçalho: logo + nome + subtítulo (HTML puro, sem artefactos)
        st.markdown(
            f"""
            <div style="text-align:center; padding: 28px 0 20px 0;">
                {logo_html}
                <div style="font-size:1.55rem; font-weight:700; color:#0f172a; line-height:1.2;">
                    {nome_empresa}
                </div>
                <div style="font-size:0.88rem; color:#64748b; margin-top:5px;">
                    {t('login.subtitle')}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Formulário Streamlit nativo (styled via CSS acima como card)
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input(
                t("auth.username"),
                placeholder=t("auth.username_placeholder"),
                label_visibility="collapsed",
            )
            password = st.text_input(
                t("auth.password"),
                type="password",
                placeholder=t("auth.password_placeholder"),
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button(
                t("auth.login"),
                type="primary",
                width="stretch",
            )

            if submitted:
                if not username or not password:
                    st.error(t("login.missing"))
                else:
                    user = autenticar_usuario(username, password)
                    if user:
                        token = str(uuid.uuid4())
                        save_session_db(token, user)
                        st.session_state['user'] = user
                        st.session_state['auth_token'] = token
                        st.query_params.session = token
                        st.success(t("login.welcome", name=user["nome"]))
                        st.rerun()
                    else:
                        st.error(t("login.invalid"))

        # Rodapé de segurança
        st.markdown(
            f"<div style='text-align:center;font-size:0.78rem;color:#94a3b8;margin-top:12px;'>"
            f"🔒 {t('login.secure')}</div>",
            unsafe_allow_html=True,
        )
        

def render_change_credentials(user, app_settings):
    st.title(t("security.title"))
    st.info(t("security.info"))

    with st.form("change_credentials_form"):
        novo_username = st.text_input(t("security.username"), value=user.get("username", ""))
        nova_password = st.text_input(t("security.new_password"), type="password")
        confirmar_password = st.text_input(t("security.confirm_password"), type="password")
        submitted = st.form_submit_button(t("security.save"), type="primary", width="stretch")

    if submitted:
        if not novo_username:
            st.error(t("error.username_required"))
            return
        if not nova_password or not confirmar_password:
            st.error(t("error.password_required"))
            return
        if nova_password != confirmar_password:
            st.error(t("error.passwords_mismatch"))
            return

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM usuarios WHERE username = %s AND id <> %s",
                (novo_username, user["id"]),
            )
            if cur.fetchone():
                cur.close()
                st.error(t("security.username_exists"))
                return

            nova_hash = criar_hash_password(nova_password)
            cur.execute(
                """
                UPDATE usuarios
                SET username = %s,
                    password_hash = %s,
                    must_change_password = FALSE,
                    updated_at = now()
                WHERE id = %s
                """,
                (novo_username, nova_hash, user["id"]),
            )
            conn.commit()
            cur.close()

        update_show_initial_credentials(False)
        st.session_state['user']['username'] = novo_username
        st.session_state['user']['must_change_password'] = False
        st.success(t("security.success"))
        st.rerun()


def render_welcome_page():
    st.markdown(
        """
        <style>
            header[data-testid="stHeader"] { display: none !important; }
            div[data-testid="stToolbar"] { display: none !important; }
            section[data-testid="stSidebar"] { display: none !important; }
            div[data-testid="stAppViewContainer"] { padding-top: 0 !important; }
            section.main > div.block-container { padding-top: 0 !important; padding-bottom: 0 !important; }

            .welcome-wrapper {
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                background: #f8fafc;
            }
            .welcome-card {
                max-width: 680px;
                text-align: center;
                padding: 40px 24px;
            }
            .welcome-title {
                font-size: 42px;
                font-weight: 700;
                color: #0f172a;
                margin-bottom: 16px;
            }
            .welcome-subtitle {
                font-size: 20px;
                font-weight: 500;
                color: #334155;
                margin-bottom: 20px;
            }
            .welcome-description {
                font-size: 16px;
                color: #64748b;
                margin-bottom: 32px;
                line-height: 1.6;
            }
            .welcome-footer {
                font-size: 12px;
                color: #94a3b8;
                margin-top: 24px;
            }
            .welcome-card .stButton > button {
                width: 100%;
                height: 52px;
                border-radius: 12px;
                font-size: 16px;
                font-weight: 600;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='welcome-wrapper'><div class='welcome-card'>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="welcome-title">{t("welcome.title")}</div>
        <div class="welcome-subtitle">{t("welcome.subtitle")}</div>
        <div class="welcome-description">{t("welcome.text")}</div>
        """,
        unsafe_allow_html=True,
    )
    if st.button(t("welcome.start"), type="primary", width="stretch"):
        if update_welcome_completed(True):
            st.rerun()
    st.markdown(
        f"<div class='welcome-footer'>{t('welcome.powered')}</div></div></div>",
        unsafe_allow_html=True,
    )


def render_onboarding(app_settings):
    inject_stock_css()
    inject_reports_css()

    st.title(t("onboarding.title"))
    st.caption(t("onboarding.subtitle"))

    if "onboarding_company_name" not in st.session_state:
        st.session_state["onboarding_company_name"] = app_settings.get("company_name") or ""
    if "onboarding_theme_key" not in st.session_state:
        st.session_state["onboarding_theme_key"] = app_settings.get("theme_key") or "blue"
    if "onboarding_admin_username" not in st.session_state:
        st.session_state["onboarding_admin_username"] = "admin"
    if "onboarding_admin_password" not in st.session_state:
        st.session_state["onboarding_admin_password"] = secrets.token_urlsafe(8)

    if app_settings.get("logo_base64") and "onboarding_logo_base64" not in st.session_state:
        st.session_state["onboarding_logo_base64"] = app_settings.get("logo_base64")

    logo_preview = st.session_state.get("onboarding_logo_base64")
    nome_preview = st.session_state.get("onboarding_company_name")

    if logo_preview:
        st.markdown(
            f"""
            <div style='display:flex; align-items:center; gap:12px; margin-bottom:8px;'>
                <img src='{logo_preview}' style='height:36px;'/>
                <h3 style='margin:0;'>{nome_preview}</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )

    render_zone_title(t("onboarding.zone_brand"), "insem-zone-title")
    col_a1, col_a2 = st.columns([2, 1.2])
    with col_a1:
        company_name = st.text_input(t("onboarding.company"), key="onboarding_company_name")
    with col_a2:
        theme_key = st.radio(
            t("onboarding.theme"),
            options=list(THEMES.keys()),
            format_func=lambda k: k.capitalize(),
            key="onboarding_theme_key",
            horizontal=True,
        )
        preview_color = THEMES.get(theme_key, THEMES["blue"])
        st.markdown(
            f"<div style='width:100%; height:10px; border-radius:6px; background:{preview_color}; border:1px solid #e2e8f0;'></div>",
            unsafe_allow_html=True,
        )

    logo_file = st.file_uploader(t("onboarding.logo"), type=["png", "jpg", "jpeg"])
    if logo_file is not None:
        logo_bytes = logo_file.read()
        if logo_bytes:
            encoded = base64.b64encode(logo_bytes).decode("utf-8")
            st.session_state["onboarding_logo_base64"] = f"data:{logo_file.type};base64,{encoded}"

    render_zone_title(t("onboarding.zone_admin"), "insem-zone-title")
    admin_username = st.text_input(t("onboarding.admin_user"), key="onboarding_admin_username")
    admin_password = st.text_input(t("onboarding.admin_password"), key="onboarding_admin_password")
    st.caption(t("onboarding.temp_note"))

    render_zone_title(t("onboarding.zone_confirm"), "insem-zone-title")
    cred_text = f"Username: {admin_username}\nPassword: {admin_password}"
    st.markdown(f"**{t('onboarding.credentials')}**")
    st.code(cred_text)

    cred_js = cred_text.replace("\\", "\\\\").replace("`", "\\`").replace("\n", "\\n")
    st.components.v1.html(
        f"""
        <button style='padding:6px 10px; border:1px solid #cbd5e1; border-radius:6px; background:#f8fafc; font-weight:600;'
                onclick="navigator.clipboard.writeText(`{cred_js}`)">Copiar</button>
        """,
        height=40,
    )

    if st.button(t("onboarding.finish"), type="primary", width="stretch"):
        if not company_name:
            st.error(t("msg.require_company"))
            return
        if not admin_username or not admin_password:
            st.error(t("msg.require_admin"))
            return

        logo_base64 = st.session_state.get("onboarding_logo_base64")
        primary_color = THEMES.get(theme_key, THEMES["blue"])
        finalize_app_settings(app_settings["id"], company_name, logo_base64, primary_color, theme_key)
        ensure_admin_user_exists(admin_username, admin_password)
        st.success(t("onboarding.done"))
        st.rerun()

# Carregar app settings e onboarding inicial
app_settings = ensure_app_settings()
if not app_settings:
    st.error(t("error.app_settings_load"))
    st.stop()

if "lang" not in st.session_state:
    st.session_state["lang"] = app_settings.get("language", "pt-PT")

inject_design_system()
inject_shell_css(app_settings.get("primary_color"))

# Forçar padding-top via JS (CSS é sobreposto pelo Streamlit interno)
import streamlit.components.v1 as _css_comp
_css_comp.html(
    """
    <script>
    (function applyPadding() {
        var el = window.parent.document.querySelector('[data-testid="stMainBlockContainer"]')
              || window.parent.document.querySelector('.block-container');
        if (el) {
            el.style.setProperty('padding-top', '60px', 'important');
        } else {
            setTimeout(applyPadding, 50);
        }
    })();

    // Restaurar zoom após sair de inputs (fix iOS Safari)
    (function setupZoomFix() {
        var doc = window.parent.document;
        if (doc._equicore_zoom_fix) return;
        doc._equicore_zoom_fix = true;
        doc.addEventListener('focusout', function(e) {
            var tag = e.target.tagName;
            if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') {
                // Forçar reset do zoom no viewport
                var meta = doc.querySelector('meta[name="viewport"]');
                if (meta) {
                    var orig = meta.getAttribute('content') || '';
                    meta.setAttribute('content', orig + ',maximum-scale=1');
                    setTimeout(function() { meta.setAttribute('content', orig); }, 50);
                }
                // Scroll para evitar deslocamento residual
                setTimeout(function() { window.parent.scrollTo(0, window.parent.scrollY); }, 60);
            }
        }, true);
    })();
    </script>
    """,
    height=0,
    scrolling=False,
)

if not app_settings.get("welcome_completed", False):
    render_welcome_page()
    st.stop()

if not app_settings.get("is_initialized"):
    render_onboarding(app_settings)
    st.stop()

# Verificar se está logado (restaurar sessão por query param → BD)
token_param = st.query_params.get("session", None)
if 'user' not in st.session_state and token_param:
    restored = load_session_db(token_param)
    if restored:
        st.session_state['user'] = restored
        st.session_state['auth_token'] = token_param

if 'user' not in st.session_state:
    mostrar_tela_login(app_settings)
    st.stop()

# Usuário logado - mostrar info no sidebar
user = st.session_state['user']

# Forçar alteração de credenciais no 1º login
if user.get("must_change_password"):
    render_change_credentials(user, app_settings)
    st.stop()

render_header(app_settings, user)

# Menu lateral final (Pedido 7 — 6 itens, sem emojis, sem "Mais opções").
# Todas as antigas entradas ficam acessíveis por sub-tabs/botões dentro
# destes 6 sítios. As permissões restrigem apenas o conteúdo de cada
# sítio (ex.: não-admin não vê o separador Utilizadores em Definições).
NAV_DASHBOARD       = "Dashboard"
NAV_ESTADIAS        = "Estadias"
NAV_TRABALHO_DIARIO = "Trabalho diário"
NAV_STOCK_SEMEN     = "Stock de sémen"
NAV_RELATORIOS      = "Relatórios"
NAV_DEFINICOES      = "Definições"

menu_principal = [
    NAV_DASHBOARD,
    NAV_ESTADIAS,
    NAV_TRABALHO_DIARIO,
    NAV_STOCK_SEMEN,
    NAV_RELATORIOS,
    NAV_DEFINICOES,
]
menu_secundario = []  # Sem "Mais opções" — todas as ações vivem dentro das páginas.

# Retrocompatibilidade: redirects antigos (`st.session_state['aba_selecionada']`
# = t("menu.stock")` / "Estadias e Visitas" / t("menu.map")` / ...) devem
# continuar a funcionar sem tocar em cada call-site. Cada entrada mapeia
# para `(nova_pagina, extra_state_dict)`.
_LEGACY_NAV_MAP = {
    t("menu.dashboard"):              (NAV_DASHBOARD, {}),
    "Estadias e Visitas":             (NAV_ESTADIAS, {}),
    "Trabalho diário":                (NAV_TRABALHO_DIARIO, {}),
    t("menu.stock"):                  (NAV_STOCK_SEMEN, {"stock_semen_tab": "Lotes"}),
    t("menu.map"):                    (NAV_STOCK_SEMEN, {"stock_semen_tab": "Mapa dos contentores"}),
    t("menu.transfers"):              (NAV_STOCK_SEMEN, {"stock_semen_tab": "Transferências"}),
    t("menu.add_stock"):              (NAV_STOCK_SEMEN, {"stock_semen_view": "add_stock"}),
    t("menu.import"):                 (NAV_STOCK_SEMEN, {"stock_semen_view": "import"}),
    # Registrar Inseminação vive dentro do Trabalho Diário via
    # `insem_flow_active` (Pedido 7).
    t("menu.register_insemination"): (NAV_TRABALHO_DIARIO, {"insem_flow_active": True}),
    t("menu.owners"):                 (NAV_DEFINICOES, {"definicoes_tab": "Proprietários"}),
    t("menu.users"):                  (NAV_DEFINICOES, {"definicoes_tab": "Utilizadores"}),
    t("menu.settings"):               (NAV_DEFINICOES, {}),
    t("menu.reports"):                (NAV_RELATORIOS, {}),
}


def _resolve_nav_label(label):
    """Mapeia labels antigos (i18n) para os 6 destinos actuais.

    Devolve `(nav_target, extra_state_dict)`. Se `label` já for um dos 6
    novos, devolve-o com dicionário vazio.
    """
    if label in menu_principal:
        return (label, {})
    return _LEGACY_NAV_MAP.get(label, (label, {}))


# Verificar se há redirecionamento pendente
if 'aba_selecionada' in st.session_state:
    raw = st.session_state['aba_selecionada']
    del st.session_state['aba_selecionada']
    resolved, extras = _resolve_nav_label(raw)
    active_key = resolved
    for k, v in extras.items():
        st.session_state[k] = v
    # Sinalizar redirect para o render_sidebar
    st.session_state['_nav_redirect_active'] = active_key
else:
    active_key = st.session_state.get("_nav_last_active", menu_principal[0])
    # Se o `_nav_last_active` guardado é de um menu antigo (ex.: reload
    # cross-versão), normalizar.
    if active_key not in menu_principal:
        resolved, _ = _resolve_nav_label(active_key)
        active_key = resolved
        st.session_state["_nav_last_active"] = active_key

aba, sidebar_logout = render_sidebar(app_settings, user, menu_principal, menu_secundario, active_key)
if sidebar_logout:
    token = st.session_state.pop('auth_token', None)
    if token:
        delete_session_db(token)
    st.query_params.clear()
    del st.session_state['user']
    st.rerun()

# Scroll ao topo + fechar sidebar (mobile) ao navegar
if st.session_state.pop("_just_navigated", False):
    import streamlit.components.v1 as _stcomp
    _stcomp.html(
        """
        <script>
        (function() {
            // 1. Scroll ao topo da área de conteúdo principal
            var main = window.parent.document.querySelector('[data-testid="stMain"]')
                    || window.parent.document.querySelector('.main')
                    || window.parent.document.body;
            if (main) main.scrollTo({top: 0, behavior: 'instant'});

            // 2. Fechar sidebar em dispositivos móveis/tablets (< 992px)
            if (window.parent.innerWidth < 992) {
                setTimeout(function() {
                    // Tentar vários seletores possíveis do botão de colapso
                    var collapseBtn =
                        window.parent.document.querySelector('[data-testid="stSidebar"] [data-testid="stBaseButton-headerNoPadding"]') ||
                        window.parent.document.querySelector('[data-testid="stSidebarCollapseButton"]') ||
                        window.parent.document.querySelector('[data-testid="stSidebar"] button');
                    if (collapseBtn) {
                        collapseBtn.click();
                    }
                }, 150);
            }
        })();
        </script>
        """,
        height=0,
        scrolling=False,
    )

# ------------------------------------------------------------
# 💬 Modal "adicionar proprietário" — extraído para
# `modules/components/modal_proprietario.py` no Pedido 9 · Fase 1.
# Importado ao nível do módulo para manter compatibilidade dos fluxos
# antigos que referenciavam `modal_adicionar_proprietario` no escopo do
# `__main__` (ex.: quando o utilizador chega via router legado).
# ------------------------------------------------------------
from modules.components.modal_proprietario import modal_adicionar_proprietario  # noqa: E402,F401

# Carregar dados
try:
    proprietarios = carregar_proprietarios(apenas_ativos=True)  # Apenas ativos por padrão
    stock = carregar_stock(apenas_ativos=True)  # Apenas de proprietários ativos
    insem = carregar_inseminacoes()
    contentores = carregar_contentores(apenas_ativos=True)  # Carregar contentores
except Exception as e:
    st.error(t("error.load_data", error=e))
    st.stop()

# Limpar session state do novo proprietário após usá-lo (evita que fique selecionado sempre)
if 'novo_proprietario_usado' in st.session_state:
    if 'novo_proprietario_id' in st.session_state:
        del st.session_state['novo_proprietario_id']
    if 'novo_proprietario_nome' in st.session_state:
        del st.session_state['novo_proprietario_nome']
    del st.session_state['novo_proprietario_usado']

if proprietarios.empty:
    st.warning(t("owners.none_registered_warn"))

# ------------------------------------------------------------
# --- Vistas legadas movidas antes do router para acessibilidade ---
# (Pedido 8 fix: `st.stop()` no router impede que os `def` abaixo
# sejam executados; mantê-los aqui garante que os orquestradores
# em stock_semen_page/definicoes_page conseguem `from app import ...`)

if aba == NAV_DASHBOARD:
    run_dashboard_page({**globals(), **locals()})
    st.stop()

if aba == NAV_ESTADIAS:
    run_estadias_page({**globals(), **locals()})
    st.stop()

if aba == NAV_TRABALHO_DIARIO:
    run_trabalho_diario_page({**globals(), **locals()})
    st.stop()

if aba == NAV_RELATORIOS:
    run_reports_page({**globals(), **locals()})
    st.stop()

# Stock de sémen: orquestrador com 4 tabs (Lotes, Garanhões, Mapa,
# Transferências) e 2 botões topo (Adicionar lote, Importar).
if aba == NAV_STOCK_SEMEN:
    from modules.pages.stock_semen_page import run_stock_semen_page
    run_stock_semen_page({**globals(), **locals()})
    st.stop()

# Definições: orquestrador com 5 separadores (Marca, Alojamentos,
# Proprietários, Utilizadores, Idioma) respeitando permissões.
if aba == NAV_DEFINICOES:
    from modules.pages.definicoes_page import run_definicoes_page
    run_definicoes_page({**globals(), **locals()})
    st.stop()

# Stock de sémen: dispatch de sub-views (add_stock / import).
# Se `stock_semen_view` não estiver setado, o orquestrador com tabs
# já correu acima (dentro de `run_stock_semen_page`) e não chegamos
# aqui. Este bloco corre APÓS o `st.stop()` do NAV_STOCK_SEMEN principal
# apenas quando o orquestrador tiver deferido a renderização — ver o
# `_render_add_stock_view()` / `run_import_page()` abaixo.
st.sidebar.markdown("---")
st.sidebar.markdown(t("footer.version"))
st.sidebar.markdown(t("footer.auth"))

if st.session_state.get("i18n_qa_mode"):
    diagnostics = get_i18n_diagnostics()
    current_lang = st.session_state.get("lang", "pt-PT")
    if current_lang == "zz":
        st.sidebar.markdown(f"⟦qa.footer_language⟧ {current_lang}")
        st.sidebar.markdown(f"⟦qa.footer_keys⟧ {diagnostics['total_keys']}")
    else:
        st.sidebar.markdown(t("qa.footer_language", lang=current_lang))
        st.sidebar.markdown(t("qa.footer_keys", total=diagnostics["total_keys"]))

    if diagnostics["missing"]:
        summary = ", ".join([f"{lang}({len(keys)})" for lang, keys in diagnostics["missing"].items()])
        if current_lang == "zz":
            st.sidebar.warning(f"⟦qa.footer_missing⟧ {summary}")
        else:
            st.sidebar.warning(t("qa.footer_missing", summary=summary))
    else:
        if current_lang == "zz":
            st.sidebar.success("⟦qa.footer_all_translated⟧")
        else:
            st.sidebar.success(t("qa.footer_all_translated"))
