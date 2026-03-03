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
from modules.pages.dashboard_page import run_dashboard_page
from modules.pages.settings_page import run_settings_page
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
                       qualidade, concentracao, motilidade, local_armazenagem, certificado, dose, observacoes, cor
                FROM estoque_dono WHERE id = %s
            """, (to_py(stock_origem_id),))

            origem = cur.fetchone()
            if not origem:
                st.error(t("error.origin_lot_not_found"))
                return False
            
            (garanhao, prop_origem_id, exist_atual, data_emb, origem_ext, 
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

            # Verificar se já existe lote do destino com mesmo garanhão
            cur.execute("""
                SELECT id, existencia_atual
                FROM estoque_dono
                WHERE garanhao = %s AND dono_id = %s AND id != %s
                LIMIT 1
            """, (to_py(garanhao), to_py(proprietario_destino_id), to_py(stock_origem_id)))

            lote_destino = cur.fetchone()

            if lote_destino:
                # Já existe lote, adicionar palhetas
                cur.execute("""
                    UPDATE estoque_dono
                    SET existencia_atual = existencia_atual + %s
                    WHERE id = %s
                """, (quantidade_int, lote_destino[0]))
            else:
                # Criar novo lote para o destino
                cur.execute("""
                    INSERT INTO estoque_dono (
                        garanhao, dono_id, data_embriovet, origem_externa,
                        palhetas_produzidas, qualidade, concentracao, motilidade,
                        local_armazenagem, certificado, dose, observacoes,
                        quantidade_inicial, existencia_atual, cor
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    to_py(garanhao), to_py(proprietario_destino_id), to_py(data_emb), to_py(origem_ext),
                    quantidade_int, to_py(qual), to_py(conc), to_py(mot),
                    to_py(local), to_py(cert), to_py(dose), to_py(obs),
                    quantidade_int, quantidade_int, to_py(cor)
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
    """Exibe tela de login"""
    nome_empresa = (app_settings or {}).get("company_name") or "Sistema"
    st.title(t("login.title", company=nome_empresa))

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown(f"### {t('login.auth')}")

        with st.form("login_form"):
            label_user = "👤 " + t("auth.username")
            label_pass = "🔒 " + t("auth.password")
            btn_label = "🚀 " + t("auth.login")

            username = st.text_input(label_user, placeholder=t("auth.username_placeholder"))
            password = st.text_input(label_pass, type="password", placeholder=t("auth.password_placeholder"))

            submitted = st.form_submit_button(btn_label, type="primary", width="stretch")

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
                        set_session_query_param(token)
                        st.success(t("login.welcome", name=user["nome"]))
                        st.rerun()
                    else:
                        st.error(t("login.invalid"))



def set_session_query_param(token: str) -> None:
    """Set session query param using Streamlit stable API."""
    st.query_params["session"] = token


def get_session_query_param():
    """Read session query param using Streamlit stable API."""
    session_value = st.query_params.get("session")
    if isinstance(session_value, list):
        return session_value[0] if session_value else None
    return session_value


def clear_query_params() -> None:
    """Clear query params using Streamlit stable API."""
    st.query_params.clear()

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
token_param = get_session_query_param()
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
    clear_query_params()
    del st.session_state['user']
    st.rerun()
if settings_clicked:
    st.session_state['aba_selecionada'] = t("menu.settings")
    st.rerun()

# Menu lateral adaptado às permissões
menu_options = [
    t("menu.dashboard"),
    t("menu.map"),
    t("menu.stock"),
    t("menu.reports"),
]

if verificar_permissao('Gestor'):
    menu_options.insert(2, t("menu.add_stock"))
    menu_options.insert(3, t("menu.import"))
    menu_options.insert(4, t("menu.register_insemination"))
    menu_options.append(t("menu.owners"))

if verificar_permissao('Administrador'):
    menu_options.append(t("menu.users"))
    menu_options.append(t("menu.settings"))

# Verificar se há redirecionamento pendente
if 'aba_selecionada' in st.session_state:
    idx_aba = menu_options.index(st.session_state['aba_selecionada']) if st.session_state['aba_selecionada'] in menu_options else 0
    del st.session_state['aba_selecionada']
else:
    idx_aba = 0

active_key = menu_options[idx_aba] if menu_options else ""
aba = render_sidebar(app_settings, user, menu_options, active_key)

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
            # Botão + fora do form
            if st.button(t("stock.new_owner"), key="btn_add_prop_stock", help=t("stock.new_owner_help")):
                modal_adicionar_proprietario()

            with st.form("novo_stock"):
                garanhao = st.text_input(t("label.garanhao_required"), help=t("add_stock.required_name"))

                # Verificar se há proprietário recém-adicionado
                if 'novo_proprietario_id' in st.session_state:
                    idx_default = list(proprietarios["id"]).index(st.session_state['novo_proprietario_id'])
                else:
                    idx_default = 0

                proprietario_nome = st.selectbox(t("add_stock.owner_semen"), proprietarios["nome"], index=idx_default)

                dono_id = int(proprietarios.loc[proprietarios["nome"] == proprietario_nome, "id"].iloc[0])

                col1, col2 = st.columns(2)
                with col1:
                    data = st.text_input(t("stock.prod_date"))
                    origem = st.text_input(t("stock.external_origin"))
                    palhetas = st.number_input(t("stock.straws_produced"), min_value=0, value=0)
                    qualidade = st.text_input(t("stock.quality_text"))
                    cor = st.text_input(t("stock.color"))
                    concentracao = st.number_input(t("stock.concentration"), min_value=0, value=0)

                with col2:
                    motilidade = st.number_input(t("stock.motility_pct"), min_value=0, max_value=100, value=0)
                    certificado = st.selectbox(t("stock.certificate"), [t("common.yes"), t("common.no")])
                    dose = st.text_input(t("stock.dose"))

                st.markdown("---")
                st.subheader(t("stock.location_title"))

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

                observacoes = st.text_area(t("label.notes"), help=t("add_stock.notes_help"))
                submitted = st.form_submit_button(t("btn.save"))

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
    st.header(t("import.title"))

    st.markdown(
        """
        <style>
            .import-zone-title {
                font-size: .78rem;
                text-transform: uppercase;
                letter-spacing: .05em;
                color: #64748b;
                margin: .2rem 0 .35rem 0;
                font-weight: 700;
            }
            .import-toolbar {
                border: 1px solid #dbe4ee;
                border-radius: 8px;
                background: #f8fafc;
                padding: 6px 8px;
                margin-bottom: 6px;
            }
            .import-hint {
                font-size: .78rem;
                color: #475569;
            }
            .import-table-wrap {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                overflow-x: auto;
                max-width: 100%;
            }
            .import-table {
                width: 100%;
                border-collapse: collapse;
                font-size: .78rem;
            }
            .import-table th, .import-table td {
                border-bottom: 1px solid #e2e8f0;
                padding: 4px 6px;
                white-space: nowrap;
                text-align: left;
            }
            .import-table th {
                position: sticky;
                top: 0;
                background: #f1f5f9;
                z-index: 4;
                font-weight: 700;
                color: #0f172a;
            }
            .import-sticky-1, .import-sticky-2, .import-sticky-3 {
                position: sticky;
                background: #f8fafc;
                z-index: 3;
            }
            .import-sticky-1 { left: 0; min-width: 160px; }
            .import-sticky-2 { left: 160px; min-width: 140px; }
            .import-sticky-3 { left: 300px; min-width: 120px; }
            .import-table th.import-sticky-1,
            .import-table th.import-sticky-2,
            .import-table th.import-sticky-3 {
                z-index: 6;
                background: #e2e8f0;
            }
            .import-error-cell {
                background: #fee2e2 !important;
                color: #991b1b;
            }
            .import-error-icon {
                margin-left: 4px;
                font-size: .75rem;
                color: #dc2626;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    template_cols = [
        "garanhao",
        "data_embriovet/ref",
        "existencia_atual",
        "dose",
        "motilidade",
        "qualidade",
        "concentracao",
        "cor",
        "proprietario_nome",
        "contentor_codigo",
        "canister",
        "andar",
        "observacoes",
        "certificado",
    ]

    template_df = pd.DataFrame(columns=template_cols)
    xlsx_ready = importlib.util.find_spec("openpyxl") is not None

    def gerar_template_xlsx():
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            template_df.to_excel(writer, index=False, sheet_name="importar_semen")
        buffer.seek(0)
        return buffer.getvalue()

    def gerar_template_csv():
        return template_df.to_csv(index=False).encode("utf-8")

    def normalizar_coluna(nome):
        base = str(nome).strip().lower()
        base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
        base = base.replace("/", "_").replace("-", "_").replace(" ", "_")
        return base

    alias_map = {
        "garanhao": "garanhao",
        "garanhao": "garanhao",
        "data_embriovet_ref": "data_ref",
        "data_embriovet": "data_ref",
        "ref": "data_ref",
        "data": "data_ref",
        "existencia_atual": "existencia_atual",
        "existencia": "existencia_atual",
        "palhetas": "existencia_atual",
        "dose": "dose",
        "motilidade": "motilidade",
        "concentracao": "concentracao",
        "concentração": "concentracao",
        "cor": "cor",
        "color": "cor",
        "proprietario_nome": "proprietario_nome",
        "proprietario": "proprietario_nome",
        "dono": "proprietario_nome",
        "contentor_codigo": "contentor_codigo",
        "contentor": "contentor_codigo",
        "canister": "canister",
        "andar": "andar",
        "observacoes": "observacoes",
        "observacoes": "observacoes",
        "certificado": "certificado",
        "qualidade": "qualidade",
    }

    required_cols = [
        "garanhao",
        "data_ref",
        "existencia_atual",
        "dose",
        "motilidade",
        "proprietario_nome",
        "contentor_codigo",
        "canister",
        "andar",
    ]

    render_zone_title(t("import.zone.context"), "import-zone-title")
    ctx1, ctx2 = st.columns([3, 1.5])
    with ctx1:
        st.markdown(
            f"<div class='import-hint'>{t('import.hint')}</div>",
            unsafe_allow_html=True,
        )
    with ctx2:
        if xlsx_ready:
            st.download_button(
                t("import.download_xlsx"),
                data=gerar_template_xlsx(),
                file_name="template_importar_semen.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )
        else:
            st.caption(t("import.xlsx_requires"))
        st.download_button(
            t("import.download_csv"),
            data=gerar_template_csv(),
            file_name="template_importar_semen.csv",
            mime="text/csv",
            width="stretch",
        )

    render_zone_title(t("import.zone.upload"), "import-zone-title")
    st.markdown("<div class='import-toolbar'>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader(t("import.upload_label"), type=["xlsx", "csv"])
    st.markdown("</div>", unsafe_allow_html=True)

    preview_df = pd.DataFrame()
    erros_df = pd.DataFrame()
    linhas_validas = []
    errors_map = {}
    row_numbers = []
    contentor_map = {}

    def parse_int(valor):
        try:
            if pd.isna(valor):
                return None
            return int(float(valor))
        except Exception:
            return None

    def parse_float(valor):
        try:
            if pd.isna(valor):
                return None
            return float(valor)
        except Exception:
            return None

    def validate_import_df(df, row_nums, cont_map):
        errors = {}
        errors_list = []
        valid_rows = []

        for idx, row in df.iterrows():
            row_num = row_nums[idx] if idx < len(row_nums) else idx + 2

            def add_error(col, msg):
                errors.setdefault(idx, {})[col] = msg
                errors_list.append({"linha": row_num, "coluna": col, "erro": msg})

            garanhao = str(row.get("garanhao", "")).strip()
            if not garanhao or garanhao.lower() == "nan":
                add_error("garanhao", t("import.error.garanhao_required"))

            prop_nome = str(row.get("proprietario_nome", "")).strip()
            if not prop_nome or prop_nome.lower() == "nan":
                add_error("proprietario_nome", t("import.error.owner_required"))

            data_ref = str(row.get("data_embriovet/ref", "")).strip()
            if not data_ref or data_ref.lower() == "nan":
                add_error("data_embriovet/ref", t("import.error.date_required"))

            palhetas = parse_int(row.get("existencia_atual"))
            if palhetas is None:
                add_error("existencia_atual", t("import.error.stock_invalid"))
            elif palhetas <= 0:
                add_error("existencia_atual", t("import.error.stock_positive"))

            motilidade = parse_int(row.get("motilidade"))
            if motilidade is None:
                add_error("motilidade", t("import.error.motility_invalid"))
            elif motilidade < 0 or motilidade > 100:
                add_error("motilidade", t("import.error.motility_range"))

            qualidade = row.get("qualidade")
            qualidade_val = None
            if qualidade not in [None, "", "nan"] and not pd.isna(qualidade):
                qualidade_val = str(qualidade).strip()

            conc_val = None
            if not pd.isna(row.get("concentracao")):
                conc_val = parse_float(row.get("concentracao"))
                if conc_val is None:
                    add_error("concentracao", t("import.error.concentration_invalid"))

            cor_val = None
            if not pd.isna(row.get("cor")):
                cor_val = str(row.get("cor")).strip() or None

            cont_code = str(row.get("contentor_codigo", "")).strip()
            cont_key = cont_code.upper()
            if not cont_code or cont_code.lower() == "nan":
                add_error("contentor_codigo", t("import.error.container_required"))
            elif cont_key not in cont_map:
                add_error("contentor_codigo", t("import.error.container_missing"))

            canister = parse_int(row.get("canister"))
            if canister is None:
                add_error("canister", t("import.error.canister_invalid"))
            elif canister < 1 or canister > 10:
                add_error("canister", t("import.error.canister_range"))

            andar = parse_int(row.get("andar"))
            if andar is None:
                add_error("andar", t("import.error.floor_invalid"))
            elif andar not in [1, 2]:
                add_error("andar", t("import.error.floor_range"))

            dose = ""
            if not pd.isna(row.get("dose")):
                dose = str(row.get("dose")).strip()

            observacoes = ""
            if not pd.isna(row.get("observacoes")):
                observacoes = str(row.get("observacoes")).strip()

            certificado = None
            if not pd.isna(row.get("certificado")):
                certificado = str(row.get("certificado")).strip()

            data_embriovet = None
            origem_externa = None
            if data_ref and data_ref.lower() != "nan":
                dayfirst = False
                if "/" in data_ref or "." in data_ref:
                    dayfirst = True
                elif "-" in data_ref:
                    parts = data_ref.split("-")
                    if parts and len(parts[0]) <= 2:
                        dayfirst = True
                parsed = pd.to_datetime(data_ref, errors="coerce", dayfirst=dayfirst)
                if pd.isna(parsed):
                    origem_externa = data_ref
                else:
                    data_embriovet = parsed.date()

            if idx not in errors:
                valid_rows.append(
                    {
                        "linha": row_num,
                        "garanhao": garanhao,
                        "proprietario_nome": prop_nome,
                        "data_embriovet": data_embriovet,
                        "origem_externa": origem_externa,
                        "existencia_atual": palhetas,
                        "dose": dose or None,
                        "motilidade": motilidade,
                        "contentor_id": cont_map.get(cont_key),
                        "contentor_codigo": cont_code,
                        "canister": canister,
                        "andar": andar,
                        "observacoes": observacoes or None,
                        "certificado": certificado or None,
                        "qualidade": qualidade_val,
                        "concentracao": conc_val,
                        "cor": cor_val,
                    }
                )

        return errors, pd.DataFrame(errors_list), valid_rows

    if uploaded_file is not None:
        try:
            if uploaded_file.name.lower().endswith(".csv"):
                raw_df = pd.read_csv(uploaded_file)
            else:
                if not xlsx_ready:
                    st.error(t("import.xlsx_install"))
                    raw_df = pd.DataFrame()
                else:
                    raw_df = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(t("import.read_error", error=e))
            raw_df = pd.DataFrame()

        if raw_df.empty:
            st.warning(t("import.file_empty"))
        else:
            col_map = {}
            for col in raw_df.columns:
                key = alias_map.get(normalizar_coluna(col))
                if key and key not in col_map:
                    col_map[key] = col

            missing = [col for col in required_cols if col not in col_map]
            if missing:
                st.error(t("import.missing_columns", cols=', '.join(missing)))
                erros_df = pd.DataFrame([
                    {"linha": "-", "coluna": "-", "erro": t("import.missing_columns", cols=', '.join(missing))}
                ])
            else:
                norm_df = pd.DataFrame({key: raw_df[col_map[key]] for key in col_map})
                norm_df["__row"] = raw_df.index + 2
                for opt in ["observacoes", "certificado", "qualidade", "concentracao", "cor"]:
                    if opt not in norm_df.columns:
                        norm_df[opt] = ""

                preview_cols = [
                    "garanhao",
                    "data_ref",
                    "existencia_atual",
                    "dose",
                    "motilidade",
                    "qualidade",
                    "concentracao",
                    "cor",
                    "proprietario_nome",
                    "contentor_codigo",
                    "canister",
                    "andar",
                    "observacoes",
                    "certificado",
                ]
                preview_df = norm_df[preview_cols].copy()
                preview_df = preview_df.rename(columns={"data_ref": "data_embriovet/ref"})
                row_numbers = norm_df["__row"].tolist()

                contentores_df = carregar_contentores()
                contentor_map = {
                    str(cod).strip().upper(): int(cid)
                    for cod, cid in zip(contentores_df.get("codigo", []), contentores_df.get("id", []))
                }

                file_id = (uploaded_file.name, getattr(uploaded_file, "size", None))
                if st.session_state.get("import_file_id") != file_id:
                    st.session_state["import_file_id"] = file_id
                    st.session_state["import_editor_df"] = preview_df.copy()
                    st.session_state["import_row_numbers"] = row_numbers
                    st.session_state.pop("import_editor", None)
                    st.session_state.pop("import_last_error_idx", None)

                editor_df = st.session_state.get("import_editor_df", preview_df.copy())
                row_numbers = st.session_state.get("import_row_numbers", row_numbers)

                st.markdown(
                    f"<div class='import-hint'>{t('import.rules_hint')}</div>",
                    unsafe_allow_html=True,
                )
                compact_view = st.toggle(t("import.compact_view"), value=True)

                full_cols = [
                    "garanhao",
                    "data_embriovet/ref",
                    "existencia_atual",
                    "dose",
                    "motilidade",
                    "qualidade",
                    "concentracao",
                    "cor",
                    "proprietario_nome",
                    "contentor_codigo",
                    "canister",
                    "andar",
                    "observacoes",
                    "certificado",
                ]
                compact_cols = [
                    "garanhao",
                    "data_embriovet/ref",
                    "existencia_atual",
                    "dose",
                    "motilidade",
                    "qualidade",
                    "concentracao",
                    "cor",
                ]
                col_order = compact_cols if compact_view else full_cols
                col_order = [c for c in col_order if c in editor_df.columns]

                preview_placeholder = st.container()

                editor_view = editor_df[col_order].copy()
                st.caption(t("import.edit_caption"))
                edited_view = st.data_editor(
                    editor_view,
                    key="import_editor",
                    num_rows="fixed",
                    width="stretch",
                    hide_index=True,
                )

                updated_df = editor_df.copy()
                for col in edited_view.columns:
                    updated_df[col] = edited_view[col]
                st.session_state["import_editor_df"] = updated_df
                preview_df = updated_df

                errors_map, erros_df, linhas_validas = validate_import_df(preview_df, row_numbers, contentor_map)

                sticky_cols = ["garanhao", "data_embriovet/ref", "existencia_atual"]

                import html as html_lib

                def render_preview_table(df, columns, error_map):
                    df_show = df[columns].fillna("")
                    header_cells = []
                    for col in columns:
                        cls = ""
                        if col in sticky_cols:
                            cls = f"import-sticky-{sticky_cols.index(col) + 1}"
                        label = col.replace("_", " ")
                        header_cells.append(f"<th class='{cls}'>{html_lib.escape(label)}</th>")

                    rows_html = []
                    for idx, row in df_show.iterrows():
                        cells = []
                        row_errors = error_map.get(idx, {})
                        for col in columns:
                            classes = []
                            if col in sticky_cols:
                                classes.append(f"import-sticky-{sticky_cols.index(col) + 1}")
                            msg = row_errors.get(col)
                            if msg:
                                classes.append("import-error-cell")
                            cls = " ".join(classes)
                            title_attr = f" title='{html_lib.escape(msg)}'" if msg else ""
                            val = html_lib.escape(str(row.get(col, "")))
                            icon = "<span class='import-error-icon'>⚠</span>" if msg else ""
                            cells.append(f"<td class='{cls}'{title_attr}>{val}{icon}</td>")
                        rows_html.append(f"<tr id='import-row-{idx}'>%s</tr>" % "".join(cells))

                    table_html = f"""
                    <div class='import-table-wrap'>
                        <table class='import-table'>
                            <thead><tr>{''.join(header_cells)}</tr></thead>
                            <tbody>{''.join(rows_html)}</tbody>
                        </table>
                    </div>
                    """
                    st.markdown(table_html, unsafe_allow_html=True)

                with preview_placeholder:
                    render_preview_table(preview_df, col_order, errors_map)

                if errors_map:
                    first_error = sorted(errors_map.keys())[0]
                    if st.session_state.get("import_last_error_idx") != first_error:
                        st.session_state["import_last_error_idx"] = first_error
                        st.components.v1.html(
                            f"""
                            <script>
                            setTimeout(() => {{
                                const row = window.parent.document.getElementById('import-row-{first_error}');
                                if (row) {{ row.scrollIntoView({{behavior: 'smooth', block: 'center'}}); }}
                            }}, 300);
                            </script>
                            """,
                            height=0,
                        )

    render_zone_title(t("import.zone.validate"), "import-zone-title")
    if uploaded_file is None:
        st.info(t("import.upload_to_validate"))
    else:
        total_linhas = len(preview_df)
        total_erros = len(errors_map) if errors_map else 0
        total_validas = max(0, total_linhas - total_erros)
        render_kpi_strip([
            (t("import.kpi.lines"), total_linhas),
            (t("import.kpi.valid"), total_validas),
            (t("import.kpi.errors"), total_erros),
        ])

        if erros_df.empty:
            st.success(t("import.validation_ok"))
        else:
            st.warning(t("import.validation_errors"))
            st.dataframe(erros_df, width="stretch", height=200, hide_index=True)

        def executar_importacao(linhas):
            report_rows = []
            try:
                with get_connection() as conn:
                    cur = conn.cursor()
                    props_df = carregar_proprietarios(apenas_ativos=False)
                    prop_map = {
                        str(nome).strip().lower(): int(pid)
                        for pid, nome in zip(props_df.get("id", []), props_df.get("nome", []))
                    }
                    criado_por = st.session_state.get("user", {}).get("username", "importacao")

                    for linha in linhas:
                        nome_prop = linha["proprietario_nome"].strip()
                        prop_key = nome_prop.lower()
                        if prop_key not in prop_map:
                            cur.execute(
                                "INSERT INTO dono (nome, ativo) VALUES (%s, TRUE) RETURNING id",
                                (to_py(nome_prop),),
                            )
                            prop_id = cur.fetchone()[0]
                            prop_map[prop_key] = prop_id
                        else:
                            prop_id = prop_map[prop_key]

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
                            RETURNING id
                            """,
                            (
                                to_py(linha.get("garanhao")),
                                to_py(prop_id),
                                to_py(linha.get("data_embriovet")),
                                to_py(linha.get("origem_externa")),
                                to_py(linha.get("existencia_atual")),
                                to_py(linha.get("qualidade")),
                                to_py(linha.get("concentracao")),
                                to_py(linha.get("motilidade")),
                                to_py(linha.get("certificado")),
                                to_py(linha.get("dose")),
                                to_py(linha.get("observacoes")),
                                to_py(linha.get("existencia_atual")),
                                to_py(linha.get("existencia_atual")),
                                to_py(linha.get("contentor_id")),
                                to_py(linha.get("canister")),
                                to_py(linha.get("andar")),
                                to_py(linha.get("cor")),
                                to_py(criado_por),
                            ),
                        )
                        stock_id = cur.fetchone()[0]
                        report_rows.append({
                            "linha": linha.get("linha"),
                            "status": "Importado",
                            "stock_id": stock_id,
                            "mensagem": "",
                        })

                    conn.commit()
                    cur.close()
                return True, pd.DataFrame(report_rows), None
            except Exception as e:
                logger.error(f"Erro ao importar: {e}")
                return False, pd.DataFrame(report_rows), str(e)

        has_errors = bool(errors_map) or not erros_df.empty
        importar_disabled = has_errors or not linhas_validas
        if st.button(t("btn.import"), type="primary", disabled=importar_disabled, width="content"):
            ok, report_df, err_msg = executar_importacao(linhas_validas)
            if ok:
                st.success(t("import.completed", count=len(report_df)))
                st.session_state["import_report"] = report_df
            else:
                st.error(t("import.failed", error=err_msg))
                if not report_df.empty:
                    st.session_state["import_report"] = report_df

        if "import_report" in st.session_state and not st.session_state["import_report"].empty:
            report_csv = st.session_state["import_report"].to_csv(index=False).encode("utf-8")
            st.download_button(
                t("import.download_report"),
                data=report_csv,
                file_name="relatorio_importacao.csv",
                mime="text/csv",
                width="stretch",
            )

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
        st.info(t("users.access_levels_info"))

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
