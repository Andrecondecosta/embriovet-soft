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
from modules.i18n import t, get_i18n_diagnostics

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
# Helpers: converter tipos numpy/pandas -> tipos Python (psycopg2 friendly)
# ------------------------------------------------------------
def to_py(v):
    """Converte tipos numpy/pandas para tipos Python que o psycopg2 aceita."""
    # None fica None
    if v is None:
        return None

    # pandas NaN / NaT -> None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass

    # numpy -> python
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)

    # pandas Timestamp -> datetime python
    if isinstance(v, (pd.Timestamp,)):
        return v.to_pydatetime()

    # datetime/date do python já é ok
    if isinstance(v, (dt.date, dt.datetime)):
        return v

    # tudo o resto fica como está (strings, etc.)
    return v

# ------------------------------------------------------------
# Pool de conexões
# ------------------------------------------------------------
def ensure_sslmode_require(url: str) -> str:
    if not url:
        return url
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "sslmode" not in qs:
        qs["sslmode"] = ["require"]
        parsed = parsed._replace(query=urlencode(qs, doseq=True))
    return urlunparse(parsed)

@st.cache_resource(show_spinner=False)
def build_connection_pool():
    database_url = (os.getenv("DATABASE_URL") or "").strip()

    if database_url:
        database_url = ensure_sslmode_require(database_url)
        pool_obj = psycopg2.pool.SimpleConnectionPool(
            1, 10,
            dsn=database_url
        )
        logger.info("✅ Pool criado com DATABASE_URL (sslmode=require)")
        return pool_obj

    pool_obj = psycopg2.pool.SimpleConnectionPool(
        1, 10,
        dbname=os.getenv("DB_NAME", "embriovet"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "123"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
    )
    logger.info("✅ Pool criado localmente")
    return pool_obj

try:
    connection_pool = build_connection_pool()
except Exception as e:
    logger.error(f"❌ Erro ao criar pool de conexões: {e}")
    st.error(f"Erro de conexão com banco de dados: {e}")
    st.stop()

@contextmanager
def get_connection():
    """Context manager para gestão segura de conexões"""
    conn = None
    try:
        conn = connection_pool.getconn()
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Erro na conexão: {e}")
        raise
    finally:
        if conn:
            connection_pool.putconn(conn)

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
def get_app_settings():
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, company_name, logo_base64, primary_color,
                       is_initialized, show_initial_credentials, theme_key, language, welcome_completed
                FROM app_settings
                WHERE id = 1
                ORDER BY id
                LIMIT 1
                """
            )
            row = cur.fetchone()
            cur.close()
        if not row:
            return None
        return {
            "id": row[0],
            "company_name": row[1],
            "logo_base64": row[2],
            "primary_color": row[3],
            "is_initialized": row[4],
            "show_initial_credentials": row[5],
            "theme_key": row[6],
            "language": row[7],
            "welcome_completed": row[8],
        }
    except Exception as e:
        logger.error(f"Erro ao carregar app_settings: {e}")
        return None


def ensure_app_settings():
    settings = get_app_settings()
    if settings:
        return settings
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO app_settings (id, company_name, theme_key, language, welcome_completed)
                SELECT 1, 'Sistema', 'blue', 'pt-PT', FALSE
                WHERE NOT EXISTS (SELECT 1 FROM app_settings);
                """
            )
            conn.commit()
            cur.close()
        return get_app_settings()
    except Exception as e:
        logger.error(f"Erro ao criar app_settings: {e}")
        return None


def save_app_settings(settings_id, company_name, logo_base64, primary_color, theme_key):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE app_settings
            SET company_name = %s,
                logo_base64 = %s,
                primary_color = %s,
                theme_key = %s,
                is_initialized = TRUE,
                updated_at = now()
            WHERE id = %s
            """,
            (company_name, logo_base64, primary_color, theme_key, settings_id),
        )
        conn.commit()
        cur.close()


def finalize_app_settings(settings_id, company_name, logo_base64, primary_color, theme_key):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE app_settings
            SET company_name = %s,
                logo_base64 = %s,
                primary_color = %s,
                theme_key = %s,
                is_initialized = TRUE,
                show_initial_credentials = FALSE,
                updated_at = now()
            WHERE id = %s
            """,
            (company_name, logo_base64, primary_color, theme_key, settings_id),
        )
        conn.commit()
        cur.close()


def update_show_initial_credentials(value: bool):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE app_settings SET show_initial_credentials = %s, updated_at = now()",
            (value,),
        )
        conn.commit()
        cur.close()


def update_language(language: str):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE app_settings SET language = %s, updated_at = now()",
            (language,),
        )
        conn.commit()
        cur.close()


def update_branding_settings(company_name, logo_base64, language, primary_color):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE app_settings
            SET company_name = %s,
                logo_base64 = %s,
                language = %s,
                primary_color = %s,
                updated_at = now()
            WHERE id = 1
            """,
            (company_name, logo_base64, language, primary_color),
        )
        conn.commit()
        cur.close()


def update_welcome_completed(completed=True):
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE app_settings SET welcome_completed = %s WHERE id = 1",
                (completed,),
            )
            conn.commit()
            cur.close()
        return True
    except Exception as e:
        logger.error(f"Erro ao atualizar welcome_completed: {e}")
        return False



# ------------------------------------------------------------
# 📥 Funções de carregamento de dados
# ------------------------------------------------------------
def carregar_proprietarios(apenas_ativos=False):
    """Carrega lista de proprietarios do banco de dados

    Args:
        apenas_ativos: Se True, retorna apenas proprietários ativos
    """
    try:
        with get_connection() as conn:
            query = "SELECT * FROM dono"
            if apenas_ativos:
                query += " WHERE ativo = TRUE"
            query += " ORDER BY nome"
            df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar proprietarios: {e}")
        st.error(f"Erro ao carregar proprietarios: {e}")
        return pd.DataFrame()

def atualizar_status_proprietarios():
    """
    Desativa automaticamente proprietários quando stock chega a 0.
    NUNCA reativa automaticamente - controle manual após desativação.
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            # APENAS desativar proprietários que estão ATIVOS e têm stock = 0
            # Nunca forçar ativação ou desativação se já está inativo
            cur.execute("""
                UPDATE dono SET ativo = FALSE
                WHERE ativo = TRUE
                AND id IN (
                    SELECT d.id FROM dono d
                    LEFT JOIN (
                        SELECT dono_id, SUM(existencia_atual) as total_stock
                        FROM estoque_dono
                        GROUP BY dono_id
                    ) s ON d.id = s.dono_id
                    WHERE COALESCE(s.total_stock, 0) = 0
                )
            """)

            # NÃO ativar automaticamente - apenas controle manual!
            # Removido: código que ativava automaticamente com stock > 0

            conn.commit()
            cur.close()
            return True
    except Exception as e:
        logger.error(f"Erro ao atualizar status: {e}")
        return False

def alternar_status_proprietario(proprietario_id):
    """Alterna o status ativo/inativo de um proprietário"""
    conn = None
    cur = None
    try:
        # Pegar credenciais
        db_name = os.getenv("DB_NAME", "embriovet")
        db_user = os.getenv("DB_USER", "postgres")
        db_pass = os.getenv("DB_PASSWORD", "123")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")

        logger.info(f"🔌 Conectando com AUTOCOMMIT em: {db_user}@{db_host}:{db_port}/{db_name}")
        logger.info(f"🆔 Proprietário ID recebido: {proprietario_id} (tipo: {type(proprietario_id)})")

        # Converter ID para int
        prop_id_int = int(proprietario_id)
        logger.info(f"🆔 Proprietário ID convertido: {prop_id_int} (tipo: {type(prop_id_int)})")

        # CRIAR CONEXÃO COM AUTOCOMMIT = TRUE
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_pass,
            host=db_host,
            port=db_port
        )

        # FORÇAR AUTOCOMMIT - COMMIT IMEDIATO APÓS CADA COMANDO
        conn.set_session(autocommit=True)
        cur = conn.cursor()

        logger.info(f"✅ AUTOCOMMIT ativado")

        # Verificar o valor atual
        sql_select = "SELECT ativo FROM dono WHERE id = %s"
        logger.info(f"📋 SQL SELECT: {sql_select} com id={prop_id_int}")
        cur.execute(sql_select, (prop_id_int,))
        status_antes = cur.fetchone()
        logger.info(f"📋 Status ANTES: {status_antes}")

        if not status_antes:
            logger.error(f"❌ Proprietário com ID {prop_id_int} não encontrado!")
            cur.close()
            conn.close()
            return None

        # Calcular novo valor
        novo_valor = not status_antes[0]
        logger.info(f"🔄 Novo valor calculado: {novo_valor} (tipo: {type(novo_valor)})")

        # UPDATE direto (SEM to_py)
        sql_update = "UPDATE dono SET ativo = %s WHERE id = %s RETURNING ativo"
        logger.info(f"📝 SQL UPDATE: {sql_update}")
        logger.info(f"📝 Parâmetros: ativo={novo_valor}, id={prop_id_int}")

        cur.execute(sql_update, (novo_valor, prop_id_int))

        resultado = cur.fetchone()
        logger.info(f"📝 Resultado do UPDATE (AUTO-COMMITADO): {resultado}")

        if resultado:
            novo_status = resultado[0]
            logger.info(f"✅ UPDATE executado com sucesso. Novo status: {novo_status}")

            # Verificar com SELECT
            cur.execute("SELECT ativo FROM dono WHERE id = %s", (prop_id_int,))
            status_verificacao = cur.fetchone()
            logger.info(f"🔍 Verificação final: {status_verificacao}")

            # Verificar FORA da conexão Python
            logger.info(f"⚠️ Execute no terminal: psql -U postgres -d embriovet -c \"SELECT id, nome, ativo FROM dono WHERE id={prop_id_int};\"")

            cur.close()
            conn.close()
            logger.info(f"🔒 Conexão fechada")

            return novo_status
        else:
            if cur:
                cur.close()
            if conn:
                conn.close()
            logger.error(f"❌ UPDATE não retornou resultado")
            return None

    except Exception as e:
        logger.error(f"💥 ERRO: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if conn:
            try:
                conn.close()
            except:
                pass
        st.error(f"Erro: {e}")
        return None

def editar_proprietario(proprietario_id, dados):
    """Edita informações do proprietário"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            # Verificar se já existe outro proprietário com este nome
            cur.execute(
                "SELECT id FROM dono WHERE LOWER(nome) = LOWER(%s) AND id != %s",
                (to_py(dados.get('nome')), to_py(proprietario_id))
            )
            existe = cur.fetchone()

            if existe:
                st.error(f"❌ Já existe outro proprietário com o nome '{dados.get('nome')}'")
                return False

            cur.execute("""
                UPDATE dono SET
                    nome = %s,
                    email = %s,
                    telemovel = %s,
                    nome_completo = %s,
                    nif = %s,
                    morada = %s,
                    codigo_postal = %s,
                    cidade = %s
                WHERE id = %s
            """, (
                to_py(dados.get('nome')),
                to_py(dados.get('email')),
                to_py(dados.get('telemovel')),
                to_py(dados.get('nome_completo')),
                to_py(dados.get('nif')),
                to_py(dados.get('morada')),
                to_py(dados.get('codigo_postal')),
                to_py(dados.get('cidade')),
                to_py(proprietario_id)
            ))
            conn.commit()
            cur.close()
            logger.info(f"Proprietário editado: ID {proprietario_id}")
            return True
    except Exception as e:
        logger.error(f"Erro ao editar proprietário: {e}")
        return False

def carregar_stock(apenas_ativos=True):
    """Carrega stock completo com informações de proprietario e contentor

    Args:
        apenas_ativos: Se True, retorna apenas stock de proprietários ativos
    """
    try:
        with get_connection() as conn:
            query = """
                SELECT e.*,
                       d.nome as proprietario_nome,
                       c.codigo as contentor_codigo
                FROM estoque_dono e
                LEFT JOIN dono d ON e.dono_id = d.id
                LEFT JOIN contentores c ON e.contentor_id = c.id
                WHERE e.existencia_atual > 0
            """
            if apenas_ativos:
                query += " AND d.ativo = TRUE"
            query += " ORDER BY e.garanhao, e.id"
            df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar stock: {e}")
        st.error(f"Erro ao carregar stock: {e}")
        return pd.DataFrame()

def carregar_inseminacoes():
    """Carrega histórico de inseminações"""
    try:
        with get_connection() as conn:
            query = """
                SELECT i.*, d.nome as proprietario_nome
                FROM inseminacoes i
                LEFT JOIN dono d ON i.dono_id = d.id
                ORDER BY i.data_inseminacao DESC
            """
            df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar inseminações: {e}")
        st.error(f"Erro ao carregar inseminações: {e}")
        return pd.DataFrame()

def carregar_transferencias():
    """Carrega histórico de transferências"""
    try:
        with get_connection() as conn:
            query = """
                SELECT t.*,
                       e.garanhao,
                       d1.nome as proprietario_origem,
                       d2.nome as proprietario_destino
                FROM transferencias t
                LEFT JOIN estoque_dono e ON t.estoque_id = e.id
                LEFT JOIN dono d1 ON t.proprietario_origem_id = d1.id
                LEFT JOIN dono d2 ON t.proprietario_destino_id = d2.id
                ORDER BY t.data_transferencia DESC
            """
            df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar transferências: {e}")
        return pd.DataFrame()

def carregar_transferencias_externas():
    """Carrega histórico de transferências externas (vendas/envios)"""
    try:
        with get_connection() as conn:
            # Verificar se a tabela existe
            cur = conn.cursor()
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'transferencias_externas'
                );
            """)
            tabela_existe = cur.fetchone()[0]
            cur.close()

            if not tabela_existe:
                logger.warning("Tabela transferencias_externas não existe")
                return pd.DataFrame()

            query = """
                SELECT te.*,
                       d.nome as proprietario_origem
                FROM transferencias_externas te
                LEFT JOIN dono d ON te.proprietario_origem_id = d.id
                ORDER BY te.data_transferencia DESC
            """
            df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar transferências externas: {e}")
        return pd.DataFrame()

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

def atualizar_proprietario_stock(stock_id, novo_dono_id):
    """Atualiza o proprietario de um item de stock"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE estoque_dono SET dono_id = %s WHERE id = %s",
                (to_py(novo_dono_id), to_py(stock_id)),
            )
            conn.commit()
            cur.close()
            logger.info(f"Proprietário atualizado: stock_id={stock_id}, novo_dono_id={novo_dono_id}")
            return True
    except Exception as e:
        logger.error(f"Erro ao atualizar proprietario: {e}")
        st.error(f"Erro ao atualizar proprietario: {e}")
        return False

# ------------------------------------------------------------
# 💾 Funções de inserção
# ------------------------------------------------------------
def inserir_stock(dados):
    """Insere novo stock no banco de dados"""
    try:
        if not dados.get("Garanhão"):
            st.error(t("error.stallion_required"))
            return False

        if not dados.get("Contentor"):
            st.error(t("error.container_required"))
            return False

        if not dados.get("Canister"):
            st.error(t("error.canister_required"))
            return False

        if not dados.get("Andar"):
            st.error(t("error.floor_required"))
            return False

        palhetas_val = to_py(dados.get("Palhetas", 0)) or 0
        try:
            palhetas_int = int(palhetas_val)
        except Exception:
            st.error(t("error.straws_numeric"))
            return False

        if palhetas_int < 0:
            st.error(t("error.straws_negative"))
            return False

        with get_connection() as conn:
            cur = conn.cursor()

            # Obter utilizador atual
            username = st.session_state.get('username', 'desconhecido')

            params = (
                to_py(dados.get("Garanhão")),
                to_py(dados.get("Proprietário")),
                to_py(dados.get("Data")),
                to_py(dados.get("Origem")),
                to_py(dados.get("Palhetas")),
                to_py(dados.get("Qualidade")),
                to_py(dados.get("Concentração")),
                to_py(dados.get("Motilidade")),
                to_py(dados.get("Certificado")),
                to_py(dados.get("Dose")),
                to_py(dados.get("Observações")),
                to_py(dados.get("Palhetas")),
                to_py(dados.get("Palhetas")),
                to_py(dados.get("Contentor")),
                to_py(dados.get("Canister")),
                to_py(dados.get("Andar")),
                to_py(dados.get("Cor")),
                username
            )

            cur.execute(
                """
                INSERT INTO estoque_dono (
                    garanhao, dono_id, data_embriovet, origem_externa,
                    palhetas_produzidas, qualidade, concentracao, motilidade,
                    certificado, dose, observacoes,
                    quantidade_inicial, existencia_atual,
                    contentor_id, canister, andar, cor,
                    criado_por, data_criacao
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                RETURNING id, garanhao
                """,
                params,
            )

            # Obter ID e garanhão do stock inserido
            result = cur.fetchone()
            stock_id = result[0]
            garanhao_nome = result[1]

            conn.commit()
            cur.close()
            logger.info(f"Stock inserido: {dados.get('Garanhão')} (ID: {stock_id})")

            # Guardar informações para redirecionamento
            st.session_state['ultimo_stock_id'] = stock_id
            st.session_state['ultimo_garanhao'] = garanhao_nome
            st.session_state['redirecionar_ver_stock'] = True

            return True

    except Exception as e:
        logger.error(f"Erro ao inserir stock: {e}")
        st.error(f"Erro ao inserir stock: {e}")
        return False

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

            logger.info(f"Inseminação registrada: {registro.get('egua')} - {palhetas_int} palhetas")
            return True

    except Exception as e:
        logger.error(f"Erro ao registrar inseminação: {e}")
        st.error(f"Erro ao registrar inseminação: {e}")
        return False


def registrar_inseminacao_multiplas(registros, data_inseminacao, egua):
    """Registra múltiplas linhas de inseminação numa transação única"""
    try:
        if not egua:
            st.error(t("error.mare_required"))
            return False

        if not registros:
            st.error(t("error.select_lot"))
            return False

        with get_connection() as conn:
            cur = conn.cursor()

            # 1) Validar e bloquear stock
            validacoes = []
            for reg in registros:
                stock_id = to_py(reg.get("stock_id"))
                palhetas = int(to_py(reg.get("palhetas")) or 0)

                if palhetas <= 0:
                    cur.close()
                    st.error(t("error.invalid_qty_line"))
                    return False

                cur.execute(
                    "SELECT existencia_atual FROM estoque_dono WHERE id = %s FOR UPDATE",
                    (stock_id,),
                )
                row = cur.fetchone()
                if not row:
                    cur.close()
                    st.error(t("error.lot_not_found"))
                    return False

                existencia = int(row[0] or 0)
                if palhetas > existencia:
                    cur.close()
                    st.error(f"❌ Stock insuficiente no lote {stock_id}. Disponível: {existencia}")
                    return False

                validacoes.append((stock_id, palhetas, reg))

            # 2) Inserir inseminações e atualizar stock
            for stock_id, palhetas, reg in validacoes:
                cur.execute(
                    """
                    INSERT INTO inseminacoes (garanhao, dono_id, data_inseminacao, egua, protocolo, palhetas_gastas)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        to_py(reg.get("garanhao")),
                        to_py(reg.get("dono_id")),
                        to_py(data_inseminacao),
                        to_py(egua),
                        to_py(reg.get("protocolo")),
                        to_py(palhetas),
                    ),
                )

                cur.execute(
                    """
                    UPDATE estoque_dono
                    SET existencia_atual = existencia_atual - %s
                    WHERE id = %s
                    """,
                    (to_py(palhetas), stock_id),
                )

            conn.commit()
            cur.close()

            atualizar_status_proprietarios()
            logger.info(f"Inseminação múltipla registrada: égua={egua}, linhas={len(registros)}")
            return True

    except Exception as e:
        logger.error(f"Erro ao registrar inseminação múltipla: {e}")
        st.error(f"Erro ao registrar inseminação: {e}")
        return False

# ------------------------------------------------------------
# 🔐 Funções de Autenticação e Utilizadores
# ------------------------------------------------------------
def criar_hash_password(password):
    """Cria hash da password usando bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def ensure_admin_user_exists(username, password):
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM usuarios")
            total = cur.fetchone()[0] or 0
            if total > 0:
                cur.close()
                return

            password_hash = criar_hash_password(password)
            cur.execute(
                """
                INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo, must_change_password)
                VALUES (%s, %s, %s, %s, TRUE, TRUE)
                """,
                (username, "Administrador", password_hash, "Administrador"),
            )
            conn.commit()
            cur.close()
            logger.info("Utilizador admin inicial criado")
    except Exception as e:
        logger.error(f"Erro ao criar admin inicial: {e}")

def verificar_password(password, password_hash):
    """Verifica se a password corresponde ao hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False

def autenticar_usuario(username, password):
    """Autentica utilizador e retorna seus dados"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, username, nome_completo, password_hash, nivel, ativo, must_change_password
                FROM usuarios
                WHERE username = %s AND ativo = TRUE
            """, (username,))

            resultado = cur.fetchone()
            cur.close()

            if not resultado:
                return None

            user_id, username, nome, pwd_hash, nivel, ativo, must_change_password = resultado

            # Verificar password
            if verificar_password(password, pwd_hash):
                # Atualizar last_login
                cur = conn.cursor()
                cur.execute("""
                    UPDATE usuarios SET last_login = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (user_id,))
                conn.commit()
                cur.close()

                return {
                    'id': user_id,
                    'username': username,
                    'nome': nome,
                    'nivel': nivel,
                    'must_change_password': must_change_password
                }

            return None

    except Exception as e:
        logger.error(f"Erro ao autenticar: {e}")
        return None

def carregar_usuarios():
    """Carrega lista de utilizadores"""
    try:
        with get_connection() as conn:
            df = pd.read_sql_query("""
                SELECT id, username, nome_completo, nivel, ativo,
                       created_at, last_login
                FROM usuarios
                ORDER BY nivel, nome_completo
            """, conn)
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar utilizadores: {e}")
        return pd.DataFrame()

def adicionar_usuario(username, nome_completo, password, nivel, created_by_id):
    """Adiciona novo utilizador"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            # Verificar se username já existe
            cur.execute("SELECT id FROM usuarios WHERE username = %s", (username,))
            if cur.fetchone():
                st.error(t("error.username_exists"))
                return False

            password_hash = criar_hash_password(password)

            cur.execute("""
                INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo, created_by)
                VALUES (%s, %s, %s, %s, TRUE, %s)
            """, (username, nome_completo, password_hash, nivel, created_by_id))

            conn.commit()
            cur.close()
            logger.info(f"Utilizador criado: {username} ({nivel})")
            return True

    except Exception as e:
        logger.error(f"Erro ao adicionar utilizador: {e}")
        st.error(f"Erro ao adicionar utilizador: {e}")
        return False

def alterar_password(user_id, nova_password):
    """Altera password do utilizador"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            password_hash = criar_hash_password(nova_password)
            cur.execute("""
                UPDATE usuarios SET password_hash = %s
                WHERE id = %s
            """, (password_hash, user_id))
            conn.commit()
            cur.close()
            return True
    except Exception as e:
        logger.error(f"Erro ao alterar password: {e}")
        return False

def desativar_usuario(user_id):
    """Desativa utilizador"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE usuarios SET ativo = FALSE WHERE id = %s", (user_id,))
            conn.commit()
            cur.close()
            return True
    except Exception as e:
        logger.error(f"Erro ao desativar utilizador: {e}")
        return False

def ativar_usuario(user_id):
    """Ativa utilizador"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE usuarios SET ativo = TRUE WHERE id = %s", (user_id,))
            conn.commit()
            cur.close()
            return True
    except Exception as e:
        logger.error(f"Erro ao ativar utilizador: {e}")
        return False

# ------------------------------------------------------------
# 👥 Funções de Gestão de Proprietários
# ------------------------------------------------------------
def adicionar_proprietario(dados):
    """Adiciona novo proprietário com todos os campos"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            # Verificar se já existe proprietário com este nome
            cur.execute("SELECT id FROM dono WHERE LOWER(nome) = LOWER(%s)", (to_py(dados.get('nome')),))
            existe = cur.fetchone()

            if existe:
                st.error(f"❌ Já existe um proprietário com o nome '{dados.get('nome')}'")
                return None

            cur.execute(
                """
                INSERT INTO dono (nome, email, telemovel, nome_completo, nif, morada, codigo_postal, cidade, ativo)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                RETURNING id
                """,
                (
                    to_py(dados.get('nome')),
                    to_py(dados.get('email')),
                    to_py(dados.get('telemovel')),
                    to_py(dados.get('nome_completo')),
                    to_py(dados.get('nif')),
                    to_py(dados.get('morada')),
                    to_py(dados.get('codigo_postal')),
                    to_py(dados.get('cidade'))
                ),
            )
            proprietario_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            logger.info(f"Proprietário adicionado: {dados.get('nome')}")
            return proprietario_id
    except Exception as e:
        logger.error(f"Erro ao adicionar proprietário: {e}")
        st.error(f"Erro ao adicionar proprietário: {e}")
        return None

def deletar_proprietario(proprietario_id):
    """Deleta proprietário (apenas se não tiver stock)"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("SELECT COUNT(*) FROM estoque_dono WHERE dono_id = %s", (to_py(proprietario_id),))
            count = cur.fetchone()[0] or 0

            if count > 0:
                st.error(f"❌ Não é possível deletar! Este proprietário tem {count} lotes de stock.")
                return False

            cur.execute("SELECT COUNT(*) FROM inseminacoes WHERE dono_id = %s", (to_py(proprietario_id),))
            count_insem = cur.fetchone()[0] or 0

            if count_insem > 0:
                st.error(f"❌ Não é possível deletar! Este proprietário tem {count_insem} inseminações registadas.")
                return False

            cur.execute("DELETE FROM dono WHERE id = %s", (to_py(proprietario_id),))
            conn.commit()
            cur.close()
            logger.info(f"Proprietário deletado: ID {proprietario_id}")
            return True

    except Exception as e:
        logger.error(f"Erro ao deletar proprietário: {e}")
        st.error(f"Erro ao deletar proprietário: {e}")
        return False

# ------------------------------------------------------------
# 📝 Funções de Edição de Stock
# ------------------------------------------------------------
def editar_stock(stock_id, dados):
    """Edita um lote de stock"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE estoque_dono SET
                    garanhao = %s,
                    dono_id = %s,
                    data_embriovet = %s,
                    origem_externa = %s,
                    palhetas_produzidas = %s,
                    qualidade = %s,
                    concentracao = %s,
                    motilidade = %s,
                    certificado = %s,
                    dose = %s,
                    observacoes = %s,
                    existencia_atual = %s,
                    contentor_id = %s,
                    canister = %s,
                    andar = %s,
                    cor = %s
                WHERE id = %s
                """,
                (
                    to_py(dados.get("garanhao")),
                    to_py(dados.get("dono_id")),
                    to_py(dados.get("data")),
                    to_py(dados.get("origem")),
                    to_py(dados.get("palhetas_produzidas")),
                    to_py(dados.get("qualidade")),
                    to_py(dados.get("concentracao")),
                    to_py(dados.get("motilidade")),
                    to_py(dados.get("certificado")),
                    to_py(dados.get("dose")),
                    to_py(dados.get("observacoes")),
                    to_py(dados.get("existencia")),
                    to_py(dados.get("contentor_id")),
                    to_py(dados.get("canister")),
                    to_py(dados.get("andar")),
                    to_py(dados.get("cor")),
                    to_py(stock_id),
                ),
            )
            conn.commit()
            cur.close()
            logger.info(f"Stock editado: ID {stock_id}")
            return True
    except Exception as e:
        logger.error(f"Erro ao editar stock: {e}")
        st.error(f"Erro ao editar stock: {e}")
        return False

def deletar_stock(stock_id):
    """Deleta um lote de stock"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM estoque_dono WHERE id = %s", (to_py(stock_id),))
            conn.commit()
            cur.close()
            logger.info(f"Stock deletado: ID {stock_id}")
            return True
    except Exception as e:
        logger.error(f"Erro ao deletar stock: {e}")
        st.error(f"Erro ao deletar stock: {e}")
        return False

# ------------------------------------------------------------
# 🗺️ Funções de Gestão de Contentores
# ------------------------------------------------------------

def carregar_contentores(apenas_ativos=True):
    """Carrega todos os contentores"""
    try:
        with get_connection() as conn:
            query = "SELECT * FROM contentores"
            if apenas_ativos:
                query += " WHERE ativo = TRUE"
            query += " ORDER BY codigo"
            df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar contentores: {e}")
        st.error(f"Erro ao carregar contentores: {e}")
        return pd.DataFrame()

def adicionar_contentor(dados):
    """Adiciona novo contentor"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO contentores (codigo, descricao, x, y, w, h, ativo)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                to_py(dados.get('codigo')),
                to_py(dados.get('descricao', '')),
                to_py(dados.get('x', 100)),
                to_py(dados.get('y', 100)),
                to_py(dados.get('w', 150)),
                to_py(dados.get('h', 150)),
                True
            ))
            contentor_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            logger.info(f"Contentor criado: {dados.get('codigo')} (ID: {contentor_id})")
            return contentor_id
    except Exception as e:
        logger.error(f"Erro ao adicionar contentor: {e}")
        st.error(f"Erro ao adicionar contentor: {e}")
        return None

def editar_contentor(contentor_id, dados):
    """Edita um contentor existente"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE contentores
                SET codigo = %s, descricao = %s, x = %s, y = %s, w = %s, h = %s
                WHERE id = %s
            """, (
                to_py(dados.get('codigo')),
                to_py(dados.get('descricao')),
                to_py(dados.get('x')),
                to_py(dados.get('y')),
                to_py(dados.get('w')),
                to_py(dados.get('h')),
                to_py(contentor_id)
            ))
            conn.commit()
            cur.close()
            logger.info(f"Contentor editado: ID {contentor_id}")
            return True
    except Exception as e:
        logger.error(f"Erro ao editar contentor: {e}")
        st.error(f"Erro ao editar contentor: {e}")
        return False

def atualizar_posicao_contentor(contentor_id, x, y):
    """Atualiza apenas a posição (x,y) de um contentor"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE contentores
                SET x = %s, y = %s
                WHERE id = %s
            """, (to_py(x), to_py(y), to_py(contentor_id)))
            conn.commit()
            cur.close()
            logger.info(f"Posição do contentor atualizada: ID {contentor_id} -> X={x}, Y={y}")
            return True
    except Exception as e:
        logger.error(f"Erro ao atualizar posição do contentor: {e}")
        st.error(f"Erro ao guardar posição do contentor: {e}")
        return False

def deletar_contentor(contentor_id):
    """Deleta um contentor apenas se não tiver stock associado"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            # Verificar se tem stock associado
            cur.execute("""
                SELECT COALESCE(SUM(existencia_atual), 0) as total
                FROM estoque_dono
                WHERE contentor_id = %s
            """, (to_py(contentor_id),))

            total_stock = cur.fetchone()[0]

            if total_stock > 0:
                st.error(f"❌ Não é possível eliminar: este contentor ainda tem sémen ({total_stock} palhetas).")
                return False

            # Se não tem stock, pode deletar
            cur.execute("DELETE FROM contentores WHERE id = %s", (to_py(contentor_id),))
            conn.commit()
            cur.close()
            logger.info(f"Contentor deletado: ID {contentor_id}")
            return True

    except Exception as e:
        logger.error(f"Erro ao deletar contentor: {e}")
        st.error(f"Erro ao deletar contentor: {e}")
        return False

def obter_stock_contentor(contentor_id):
    """Obtém informações de stock de um contentor específico"""
    try:
        with get_connection() as conn:
            query = """
                SELECT
                    e.id,
                    e.garanhao,
                    d.nome as proprietario_nome,
                    e.canister,
                    e.andar,
                    e.existencia_atual,
                    e.qualidade,
                    e.data_embriovet,
                    e.origem_externa
                FROM estoque_dono e
                LEFT JOIN dono d ON e.dono_id = d.id
                WHERE e.contentor_id = %s AND e.existencia_atual > 0
                ORDER BY e.canister, e.andar, e.garanhao
            """
            df = pd.read_sql_query(query, conn, params=(contentor_id,))
        return df
    except Exception as e:
        logger.error(f"Erro ao obter stock do contentor: {e}")
        return pd.DataFrame()

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


def transferir_palhetas_parcial(stock_origem_id, proprietario_destino_id, quantidade):
    """Transfere quantidade parcial de palhetas para outro proprietário"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            # Buscar dados do lote origem
            cur.execute("""
                SELECT garanhao, dono_id, existencia_atual, data_embriovet, origem_externa,
                       qualidade, concentracao, motilidade, local_armazenagem, certificado, dose, observacoes, cor,
                       contentor_id, canister, andar
                FROM estoque_dono WHERE id = %s
            """, (to_py(stock_origem_id),))

            origem = cur.fetchone()
            if not origem:
                st.error(t("error.origin_lot_not_found"))
                return False

            (garanhao, prop_origem_id, exist_atual, data_emb, origem_ext,
             qual, conc, mot, local, cert, dose, obs, cor, contentor_id, canister, andar) = origem

            exist_atual = int(to_py(exist_atual) or 0)
            quantidade_int = int(to_py(quantidade) or 0)

            if quantidade_int <= 0:
                st.error(t("error.qty_positive"))
                return False

            if quantidade_int > exist_atual:
                st.error(f"❌ Quantidade insuficiente! Disponível: {exist_atual}")
                return False

            # Atualizar stock origem (diminuir)
            cur.execute("""
                UPDATE estoque_dono
                SET existencia_atual = existencia_atual - %s
                WHERE id = %s
            """, (quantidade_int, to_py(stock_origem_id)))

            # Verificar se já existe lote do destino com mesmo garanhão e mesma localização
            cur.execute("""
                SELECT id, existencia_atual
                FROM estoque_dono
                WHERE garanhao = %s AND dono_id = %s AND id != %s
                AND COALESCE(contentor_id, 0) = COALESCE(%s, 0)
                AND COALESCE(canister, 0) = COALESCE(%s, 0)
                AND COALESCE(andar, 0) = COALESCE(%s, 0)
                LIMIT 1
            """, (to_py(garanhao), to_py(proprietario_destino_id), to_py(stock_origem_id),
                  to_py(contentor_id), to_py(canister), to_py(andar)))

            lote_destino = cur.fetchone()

            if lote_destino:
                # Já existe lote, adicionar palhetas
                cur.execute("""
                    UPDATE estoque_dono
                    SET existencia_atual = existencia_atual + %s
                    WHERE id = %s
                """, (quantidade_int, lote_destino[0]))
            else:
                # Criar novo lote para o destino (mantém mesma localização)
                cur.execute("""
                    INSERT INTO estoque_dono (
                        garanhao, dono_id, data_embriovet, origem_externa,
                        palhetas_produzidas, qualidade, concentracao, motilidade,
                        local_armazenagem, certificado, dose, observacoes,
                        quantidade_inicial, existencia_atual, cor,
                        contentor_id, canister, andar
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    to_py(garanhao), to_py(proprietario_destino_id), to_py(data_emb), to_py(origem_ext),
                    quantidade_int, to_py(qual), to_py(conc), to_py(mot),
                    to_py(local), to_py(cert), to_py(dose), to_py(obs),
                    quantidade_int, quantidade_int, to_py(cor),
                    to_py(contentor_id), to_py(canister), to_py(andar)
                ))

            # Registrar transferência na tabela de transferências
            cur.execute("""
                INSERT INTO transferencias (
                    estoque_id, proprietario_origem_id, proprietario_destino_id,
                    quantidade, data_transferencia
                ) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (to_py(stock_origem_id), to_py(prop_origem_id), to_py(proprietario_destino_id), quantidade_int))

            conn.commit()
            cur.close()

            # Verificar e desativar proprietários com stock = 0
            atualizar_status_proprietarios()

            logger.info(f"Transferência: {quantidade_int} palhetas de {prop_origem_id} para {proprietario_destino_id}")
            return True

    except Exception as e:
        logger.error(f"Erro ao transferir palhetas: {e}")
        st.error(f"Erro ao transferir palhetas: {e}")
        return False

# Alias para compatibilidade
transferir_stock_interno = transferir_palhetas_parcial

def transferir_stock_interno_com_localizacao(prop_origem_id, prop_destino_id, stock_origem_id, quantidade,
                                              contentor_id_novo, canister_novo, andar_novo):
    """Transfere palhetas para outro proprietário e muda a localização"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            # Buscar dados do lote origem
            cur.execute("""
                SELECT garanhao, dono_id, existencia_atual, data_embriovet, origem_externa,
                       qualidade, concentracao, motilidade, local_armazenagem, certificado, dose, observacoes, cor
                FROM estoque_dono WHERE id = %s
            """, (to_py(stock_origem_id),))

            origem = cur.fetchone()
            if not origem:
                st.error(t("error.origin_lot_not_found"))
                return False

            (garanhao, prop_origem_db, exist_atual, data_emb, origem_ext,
             qual, conc, mot, local, cert, dose, obs, cor) = origem

            exist_atual = int(to_py(exist_atual) or 0)
            quantidade_int = int(to_py(quantidade) or 0)

            if quantidade_int <= 0:
                st.error(t("error.qty_positive"))
                return False

            if quantidade_int > exist_atual:
                st.error(f"❌ Quantidade insuficiente! Disponível: {exist_atual}")
                return False

            # Atualizar stock origem (diminuir)
            cur.execute("""
                UPDATE estoque_dono
                SET existencia_atual = existencia_atual - %s
                WHERE id = %s
            """, (quantidade_int, to_py(stock_origem_id)))

            # Verificar se já existe lote do destino com mesmo garanhão e mesma NOVA localização
            cur.execute("""
                SELECT id, existencia_atual
                FROM estoque_dono
                WHERE garanhao = %s AND dono_id = %s AND id != %s
                AND COALESCE(contentor_id, 0) = COALESCE(%s, 0)
                AND COALESCE(canister, 0) = COALESCE(%s, 0)
                AND COALESCE(andar, 0) = COALESCE(%s, 0)
                LIMIT 1
            """, (to_py(garanhao), to_py(prop_destino_id), to_py(stock_origem_id),
                  to_py(contentor_id_novo), to_py(canister_novo), to_py(andar_novo)))

            lote_destino = cur.fetchone()

            if lote_destino:
                # Já existe lote na nova localização, adicionar palhetas
                cur.execute("""
                    UPDATE estoque_dono
                    SET existencia_atual = existencia_atual + %s
                    WHERE id = %s
                """, (quantidade_int, lote_destino[0]))
            else:
                # Criar novo lote para o destino com NOVA localização
                cur.execute("""
                    INSERT INTO estoque_dono (
                        garanhao, dono_id, data_embriovet, origem_externa,
                        palhetas_produzidas, qualidade, concentracao, motilidade,
                        local_armazenagem, certificado, dose, observacoes,
                        quantidade_inicial, existencia_atual, cor,
                        contentor_id, canister, andar
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    to_py(garanhao), to_py(prop_destino_id), to_py(data_emb), to_py(origem_ext),
                    quantidade_int, to_py(qual), to_py(conc), to_py(mot),
                    to_py(local), to_py(cert), to_py(dose), to_py(obs),
                    quantidade_int, quantidade_int, to_py(cor),
                    to_py(contentor_id_novo), to_py(canister_novo), to_py(andar_novo)
                ))

            # Registrar transferência na tabela de transferências
            cur.execute("""
                INSERT INTO transferencias (
                    estoque_id, proprietario_origem_id, proprietario_destino_id,
                    quantidade, data_transferencia
                ) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (to_py(stock_origem_id), to_py(prop_origem_db), to_py(prop_destino_id), quantidade_int))

            conn.commit()
            cur.close()

            # Verificar e desativar proprietários com stock = 0
            atualizar_status_proprietarios()

            logger.info(f"Transferência com mudança de local: {quantidade_int} palhetas de {prop_origem_id} para {prop_destino_id}")
            return True

    except Exception as e:
        logger.error(f"Erro ao transferir palhetas com nova localização: {e}")
        st.error(f"Erro ao transferir palhetas: {e}")
        return False

def transferir_palhetas_externo(stock_origem_id, destinatario_externo, quantidade, tipo="Venda", observacoes=""):
    """Transfere palhetas para fora do sistema (venda/doação/exportação)"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            # Buscar dados do lote origem
            cur.execute("""
                SELECT garanhao, dono_id, existencia_atual
                FROM estoque_dono WHERE id = %s
            """, (to_py(stock_origem_id),))

            origem = cur.fetchone()
            if not origem:
                st.error(t("error.origin_lot_not_found"))
                return False

            garanhao, prop_origem_id, exist_atual = origem
            exist_atual = int(to_py(exist_atual) or 0)
            quantidade_int = int(to_py(quantidade) or 0)

            if quantidade_int <= 0:
                st.error(t("error.qty_positive"))
                return False

            if quantidade_int > exist_atual:
                st.error(f"❌ Quantidade insuficiente! Disponível: {exist_atual}")
                return False

            # Atualizar stock origem (diminuir)
            cur.execute("""
                UPDATE estoque_dono
                SET existencia_atual = existencia_atual - %s
                WHERE id = %s
            """, (quantidade_int, to_py(stock_origem_id)))

            # Registrar transferência externa
            cur.execute("""
                INSERT INTO transferencias_externas (
                    estoque_id, proprietario_origem_id, garanhao,
                    destinatario_externo, quantidade, tipo, observacoes,
                    data_transferencia
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (
                to_py(stock_origem_id),
                to_py(prop_origem_id),
                to_py(garanhao),
                to_py(destinatario_externo),
                quantidade_int,
                to_py(tipo),
                to_py(observacoes)
            ))

            conn.commit()
            cur.close()

            # Verificar e desativar proprietários com stock = 0
            atualizar_status_proprietarios()

            logger.info(f"Transferência externa: {quantidade_int} palhetas para {destinatario_externo}")
            return True

    except Exception as e:
        logger.error(f"Erro ao transferir para externo: {e}")
        st.error(f"Erro ao transferir para externo: {e}")
        return False

# Alias para compatibilidade
transferir_stock_externo = transferir_palhetas_externo

# ------------------------------------------------------------
# 🖼️ Interface Streamlit
# ------------------------------------------------------------
st.set_page_config(
    page_title=os.getenv("APP_TITLE", "Sistema"),
    layout=os.getenv("APP_LAYOUT", "wide"),
    initial_sidebar_state="expanded",
    page_icon="🐴",
)

# Consolidar todo o CSS em um único bloco para evitar containers vazios
st.markdown(
    """
    <style>
    [data-testid="stMainMenu"] { display:none !important; }
    footer { display:none !important; }

    div[data-testid="stAppViewContainer"] { padding-top: 0rem !important; }
    section.main > div.block-container { padding-top: .5rem !important; padding-bottom: 1rem !important; }
    [data-testid="stSidebarContent"] { padding-top: .5rem !important; }
    .sidebar-shell { padding-top: 8px !important; }

    header[data-testid="stHeader"] { height: 2.6rem !important; }
    header[data-testid="stHeader"] > div { padding-top: .15rem !important; padding-bottom: .15rem !important; }

    .block-container { margin-top: 0 !important; }

    /* Forçar altura zero em containers vazios */
    div[data-testid="stElementContainer"]:empty {
        display: none !important;
        height: 0px !important;
        min-height: 0px !important;
        max-height: 0px !important;
        margin: 0px !important;
        padding: 0px !important;
        line-height: 0px !important;
    }

    /* Remover espaçamento de elementos sem conteúdo texto */
    div[data-testid="stVerticalBlock"] > div[data-testid="stElementContainer"]:not(:has(*)) {
        display: none !important;
    }

    </style>
    <script>
    (function() {
        // Remover containers vazios diretamente do DOM
        const removeEmptyContainers = () => {
            const containers = document.querySelectorAll('[data-testid="stElementContainer"]');
            containers.forEach(container => {
                // Se o container está vazio ou só contém whitespace
                if (!container.textContent.trim() && !container.querySelector('img, button, input, select, textarea, canvas, svg, iframe')) {
                    container.style.display = 'none';
                    container.style.height = '0px';
                    container.style.margin = '0px';
                    container.style.padding = '0px';
                }
            });
        };

        // Ocultar botão Deploy
        const hideDeploy = () => {
            const root = window.parent.document;
            root.querySelectorAll('button, a').forEach(el => {
                if (el.textContent && el.textContent.trim() === 'Deploy') {
                    el.style.display = 'none';
                }
            });
        };

        // Executar imediatamente
        removeEmptyContainers();
        hideDeploy();

        // Observar mudanças e re-executar
        const obs = new MutationObserver(() => {
            removeEmptyContainers();
            hideDeploy();
        });
        obs.observe(document.body, { childList: true, subtree: true });

        // Executar novamente após um delay para garantir
        setTimeout(() => {
            removeEmptyContainers();
            hideDeploy();
        }, 500);
    })();
    </script>
    """,
    unsafe_allow_html=True,
)

# Injetar TODO o CSS consolidado em um único bloco
inject_all_css_consolidated()

# ------------------------------------------------------------
# 🔐 Sistema de Login
# ------------------------------------------------------------
@st.cache_resource
def get_auth_store():
    return {}

def mostrar_tela_login(app_settings):
    """Exibe tela de login com design premium"""
    nome_empresa = (app_settings or {}).get("company_name") or "Sistema"
    logo_base64 = (app_settings or {}).get("logo_base64")
    cor_primaria = (app_settings or {}).get("primary_color") or "#3b82f6"

    # CSS Premium para a página de login
    st.markdown(
        f"""
        <style>
            /* Esconder elementos do Streamlit */
            #MainMenu, footer, header {{visibility: hidden;}}

            /* Fundo gradiente premium */
            .stApp {{
                background: linear-gradient(135deg, {cor_primaria}15 0%, {cor_primaria}05 100%);
            }}

            /* Card de login */
            .login-card {{
                background: white;
                border-radius: 16px;
                padding: 40px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.08);
                border: 1px solid rgba(0, 0, 0, 0.06);
                max-width: 440px;
                margin: 60px auto;
            }}

            /* Logo */
            .login-logo {{
                text-align: center;
                margin-bottom: 24px;
            }}

            .login-logo img {{
                max-width: 120px;
                height: auto;
                border-radius: 12px;
            }}

            /* Título */
            .login-title {{
                text-align: center;
                font-size: 1.75rem;
                font-weight: 700;
                color: #0f172a;
                margin-bottom: 8px;
            }}

            .login-subtitle {{
                text-align: center;
                font-size: 0.95rem;
                color: #64748b;
                margin-bottom: 32px;
            }}

            /* Inputs mais bonitos */
            .stTextInput input {{
                border-radius: 10px !important;
                border: 1.5px solid #e2e8f0 !important;
                padding: 12px 16px !important;
                font-size: 0.95rem !important;
                transition: all 0.2s ease !important;
            }}

            .stTextInput input:focus {{
                border-color: {cor_primaria} !important;
                box-shadow: 0 0 0 3px {cor_primaria}20 !important;
            }}

            /* Botão premium */
            .stButton > button {{
                border-radius: 10px !important;
                padding: 12px 24px !important;
                font-weight: 600 !important;
                font-size: 1rem !important;
                background: linear-gradient(135deg, {cor_primaria} 0%, {cor_primaria}dd 100%) !important;
                border: none !important;
                box-shadow: 0 4px 12px {cor_primaria}40 !important;
                transition: all 0.2s ease !important;
            }}

            .stButton > button:hover {{
                transform: translateY(-2px) !important;
                box-shadow: 0 6px 20px {cor_primaria}50 !important;
            }}

            /* Footer do card */
            .login-footer {{
                text-align: center;
                margin-top: 24px;
                padding-top: 24px;
                border-top: 1px solid #f1f5f9;
                font-size: 0.85rem;
                color: #94a3b8;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Centralizar o formulário
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("<div class='login-card'>", unsafe_allow_html=True)

        # Logo
        if logo_base64:
            st.markdown(
                f"<div class='login-logo'><img src='data:image/png;base64,{logo_base64}' /></div>",
                unsafe_allow_html=True
            )

        # Título
        st.markdown(f"<div class='login-title'>{nome_empresa}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='login-subtitle'>{t('login.subtitle')}</div>", unsafe_allow_html=True)

        # Formulário
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input(
                t("auth.username"),
                placeholder=t("auth.username_placeholder"),
                label_visibility="collapsed"
            )
            password = st.text_input(
                t("auth.password"),
                type="password",
                placeholder=t("auth.password_placeholder"),
                label_visibility="collapsed"
            )

            submitted = st.form_submit_button(
                t("auth.login"),
                type="primary",
                use_container_width=True
            )

            if submitted:
                if not username or not password:
                    st.error(t("login.missing"))
                else:
                    user = autenticar_usuario(username, password)
                    if user:
                        token = str(uuid.uuid4())
                        auth_store = get_auth_store()
                        auth_store[token] = user
                        st.session_state['user'] = user
                        st.session_state['auth_token'] = token
                        st.query_params.session = token
                        st.success(t("login.welcome", name=user["nome"]))
                        st.rerun()
                    else:
                        st.error(t("login.invalid"))

        # Footer
        st.markdown(
            f"<div class='login-footer'>🔒 {t('login.secure')}</div>",
            unsafe_allow_html=True
        )

        st.markdown("</div>", unsafe_allow_html=True)


def verificar_permissao(nivel_minimo):
    """Verifica se o usuário tem permissão mínima necessária"""
    if 'user' not in st.session_state:
        return False

    user_nivel = st.session_state['user']['nivel']

    niveis = {
        'Administrador': 3,
        'Gestor': 2,
        'Visualizador': 1
    }

    return niveis.get(user_nivel, 0) >= niveis.get(nivel_minimo, 0)


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

if not app_settings.get("welcome_completed", False):
    render_welcome_page()
    st.stop()

if not app_settings.get("is_initialized"):
    render_onboarding(app_settings)
    st.stop()

# Verificar se está logado (restaurar sessão por query param)
auth_store = get_auth_store()
token_param = st.query_params.get("session", None)
if 'user' not in st.session_state and token_param and token_param in auth_store:
    st.session_state['user'] = auth_store[token_param]
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

settings_clicked, logout_clicked = render_header(app_settings, user)
if logout_clicked:
    token = st.session_state.pop('auth_token', None)
    if token:
        auth_store = get_auth_store()
        auth_store.pop(token, None)
    st.query_params.clear()
    del st.session_state['user']
    st.rerun()
if settings_clicked:
    st.session_state['aba_selecionada'] = t("menu.settings")
    st.rerun()

# Menu lateral adaptado às permissões
# Menu Principal (sempre visível)
menu_principal = [
    t("menu.dashboard"),
]

# Menu Secundário (dentro do expander)
menu_secundario = [
    t("menu.map"),
]

# Adicionar opções baseadas em permissões
if verificar_permissao('Gestor'):
    menu_principal.append(t("menu.add_stock"))
    menu_principal.append(t("menu.register_insemination"))
    menu_principal.append(t("menu.transfers"))
    menu_secundario.append(t("menu.import"))
    menu_secundario.append(t("menu.owners"))

# Ver Stock e Relatórios sempre no menu principal (para todos)
menu_principal.append(t("menu.stock"))
menu_principal.append(t("menu.reports"))

# Administrador tem acesso a mais opções secundárias
if verificar_permissao('Administrador'):
    menu_secundario.append(t("menu.users"))
    menu_secundario.append(t("menu.settings"))

# Verificar se há redirecionamento pendente
if 'aba_selecionada' in st.session_state:
    active_key = st.session_state['aba_selecionada']
    del st.session_state['aba_selecionada']
    # Sinalizar redirect para o render_sidebar
    st.session_state['_nav_redirect_active'] = active_key
else:
    active_key = st.session_state.get("_nav_last_active", menu_principal[0])

aba = render_sidebar(app_settings, user, menu_principal, menu_secundario, active_key)

# ------------------------------------------------------------
# 💬 Modal para adicionar proprietário
# ------------------------------------------------------------
@st.dialog(t("owners.add_new_title"))
def modal_adicionar_proprietario():
    """Modal para adicionar novo proprietário rapidamente"""
    novo_nome = st.text_input(t("owners.name_required"), key="modal_novo_prop")

    col1, col2 = st.columns(2)
    with col1:
        if st.button(t("btn.add"), type="primary", width="stretch"):
            if not novo_nome:
                st.error(t("error.name_required"))
            else:
                # Criar dados mínimos
                dados_novo = {'nome': novo_nome, 'email': None, 'telemovel': None,
                              'nome_completo': None, 'nif': None, 'morada': None,
                              'codigo_postal': None, 'cidade': None}
                prop_id = adicionar_proprietario(dados_novo)
                if prop_id:
                    st.session_state['novo_proprietario_id'] = prop_id
                    st.session_state['novo_proprietario_nome'] = novo_nome
                    st.success(t("owners.added", name=novo_nome))
                    st.rerun()
    with col2:
        if st.button(t("btn.cancel"), width="stretch"):
            st.rerun()

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
# Router de páginas (Fase 3 da modularização)
# ------------------------------------------------------------
if aba == t("menu.map"):
    run_map_page({**globals(), **locals()})
    st.stop()

if aba == t("menu.dashboard"):
    run_dashboard_page({**globals(), **locals()})
    st.stop()

if aba == t("menu.stock"):
    run_stock_page({**globals(), **locals()})
    st.stop()

if aba == t("menu.transfers"):
    run_transfer_page({**globals(), **locals()})
    st.stop()

if aba == t("menu.reports"):
    run_reports_page({**globals(), **locals()})
    st.stop()

if aba == t("menu.settings"):
    run_settings_page({**globals(), **locals()})
    st.stop()

# ------------------------------------------------------------
# ➕ Adicionar Stock
# ------------------------------------------------------------
elif aba == t("menu.add_stock"):
    st.header(t("add_stock.title"))
    primary = (app_settings or {}).get("primary_color") or "#E85D4A"
    inject_add_stock_form_css(primary_color=primary)

    if proprietarios.empty:
        st.warning(t("add_stock.no_owners"))
        if st.button(t("add_stock.add_first_owner"), type="primary"):
            modal_adicionar_proprietario()
    else:
        # Carregar contentores
        contentores_df = carregar_contentores()

        if contentores_df.empty:
            st.warning(t("add_stock.no_containers"))
        else:
            # Botão + fora do form (Alinhado à direita)
            col_act1, col_act2 = st.columns([6, 2])
            with col_act2:
                if st.button(f"➕ {t('stock.new_owner')}", key="btn_add_prop_stock", help=t("stock.new_owner_help"), use_container_width=True):
                    modal_adicionar_proprietario()
            
            with st.form("novo_stock"):
                # SEÇÃO 1: IDENTIDADE
                st.markdown('<div class="form-card"><div class="form-section-header">🐴 Identificação</div>', unsafe_allow_html=True)
                col_id1, col_id2 = st.columns(2)
                
                with col_id1:
                    garanhao = st.text_input(t("label.garanhao_required"), help=t("add_stock.required_name"))
                
                with col_id2:
                    # Verificar se há proprietário recém-adicionado
                    if 'novo_proprietario_id' in st.session_state:
                        try:
                            idx_default = list(proprietarios["id"]).index(st.session_state['novo_proprietario_id'])
                        except ValueError:
                            idx_default = 0
                    else:
                        idx_default = 0
                    
                    proprietario_nome = st.selectbox(t("add_stock.owner_semen"), proprietarios["nome"], index=idx_default)
                    dono_id = int(proprietarios.loc[proprietarios["nome"] == proprietario_nome, "id"].iloc[0])
                st.markdown('</div>', unsafe_allow_html=True)

                # SEÇÃO 2: DADOS TÉCNICOS
                st.markdown('<div class="form-card"><div class="form-section-header">🔬 Dados Técnicos</div>', unsafe_allow_html=True)
                col_tec1, col_tec2, col_tec3, col_tec4 = st.columns(4)
                
                with col_tec1:
                    motilidade = st.number_input(t("stock.motility_pct"), min_value=0, max_value=100, value=0)
                with col_tec2:
                    concentracao = st.number_input(t("stock.concentration"), min_value=0, value=0)
                with col_tec3:
                    qualidade = st.text_input(t("stock.quality_text"))
                with col_tec4:
                    cor = st.text_input(t("stock.color"))
                
                col_tec5, col_tec6 = st.columns(2)
                with col_tec5:
                    certificado = st.selectbox(t("stock.certificate"), [t("common.yes"), t("common.no")])
                with col_tec6:
                    dose = st.text_input(t("stock.dose"))
                st.markdown('</div>', unsafe_allow_html=True)

                # SEÇÃO 3: PRODUÇÃO
                st.markdown('<div class="form-card"><div class="form-section-header">📦 Produção</div>', unsafe_allow_html=True)
                col_prod1, col_prod2, col_prod3 = st.columns(3)
                
                with col_prod1:
                    data = st.text_input(t("stock.prod_date"))
                with col_prod2:
                    palhetas = st.number_input(t("stock.straws_produced"), min_value=0, value=0)
                with col_prod3:
                    origem = st.text_input(t("stock.external_origin"))
                st.markdown('</div>', unsafe_allow_html=True)

                # SEÇÃO 4: LOCALIZAÇÃO
                st.markdown('<div class="form-card"><div class="form-section-header">📍 Localização no Contentor</div>', unsafe_allow_html=True)
                
                col_loc1, col_loc2, col_loc3 = st.columns(3)
                with col_loc1:
                    contentor_selecionado = st.selectbox(
                        t("label.container_required"),
                        options=contentores_df["codigo"].tolist(),
                        help=t("add_stock.container_help")
                    )
                    contentor_id = int(contentores_df.loc[contentores_df["codigo"] == contentor_selecionado, "id"].iloc[0])

                with col_loc2:
                    canister = st.selectbox(
                        t("label.canister_required"),
                        options=list(range(1, 11)),
                        help=t("add_stock.canister_help")
                    )

                with col_loc3:
                    andar = st.radio(
                        t("label.floor_required"),
                        options=[1, 2],
                        format_func=lambda x: f"{x}º",
                        horizontal=True,
                        help=t("add_stock.floor_help")
                    )
                st.markdown('</div>', unsafe_allow_html=True)

                # OBSERVAÇÕES E SUBMIT
                st.markdown('<div class="form-card"><div class="form-section-header">💬 Observações</div>', unsafe_allow_html=True)
                observacoes = st.text_area(t("label.notes"), help=t("add_stock.notes_help"), label_visibility="collapsed")
                st.markdown('</div>', unsafe_allow_html=True)

                submitted = st.form_submit_button(t("btn.save"), type="primary", use_container_width=True)

                if submitted:
                    palhetas_int = int(to_py(palhetas) or 0)

                    if not garanhao:
                        st.error(t("error.stallion_required"))
                    elif palhetas_int <= 0:
                        st.error(t("error.straws_positive"))
                    else:
                        ok = inserir_stock(
                            {
                                "Garanhão": garanhao,
                                "Proprietário": dono_id,
                                "Data": data,
                                "Origem": origem,
                                "Palhetas": palhetas_int,
                                "Qualidade": to_py(qualidade),
                                "Concentração": to_py(concentracao),
                                "Motilidade": int(to_py(motilidade) or 0),
                                "Certificado": certificado,
                                "Dose": dose,
                                "Contentor": contentor_id,
                                "Canister": canister,
                                "Andar": andar,
                                "Cor": to_py(cor),
                                "Observações": observacoes,
                            }
                        )
                        if ok:
                            st.success(t("success.stock_added"))
                            # Marcar que usou o proprietário
                            if 'novo_proprietario_id' in st.session_state:
                                st.session_state['novo_proprietario_usado'] = True
                            # Mudar aba para Ver Stock
                            st.session_state['aba_selecionada'] = t("menu.stock")
                            st.rerun()

# ------------------------------------------------------------
# 📥 Importar Sémen
# ------------------------------------------------------------
elif aba == t("menu.import"):
    run_import_page({**globals(), **locals()})
    st.stop()

# ------------------------------------------------------------
# 📝 Registrar Inseminação
# ------------------------------------------------------------
elif aba == t("menu.register_insemination"):
    run_insemination_page({**globals(), **locals()})
    st.stop()

elif aba == t("menu.owners"):
    st.header(t("owners.title"))

    # Verificar e criar coluna ativo se não existir
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            # Verificar se a coluna existe
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name='dono' AND column_name='ativo'
            """)
            if not cur.fetchone():
                # Criar coluna se não existir
                cur.execute("ALTER TABLE dono ADD COLUMN ativo BOOLEAN DEFAULT TRUE")
                cur.execute("UPDATE dono SET ativo = TRUE WHERE ativo IS NULL")
                conn.commit()
                st.success(t("owners.column_created"))
            cur.close()
    except Exception as e:
        st.error(t("owners.column_error", error=e))

    # TODO: Implementar desativação automática nas transações de stock
    # atualizar_status_proprietarios()

    # Limpar cache se houver mudança de status
    if 'status_changed' in st.session_state:
        del st.session_state['status_changed']
        st.cache_data.clear()

    # Recarregar proprietários (todos, não apenas ativos) - sempre fresh
    proprietarios_todos = carregar_proprietarios(apenas_ativos=False)

    tab1, tab2 = st.tabs([t("owners.tab.list"), t("owners.tab.add")])

    # TAB 1: Lista
    with tab1:
        if proprietarios_todos.empty:
            st.info(t("owners.none_registered"))
        else:
            # Filtro e Ordenação
            col_f1, col_f2 = st.columns(2)

            with col_f1:
                filtro_status = st.radio(t("owners.filter"), [t("owners.filter.all"), t("owners.filter.active"), t("owners.filter.inactive")], horizontal=True)

            with col_f2:
                ordenar_por = st.selectbox(t("owners.sort_by"), [t("owners.sort.name"), t("owners.sort.id"), t("owners.sort.status")])

            # Aplicar filtro
            if filtro_status == t("owners.filter.active"):
                props_exibir = proprietarios_todos[proprietarios_todos['ativo'] == True].copy()
            elif filtro_status == t("owners.filter.inactive"):
                props_exibir = proprietarios_todos[proprietarios_todos['ativo'] == False].copy()
            else:
                props_exibir = proprietarios_todos.copy()

            # Aplicar ordenação
            if ordenar_por == t("owners.sort.name"):
                props_exibir = props_exibir.sort_values('nome')
            elif ordenar_por == t("owners.sort.id"):
                props_exibir = props_exibir.sort_values('id')
            elif ordenar_por == t("owners.sort.status"):
                props_exibir = props_exibir.sort_values('ativo', ascending=False)

            st.markdown(t("owners.count", count=len(props_exibir)))
            st.markdown("---")

            # Lista de proprietários (estilo lotes)
            for _, prop in props_exibir.iterrows():
                # Status
                status_icon = "🟢" if prop.get('ativo', True) else "🔴"
                status_text = t("owners.status.active") if prop.get('ativo', True) else t("owners.status.inactive")

                # Título do expander com ID | Nome | Status
                titulo = f"**{prop['id']}** | {prop['nome']} | {status_icon} {status_text}"

                # Verificar se este expander deve estar expandido
                expandido = st.session_state.get(f'expand_{prop["id"]}', False)

                # Expander
                with st.expander(titulo, expanded=expandido):

                    # Tabs: Detalhes e Editar
                    tab_det, tab_edit = st.tabs([t("owners.tab.details"), t("owners.tab.edit")])

                    # TAB: Detalhes
                    with tab_det:
                        col1, col2 = st.columns(2)

                        with col1:
                            st.markdown(f"**🆔 {t('label.id')}:** {prop['id']}")
                            st.markdown(f"**👤 {t('label.name')}:** {prop['nome']}")
                            st.markdown(f"**📧 {t('label.email')}:** {prop.get('email') or t('common.na')}")
                            st.markdown(f"**📱 {t('label.phone')}:** {prop.get('telemovel') or t('common.na')}")

                        with col2:
                            st.markdown(f"**📄 {t('label.full_name')}:** {prop.get('nome_completo') or t('common.na')}")
                            st.markdown(f"**🔢 {t('label.nif')}:** {prop.get('nif') or t('common.na')}")
                            st.markdown(f"**📍 {t('label.address')}:** {prop.get('morada') or t('common.na')}")
                            st.markdown(f"**📮 {t('label.postal_code')}:** {prop.get('codigo_postal') or t('common.na')}")
                            st.markdown(f"**🏙️ {t('label.city')}:** {prop.get('cidade') or t('common.na')}")

                        st.markdown("---")

                        # Botões de ação
                        col_a1, col_a2 = st.columns(2)

                        with col_a1:
                            # Botão de alternar status
                            status_atual = prop.get('ativo', True)
                            btn_label = t("owners.deactivate") if status_atual else t("owners.activate")
                            btn_type = "secondary" if status_atual else "primary"

                            if st.button(btn_label, key=f"status_{prop['id']}", width="stretch", type=btn_type):
                                # Marcar para manter expandido
                                st.session_state[f'expand_{prop["id"]}'] = True
                                st.session_state['status_changed'] = True
                                # Alternar status
                                resultado = alternar_status_proprietario(prop['id'])
                                if resultado is not None:
                                    novo_status = t("owners.status.active") if resultado else t("owners.status.inactive")
                                    st.success(t("owners.status_changed", status=novo_status))
                                    # Forçar rerun imediato
                                    time.sleep(0.3)
                                    st.rerun()
                                else:
                                    st.error(t("owners.status_error"))

                        with col_a2:
                            if st.button(t("btn.delete"), key=f"del_{prop['id']}", width="stretch", type="secondary"):
                                if deletar_proprietario(prop['id']):
                                    if f'expand_{prop["id"]}' in st.session_state:
                                        del st.session_state[f'expand_{prop["id"]}']
                                    st.success(t("success.deleted"))
                                    st.rerun()

                    # TAB: Editar
                    with tab_edit:
                        st.markdown(f"### {t('owners.edit_title')}")

                        with st.form(key=f"form_edit_{prop['id']}"):
                            col1, col2 = st.columns(2)

                            with col1:
                                nome_e = st.text_input(t("label.name_required"), value=prop.get('nome', ''))
                                email_e = st.text_input(t("label.email"), value=prop.get('email', '') or '')
                                tel_e = st.text_input(t("label.phone"), value=prop.get('telemovel', '') or '')
                                nc_e = st.text_input(t("label.full_name"), value=prop.get('nome_completo', '') or '')

                            with col2:
                                nif_e = st.text_input(t("label.nif"), value=prop.get('nif', '') or '')
                                morada_e = st.text_area(t("label.address"), value=prop.get('morada', '') or '', height=100)
                                cp_e = st.text_input(t("label.postal_code"), value=prop.get('codigo_postal', '') or '')
                                cidade_e = st.text_input(t("label.city"), value=prop.get('cidade', '') or '')

                            salvar = st.form_submit_button(t("btn.save_changes"), type="primary", width="stretch")

                            if salvar:
                                if not nome_e:
                                    st.error(t("error.name_required"))
                                else:
                                    dados = {
                                        'nome': nome_e,
                                        'email': email_e,
                                        'telemovel': tel_e,
                                        'nome_completo': nc_e,
                                        'nif': nif_e,
                                        'morada': morada_e,
                                        'codigo_postal': cp_e,
                                        'cidade': cidade_e
                                    }
                                    if editar_proprietario(prop['id'], dados):
                                        st.success(t("success.updated"))
                                        st.rerun()

    # TAB 2: Adicionar
    with tab2:
        st.markdown(f"### {t('owners.new_title')}")

        with st.form("form_adicionar"):
            col1, col2 = st.columns(2)

            with col1:
                nome_n = st.text_input(t("label.name_required"))
                email_n = st.text_input(t("label.email"))
                tel_n = st.text_input(t("label.phone"))
                nc_n = st.text_input(t("label.full_name"))

            with col2:
                nif_n = st.text_input(t("label.nif"))
                morada_n = st.text_area(t("label.address"), height=100)
                cp_n = st.text_input(t("label.postal_code"))
                cidade_n = st.text_input(t("label.city"))

            adicionar = st.form_submit_button(t("btn.add"), type="primary", width="stretch")

            if adicionar:
                if not nome_n:
                    st.error(t("error.name_required"))
                else:
                    dados = {
                        'nome': nome_n,
                        'email': email_n,
                        'telemovel': tel_n,
                        'nome_completo': nc_n,
                        'nif': nif_n,
                        'morada': morada_n,
                        'codigo_postal': cp_n,
                        'cidade': cidade_n
                    }
                    prop_id = adicionar_proprietario(dados)
                    if prop_id:
                        st.success(t("owners.added", name=nome_n))
                        st.rerun()

# ------------------------------------------------------------
# ⚙️ Gestão de Utilizadores (Apenas Administrador)
# ------------------------------------------------------------
elif aba == t("menu.users"):
    st.header(t("users.title"))

    usuarios_df = carregar_usuarios()

    tab1, tab2, tab3 = st.tabs([
        t("users.tab.list"),
        t("users.tab.add"),
        t("users.tab.change_password"),
    ])

    # TAB 1: Lista
    with tab1:
        if usuarios_df.empty:
            st.info(t("users.none_registered"))
        else:
            st.markdown(t("users.total", count=len(usuarios_df)))

            # Filtros
            col1, col2 = st.columns(2)
            with col1:
                filtro_nivel = st.multiselect(
                    t("users.filter_level"),
                    options=usuarios_df["nivel"].unique(),
                    default=None,
                )
            with col2:
                filtro_status = st.selectbox(
                    t("label.status"),
                    [t("owners.filter.all"), t("owners.filter.active"), t("owners.filter.inactive")],
                )

            usuarios_filtrado = usuarios_df.copy()
            if filtro_nivel:
                usuarios_filtrado = usuarios_filtrado[usuarios_filtrado["nivel"].isin(filtro_nivel)]
            if filtro_status == t("owners.filter.active"):
                usuarios_filtrado = usuarios_filtrado[usuarios_filtrado["ativo"] == True]
            elif filtro_status == t("owners.filter.inactive"):
                usuarios_filtrado = usuarios_filtrado[usuarios_filtrado["ativo"] == False]

            st.markdown("---")

            for _, usr in usuarios_filtrado.iterrows():
                status_emoji = "✅" if usr['ativo'] else "❌"
                with st.expander(t("users.expander", name=usr['nome_completo'], username=usr['username'], level=usr['nivel'], status_icon=status_emoji)):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**{t('label.id')}:** {usr['id']}")
                        st.markdown(f"**Username:** {usr['username']}")
                        st.markdown(f"**{t('label.name')}:** {usr['nome_completo']}")
                        st.markdown(f"**{t('label.level')}:** {usr['nivel']}")
                        st.markdown(f"**{t('label.status')}:** {t('owners.status.active') if usr['ativo'] else t('owners.status.inactive')}")
                        st.markdown(f"**{t('label.created_at')}:** {usr['created_at']}")
                        if usr['last_login']:
                            st.markdown(f"**{t('label.last_login')}:** {usr['last_login']}")

                    with col2:
                        if usr['ativo']:
                            if st.button(t("users.deactivate"), key=f"deactivate_{usr['id']}", type="secondary"):
                                if desativar_usuario(usr['id']):
                                    st.success(t("users.deactivated"))
                                    st.rerun()
                        else:
                            if st.button(t("users.activate"), key=f"activate_{usr['id']}", type="primary"):
                                if ativar_usuario(usr['id']):
                                    st.success(t("users.activated"))
                                    st.rerun()

    # TAB 2: Adicionar
    with tab2:
        st.markdown(f"### {t('users.add_new')}")

        with st.form("add_usuario"):
            novo_username = st.text_input(t("users.username_required"), placeholder=t("users.username_placeholder"))
            novo_nome = st.text_input(t("label.full_name_required"))
            novo_nivel = st.selectbox(t("users.access_level"), [t("users.level.admin"), t("users.level.manager"), t("users.level.viewer")])
            nova_password = st.text_input(t("users.password_label"), type="password", placeholder=t("users.password_min"))
            confirma_password = st.text_input(t("users.password_confirm"), type="password")

            submit = st.form_submit_button(t("users.create_user"), type="primary")

            if submit:
                if not novo_username or not novo_nome or not nova_password:
                    st.error(t("users.fill_required"))
                elif len(nova_password) < 6:
                    st.error(t("users.password_min_error"))
                elif nova_password != confirma_password:
                    st.error(t("error.passwords_mismatch"))
                elif " " in novo_username:
                    st.error(t("users.username_no_spaces"))
                else:
                    if adicionar_usuario(novo_username, novo_nome, nova_password, novo_nivel, user['id']):
                        st.success(t("users.created", username=novo_username))
                        st.info(t("users.credentials", username=novo_username, password=nova_password))
                        # Redirecionar para a lista de utilizadores
                        st.session_state['show_user_tab'] = 0  # Tab lista
                        st.rerun()

        st.markdown("---")
        st.markdown(f"### {t('users.access_levels_title')}")

        st.markdown(f"""
        **🔴 {t('users.level.admin')}** (Nível 3 - Acesso Total)
        - ✅ Ver Dashboard, Mapa, Stock e Relatórios
        - ✅ Adicionar Stock, Importar Sémen
        - ✅ Registar Inseminações
        - ✅ **Editar Stock** (alterar dados dos lotes)
        - ✅ **Página de Transferências** (interno e externo)
        - ✅ Gerir Proprietários (adicionar, editar, desativar)
        - ✅ **Gerir Utilizadores** (criar, editar, desativar)
        - ✅ **Aceder às Definições** (branding, idioma)

        **🟡 {t('users.level.manager')}** (Nível 2 - Gestão Operacional)
        - ✅ Ver Dashboard, Mapa, Stock e Relatórios
        - ✅ Adicionar Stock, Importar Sémen
        - ✅ Registar Inseminações
        - ❌ **NÃO pode Editar Stock** (apenas visualizar detalhes)
        - ✅ **Página de Transferências** (interno e externo)
        - ✅ Gerir Proprietários (adicionar, editar, desativar)
        - ❌ NÃO pode Gerir Utilizadores
        - ❌ NÃO pode aceder às Definições

        **🟢 {t('users.level.viewer')}** (Nível 1 - Apenas Visualização)
        - ✅ Ver Dashboard, Mapa, Stock e Relatórios
        - ❌ NÃO pode Adicionar Stock
        - ❌ NÃO pode Importar Sémen
        - ❌ NÃO pode Registar Inseminações
        - ❌ NÃO pode Editar Stock
        - ❌ **NÃO pode aceder à Página de Transferências**
        - ❌ NÃO pode Gerir Proprietários
        - ❌ NÃO pode Gerir Utilizadores
        - ❌ NÃO pode aceder às Definições
        """)

        st.info("💡 **Nota:** O primeiro utilizador criado no sistema é sempre Administrador.")

    # TAB 3: Alterar Password
    with tab3:
        st.markdown(f"### {t('users.change_password_title')}")

        if not usuarios_df.empty:
            with st.form("change_password"):
                usuario_selecionado = st.selectbox(
                    t("users.select_user"),
                    options=usuarios_df["id"].tolist(),
                    format_func=lambda x: f"{usuarios_df[usuarios_df['id']==x]['nome_completo'].values[0]} (@{usuarios_df[usuarios_df['id']==x]['username'].values[0]})"
                )

                nova_senha = st.text_input(t("users.new_password"), type="password", placeholder=t("users.password_min"))
                confirma_senha = st.text_input(t("users.password_confirm_new"), type="password")

                submit_senha = st.form_submit_button(t("users.change_password_btn"), type="primary")

                if submit_senha:
                    if not nova_senha:
                        st.error(t("users.password_required"))
                    elif len(nova_senha) < 6:
                        st.error(t("users.password_min_error"))
                    elif nova_senha != confirma_senha:
                        st.error(t("error.passwords_mismatch"))
                    else:
                        if alterar_password(usuario_selecionado, nova_senha):
                            usr_nome = usuarios_df[usuarios_df['id']==usuario_selecionado]['nome_completo'].values[0]
                            st.success(t("users.password_changed", name=usr_nome))
                            st.info(t("users.new_password_info", password=nova_senha))

# ------------------------------------------------------------
# Footer
# ------------------------------------------------------------
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
