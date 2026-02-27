import streamlit as st
import pandas as pd
import psycopg2
from psycopg2 import pool
import os
from dotenv import load_dotenv
from contextlib import contextmanager
import logging
import numpy as np
import datetime as dt
import bcrypt
import hashlib
import time
import json
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
import warnings

# Suprimir avisos do pandas sobre conexões
warnings.filterwarnings('ignore', category=UserWarning, module='pandas')

# ------------------------------------------------------------
# Configurar logging
# ------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# Carregar variáveis de ambiente
# ------------------------------------------------------------
load_dotenv()

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
try:
    # Verificar se há DATABASE_URL (Render, Heroku, etc)
    database_url = os.getenv("DATABASE_URL")
    
    if database_url:
        # Usar DATABASE_URL (produção)
        connection_pool = psycopg2.pool.SimpleConnectionPool(1, 10, database_url)
        logger.info("✅ Pool de conexões PostgreSQL criado com DATABASE_URL")
    else:
        # Usar variáveis individuais (desenvolvimento local)
        connection_pool = psycopg2.pool.SimpleConnectionPool(
            1, 10,
            dbname=os.getenv("DB_NAME", "embriovet"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "123"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
        )
        logger.info("✅ Pool de conexões PostgreSQL criado localmente")
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
    """Carrega stock completo com informações de proprietario
    
    Args:
        apenas_ativos: Se True, retorna apenas stock de proprietários ativos
    """
    try:
        with get_connection() as conn:
            query = """
                SELECT e.*, d.nome as proprietario_nome
                FROM estoque_dono e
                LEFT JOIN dono d ON e.dono_id = d.id
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
                    f"{int(row.get('qualidade', 0))}%",
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
            st.error("❌ Nome do garanhão é obrigatório")
            return False
        
        if not dados.get("Contentor"):
            st.error("❌ Contentor é obrigatório")
            return False
        
        if not dados.get("Canister"):
            st.error("❌ Canister é obrigatório")
            return False
        
        if not dados.get("Andar"):
            st.error("❌ Andar é obrigatório")
            return False

        palhetas_val = to_py(dados.get("Palhetas", 0)) or 0
        try:
            palhetas_int = int(palhetas_val)
        except Exception:
            st.error("❌ Palhetas tem de ser numérico")
            return False

        if palhetas_int < 0:
            st.error("❌ Número de palhetas não pode ser negativo")
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
                username
            )

            cur.execute(
                """
                INSERT INTO estoque_dono (
                    garanhao, dono_id, data_embriovet, origem_externa,
                    palhetas_produzidas, qualidade, concentracao, motilidade,
                    certificado, dose, observacoes,
                    quantidade_inicial, existencia_atual,
                    contentor_id, canister, andar,
                    criado_por, data_criacao
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
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
            st.error("❌ Número de palhetas deve ser numérico")
            return False

        if palhetas_int <= 0:
            st.error("❌ Número de palhetas deve ser maior que zero")
            return False

        if not registro.get("egua"):
            st.error("❌ Nome da égua é obrigatório")
            return False

        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute(
                "SELECT existencia_atual FROM estoque_dono WHERE id = %s",
                (to_py(registro.get("stock_id")),),
            )
            result = cur.fetchone()

            if not result:
                st.error("❌ Estoque não encontrado")
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

# ------------------------------------------------------------
# 🔐 Funções de Autenticação e Utilizadores
# ------------------------------------------------------------
def criar_hash_password(password):
    """Cria hash da password usando bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

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
                SELECT id, username, nome_completo, password_hash, nivel, ativo
                FROM usuarios
                WHERE username = %s AND ativo = TRUE
            """, (username,))
            
            resultado = cur.fetchone()
            cur.close()
            
            if not resultado:
                return None
            
            user_id, username, nome, pwd_hash, nivel, ativo = resultado
            
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
                    'nivel': nivel
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
                st.error("❌ Nome de utilizador já existe")
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
                    andar = %s
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
                       qualidade, concentracao, motilidade, local_armazenagem, certificado, dose, observacoes
                FROM estoque_dono WHERE id = %s
            """, (to_py(stock_origem_id),))
            
            origem = cur.fetchone()
            if not origem:
                st.error("❌ Lote de origem não encontrado")
                return False
            
            (garanhao, prop_origem_id, exist_atual, data_emb, origem_ext, 
             qual, conc, mot, local, cert, dose, obs) = origem
            
            exist_atual = int(to_py(exist_atual) or 0)
            quantidade_int = int(to_py(quantidade) or 0)
            
            if quantidade_int <= 0:
                st.error("❌ Quantidade deve ser maior que zero")
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
                        quantidade_inicial, existencia_atual
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    to_py(garanhao), to_py(proprietario_destino_id), to_py(data_emb), to_py(origem_ext),
                    quantidade_int, to_py(qual), to_py(conc), to_py(mot),
                    to_py(local), to_py(cert), to_py(dose), to_py(obs),
                    quantidade_int, quantidade_int
                ))
            
            # Registrar transferência na tabela de transferências
            cur.execute("""
                INSERT INTO transferencias (
                    stock_id, proprietario_origem_id, proprietario_destino_id,
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
                st.error("❌ Lote de origem não encontrado")
                return False
            
            garanhao, prop_origem_id, exist_atual = origem
            exist_atual = int(to_py(exist_atual) or 0)
            quantidade_int = int(to_py(quantidade) or 0)
            
            if quantidade_int <= 0:
                st.error("❌ Quantidade deve ser maior que zero")
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
    page_title=os.getenv("APP_TITLE", "Gestor Sémen - Embriovet"),
    layout=os.getenv("APP_LAYOUT", "wide"),
    page_icon="🐴",
)

# ------------------------------------------------------------
# 🔐 Sistema de Login
# ------------------------------------------------------------
def mostrar_tela_login():
    """Exibe tela de login"""
    st.title("🔐 Login - Gestor de Sémen Embriovet")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### Autenticação")
        
        with st.form("login_form"):
            username = st.text_input("👤 Utilizador", placeholder="Digite seu username")
            password = st.text_input("🔒 Password", type="password", placeholder="Digite sua password")
            
            submitted = st.form_submit_button("🚀 Entrar", type="primary", use_container_width=True)
            
            if submitted:
                if not username or not password:
                    st.error("❌ Preencha todos os campos")
                else:
                    user = autenticar_usuario(username, password)
                    if user:
                        st.session_state['user'] = user
                        st.success(f"✅ Bem-vindo, {user['nome']}!")
                        st.rerun()
                    else:
                        st.error("❌ Utilizador ou password incorretos")
        
        st.markdown("---")
        st.info("ℹ️ **Credenciais iniciais:**\n\n👤 Username: `admin`\n\n🔒 Password: `admin123`")

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

# Verificar se está logado
if 'user' not in st.session_state:
    mostrar_tela_login()
    st.stop()

# Usuário logado - mostrar info no sidebar
user = st.session_state['user']

st.title("🐴 Gestor de Sémen com Múltiplos Proprietários")

# Sidebar com info do utilizador
st.sidebar.markdown("---")
st.sidebar.markdown(f"### 👤 {user['nome']}")
st.sidebar.markdown(f"**Nível:** {user['nivel']}")

if st.sidebar.button("🚪 Logout", width="stretch"):
    del st.session_state['user']
    st.rerun()

st.sidebar.markdown("---")

# Menu lateral adaptado às permissões
menu_options = ["🗺️ Mapa dos Contentores", "📦 Ver Stock", "📈 Relatórios"]

if verificar_permissao('Gestor'):
    menu_options.insert(2, "➕ Adicionar Stock")
    menu_options.insert(3, "📝 Registrar Inseminação")
    menu_options.append("👥 Gestão de Proprietários")

if verificar_permissao('Administrador'):
    menu_options.append("⚙️ Gestão de Utilizadores")

# Verificar se há redirecionamento pendente
if 'aba_selecionada' in st.session_state:
    idx_aba = menu_options.index(st.session_state['aba_selecionada']) if st.session_state['aba_selecionada'] in menu_options else 0
    del st.session_state['aba_selecionada']
else:
    idx_aba = 0

aba = st.sidebar.radio("Menu", menu_options, index=idx_aba)

# ------------------------------------------------------------
# 💬 Modal para adicionar proprietário
# ------------------------------------------------------------
@st.dialog("➕ Adicionar Novo Proprietário")
def modal_adicionar_proprietario():
    """Modal para adicionar novo proprietário rapidamente"""
    novo_nome = st.text_input("Nome do Proprietário *", key="modal_novo_prop")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Adicionar", type="primary", use_container_width=True):
            if not novo_nome:
                st.error("❌ Nome é obrigatório")
            else:
                # Criar dados mínimos
                dados_novo = {'nome': novo_nome, 'email': None, 'telemovel': None, 
                              'nome_completo': None, 'nif': None, 'morada': None,
                              'codigo_postal': None, 'cidade': None}
                prop_id = adicionar_proprietario(dados_novo)
                if prop_id:
                    st.session_state['novo_proprietario_id'] = prop_id
                    st.session_state['novo_proprietario_nome'] = novo_nome
                    st.success(f"✅ Proprietário '{novo_nome}' adicionado!")
                    st.rerun()
    with col2:
        if st.button("❌ Cancelar", use_container_width=True):
            st.rerun()

# Carregar dados
try:
    proprietarios = carregar_proprietarios(apenas_ativos=True)  # Apenas ativos por padrão
    stock = carregar_stock(apenas_ativos=True)  # Apenas de proprietários ativos
    insem = carregar_inseminacoes()
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

# Limpar session state do novo proprietário após usá-lo (evita que fique selecionado sempre)
if 'novo_proprietario_usado' in st.session_state:
    if 'novo_proprietario_id' in st.session_state:
        del st.session_state['novo_proprietario_id']
    if 'novo_proprietario_nome' in st.session_state:
        del st.session_state['novo_proprietario_nome']
    del st.session_state['novo_proprietario_usado']

if proprietarios.empty:
    st.warning("⚠️ Nenhum proprietario cadastrado. Por favor, cadastre proprietarios primeiro.")

# ------------------------------------------------------------
# 📦 Ver Stock
# ------------------------------------------------------------

# ------------------------------------------------------------
# 🗺️ Mapa dos Contentores
# ------------------------------------------------------------
if aba == "🗺️ Mapa dos Contentores":
    # Carregar contentores
    contentores_df = carregar_contentores()

    if "mapa_modo_edicao" not in st.session_state:
        st.session_state["mapa_modo_edicao"] = False

    if "mapa_layout_reader_tick" not in st.session_state:
        st.session_state["mapa_layout_reader_tick"] = 0

    if "mapa_salvar_layout_pendente" not in st.session_state:
        st.session_state["mapa_salvar_layout_pendente"] = False

    if "mapa_salvar_layout_tentativas" not in st.session_state:
        st.session_state["mapa_salvar_layout_tentativas"] = 0

    try:
        from streamlit_js_eval import streamlit_js_eval
        js_eval_disponivel = True
    except Exception:
        streamlit_js_eval = None
        js_eval_disponivel = False

    if not js_eval_disponivel:
        st.warning("Dependência em falta: execute `pip install streamlit-js-eval` para salvar layout do mapa.")
    else:
        streamlit_js_eval(
            js_expressions="""
                (function(){
                    try {
                        if (!window.__contentorLayoutBridgeInstalled) {
                            window.__contentorLayoutBridgeInstalled = true;
                            window.addEventListener('message', function(event){
                                var data = event && event.data ? event.data : null;
                                if (!data || typeof data !== 'object') return;

                                if (data.type === 'CONTENTOR_LAYOUT_UPDATE') {
                                    try {
                                        var atual = JSON.parse(window.localStorage.getItem('contentor_layout_pending') || '{}');
                                        atual[String(data.id)] = {
                                            x: parseInt(data.x, 10) || 0,
                                            y: parseInt(data.y, 10) || 0
                                        };
                                        window.localStorage.setItem('contentor_layout_pending', JSON.stringify(atual));
                                    } catch (e) {}
                                }

                                if (data.type === 'CONTENTOR_LAYOUT_CLEAR') {
                                    try { window.localStorage.removeItem('contentor_layout_pending'); } catch (e) {}
                                }
                            });
                        }
                    } catch (e) {}
                    return true;
                })()
            """,
            key="map_layout_bridge_bootstrap",
            want_output=True,
        )

    largura_viewport = None
    if js_eval_disponivel:
        largura_viewport = streamlit_js_eval(
            js_expressions='window.innerWidth',
            key='map_viewport_width',
            want_output=True,
        )

    is_mobile = bool(largura_viewport) and int(largura_viewport) < 900
    modo_visualizacao = True

    layout_pending_raw = None
    if js_eval_disponivel:
        layout_pending_raw = streamlit_js_eval(
            js_expressions='window.localStorage.getItem("contentor_layout_pending")',
            key=f"map_layout_pending_reader_{st.session_state['mapa_layout_reader_tick']}",
            want_output=True,
        )
    
    # Modal para adicionar contentor - design limpo
    if st.session_state.get('modal_novo_contentor', False):
        st.markdown("---")
        st.markdown("### Adicionar Novo Contentor")
        
        with st.form("form_novo_contentor"):
            col_form1, col_form2 = st.columns([1, 1])
            
            with col_form1:
                codigo = st.text_input(
                    "Código do Contentor *", 
                    placeholder="Ex: CT-01, A1, EMB01",
                    help="Identificador único alfanumérico"
                )
            
            with col_form2:
                descricao = st.text_input("Descrição (opcional)", placeholder="Localização ou notas")
            
            col_submit1, col_submit2 = st.columns([1, 1])
            with col_submit1:
                submitted = st.form_submit_button("Criar Contentor", use_container_width=True)
            with col_submit2:
                cancelar = st.form_submit_button("Cancelar", use_container_width=True)
            
            if cancelar:
                st.session_state['modal_novo_contentor'] = False
                st.rerun()
            
            if submitted:
                if not codigo:
                    st.error("Código é obrigatório")
                else:
                    if codigo in contentores_df['codigo'].values:
                        st.error(f"Já existe um contentor com o código '{codigo}'")
                    else:
                        import random
                        contentor_id = adicionar_contentor({
                            'codigo': codigo,
                            'descricao': descricao,
                            'x': random.randint(100, 600),
                            'y': random.randint(100, 350),
                            'w': 90,
                            'h': 90
                        })
                        if contentor_id:
                            st.success(f"Contentor '{codigo}' criado com sucesso")
                            st.session_state['modal_novo_contentor'] = False
                            st.rerun()
    
    # Área do mapa
    if contentores_df.empty:
        st.info("Nenhum contentor cadastrado. Utilize 'Novo Contentor' para começar.")
    else:
        if modo_visualizacao:
            total_contentores = len(contentores_df)
            total_palhetas_geral = 0
            contentores_data = []

            for _, row in contentores_df.iterrows():
                stock_contentor = obter_stock_contentor(row['id'])
                total_palhetas = int(stock_contentor['existencia_atual'].sum()) if not stock_contentor.empty else 0
                total_palhetas_geral += total_palhetas

                lotes = []
                if not stock_contentor.empty:
                    for _, lote in stock_contentor.iterrows():
                        observacao = ""
                        if isinstance(lote.get('qualidade'), str) and lote.get('qualidade'):
                            observacao = lote.get('qualidade')
                        elif isinstance(lote.get('origem_externa'), str) and lote.get('origem_externa'):
                            observacao = lote.get('origem_externa')

                        lotes.append({
                            "garanhao": lote.get('garanhao') or "—",
                            "proprietario": lote.get('proprietario_nome') or "—",
                            "quantidade": int(lote.get('existencia_atual') or 0),
                            "canister": int(lote.get('canister') or 0),
                            "andar": int(lote.get('andar') or 0),
                            "observacoes": observacao,
                        })

                contentores_data.append({
                    "id": int(row['id']),
                    "codigo": row['codigo'],
                    "descricao": row['descricao'] or "",
                    "x": int(row['x']),
                    "y": int(row['y']),
                    "w": max(80, int(row['w'])),
                    "h": max(80, int(row['h'])),
                    "palhetas": total_palhetas,
                    "lotes": lotes,
                })

            criar_novo = False
            ativar_edicao = False
            cancelar_edicao = False
            salvar_layout = False

            st.markdown(
                """
                <style>
                    .map-tech-context {
                        font-size: 12px;
                        color: #64748b;
                        line-height: 1.45;
                        margin-top: 0;
                        margin-bottom: 2px;
                    }
                    .map-tech-context-inline {
                        font-size: 11px;
                        color: #64748b;
                        opacity: 0.95;
                    }
                    .map-toolbar-shell {
                        border: 1px solid #d1d5db;
                        border-radius: 8px;
                        background: #f8fafc;
                        padding: 6px 10px;
                        margin-bottom: 4px;
                    }
                    .map-toolbar-kpis {
                        display: flex;
                        gap: 10px;
                        align-items: center;
                        font-size: 11px;
                        color: #475569;
                    }
                    .map-toolbar-kpis b {
                        color: #0f172a;
                    }
                    div[data-testid="stVerticalBlock"]:has(.map-toolbar-shell) {
                        position: sticky;
                        top: 0;
                        z-index: 80;
                        background: rgba(248, 250, 252, 0.96);
                        border: 1px solid #e2e8f0;
                        border-radius: 10px;
                        padding: 6px 8px 8px;
                        margin-bottom: 4px;
                        backdrop-filter: blur(4px);
                    }
                </style>
                """,
                unsafe_allow_html=True,
            )

            with st.container():
                if is_mobile:
                    st.markdown("<div class='map-tech-context'>Sistema de localização física e inventário de sémen equino</div>", unsafe_allow_html=True)
                    st.markdown(
                        f"<div class='map-toolbar-shell'><div class='map-toolbar-kpis'><span><b>{total_contentores}</b> contentores</span><span><b>{int(total_palhetas_geral)}</b> palhetas</span></div></div>",
                        unsafe_allow_html=True,
                    )

                    btn_m1, btn_m2, btn_m3 = st.columns([1, 1, 1])
                    with btn_m1:
                        criar_novo = st.button("Adicionar", use_container_width=True)
                    with btn_m2:
                        if st.session_state["mapa_modo_edicao"]:
                            salvar_layout = st.button("Salvar", type="primary", use_container_width=True)
                        else:
                            ativar_edicao = st.button("Editar mapa", use_container_width=True)
                    with btn_m3:
                        if st.session_state["mapa_modo_edicao"]:
                            cancelar_edicao = st.button("Cancelar", use_container_width=True)
                else:
                    st.markdown(
                        f"<div class='map-toolbar-shell'><div class='map-toolbar-kpis'><span class='map-tech-context-inline'>Sistema de localização física e inventário de sémen equino</span><span><b>{total_contentores}</b> contentores</span><span><b>{int(total_palhetas_geral)}</b> palhetas</span><span>{'modo edição ativo' if st.session_state['mapa_modo_edicao'] else 'modo normal'}</span></div></div>",
                        unsafe_allow_html=True,
                    )
                    bar_btn1, bar_btn2, bar_btn3 = st.columns([1, 1, 1])
                    with bar_btn1:
                        criar_novo = st.button("Adicionar contentor", use_container_width=True)
                    with bar_btn2:
                        if st.session_state["mapa_modo_edicao"]:
                            salvar_layout = st.button("Salvar layout", type="primary", use_container_width=True)
                        else:
                            ativar_edicao = st.button("Editar mapa", use_container_width=True)
                    with bar_btn3:
                        if st.session_state["mapa_modo_edicao"]:
                            cancelar_edicao = st.button("Cancelar edição", use_container_width=True)

            if criar_novo:
                st.session_state['modal_novo_contentor'] = True
                st.rerun()

            if ativar_edicao:
                st.session_state["mapa_modo_edicao"] = True
                if js_eval_disponivel:
                    streamlit_js_eval(
                        js_expressions='window.localStorage.removeItem("contentor_layout_pending")',
                        key=f"clear_layout_pending_start_{int(time.time() * 1000)}"
                    )
                st.session_state["mapa_salvar_layout_tentativas"] = 0
                st.rerun()

            if cancelar_edicao:
                st.session_state["mapa_modo_edicao"] = False
                if js_eval_disponivel:
                    streamlit_js_eval(
                        js_expressions='window.localStorage.removeItem("contentor_layout_pending")',
                        key=f"clear_layout_pending_cancel_{int(time.time() * 1000)}"
                    )
                st.session_state["mapa_salvar_layout_tentativas"] = 0
                st.rerun()

            if salvar_layout:
                if not js_eval_disponivel:
                    st.error("Para salvar layout no mapa, instale: pip install streamlit-js-eval")
                else:
                    st.session_state["mapa_salvar_layout_pendente"] = True
                    st.session_state["mapa_salvar_layout_tentativas"] = 0
                    st.session_state["mapa_layout_reader_tick"] += 1
                    st.rerun()

            if st.session_state.get("mapa_salvar_layout_pendente", False):
                atualizados = 0
                if layout_pending_raw and layout_pending_raw != "null":
                    try:
                        layout_data = json.loads(layout_pending_raw)
                        for _, row in contentores_df.iterrows():
                            cid = str(int(row['id']))
                            pos = layout_data.get(cid)
                            if not isinstance(pos, dict):
                                continue

                            novo_x = int(pos.get("x", int(row['x'])))
                            novo_y = int(pos.get("y", int(row['y'])))
                            largura = max(1, int(row['w']))
                            altura = max(1, int(row['h']))
                            novo_x = max(0, min(novo_x, 900 - largura))
                            novo_y = max(0, min(novo_y, 550 - altura))

                            if novo_x != int(row['x']) or novo_y != int(row['y']):
                                if atualizar_posicao_contentor(int(row['id']), novo_x, novo_y):
                                    atualizados += 1

                        streamlit_js_eval(
                            js_expressions='window.localStorage.removeItem("contentor_layout_pending")',
                            key=f"clear_layout_pending_save_{int(time.time() * 1000)}"
                        )
                        st.session_state["mapa_modo_edicao"] = False
                        st.session_state["mapa_salvar_layout_pendente"] = False
                        st.session_state["mapa_salvar_layout_tentativas"] = 0

                        if atualizados > 0:
                            st.success(f"Layout guardado com sucesso. {atualizados} contentor(es) atualizado(s).")
                        else:
                            st.info("Nenhuma alteração de posição para guardar.")
                        st.rerun()
                    except Exception as e:
                        st.session_state["mapa_salvar_layout_pendente"] = False
                        st.session_state["mapa_salvar_layout_tentativas"] = 0
                        logger.error(f"Erro ao salvar layout do mapa: {e}")
                        st.error("Falha ao salvar layout do mapa.")
                else:
                    tentativas = int(st.session_state.get("mapa_salvar_layout_tentativas", 0))
                    if tentativas < 2:
                        st.session_state["mapa_salvar_layout_tentativas"] = tentativas + 1
                        st.session_state["mapa_layout_reader_tick"] += 1
                        st.rerun()
                    else:
                        st.session_state["mapa_salvar_layout_pendente"] = False
                        st.session_state["mapa_salvar_layout_tentativas"] = 0
                        st.info("Nenhuma alteração pendente para guardar.")

            if st.session_state["mapa_modo_edicao"] and is_mobile:
                st.warning("No telemóvel, o arrastar pode ser menos preciso. Recomenda-se desktop para reorganização fina.")

            if st.session_state.get("move_feedback"):
                st.success(st.session_state.pop("move_feedback"))
            if st.session_state.get("move_feedback_erro"):
                st.error(st.session_state.pop("move_feedback_erro"))

            mapa_html = """
            <style>
                :root {
                    --map-bg: #f4f6f8;
                    --map-border: #cbd5e1;
                    --card-bg: #f8fafc;
                    --card-border: #475569;
                    --text-main: #0f172a;
                    --text-muted: #64748b;
                }

                #mapa-wrapper {
                    position: relative;
                    width: 100%;
                    border: 1px solid var(--map-border);
                    border-radius: 8px;
                    background: var(--map-bg);
                    padding: 10px;
                    overflow: hidden;
                    font-family: 'Courier New', monospace;
                }

                #mapa-area {
                    position: relative;
                    width: min(100%, 720px);
                    margin: 0 auto;
                    aspect-ratio: 900 / 550;
                    border: 2px solid #64748b;
                    background: #fff;
                    background-image:
                        linear-gradient(rgba(15,23,42,.05) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(15,23,42,.05) 1px, transparent 1px);
                    background-size: 50px 50px;
                    overflow: hidden;
                }

                .cont-box {
                    position: absolute;
                    border: 2px solid var(--card-border);
                    background: var(--card-bg);
                    color: var(--text-main);
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    user-select: none;
                    transition: box-shadow .2s ease, transform .2s ease;
                }

                .cont-box.clickable {
                    cursor: pointer;
                }

                .cont-box.draggable {
                    cursor: move;
                }

                .cont-box:hover {
                    box-shadow: 0 8px 16px rgba(2, 6, 23, .14);
                    transform: translateY(-1px);
                    z-index: 50;
                }

                .cont-box.dragging {
                    opacity: .9;
                    z-index: 999;
                }

                .cont-codigo {
                    font-size: 12px;
                    font-weight: 700;
                    margin-bottom: 3px;
                }

                .cont-qtd {
                    font-size: 20px;
                    font-weight: 800;
                    line-height: 1;
                }

                .cont-label {
                    font-size: 10px;
                    color: var(--text-muted);
                    text-transform: uppercase;
                    letter-spacing: .3px;
                }

                #mapa-status {
                    margin-top: 8px;
                    font-size: 11px;
                    color: var(--text-muted);
                }

                #inv-overlay {
                    position: absolute;
                    inset: 0;
                    background: rgba(15, 23, 42, .28);
                    display: none;
                    z-index: 2000;
                }

                #inv-panel {
                    position: absolute;
                    top: 0;
                    right: 0;
                    width: 360px;
                    height: 100%;
                    background: #fff;
                    border-left: 1px solid #d1d5db;
                    padding: 14px;
                    overflow-y: auto;
                }

                .mobile #inv-panel {
                    width: 100%;
                    border-left: none;
                }

                .inv-head {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    margin-bottom: 10px;
                }

                .inv-title {
                    font-size: 16px;
                    font-weight: 700;
                    color: #111827;
                }

                .inv-close {
                    border: 1px solid #cbd5e1;
                    background: #fff;
                    border-radius: 6px;
                    padding: 4px 8px;
                    cursor: pointer;
                }

                .inv-summary {
                    font-size: 12px;
                    color: #334155;
                    margin-bottom: 10px;
                }

                .inv-lote {
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                    padding: 8px;
                    margin-bottom: 8px;
                    background: #f8fafc;
                    font-size: 12px;
                    line-height: 1.35;
                }
            </style>

            <div id="mapa-wrapper" class="__MOBILE_CLASS__">
                <div id="mapa-area"></div>
                <div id="mapa-status">__STATUS_TEXT__</div>

                <div id="inv-overlay">
                    <div id="inv-panel"></div>
                </div>
            </div>

            <script>
                const contentores = __CONTENTORES_DATA__;
                const isEditMode = __EDIT_MODE__;
                const isMobile = __IS_MOBILE__;
                const baseW = 900;
                const baseH = 550;

                const wrapper = document.getElementById('mapa-wrapper');
                const mapaArea = document.getElementById('mapa-area');
                const statusBar = document.getElementById('mapa-status');
                const invOverlay = document.getElementById('inv-overlay');
                const invPanel = document.getElementById('inv-panel');

                let scale = 1;
                let draggedEl = null;
                let draggedMeta = null;
                let offsetX = 0;
                let offsetY = 0;
                let moved = false;

                function esc(v) {
                    return String(v ?? '').replace(/[&<>"']/g, (c) => ({
                        '&': '&amp;',
                        '<': '&lt;',
                        '>': '&gt;',
                        '"': '&quot;',
                        "'": '&#39;'
                    }[c]));
                }

                function computeScale() {
                    const rect = mapaArea.getBoundingClientRect();
                    scale = rect.width / baseW;
                    if (!scale || scale <= 0) scale = 1;
                }

                function openInventory(cont) {
                    const lotes = Array.isArray(cont.lotes) ? cont.lotes : [];
                    const lotesHtml = lotes.length === 0
                        ? '<div class="inv-lote">Sem lotes neste contentor.</div>'
                        : lotes.map(l => `
                            <div class="inv-lote">
                                <b>Garanhão:</b> ${esc(l.garanhao)}<br/>
                                <b>Proprietário:</b> ${esc(l.proprietario)}<br/>
                                <b>Quantidade:</b> ${esc(l.quantidade)}<br/>
                                <b>Canister:</b> ${esc(l.canister)} | <b>Andar:</b> ${esc(l.andar)}<br/>
                                <b>Observações:</b> ${esc(l.observacoes || '—')}
                            </div>
                        `).join('');

                    invPanel.innerHTML = `
                        <div class="inv-head">
                            <div class="inv-title">${esc(cont.codigo)}</div>
                            <button class="inv-close" id="inv-close-btn">Fechar</button>
                        </div>
                        <div class="inv-summary">
                            <b>Total de palhetas:</b> ${esc(cont.palhetas)}<br/>
                            <b>Total de lotes:</b> ${esc(lotes.length)}
                        </div>
                        ${lotesHtml}
                    `;

                    invOverlay.style.display = 'block';
                    const closeBtn = document.getElementById('inv-close-btn');
                    if (closeBtn) closeBtn.addEventListener('click', closeInventory);
                }

                function closeInventory() {
                    invOverlay.style.display = 'none';
                }

                invOverlay.addEventListener('click', (e) => {
                    if (e.target === invOverlay) closeInventory();
                });

                function guardarPosicaoPendente(id, x, y) {
                    try {
                        let storageRef = window.localStorage;
                        try {
                            if (window.parent && window.parent.localStorage) {
                                storageRef = window.parent.localStorage;
                            }
                        } catch (e) {}

                        const atual = JSON.parse(storageRef.getItem('contentor_layout_pending') || '{}');
                        atual[String(id)] = { x, y };
                        storageRef.setItem('contentor_layout_pending', JSON.stringify(atual));
                        statusBar.textContent = 'Alteração pendente. Clique em "Salvar layout".';
                    } catch (err) {
                        console.error('Erro ao guardar posição pendente:', err);
                        statusBar.textContent = 'Falha ao guardar posição pendente.';
                    }
                }

                function criarContentor(cont) {
                    const div = document.createElement('div');
                    div.className = `cont-box ${isEditMode ? 'draggable' : 'clickable'}`;
                    div.id = `cont-${cont.id}`;

                    const wPx = Math.max(40, Math.round(cont.w * scale));
                    const hPx = Math.max(40, Math.round(cont.h * scale));
                    const xPx = Math.round(cont.x * scale);
                    const yPx = Math.round(cont.y * scale);

                    div.style.width = wPx + 'px';
                    div.style.height = hPx + 'px';
                    div.style.left = xPx + 'px';
                    div.style.top = yPx + 'px';

                    div.innerHTML = `
                        <div class="cont-codigo">${esc(cont.codigo)}</div>
                        <div class="cont-qtd">${esc(cont.palhetas)}</div>
                        <div class="cont-label">palhetas</div>
                    `;

                    div.addEventListener('mousedown', (e) => {
                        if (!isEditMode) return;
                        if (e.button !== 0) return;
                        moved = false;
                        draggedEl = div;
                        draggedMeta = cont;
                        draggedEl.classList.add('dragging');

                        const rect = draggedEl.getBoundingClientRect();
                        offsetX = e.clientX - rect.left;
                        offsetY = e.clientY - rect.top;
                        e.preventDefault();
                    });

                    div.addEventListener('click', () => {
                        if (isEditMode) return;
                        openInventory(cont);
                    });

                    mapaArea.appendChild(div);
                }

                document.addEventListener('mousemove', (e) => {
                    if (!draggedEl || !isEditMode) return;
                    moved = true;

                    const mapRect = mapaArea.getBoundingClientRect();
                    let x = e.clientX - mapRect.left - offsetX;
                    let y = e.clientY - mapRect.top - offsetY;

                    const w = parseInt(draggedEl.style.width, 10);
                    const h = parseInt(draggedEl.style.height, 10);
                    x = Math.max(0, Math.min(x, mapRect.width - w));
                    y = Math.max(0, Math.min(y, mapRect.height - h));

                    draggedEl.style.left = Math.round(x) + 'px';
                    draggedEl.style.top = Math.round(y) + 'px';
                    statusBar.textContent = `Movendo... X=${Math.round(x / scale)} | Y=${Math.round(y / scale)}`;
                });

                document.addEventListener('mouseup', () => {
                    if (!draggedEl || !isEditMode || !draggedMeta) return;

                    const xPx = parseInt(draggedEl.style.left, 10);
                    const yPx = parseInt(draggedEl.style.top, 10);
                    const xCanon = Math.max(0, Math.min(Math.round(xPx / scale), baseW - draggedMeta.w));
                    const yCanon = Math.max(0, Math.min(Math.round(yPx / scale), baseH - draggedMeta.h));

                    draggedEl.classList.remove('dragging');
                    draggedEl = null;

                    if (moved) {
                        guardarPosicaoPendente(draggedMeta.id, xCanon, yCanon);
                    }

                    draggedMeta = null;
                });

                computeScale();
                contentores.forEach(criarContentor);

                if (!isEditMode) {
                    statusBar.textContent = 'Clique num contentor para ver o inventário.';
                }
            </script>
            """

            import streamlit.components.v1 as components
            mapa_render = mapa_html.replace("__CONTENTORES_DATA__", json.dumps(contentores_data, ensure_ascii=False))
            mapa_render = mapa_render.replace("__EDIT_MODE__", "true" if st.session_state["mapa_modo_edicao"] else "false")
            mapa_render = mapa_render.replace("__IS_MOBILE__", "true" if is_mobile else "false")
            mapa_render = mapa_render.replace("__MOBILE_CLASS__", "mobile" if is_mobile else "desktop")
            mapa_render = mapa_render.replace(
                "__STATUS_TEXT__",
                "Arraste os contentores e salve o layout." if st.session_state["mapa_modo_edicao"] else "Clique num contentor para ver inventário."
            )

            if is_mobile:
                components.html(mapa_render, height=620)
            else:
                components.html(mapa_render, height=530)
            
            # Mostrar lista de contentores abaixo do mapa
            st.markdown("---")
            st.markdown("### Inventário de Contentores")
            
            for idx, row in contentores_df.iterrows():
                stock_contentor = obter_stock_contentor(row['id'])
                total_palhetas = stock_contentor['existencia_atual'].sum() if not stock_contentor.empty else 0
                total_lotes = len(stock_contentor)
                
                # Design técnico limpo
                with st.expander(f"**{row['codigo']}** — {int(total_palhetas)} palhetas, {total_lotes} lotes"):
                    col_det1, col_det2, col_det3 = st.columns([2, 2, 1])
                    
                    with col_det1:
                        st.markdown(f"**Código:** {row['codigo']}")
                        st.markdown(f"**Descrição:** {row['descricao'] or '—'}")
                        st.markdown(f"**Posição:** X={row['x']}, Y={row['y']}")
                    
                    with col_det2:
                        st.markdown(f"**Total Palhetas:** {int(total_palhetas)}")
                        st.markdown(f"**Total Lotes:** {total_lotes}")
                    
                    with col_det3:
                        if st.button("Editar", key=f"edit_{row['id']}", use_container_width=True):
                            st.session_state[f'modal_editar_{row["id"]}'] = True
                            st.rerun()
                        
                        if st.button("Apagar", key=f"del_{row['id']}", use_container_width=True):
                            if deletar_contentor(row['id']):
                                st.success(f"Contentor '{row['codigo']}' apagado")
                                st.rerun()
                    
                    if not stock_contentor.empty:
                        st.markdown("**Lotes:**")
                        for canister in sorted(stock_contentor['canister'].unique()):
                            stock_canister = stock_contentor[stock_contentor['canister'] == canister]
                            for andar in sorted(stock_canister['andar'].unique()):
                                stock_andar = stock_canister[stock_canister['andar'] == andar]
                                for _, lote in stock_andar.iterrows():
                                    ref = lote['origem_externa'] or lote['data_embriovet'] or '—'
                                    st.text(f"Can.{canister} / {andar}º | {lote['garanhao']} | {lote['proprietario_nome']} | {int(lote['existencia_atual'])}p | {ref}")
                    
                    # Modal edição
                    if st.session_state.get(f'modal_editar_{row["id"]}', False):
                        st.markdown("---")
                        with st.form(f"form_editar_{row['id']}"):
                            st.markdown("#### Editar Contentor")
                            
                            col_edit1, col_edit2 = st.columns(2)
                            with col_edit1:
                                novo_codigo = st.text_input("Código", value=row['codigo'])
                            with col_edit2:
                                nova_descricao = st.text_input("Descrição", value=row['descricao'] or '')
                            
                            col_btn_edit1, col_btn_edit2 = st.columns(2)
                            with col_btn_edit1:
                                salvar = st.form_submit_button("Salvar", use_container_width=True)
                            with col_btn_edit2:
                                cancelar_edit = st.form_submit_button("Cancelar", use_container_width=True)
                            
                            if cancelar_edit:
                                st.session_state[f'modal_editar_{row["id"]}'] = False
                                st.rerun()
                            
                            if salvar:
                                if editar_contentor(row['id'], {
                                    'codigo': novo_codigo,
                                    'descricao': nova_descricao,
                                    'x': row['x'],
                                    'y': row['y'],
                                    'w': row['w'],
                                    'h': row['h']
                                }):
                                    st.success("Contentor atualizado")
                                    st.session_state[f'modal_editar_{row["id"]}'] = False
                                    st.rerun()
        
        else:
            # MODO LISTA (mantido para compatibilidade)
            st.markdown("### Lista de Contentores")
            
            for idx, row in contentores_df.iterrows():
                stock_contentor = obter_stock_contentor(row['id'])
                total_palhetas = stock_contentor['existencia_atual'].sum() if not stock_contentor.empty else 0
                total_lotes = len(stock_contentor)
                
                with st.expander(f"**{row['codigo']}** — {int(total_palhetas)} palhetas, {total_lotes} lotes"):
                    st.markdown(f"**Descrição:** {row['descricao'] or '—'}")
                    st.markdown(f"**Total de palhetas:** {int(total_palhetas)}")
                    st.markdown(f"**Total de lotes:** {total_lotes}")
                    
                    if not stock_contentor.empty:
                        st.markdown("---")
                        for canister in sorted(stock_contentor['canister'].unique()):
                            st.markdown(f"**Canister {canister}:**")
                            stock_canister = stock_contentor[stock_contentor['canister'] == canister]
                            
                            for andar in sorted(stock_canister['andar'].unique()):
                                st.markdown(f"  *{andar}º Andar:*")
                                stock_andar = stock_canister[stock_canister['andar'] == andar]
                                
                                for _, lote in stock_andar.iterrows():
                                    ref = lote['origem_externa'] or lote['data_embriovet'] or '—'
                                    st.markdown(f"  - {lote['garanhao']} | {lote['proprietario_nome']} | {int(lote['existencia_atual'])} palhetas | {ref}")

    st.stop()

if aba == "📦 Ver Stock":
    st.header("📦 Estoque Atual por Garanhão e Proprietário")

    if not stock.empty:
        garanhaos_disponiveis = sorted(stock["garanhao"].dropna().unique())
        
        # Verificar se há redirecionamento de stock recém-adicionado
        filtro_default = None
        stock_id_expandir = None
        
        if 'redirecionar_ver_stock' in st.session_state:
            if 'ultimo_garanhao' in st.session_state:
                filtro_default = st.session_state['ultimo_garanhao']
                stock_id_expandir = st.session_state.get('ultimo_stock_id')
            # Limpar flags
            del st.session_state['redirecionar_ver_stock']
            if 'ultimo_garanhao' in st.session_state:
                del st.session_state['ultimo_garanhao']
            if 'ultimo_stock_id' in st.session_state:
                del st.session_state['ultimo_stock_id']
        
        # Definir índice do selectbox
        if filtro_default and filtro_default in garanhaos_disponiveis:
            idx_default = garanhaos_disponiveis.index(filtro_default)
        else:
            idx_default = 0
        
        filtro = st.selectbox("Filtrar por Garanhão:", garanhaos_disponiveis, index=idx_default)
        stock_filtrado = stock[stock["garanhao"] == filtro]

        st.markdown("### 📊 Resumo por Proprietário")
        resumo_por_proprietario = (
            stock_filtrado.groupby("proprietario_nome")["existencia_atual"].sum().reset_index()
        )
        resumo_por_proprietario.columns = ["Proprietário", "Total Palhetas"]

        cols = st.columns(max(1, len(resumo_por_proprietario)))
        for idx, (_, row) in enumerate(resumo_por_proprietario.iterrows()):
            with cols[idx]:
                total_palhetas = to_py(row["Total Palhetas"]) or 0
                try:
                    total_palhetas = int(total_palhetas)
                except Exception:
                    total_palhetas = 0
                st.metric(label=f"👤 {row['Proprietário']}", value=f"{total_palhetas} palhetas")

        st.markdown("---")
        st.markdown("### 📦 Lotes Detalhados")

        proprietarios_dict = dict(zip(proprietarios["id"], proprietarios["nome"]))

        for _, row in stock_filtrado.iterrows():
            existencia = 0 if pd.isna(row.get("existencia_atual")) else int(to_py(row.get("existencia_atual")) or 0)
            referencia = row.get("origem_externa") or row.get("data_embriovet") or "Sem referência"
            proprietario_nome = row.get("proprietario_nome", "Sem proprietario")
            
            # Verificar se é o lote recém-adicionado para abrir automaticamente
            expanded = (stock_id_expandir == row["id"]) if stock_id_expandir else False

            with st.expander(f"📦 {referencia} — **{proprietario_nome}** — {existencia} palhetas", expanded=expanded):
                
                # Tabs: Mostrar conforme permissões
                if verificar_permissao('Administrador'):
                    # Admin vê tudo: Detalhes, Editar, Transferir
                    tab1, tab2, tab3 = st.tabs(["📋 Detalhes", "✏️ Editar", "🔄 Transferir"])
                elif verificar_permissao('Gestor'):
                    # Gestor vê: Detalhes, Transferir (sem Editar)
                    tab1, tab3 = st.tabs(["📋 Detalhes", "🔄 Transferir"])
                    tab2 = None
                else:
                    # Visualizador vê apenas: Detalhes
                    tab1 = st.tabs(["📋 Detalhes"])[0]
                    tab2 = None
                    tab3 = None
                
                # TAB 1: Detalhes
                with tab1:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**🏷️ Proprietário:** {proprietario_nome}")
                        
                        # Localização estruturada
                        if row.get('contentor_id'):
                            try:
                                contentor_query = f"SELECT codigo FROM contentores WHERE id = {int(row['contentor_id'])}"
                                with get_connection() as conn:
                                    contentor_df = pd.read_sql_query(contentor_query, conn)
                                    if not contentor_df.empty:
                                        contentor_codigo = contentor_df.iloc[0]['codigo']
                                        canister_num = row.get('canister', 'N/A')
                                        andar_num = row.get('andar', 'N/A')
                                        st.markdown(f"**📍 Localização:** {contentor_codigo} | Canister {canister_num} | {andar_num}º")
                                    else:
                                        st.markdown(f"**📍 Localização:** N/A")
                            except Exception:
                                st.markdown(f"**📍 Localização:** N/A")
                        else:
                            st.markdown(f"**📍 Localização:** N/A")
                        
                        st.markdown(f"**📜 Certificado:** {row.get('certificado') or 'N/A'}")
                        st.markdown(f"**✨ Qualidade:** {row.get('qualidade') or 0}%")
                    with col2:
                        st.markdown(f"**🔬 Concentração:** {row.get('concentracao') or 0} milhões/mL")
                        st.markdown(f"**⚡ Motilidade:** {row.get('motilidade') or 0}%")
                        st.markdown(f"**💊 Dose:** {row.get('dose') or 'N/A'}")
                        if row.get("observacoes"):
                            st.markdown(f"**📝 Observações:** {row.get('observacoes')}")
                    
                    # Informações de auditoria
                    st.markdown("---")
                    audit_col1, audit_col2 = st.columns(2)
                    with audit_col1:
                        if row.get("data_criacao"):
                            from datetime import datetime
                            try:
                                data_criacao = row.get("data_criacao")
                                if isinstance(data_criacao, str):
                                    data_criacao = datetime.fromisoformat(data_criacao.replace('Z', '+00:00'))
                                st.markdown(f"**📅 Criado em:** {data_criacao.strftime('%d/%m/%Y %H:%M')}")
                            except Exception:
                                st.markdown(f"**📅 Criado em:** {row.get('data_criacao')}")
                    with audit_col2:
                        if row.get("criado_por"):
                            st.markdown(f"**👤 Criado por:** {row.get('criado_por')}")
                
                # TAB 2: Editar (Apenas Admin)
                if tab2 is not None:
                    with tab2:
                        st.markdown("### ✏️ Editar Stock")
                        
                        # Botão + para adicionar proprietário
                        if st.button("➕ Novo Proprietário", key=f"btn_add_prop_edit_{row['id']}", help="Adicionar novo proprietário"):
                            modal_adicionar_proprietario()
                        
                        # Carregar contentores para edição
                        contentores_df_edit = carregar_contentores()
                        
                        with st.form(key=f"edit_form_{row['id']}"):
                            edit_garanhao = st.text_input("Garanhão", value=row.get("garanhao", ""))
                            
                            # Proprietário
                            prop_atual = row.get("dono_id")
                            idx_prop = 0
                            
                            # Se acabou de adicionar um proprietário novo, selecionar ele
                            if 'novo_proprietario_id' in st.session_state:
                                if st.session_state['novo_proprietario_id'] in proprietarios["id"].values:
                                    idx_prop = list(proprietarios["id"]).index(st.session_state['novo_proprietario_id'])
                            elif prop_atual in proprietarios["id"].values:
                                idx_prop = list(proprietarios["id"]).index(prop_atual)
                            
                            edit_proprietario = st.selectbox(
                                "Proprietário",
                                options=proprietarios["id"].tolist(),
                                format_func=lambda x: proprietarios_dict.get(x, "Desconhecido"),
                                index=idx_prop,
                                key=f"edit_prop_{row['id']}"
                            )
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                edit_data = st.text_input("Data Produção", value=row.get("data_embriovet") or "")
                                edit_origem = st.text_input("Origem Externa", value=row.get("origem_externa") or "")
                                edit_palhetas = st.number_input("Palhetas Produzidas", min_value=0, value=int(to_py(row.get("palhetas_produzidas")) or 0))
                                edit_existencia = st.number_input("Existência Atual", min_value=0, value=existencia)
                                edit_qualidade = st.number_input("Qualidade (%)", min_value=0, max_value=100, value=int(to_py(row.get("qualidade")) or 0))
                            
                            with col2:
                                edit_concentracao = st.number_input("Concentração", min_value=0, value=int(to_py(row.get("concentracao")) or 0))
                                edit_motilidade = st.number_input("Motilidade (%)", min_value=0, max_value=100, value=int(to_py(row.get("motilidade")) or 0))
                                edit_certificado = st.selectbox("Certificado", ["Sim", "Não"], index=0 if row.get("certificado") == "Sim" else 1)
                                edit_dose = st.text_input("Dose", value=row.get("dose") or "")
                            
                            st.markdown("---")
                            st.subheader("📍 Localização Física")
                            
                            if not contentores_df_edit.empty:
                                col_loc1, col_loc2, col_loc3 = st.columns(3)
                                
                                # Contentor atual
                                contentor_atual_id = row.get("contentor_id")
                                idx_contentor = 0
                                if contentor_atual_id and contentor_atual_id in contentores_df_edit["id"].values:
                                    idx_contentor = list(contentores_df_edit["id"]).index(contentor_atual_id)
                                
                                with col_loc1:
                                    edit_contentor_codigo = st.selectbox(
                                        "Contentor *",
                                        options=contentores_df_edit["codigo"].tolist(),
                                        index=idx_contentor,
                                        key=f"edit_cont_{row['id']}"
                                    )
                                    edit_contentor_id = int(contentores_df_edit.loc[contentores_df_edit["codigo"] == edit_contentor_codigo, "id"].iloc[0])
                                
                                with col_loc2:
                                    canister_atual = row.get("canister", 1)
                                    edit_canister = st.selectbox(
                                        "Canister *",
                                        options=list(range(1, 11)),
                                        index=canister_atual - 1 if canister_atual else 0,
                                        key=f"edit_can_{row['id']}"
                                    )
                                
                                with col_loc3:
                                    andar_atual = row.get("andar", 1)
                                    edit_andar = st.radio(
                                        "Andar *",
                                        options=[1, 2],
                                        format_func=lambda x: f"{x}º",
                                        horizontal=True,
                                        index=andar_atual - 1 if andar_atual else 0,
                                        key=f"edit_and_{row['id']}"
                                    )
                            else:
                                st.warning("⚠️ Nenhum contentor disponível. Crie contentores no Mapa primeiro.")
                                edit_contentor_id = None
                                edit_canister = 1
                                edit_andar = 1
                            
                            edit_obs = st.text_area("Observações", value=row.get("observacoes") or "")
                            
                            submit_edit = st.form_submit_button("💾 Guardar Alterações", type="primary")
                            
                            if submit_edit:
                                if editar_stock(row["id"], {
                                    "garanhao": edit_garanhao,
                                    "dono_id": edit_proprietario,
                                    "data": edit_data,
                                    "origem": edit_origem,
                                    "palhetas_produzidas": edit_palhetas,
                                    "qualidade": edit_qualidade,
                                    "concentracao": edit_concentracao,
                                    "motilidade": edit_motilidade,
                                    "contentor_id": edit_contentor_id,
                                    "canister": edit_canister,
                                    "andar": edit_andar,
                                    "certificado": edit_certificado,
                                    "dose": edit_dose,
                                    "observacoes": edit_obs,
                                    "existencia": edit_existencia
                                }):
                                    st.success("✅ Stock atualizado com sucesso!")
                                    # Marcar que usou
                                    if 'novo_proprietario_id' in st.session_state:
                                        st.session_state['novo_proprietario_usado'] = True
                                    st.rerun()
                
                # TAB 3: Transferir (Gestor e Admin apenas)
                if tab3 is not None:
                    with tab3:
                        st.markdown("### 🔄 Transferir Palhetas")
                        
                        # Escolher tipo de transferência
                        tipo_transf = st.radio(
                            "Tipo de Transferência:",
                            ["🔄 Interna (para outro proprietário do sistema)", "📤 Externa (venda/envio para fora)"],
                            key=f"tipo_transf_{row['id']}"
                        )
                        
                        if tipo_transf.startswith("🔄"):
                            # TRANSFERÊNCIA INTERNA
                            st.info("Transferir para outro proprietário cadastrado no sistema")
                            
                            # Botão + para adicionar proprietário
                            if st.button("➕ Novo Proprietário", key=f"btn_add_prop_transf_{row['id']}", help="Adicionar novo proprietário"):
                                modal_adicionar_proprietario()
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                if not proprietarios.empty:
                                    ids = proprietarios["id"].tolist()
                                    
                                    # Se acabou de adicionar, selecionar o novo
                                    idx_transf = 0
                                    if 'novo_proprietario_id' in st.session_state:
                                        if st.session_state['novo_proprietario_id'] in ids:
                                            idx_transf = ids.index(st.session_state['novo_proprietario_id'])
                                    
                                    novo_proprietario = st.selectbox(
                                        "Para qual proprietário?",
                                        options=ids,
                                        format_func=lambda x: proprietarios_dict.get(x, "Desconhecido"),
                                        index=idx_transf,
                                        key=f"transf_select_{row['id']}",
                                    )
                            
                            with col2:
                                qtd_transferir = st.number_input(
                                    "Quantidade de palhetas",
                                    min_value=1,
                                    max_value=max(existencia, 1),
                                    value=max(min(existencia, 1), 1),
                                    key=f"transf_qtd_{row['id']}"
                                )
                            
                            if st.button("🔄 Transferir Internamente", key=f"btn_transf_{row['id']}", type="primary"):
                                if transferir_palhetas_parcial(row["id"], novo_proprietario, qtd_transferir):
                                    st.success(f"✅ {qtd_transferir} palhetas transferidas de {proprietario_nome} para {proprietarios_dict.get(novo_proprietario, 'Desconhecido')}!")
                                    # Marcar que usou
                                    if 'novo_proprietario_id' in st.session_state:
                                        st.session_state['novo_proprietario_usado'] = True
                                    st.rerun()
                        
                        else:
                            # TRANSFERÊNCIA EXTERNA
                            st.warning("⚠️ Esta operação retira o sêmen do stock (venda/envio)")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                destinatario_ext = st.text_input(
                                    "Nome do Comprador/Destinatário *",
                                    placeholder="Ex: João Silva, Fazenda XYZ",
                                    key=f"dest_ext_{row['id']}"
                                )
                                tipo_saida = st.selectbox(
                                    "Tipo de Saída",
                                    ["Venda", "Doação", "Exportação", "Outro"],
                                    key=f"tipo_saida_{row['id']}"
                                )
                            
                            with col2:
                                qtd_transferir_ext = st.number_input(
                                    "Quantidade de palhetas",
                                    min_value=1,
                                    max_value=max(existencia, 1),
                                    value=max(min(existencia, 1), 1),
                                    key=f"transf_qtd_ext_{row['id']}"
                                )
                                obs_ext = st.text_area(
                                    "Observações",
                                    placeholder="Ex: Valor, forma de pagamento, contato...",
                                    key=f"obs_ext_{row['id']}",
                                    height=80
                                )
                            
                            if st.button("📤 Enviar para Externo", key=f"btn_transf_ext_{row['id']}", type="primary"):
                                if not destinatario_ext:
                                    st.error("❌ Nome do destinatário é obrigatório")
                                elif transferir_palhetas_externo(row["id"], destinatario_ext, qtd_transferir_ext, tipo_saida, obs_ext):
                                    st.success(f"✅ {qtd_transferir_ext} palhetas enviadas para {destinatario_ext} ({tipo_saida})")
                                    st.rerun()
    else:
        st.info("ℹ️ Nenhum stock cadastrado.")

# ------------------------------------------------------------
# ➕ Adicionar Stock
# ------------------------------------------------------------
elif aba == "➕ Adicionar Stock":
    st.header("➕ Inserir novo stock com Proprietário")

    if proprietarios.empty:
        st.warning("⚠️ Nenhum proprietário cadastrado.")
        if st.button("➕ Adicionar Primeiro Proprietário", type="primary"):
            modal_adicionar_proprietario()
    else:
        # Carregar contentores
        contentores_df = carregar_contentores()
        
        if contentores_df.empty:
            st.warning("⚠️ Nenhum contentor cadastrado. Por favor, crie contentores primeiro no Mapa.")
        else:
            # Botão + fora do form
            if st.button("➕ Novo Proprietário", key="btn_add_prop_stock", help="Adicionar novo proprietário"):
                modal_adicionar_proprietario()
            
            with st.form("novo_stock"):
                garanhao = st.text_input("Garanhão *", help="Nome obrigatório")
                
                # Verificar se há proprietário recém-adicionado
                if 'novo_proprietario_id' in st.session_state:
                    idx_default = list(proprietarios["id"]).index(st.session_state['novo_proprietario_id'])
                else:
                    idx_default = 0
                
                proprietario_nome = st.selectbox("Proprietário do Sémen *", proprietarios["nome"], index=idx_default)

                dono_id = int(proprietarios.loc[proprietarios["nome"] == proprietario_nome, "id"].iloc[0])

                col1, col2 = st.columns(2)
                with col1:
                    data = st.text_input("Data de Produção")
                    origem = st.text_input("Origem Externa / Referência")
                    palhetas = st.number_input("Palhetas Produzidas *", min_value=0, value=0)
                    qualidade = st.number_input("Qualidade (%)", min_value=0, max_value=100, value=0)
                    concentracao = st.number_input("Concentração (milhões/mL)", min_value=0, value=0)

                with col2:
                    motilidade = st.number_input("Motilidade (%)", min_value=0, max_value=100, value=0)
                    certificado = st.selectbox("Certificado?", ["Sim", "Não"])
                    dose = st.text_input("Dose")

                st.markdown("---")
                st.subheader("📍 Localização Física")
                
                col_loc1, col_loc2, col_loc3 = st.columns(3)
                with col_loc1:
                    contentor_selecionado = st.selectbox(
                        "Contentor *",
                        options=contentores_df["codigo"].tolist(),
                        help="Selecione o contentor onde o sémen será armazenado"
                    )
                    contentor_id = int(contentores_df.loc[contentores_df["codigo"] == contentor_selecionado, "id"].iloc[0])
                
                with col_loc2:
                    canister = st.selectbox(
                        "Canister *",
                        options=list(range(1, 11)),
                        help="Número do canister (1-10)"
                    )
                
                with col_loc3:
                    andar = st.radio(
                        "Andar *",
                        options=[1, 2],
                        format_func=lambda x: f"{x}º",
                        horizontal=True,
                        help="Nível dentro do canister"
                    )

                observacoes = st.text_area("Observações", help="Informações adicionais (opcional)")
                submitted = st.form_submit_button("💾 Salvar")

                if submitted:
                    palhetas_int = int(to_py(palhetas) or 0)

                    if not garanhao:
                        st.error("❌ Nome do garanhão é obrigatório")
                    elif palhetas_int <= 0:
                        st.error("❌ Número de palhetas deve ser maior que zero")
                    else:
                        ok = inserir_stock(
                            {
                                "Garanhão": garanhao,
                                "Proprietário": dono_id,
                                "Data": data,
                                "Origem": origem,
                                "Palhetas": palhetas_int,
                                "Qualidade": int(to_py(qualidade) or 0),
                                "Concentração": int(to_py(concentracao) or 0),
                                "Motilidade": int(to_py(motilidade) or 0),
                                "Certificado": certificado,
                                "Dose": dose,
                                "Contentor": contentor_id,
                                "Canister": canister,
                                "Andar": andar,
                                "Observações": observacoes,
                            }
                        )
                        if ok:
                            st.success("✅ Stock adicionado com sucesso!")
                            # Marcar que usou o proprietário
                            if 'novo_proprietario_id' in st.session_state:
                                st.session_state['novo_proprietario_usado'] = True
                            # Mudar aba para Ver Stock
                            st.session_state['aba_selecionada'] = "📦 Ver Stock"
                            st.rerun()

# ------------------------------------------------------------
# 📝 Registrar Inseminação
# ------------------------------------------------------------
elif aba == "📝 Registrar Inseminação":
    st.header("📝 Registrar uso de Sémen")

    if stock.empty:
        st.warning("⚠️ Nenhum stock disponível.")
    else:
        stock_disponivel = stock[stock["existencia_atual"] > 0]

        if stock_disponivel.empty:
            st.warning("⚠️ Todo o stock está esgotado.")
        else:
            garanhao = st.selectbox("Garanhão", sorted(stock_disponivel["garanhao"].unique()))
            stocks_filtrados = stock_disponivel[stock_disponivel["garanhao"] == garanhao]

            if len(stocks_filtrados) > 0:
                st.markdown("### 📊 Sémen Disponível por Proprietário")
                resumo = stocks_filtrados.groupby("proprietario_nome")["existencia_atual"].sum().reset_index()
                cols = st.columns(max(1, len(resumo)))
                for idx, (_, row) in enumerate(resumo.iterrows()):
                    with cols[idx]:
                        st.metric(f"👤 {row['proprietario_nome']}", f"{int(to_py(row['existencia_atual']) or 0)} palhetas")
                st.markdown("---")

            st.markdown("### 🎯 Selecionar Lote (DE QUAL PROPRIETÁRIO)")
            lote_opcoes = {}
            for _, row in stocks_filtrados.iterrows():
                ref = row.get("origem_externa") or row.get("data_embriovet") or f"Lote #{row.get('id')}"
                proprietario_nome = row.get("proprietario_nome", "Sem proprietario")
                existencia = int(to_py(row.get("existencia_atual")) or 0)
                local = row.get("local_armazenagem", "N/A")
                lote_opcoes[row["id"]] = f"👤 {proprietario_nome} | 📦 {ref} | 📍 {local} ({existencia} palhetas)"

            stock_id = st.selectbox(
                "Selecionar lote de qual proprietario usar:",
                options=list(lote_opcoes.keys()),
                format_func=lambda x: lote_opcoes[x],
                help="Escolha de qual proprietario você quer usar o sémen",
            )

            lote_selecionado = stocks_filtrados[stocks_filtrados["id"] == stock_id].iloc[0]
            proprietario_nome = lote_selecionado.get("proprietario_nome", "Desconhecido")
            max_palhetas = int(to_py(lote_selecionado.get("existencia_atual")) or 0)

            st.info(f"🎯 Você vai usar sémen **do {proprietario_nome}** | Disponível: **{max_palhetas} palhetas**")

            col1, col2 = st.columns(2)
            with col1:
                data = st.date_input("Data de Inseminação")
                egua = st.text_input("Égua *", help="Nome obrigatório")
            with col2:
                protocolo = lote_selecionado.get("data_embriovet") or lote_selecionado.get("origem_externa") or "N/A"
                palhetas = st.number_input("Palhetas utilizadas", min_value=1, max_value=max(max_palhetas, 1), value=min(max_palhetas, 1) if max_palhetas > 0 else 1)

            if st.button("📝 Registrar Inseminação", type="primary", key="btn_registrar_insem"):
                palhetas_int = int(to_py(palhetas) or 0)
                if not egua:
                    st.error("❌ Nome da égua é obrigatório")
                elif palhetas_int <= 0:
                    st.error("❌ Número de palhetas deve ser maior que zero")
                elif palhetas_int > max_palhetas:
                    st.error(f"❌ Estoque insuficiente! Disponível: {max_palhetas} palhetas")
                else:
                    ok = registrar_inseminacao(
                        {
                            "garanhao": garanhao,
                            "dono_id": to_py(lote_selecionado.get("dono_id")),
                            "data": data,
                            "egua": egua,
                            "protocolo": protocolo,
                            "palhetas": palhetas_int,
                            "stock_id": stock_id,
                        }
                    )
                    if ok:
                        st.success(f"✅ Inseminação registrada! Usado sémen do **{proprietario_nome}** ({palhetas_int} palhetas)")
                        st.balloons()
                        st.rerun()

# ------------------------------------------------------------
# 📈 Relatórios
# ------------------------------------------------------------
elif aba == "📈 Relatórios":
    st.header("📈 Relatórios e Análises")
    
    # Filtros globais de data
    st.markdown("### 📅 Filtros de Período")
    col_filtro1, col_filtro2, col_filtro3 = st.columns([2, 2, 1])
    
    with col_filtro1:
        usar_filtro_data = st.checkbox("Filtrar por período", value=False, help="Ativar para filtrar por datas")
    
    data_inicio = None
    data_fim = None
    
    if usar_filtro_data:
        with col_filtro2:
            data_inicio = st.date_input("Data início", value=None, help="Deixe vazio para sem limite")
        
        with col_filtro3:
            data_fim = st.date_input("Data fim", value=None, help="Deixe vazio para sem limite")
        
        if data_inicio and data_fim and data_inicio > data_fim:
            st.error("❌ Data de início não pode ser maior que data de fim")
            data_inicio = None
            data_fim = None
    
    st.markdown("---")
    
    # Sub-abas principais simplificadas
    rel_tab1, rel_tab2, rel_tab3 = st.tabs([
        "🔍 Pesquisa por Garanhão", 
        "🔍 Pesquisa por Proprietário",
        "📊 Histórico Geral"
    ])
    
    # TAB 1: Pesquisa Completa por Garanhão
    with rel_tab1:
        st.markdown("### 🔍 Pesquisa Completa por Garanhão")
        st.info("📋 Selecione um garanhão para ver TODO o histórico e informações")
        
        stock = carregar_stock()
        insem = carregar_inseminacoes()
        
        # Aplicar filtros de data se ativos
        if usar_filtro_data and (data_inicio or data_fim):
            insem = aplicar_filtro_data(insem, 'data_inseminacao', data_inicio, data_fim)
        
        if stock.empty:
            st.warning("⚠️ Nenhum stock registrado.")
        else:
            # Seleção do garanhão
            col_select, col_export = st.columns([5, 1])
            with col_select:
                garanhoes_lista = sorted(stock["garanhao"].unique())
                garanhao_selecionado = st.selectbox(
                    "🐴 Escolha o Garanhão",
                    garanhoes_lista,
                    key="garanhao_pesquisa"
                )
            
            if garanhao_selecionado:
                # Filtrar dados deste garanhão
                dados_garanhao = stock[stock["garanhao"] == garanhao_selecionado]
                insem_garanhao = insem[insem["garanhao"] == garanhao_selecionado] if not insem.empty else pd.DataFrame()
                transf = carregar_transferencias()
                transf_ext = carregar_transferencias_externas()
                
                # Aplicar filtros de data nas transferências
                if usar_filtro_data and (data_inicio or data_fim):
                    transf = aplicar_filtro_data(transf, 'data_transferencia', data_inicio, data_fim)
                    transf_ext = aplicar_filtro_data(transf_ext, 'data_transferencia', data_inicio, data_fim)
                
                transf_garanhao = transf[transf["garanhao"] == garanhao_selecionado] if not transf.empty else pd.DataFrame()
                transf_ext_garanhao = transf_ext[transf_ext["garanhao"] == garanhao_selecionado] if not transf_ext.empty else pd.DataFrame()
                
                # Botão exportar tudo deste garanhão
                with col_export:
                    # Preparar dados completos para exportação
                    export_data = {
                        'Stock': dados_garanhao[["proprietario_nome", "data_embriovet", "existencia_atual", "qualidade", "local_armazenagem"]],
                        'Inseminações': insem_garanhao[["data_inseminacao", "egua", "proprietario_nome", "palhetas_gastas"]] if not insem_garanhao.empty else pd.DataFrame(),
                        'Transferências Internas': transf_garanhao[["data_transferencia", "proprietario_origem", "proprietario_destino", "quantidade"]] if not transf_garanhao.empty else pd.DataFrame(),
                        'Transferências Externas': transf_ext_garanhao[["data_transferencia", "proprietario_origem", "destinatario_externo", "quantidade", "tipo", "observacoes"]] if not transf_ext_garanhao.empty else pd.DataFrame()
                    }
                    
                    # Criar CSV completo
                    csv_completo = f"=== GARANHÃO: {garanhao_selecionado} ===\n\n"
                    for nome, df in export_data.items():
                        if not df.empty:
                            csv_completo += f"\n{nome}:\n{df.to_csv(index=False)}\n"
                    
                    st.download_button(
                        label="📥 CSV",
                        data=csv_completo.encode('utf-8'),
                        file_name=f"garanhao_{garanhao_selecionado}.csv",
                        mime="text/csv",
                        help="Exportar em CSV",
                        use_container_width=True
                    )
                    
                    # Botão PDF
                    pdf_buffer = gerar_pdf_garanhao(
                        garanhao_selecionado,
                        dados_garanhao,
                        insem_garanhao,
                        transf_garanhao,
                        transf_ext_garanhao
                    )
                    
                    if pdf_buffer:
                        st.download_button(
                            label="📄 PDF",
                            data=pdf_buffer,
                            file_name=f"garanhao_{garanhao_selecionado}.pdf",
                            mime="application/pdf",
                            help="Exportar relatório completo em PDF",
                            use_container_width=True
                        )
                
                st.markdown(f"# 🐴 {garanhao_selecionado}")
                st.markdown("---")
                
                # Filtros de visualização
                st.markdown("### 🔍 Escolha o que quer ver:")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    ver_resumo = st.checkbox("📊 Resumo Geral", value=True)
                with col2:
                    ver_stock = st.checkbox("📦 Stock Detalhado", value=True)
                with col3:
                    ver_insem = st.checkbox("📝 Inseminações", value=True)
                with col4:
                    ver_transf = st.checkbox("🔄 Transferências", value=True)
                
                st.markdown("---")
                
                # RESUMO GERAL
                if ver_resumo:
                    st.markdown("## 📊 Resumo Geral")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        total_palhetas = int(to_py(dados_garanhao["existencia_atual"].sum()) or 0)
                        st.metric("📦 Stock Total", total_palhetas)
                    with col2:
                        num_proprietarios = dados_garanhao["proprietario_nome"].nunique()
                        st.metric("👥 Proprietários", num_proprietarios)
                    with col3:
                        if not insem_garanhao.empty:
                            total_insem = len(insem_garanhao)
                            st.metric("📝 Inseminações", total_insem)
                        else:
                            st.metric("📝 Inseminações", 0)
                    with col4:
                        media_qualidade = int(to_py(dados_garanhao["qualidade"].mean()) or 0)
                        st.metric("⭐ Qualidade Média", f"{media_qualidade}%")
                    st.markdown("---")
                
                # STOCK DETALHADO
                if ver_stock:
                    st.markdown("## 📦 Stock Detalhado")
                    st.markdown("#### Distribuição por Proprietário")
                    
                    # Tabela de stock por proprietário
                    stock_resumo = dados_garanhao.groupby("proprietario_nome").agg({
                        "existencia_atual": "sum",
                        "qualidade": "mean",
                        "data_embriovet": "max"
                    }).reset_index()
                    stock_resumo.columns = ["Proprietário", "Palhetas", "Qualidade Média (%)", "Última Data"]
                    stock_resumo["Qualidade Média (%)"] = stock_resumo["Qualidade Média (%)"].round(1)
                    stock_resumo = stock_resumo.sort_values("Palhetas", ascending=False)
                    
                    st.dataframe(stock_resumo, width="stretch", hide_index=True)
                    
                    # Detalhes de cada lote
                    with st.expander("📋 Ver Todos os Lotes Detalhados"):
                        lotes_detalhados = dados_garanhao[[
                            "proprietario_nome", "data_embriovet", "palhetas_produzidas",
                            "existencia_atual", "qualidade", "concentracao", "motilidade",
                            "local_armazenagem", "certificado"
                        ]].copy()
                        lotes_detalhados.columns = [
                            "Proprietário", "Data", "Produzidas", "Stock Atual",
                            "Qualidade (%)", "Concentração", "Motilidade (%)", "Local", "Certificado"
                        ]
                        st.dataframe(lotes_detalhados, width="stretch", hide_index=True)
                    
                    st.markdown("---")
                
                # INSEMINAÇÕES
                if ver_insem:
                    st.markdown("## 📝 Histórico de Inseminações")
                    if insem_garanhao.empty:
                        st.info("ℹ️ Nenhuma inseminação registrada para este garanhão")
                    else:
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total Inseminações", len(insem_garanhao))
                        with col2:
                            total_palhetas_usadas = int(to_py(insem_garanhao["palhetas_gastas"].sum()) or 0)
                            st.metric("Palhetas Utilizadas", total_palhetas_usadas)
                        with col3:
                            num_eguas = insem_garanhao["egua"].nunique()
                            st.metric("Éguas Diferentes", num_eguas)
                        
                        st.markdown("#### 📋 Todas as Inseminações")
                        insem_exibir = insem_garanhao[[
                            "data_inseminacao", "egua", "proprietario_nome", "palhetas_gastas"
                        ]].copy().sort_values("data_inseminacao", ascending=False)
                        insem_exibir.columns = ["Data", "Égua", "Proprietário", "Palhetas"]
                        st.dataframe(insem_exibir, width="stretch", hide_index=True, height=300)
                    
                    st.markdown("---")
                
                # TRANSFERÊNCIAS
                if ver_transf:
                    st.markdown("## 🔄 Histórico de Transferências")
                    
                    # Mostrar transferências internas
                    if not transf_garanhao.empty:
                        st.markdown("### 🔄 Transferências Internas")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Total Transferências Internas", len(transf_garanhao))
                        with col2:
                            total_transf = int(to_py(transf_garanhao["quantidade"].sum()) or 0)
                            st.metric("Palhetas Movimentadas", total_transf)
                        
                        transf_exibir = transf_garanhao[[
                            "data_transferencia", "proprietario_origem", "proprietario_destino", "quantidade"
                        ]].copy().sort_values("data_transferencia", ascending=False)
                        transf_exibir.columns = ["Data", "De", "Para", "Palhetas"]
                        st.dataframe(transf_exibir, width="stretch", hide_index=True, height=250)
                        st.markdown("---")
                    
                    # Mostrar transferências externas
                    if not transf_ext_garanhao.empty:
                        st.markdown("### 📤 Transferências Externas (Vendas/Doações)")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Total Transferências Externas", len(transf_ext_garanhao))
                        with col2:
                            total_ext = int(to_py(transf_ext_garanhao["quantidade"].sum()) or 0)
                            st.metric("Palhetas Enviadas", total_ext)
                        
                        transf_ext_exibir = transf_ext_garanhao[[
                            "data_transferencia", "proprietario_origem", "destinatario_externo", "quantidade", "tipo", "observacoes"
                        ]].copy().sort_values("data_transferencia", ascending=False)
                        transf_ext_exibir.columns = ["Data", "De", "Para", "Palhetas", "Tipo", "Observações"]
                        st.dataframe(transf_ext_exibir, width="stretch", hide_index=True, height=250)
                    
                    # Se não houver nenhuma transferência
                    if transf_garanhao.empty and transf_ext_garanhao.empty:
                        st.info("ℹ️ Nenhuma transferência registrada para este garanhão")
    
    # TAB 2: Pesquisa Completa por Proprietário
    with rel_tab2:
        st.markdown("### 🔍 Pesquisa Completa por Proprietário")
        st.info("📋 Selecione um proprietário para ver TODO o histórico e informações")
        
        stock = carregar_stock()
        insem = carregar_inseminacoes()
        proprietarios = carregar_proprietarios()
        
        if proprietarios.empty:
            st.warning("⚠️ Nenhum proprietário cadastrado.")
        else:
            # Seleção do proprietário
            col_select, col_export = st.columns([5, 1])
            with col_select:
                prop_selecionado = st.selectbox(
                    "👤 Escolha o Proprietário",
                    proprietarios["id"].tolist(),
                    format_func=lambda x: proprietarios[proprietarios["id"]==x]["nome"].values[0],
                    key="prop_pesquisa"
                )
            
            if prop_selecionado:
                prop_nome = proprietarios[proprietarios["id"]==prop_selecionado]["nome"].values[0]
                
                # Filtrar dados deste proprietário
                stock_prop = stock[stock["dono_id"] == prop_selecionado]
                insem_prop = insem[insem["dono_id"] == prop_selecionado] if not insem.empty else pd.DataFrame()
                transf = carregar_transferencias()
                transf_recebidas = transf[transf["proprietario_destino_id"] == prop_selecionado] if not transf.empty else pd.DataFrame()
                transf_enviadas = transf[transf["proprietario_origem_id"] == prop_selecionado] if not transf.empty else pd.DataFrame()
                transf_ext = carregar_transferencias_externas()
                transf_ext_prop = transf_ext[transf_ext["proprietario_origem_id"] == prop_selecionado] if not transf_ext.empty else pd.DataFrame()
                
                # Botão exportar tudo deste proprietário
                with col_export:
                    csv_completo = f"=== PROPRIETÁRIO: {prop_nome} ===\n\n"
                    if not stock_prop.empty:
                        csv_completo += f"\nStock:\n{stock_prop[['garanhao', 'existencia_atual', 'qualidade']].to_csv(index=False)}\n"
                    if not insem_prop.empty:
                        csv_completo += f"\nInseminações:\n{insem_prop[['data_inseminacao', 'garanhao', 'egua']].to_csv(index=False)}\n"
                    
                    st.download_button(
                        label="📥 Exportar",
                        data=csv_completo.encode('utf-8'),
                        file_name=f"proprietario_{prop_nome}.csv",
                        mime="text/csv"
                    )
                
                st.markdown(f"# 👤 {prop_nome}")
                st.markdown("---")
                
                # Filtros de visualização
                st.markdown("### 🔍 Escolha o que quer ver:")
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    ver_resumo = st.checkbox("📊 Resumo", value=True, key="prop_resumo")
                with col2:
                    ver_stock = st.checkbox("📦 Stock", value=True, key="prop_stock")
                with col3:
                    ver_insem = st.checkbox("📝 Inseminações", value=True, key="prop_insem")
                with col4:
                    ver_recebidas = st.checkbox("📥 Recebidas", value=True, key="prop_receb")
                with col5:
                    ver_enviadas = st.checkbox("📤 Enviadas", value=True, key="prop_env")
                
                st.markdown("---")
                
                # RESUMO GERAL
                if ver_resumo:
                    st.markdown("## 📊 Resumo Geral")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        total_palhetas = int(to_py(stock_prop["existencia_atual"].sum()) or 0) if not stock_prop.empty else 0
                        st.metric("📦 Stock Total", total_palhetas)
                    with col2:
                        num_garanhaos = stock_prop["garanhao"].nunique() if not stock_prop.empty else 0
                        st.metric("🐴 Garanhões", num_garanhaos)
                    with col3:
                        num_insem = len(insem_prop) if not insem_prop.empty else 0
                        st.metric("📝 Inseminações", num_insem)
                    with col4:
                        num_transf = len(transf_recebidas) + len(transf_enviadas)
                        st.metric("🔄 Transferências", num_transf)
                    st.markdown("---")
                
                # STOCK DETALHADO
                if ver_stock:
                    st.markdown("## 📦 Stock Detalhado")
                    if stock_prop.empty:
                        st.info("ℹ️ Nenhum stock registrado para este proprietário")
                    else:
                        # Resumo por garanhão
                        stock_resumo = stock_prop.groupby("garanhao").agg({
                            "existencia_atual": "sum",
                            "qualidade": "mean",
                            "data_embriovet": "max"
                        }).reset_index()
                        stock_resumo.columns = ["Garanhão", "Palhetas", "Qualidade Média (%)", "Última Data"]
                        stock_resumo["Qualidade Média (%)"] = stock_resumo["Qualidade Média (%)"].round(1)
                        stock_resumo = stock_resumo.sort_values("Palhetas", ascending=False)
                        
                        st.dataframe(stock_resumo, width="stretch", hide_index=True)
                        
                        # Todos os lotes
                        with st.expander("📋 Ver Todos os Lotes"):
                            lotes = stock_prop[[
                                "garanhao", "data_embriovet", "palhetas_produzidas", "existencia_atual",
                                "qualidade", "concentracao", "motilidade", "local_armazenagem"
                            ]].copy()
                            lotes.columns = [
                                "Garanhão", "Data", "Produzidas", "Stock Atual",
                                "Qualidade (%)", "Concentração", "Motilidade (%)", "Local"
                            ]
                            st.dataframe(lotes, width="stretch", hide_index=True)
                    st.markdown("---")
                
                # INSEMINAÇÕES
                if ver_insem:
                    st.markdown("## 📝 Histórico de Inseminações")
                    if insem_prop.empty:
                        st.info("ℹ️ Nenhuma inseminação registrada")
                    else:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Total Inseminações", len(insem_prop))
                        with col2:
                            total_gasto = int(to_py(insem_prop["palhetas_gastas"].sum()) or 0)
                            st.metric("Palhetas Utilizadas", total_gasto)
                        
                        insem_exibir = insem_prop[[
                            "data_inseminacao", "garanhao", "egua", "palhetas_gastas"
                        ]].copy().sort_values("data_inseminacao", ascending=False)
                        insem_exibir.columns = ["Data", "Garanhão", "Égua", "Palhetas"]
                        st.dataframe(insem_exibir, width="stretch", hide_index=True, height=300)
                    st.markdown("---")
                
                # TRANSFERÊNCIAS RECEBIDAS
                if ver_recebidas:
                    st.markdown("## 📥 Transferências Recebidas")
                    if transf_recebidas.empty:
                        st.info("ℹ️ Nenhuma transferência recebida")
                    else:
                        total_recebido = int(to_py(transf_recebidas["quantidade"].sum()) or 0)
                        st.metric("Total Palhetas Recebidas", total_recebido)
                        
                        transf_rec_exibir = transf_recebidas[[
                            "data_transferencia", "garanhao", "proprietario_origem", "quantidade"
                        ]].copy().sort_values("data_transferencia", ascending=False)
                        transf_rec_exibir.columns = ["Data", "Garanhão", "De", "Palhetas"]
                        st.dataframe(transf_rec_exibir, width="stretch", hide_index=True, height=200)
                    st.markdown("---")
                
                # TRANSFERÊNCIAS ENVIADAS
                if ver_enviadas:
                    st.markdown("## 📤 Transferências Enviadas (Internas)")
                    if transf_enviadas.empty:
                        st.info("ℹ️ Nenhuma transferência interna enviada")
                    else:
                        total_enviado = int(to_py(transf_enviadas["quantidade"].sum()) or 0)
                        st.metric("Total Palhetas Enviadas", total_enviado)
                        
                        transf_env_exibir = transf_enviadas[[
                            "data_transferencia", "garanhao", "proprietario_destino", "quantidade"
                        ]].copy().sort_values("data_transferencia", ascending=False)
                        transf_env_exibir.columns = ["Data", "Garanhão", "Para", "Palhetas"]
                        st.dataframe(transf_env_exibir, width="stretch", hide_index=True, height=200)
                    
                    st.markdown("---")
                    
                    # TRANSFERÊNCIAS EXTERNAS
                    st.markdown("## 📤 Transferências Externas (Vendas/Doações)")
                    if transf_ext_prop.empty:
                        st.info("ℹ️ Nenhuma transferência externa registrada")
                    else:
                        total_ext = int(to_py(transf_ext_prop["quantidade"].sum()) or 0)
                        st.metric("Total Palhetas Vendidas/Enviadas", total_ext)
                        
                        transf_ext_exibir = transf_ext_prop[[
                            "data_transferencia", "garanhao", "destinatario_externo", "quantidade", "tipo", "observacoes"
                        ]].copy().sort_values("data_transferencia", ascending=False)
                        transf_ext_exibir.columns = ["Data", "Garanhão", "Para", "Palhetas", "Tipo", "Observações"]
                        st.dataframe(transf_ext_exibir, width="stretch", hide_index=True, height=200)
    
    # TAB 3: Histórico Geral
    with rel_tab3:
        st.markdown("### 📊 Histórico Geral do Sistema")
        st.info("📋 Visualize todo o histórico com filtros")
        
        stock = carregar_stock()
        insem = carregar_inseminacoes()
        
        # Escolher tipo de histórico
        tipo_historico = st.radio(
            "Escolha o tipo de histórico:",
            ["📝 Inseminações", "🔄 Transferências Internas", "📤 Transferências Externas", "📦 Stock Completo"],
            horizontal=True
        )
        
        st.markdown("---")
        
        if tipo_historico == "📝 Inseminações":
            st.markdown("### 📝 Todas as Inseminações")
            
            if insem.empty:
                st.info("ℹ️ Nenhuma inseminação registrada")
            else:
                # Exportação
                col1, col2 = st.columns([6, 1])
                with col2:
                    csv_insem = insem[["data_inseminacao", "garanhao", "egua", "proprietario_nome", "palhetas_gastas"]].copy()
                    csv_insem.columns = ["Data", "Garanhão", "Égua", "Proprietário", "Palhetas"]
                    st.download_button(
                        "📥 Exportar",
                        csv_insem.to_csv(index=False).encode('utf-8'),
                        "inseminacoes_todas.csv",
                        "text/csv"
                    )
                
                # Filtros
                col1, col2, col3 = st.columns(3)
                with col1:
                    filtro_garanhao = st.multiselect("Filtrar por Garanhão", sorted(insem["garanhao"].unique()))
                with col2:
                    filtro_prop = st.multiselect("Filtrar por Proprietário", sorted(insem["proprietario_nome"].unique()))
                with col3:
                    filtro_egua = st.multiselect("Filtrar por Égua", sorted(insem["egua"].unique()))
                
                insem_filtrado = insem.copy()
                if filtro_garanhao:
                    insem_filtrado = insem_filtrado[insem_filtrado["garanhao"].isin(filtro_garanhao)]
                if filtro_prop:
                    insem_filtrado = insem_filtrado[insem_filtrado["proprietario_nome"].isin(filtro_prop)]
                if filtro_egua:
                    insem_filtrado = insem_filtrado[insem_filtrado["egua"].isin(filtro_egua)]
                
                st.metric("Total Registos", len(insem_filtrado))
                
                insem_exibir = insem_filtrado[[
                    "data_inseminacao", "garanhao", "egua", "proprietario_nome", "palhetas_gastas"
                ]].copy().sort_values("data_inseminacao", ascending=False)
                insem_exibir.columns = ["Data", "Garanhão", "Égua", "Proprietário", "Palhetas"]
                st.dataframe(insem_exibir, width="stretch", hide_index=True, height=500)
        
        elif tipo_historico == "🔄 Transferências Internas":
            st.markdown("### 🔄 Todas as Transferências Internas")
            
            transf = carregar_transferencias()
            if transf.empty:
                st.info("ℹ️ Nenhuma transferência registrada")
            else:
                # Exportação
                col1, col2 = st.columns([6, 1])
                with col2:
                    csv_transf = transf[["data_transferencia", "garanhao", "proprietario_origem", "proprietario_destino", "quantidade"]].copy()
                    csv_transf.columns = ["Data", "Garanhão", "De", "Para", "Palhetas"]
                    st.download_button(
                        "📥 Exportar",
                        csv_transf.to_csv(index=False).encode('utf-8'),
                        "transferencias_internas.csv",
                        "text/csv"
                    )
                
                # Filtros
                col1, col2 = st.columns(2)
                with col1:
                    filtro_garanhao = st.multiselect("Filtrar por Garanhão", sorted(transf["garanhao"].unique()), key="transf_gar")
                with col2:
                    filtro_prop = st.multiselect("Filtrar por Proprietário", sorted(set(transf["proprietario_origem"].tolist() + transf["proprietario_destino"].tolist())), key="transf_prop")
                
                transf_filtrado = transf.copy()
                if filtro_garanhao:
                    transf_filtrado = transf_filtrado[transf_filtrado["garanhao"].isin(filtro_garanhao)]
                if filtro_prop:
                    transf_filtrado = transf_filtrado[
                        (transf_filtrado["proprietario_origem"].isin(filtro_prop)) |
                        (transf_filtrado["proprietario_destino"].isin(filtro_prop))
                    ]
                
                st.metric("Total Registos", len(transf_filtrado))
                
                transf_exibir = transf_filtrado[[
                    "data_transferencia", "garanhao", "proprietario_origem", "proprietario_destino", "quantidade"
                ]].copy().sort_values("data_transferencia", ascending=False)
                transf_exibir.columns = ["Data", "Garanhão", "De", "Para", "Palhetas"]
                st.dataframe(transf_exibir, width="stretch", hide_index=True, height=500)
        
        elif tipo_historico == "📤 Transferências Externas":
            st.markdown("### 📤 Todas as Vendas/Envios Externos")
            
            transf_ext = carregar_transferencias_externas()
            if transf_ext.empty:
                st.info("ℹ️ Nenhuma transferência externa registrada")
            else:
                st.dataframe(transf_ext, width="stretch", hide_index=True, height=500)
        
        elif tipo_historico == "📦 Stock Completo":
            st.markdown("### 📦 Todo o Stock do Sistema")
            
            if stock.empty:
                st.info("ℹ️ Nenhum stock registrado")
            else:
                # Exportação
                col1, col2 = st.columns([6, 1])
                with col2:
                    csv_stock = stock[["proprietario_nome", "garanhao", "existencia_atual", "qualidade", "local_armazenagem"]].copy()
                    st.download_button(
                        "📥 Exportar",
                        csv_stock.to_csv(index=False).encode('utf-8'),
                        "stock_completo.csv",
                        "text/csv"
                    )
                
                # Filtros
                col1, col2 = st.columns(2)
                with col1:
                    filtro_prop = st.multiselect("Filtrar por Proprietário", sorted(stock["proprietario_nome"].unique()), key="stock_prop")
                with col2:
                    filtro_gar = st.multiselect("Filtrar por Garanhão", sorted(stock["garanhao"].unique()), key="stock_gar")
                
                stock_filtrado = stock.copy()
                if filtro_prop:
                    stock_filtrado = stock_filtrado[stock_filtrado["proprietario_nome"].isin(filtro_prop)]
                if filtro_gar:
                    stock_filtrado = stock_filtrado[stock_filtrado["garanhao"].isin(filtro_gar)]
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Lotes", len(stock_filtrado))
                with col2:
                    st.metric("Total Palhetas", int(to_py(stock_filtrado["existencia_atual"].sum()) or 0))
                
                stock_exibir = stock_filtrado[[
                    "proprietario_nome", "garanhao", "data_embriovet", "existencia_atual",
                    "qualidade", "concentracao", "motilidade", "local_armazenagem"
                ]].copy()
                stock_exibir.columns = [
                    "Proprietário", "Garanhão", "Data", "Stock", "Qualidade (%)",
                    "Concentração", "Motilidade (%)", "Local"
                ]
                st.dataframe(stock_exibir, width="stretch", hide_index=True, height=500)

# ------------------------------------------------------------
# 👥 Gestão de Proprietários
# ------------------------------------------------------------
            # Botão de exportação no topo
            col_export1, col_export2 = st.columns([6, 1])
            with col_export2:
                # Preparar dados para exportação
                insem_export = insem[["data_inseminacao", "garanhao", "egua", "proprietario_nome", "palhetas_gastas"]].copy()
                insem_export.columns = ["Data", "Garanhão", "Égua", "Proprietário", "Palhetas"]
                
                csv_insem = insem_export.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Exportar CSV",
                    data=csv_insem,
                    file_name="inseminacoes.csv",
                    mime="text/csv",
                    width="stretch"
                )
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total de Inseminações", len(insem))
            with col2:
                st.metric("Total de Palhetas Gastas", int(to_py(insem["palhetas_gastas"].sum()) or 0))
            with col3:
                st.metric("Garanhões Utilizados", insem["garanhao"].nunique())
            with col4:
                st.metric("Proprietários Envolvidos", insem["proprietario_nome"].nunique())

            st.markdown("---")

            st.markdown("### 📊 Consumo por Garanhão e Proprietário")
            consumo = insem.groupby(["garanhao", "proprietario_nome"])["palhetas_gastas"].sum().reset_index()
            consumo.columns = ["Garanhão", "Proprietário", "Palhetas Gastas"]
            consumo = consumo.sort_values("Palhetas Gastas", ascending=False)
            st.dataframe(consumo, width="stretch", hide_index=True)

            st.markdown("---")

            st.markdown("### 🔍 Filtrar Histórico")
            col1, col2 = st.columns(2)
            with col1:
                filtro_garanhao = st.multiselect(
                    "Filtrar por Garanhão",
                    options=sorted(insem["garanhao"].unique()),
                    default=None,
                    help="Deixe vazio para ver todos",
                )
            with col2:
                filtro_proprietario = st.multiselect(
                    "Filtrar por Proprietário",
                    options=sorted(insem["proprietario_nome"].unique()),
                    default=None,
                    help="Deixe vazio para ver todos",
                )

            insem_filtrado = insem.copy()
            if filtro_garanhao:
                insem_filtrado = insem_filtrado[insem_filtrado["garanhao"].isin(filtro_garanhao)]
            if filtro_proprietario:
                insem_filtrado = insem_filtrado[insem_filtrado["proprietario_nome"].isin(filtro_proprietario)]

            if len(insem_filtrado) > 0:
                st.markdown(f"**📋 Mostrando {len(insem_filtrado)} registos**")

            st.dataframe(
                insem_filtrado[
                    ["garanhao", "proprietario_nome", "data_inseminacao", "egua", "protocolo", "palhetas_gastas"]
                ]
                .rename(
                    columns={
                        "garanhao": "Garanhão",
                        "proprietario_nome": "Proprietário do Sémen",
                        "data_inseminacao": "Data",
                        "egua": "Égua",
                        "protocolo": "Protocolo",
                        "palhetas_gastas": "Palhetas",
                    }
                )
                .sort_values("Data", ascending=False),
                width="stretch",
                hide_index=True,
            )

            st.markdown("---")
            st.markdown("### 🔎 Pesquisa Rápida")
            pesquisa = st.text_input("Digite o nome do garanhão ou proprietario:", placeholder="Ex: Retoque")

            if pesquisa:
                resultado = insem_filtrado[
                    insem_filtrado["garanhao"].str.contains(pesquisa, case=False, na=False)
                    | insem_filtrado["proprietario_nome"].str.contains(pesquisa, case=False, na=False)
                ]

                if len(resultado) > 0:
                    st.success(f"✅ Encontrados {len(resultado)} registos")
                    st.dataframe(
                        resultado[["garanhao", "proprietario_nome", "data_inseminacao", "egua", "palhetas_gastas"]].rename(
                            columns={
                                "garanhao": "Garanhão",
                                "proprietario_nome": "Proprietário",
                                "data_inseminacao": "Data",
                                "egua": "Égua",
                                "palhetas_gastas": "Palhetas",
                            }
                        ),
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.warning(f"❌ Nenhum resultado para '{pesquisa}'")
    
    # TAB 2: Relatório de Transferências Internas
    with rel_tab2:
        st.markdown("### 🔄 Histórico de Transferências Internas")
        st.info("Transferências entre proprietários do sistema")
        
        transf = carregar_transferencias()
        
        if transf.empty:
            st.info("ℹ️ Nenhuma transferência interna registrada ainda.")
        else:
            # Botão de exportação
            col_export1, col_export2 = st.columns([6, 1])
            with col_export2:
                transf_export = transf[["garanhao", "proprietario_origem", "proprietario_destino", "quantidade", "data_transferencia"]].copy()
                transf_export.columns = ["Garanhão", "De", "Para", "Palhetas", "Data"]
                csv_transf = transf_export.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Exportar CSV",
                    data=csv_transf,
                    file_name="transferencias_internas.csv",
                    mime="text/csv",
                    width="stretch"
                )
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total de Transferências", len(transf))
            with col2:
                st.metric("Total de Palhetas Transferidas", int(to_py(transf["quantidade"].sum()) or 0))
            
            st.markdown("---")
            
            st.dataframe(
                transf[[
                    "garanhao", "proprietario_origem", "proprietario_destino", 
                    "quantidade", "data_transferencia"
                ]].rename(columns={
                    "garanhao": "Garanhão",
                    "proprietario_origem": "De",
                    "proprietario_destino": "Para",
                    "quantidade": "Palhetas",
                    "data_transferencia": "Data"
                }),
                width="stretch",
                hide_index=True
            )
    
    # TAB 3: Relatório de Transferências Externas (Vendas/Envios)
    with rel_tab3:
        st.markdown("### 📤 Histórico de Vendas e Envios Externos")
        st.warning("Saídas de sêmen para fora do sistema")
        
        transf_ext = carregar_transferencias_externas()
        
        if transf_ext.empty:
            st.info("ℹ️ Nenhuma venda ou envio externo registrado ainda.")
        else:
            # Botão de exportação
            col_export1, col_export2 = st.columns([6, 1])
            with col_export2:
                colunas_export = ["garanhao", "proprietario_origem", "destinatario_externo", "tipo", "quantidade", "data_transferencia"]
                if "observacoes" in transf_ext.columns:
                    colunas_export.append("observacoes")
                transf_ext_export = transf_ext[colunas_export].copy()
                transf_ext_export.columns = ["Garanhão", "Proprietário", "Destinatário", "Tipo", "Palhetas", "Data"] + (["Observações"] if "observacoes" in transf_ext.columns else [])
                csv_ext = transf_ext_export.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Exportar CSV",
                    data=csv_ext,
                    file_name="transferencias_externas.csv",
                    mime="text/csv",
                    width="stretch"
                )
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total de Saídas", len(transf_ext))
            with col2:
                st.metric("Total de Palhetas Vendidas/Enviadas", int(to_py(transf_ext["quantidade"].sum()) or 0))
            with col3:
                vendas = len(transf_ext[transf_ext["tipo"] == "Venda"]) if "tipo" in transf_ext.columns else 0
                st.metric("Vendas", vendas)
            
            st.markdown("---")
            
            # Filtros
            col1, col2 = st.columns(2)
            with col1:
                filtro_tipo = st.multiselect(
                    "Filtrar por Tipo",
                    options=sorted(transf_ext["tipo"].unique()) if "tipo" in transf_ext.columns else [],
                    default=None
                )
            with col2:
                filtro_garanhao_ext = st.multiselect(
                    "Filtrar por Garanhão",
                    options=sorted(transf_ext["garanhao"].unique()),
                    default=None
                )
            
            transf_ext_filtrado = transf_ext.copy()
            if filtro_tipo:
                transf_ext_filtrado = transf_ext_filtrado[transf_ext_filtrado["tipo"].isin(filtro_tipo)]
            if filtro_garanhao_ext:
                transf_ext_filtrado = transf_ext_filtrado[transf_ext_filtrado["garanhao"].isin(filtro_garanhao_ext)]
            
            if len(transf_ext_filtrado) > 0:
                st.markdown(f"**📋 Mostrando {len(transf_ext_filtrado)} registos**")
            
            # Tabela principal
            colunas_mostrar = ["garanhao", "proprietario_origem", "destinatario_externo", "tipo", "quantidade", "data_transferencia"]
            if "observacoes" in transf_ext_filtrado.columns:
                colunas_mostrar.append("observacoes")
            
            st.dataframe(
                transf_ext_filtrado[colunas_mostrar].rename(columns={
                    "garanhao": "Garanhão",
                    "proprietario_origem": "Proprietário",
                    "destinatario_externo": "Destinatário",
                    "tipo": "Tipo",
                    "quantidade": "Palhetas",
                    "data_transferencia": "Data",
                    "observacoes": "Observações"
                }),
                width="stretch",
                hide_index=True
            )
            
            # Expandir detalhes
            with st.expander("📊 Ver Detalhes por Destinatário"):
                resumo_dest = transf_ext_filtrado.groupby("destinatario_externo").agg({
                    "quantidade": "sum",
                    "id": "count"
                }).reset_index()
                resumo_dest.columns = ["Destinatário", "Total Palhetas", "Nº Operações"]
                resumo_dest = resumo_dest.sort_values("Total Palhetas", ascending=False)
                st.dataframe(resumo_dest, width="stretch", hide_index=True)

# ------------------------------------------------------------
# 👥 Gestão de Proprietários
# ------------------------------------------------------------
elif aba == "👥 Gestão de Proprietários":
    st.header("👥 Gestão de Proprietários")
    
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
                st.success("✅ Coluna 'ativo' criada automaticamente!")
            cur.close()
    except Exception as e:
        st.error(f"❌ Erro ao verificar/criar coluna ativo: {e}")
    
    # TODO: Implementar desativação automática nas transações de stock
    # atualizar_status_proprietarios()
    
    # Limpar cache se houver mudança de status
    if 'status_changed' in st.session_state:
        del st.session_state['status_changed']
        st.cache_data.clear()
    
    # Recarregar proprietários (todos, não apenas ativos) - sempre fresh
    proprietarios_todos = carregar_proprietarios(apenas_ativos=False)
    
    tab1, tab2 = st.tabs(["📋 Lista", "➕ Adicionar"])
    
    # TAB 1: Lista
    with tab1:
        if proprietarios_todos.empty:
            st.info("ℹ️ Nenhum proprietário cadastrado.")
        else:
            # Filtro e Ordenação
            col_f1, col_f2 = st.columns(2)
            
            with col_f1:
                filtro_status = st.radio("Filtrar:", ["Todos", "Ativos", "Inativos"], horizontal=True)
            
            with col_f2:
                ordenar_por = st.selectbox("Ordenar por:", ["Nome", "ID", "Status"])
            
            # Aplicar filtro
            if filtro_status == "Ativos":
                props_exibir = proprietarios_todos[proprietarios_todos['ativo'] == True].copy()
            elif filtro_status == "Inativos":
                props_exibir = proprietarios_todos[proprietarios_todos['ativo'] == False].copy()
            else:
                props_exibir = proprietarios_todos.copy()
            
            # Aplicar ordenação
            if ordenar_por == "Nome":
                props_exibir = props_exibir.sort_values('nome')
            elif ordenar_por == "ID":
                props_exibir = props_exibir.sort_values('id')
            elif ordenar_por == "Status":
                props_exibir = props_exibir.sort_values('ativo', ascending=False)
            
            st.markdown(f"**{len(props_exibir)} proprietários**")
            st.markdown("---")
            
            # Lista de proprietários (estilo lotes)
            for _, prop in props_exibir.iterrows():
                # Status
                status_icon = "🟢" if prop.get('ativo', True) else "🔴"
                status_text = "ATIVO" if prop.get('ativo', True) else "INATIVO"
                
                # Título do expander com ID | Nome | Status
                titulo = f"**{prop['id']}** | {prop['nome']} | {status_icon} {status_text}"
                
                # Verificar se este expander deve estar expandido
                expandido = st.session_state.get(f'expand_{prop["id"]}', False)
                
                # Expander
                with st.expander(titulo, expanded=expandido):
                    
                    # Tabs: Detalhes e Editar
                    tab_det, tab_edit = st.tabs(["📋 Detalhes", "✏️ Editar"])
                    
                    # TAB: Detalhes
                    with tab_det:
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown(f"**🆔 ID:** {prop['id']}")
                            st.markdown(f"**👤 Nome:** {prop['nome']}")
                            st.markdown(f"**📧 Email:** {prop.get('email') or 'N/A'}")
                            st.markdown(f"**📱 Telemóvel:** {prop.get('telemovel') or 'N/A'}")
                        
                        with col2:
                            st.markdown(f"**📄 Nome Completo:** {prop.get('nome_completo') or 'N/A'}")
                            st.markdown(f"**🔢 NIF:** {prop.get('nif') or 'N/A'}")
                            st.markdown(f"**📍 Morada:** {prop.get('morada') or 'N/A'}")
                            st.markdown(f"**📮 CP:** {prop.get('codigo_postal') or 'N/A'}")
                            st.markdown(f"**🏙️ Cidade:** {prop.get('cidade') or 'N/A'}")
                        
                        st.markdown("---")
                        
                        # Botões de ação
                        col_a1, col_a2 = st.columns(2)
                        
                        with col_a1:
                            # Botão de alternar status
                            status_atual = prop.get('ativo', True)
                            btn_label = "🔴 Desativar" if status_atual else "🟢 Ativar"
                            btn_type = "secondary" if status_atual else "primary"
                            
                            if st.button(btn_label, key=f"status_{prop['id']}", use_container_width=True, type=btn_type):
                                # Marcar para manter expandido
                                st.session_state[f'expand_{prop["id"]}'] = True
                                st.session_state['status_changed'] = True
                                # Alternar status
                                resultado = alternar_status_proprietario(prop['id'])
                                if resultado is not None:
                                    novo_status = "ATIVO" if resultado else "INATIVO"
                                    st.success(f"✅ Status alterado para {novo_status}!")
                                    # Forçar rerun imediato
                                    time.sleep(0.3)
                                    st.rerun()
                                else:
                                    st.error("❌ Erro ao alterar status. Verifique se a coluna 'ativo' existe.")
                        
                        with col_a2:
                            if st.button("🗑️ Apagar", key=f"del_{prop['id']}", use_container_width=True, type="secondary"):
                                if deletar_proprietario(prop['id']):
                                    if f'expand_{prop["id"]}' in st.session_state:
                                        del st.session_state[f'expand_{prop["id"]}']
                                    st.success("✅ Apagado!")
                                    st.rerun()
                    
                    # TAB: Editar
                    with tab_edit:
                        st.markdown("### ✏️ Editar Proprietário")
                        
                        with st.form(key=f"form_edit_{prop['id']}"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                nome_e = st.text_input("Nome *", value=prop.get('nome', ''))
                                email_e = st.text_input("Email", value=prop.get('email', '') or '')
                                tel_e = st.text_input("Telemóvel", value=prop.get('telemovel', '') or '')
                                nc_e = st.text_input("Nome Completo", value=prop.get('nome_completo', '') or '')
                            
                            with col2:
                                nif_e = st.text_input("NIF", value=prop.get('nif', '') or '')
                                morada_e = st.text_area("Morada", value=prop.get('morada', '') or '', height=100)
                                cp_e = st.text_input("Código Postal", value=prop.get('codigo_postal', '') or '')
                                cidade_e = st.text_input("Cidade", value=prop.get('cidade', '') or '')
                            
                            salvar = st.form_submit_button("💾 Guardar Alterações", type="primary", use_container_width=True)
                            
                            if salvar:
                                if not nome_e:
                                    st.error("❌ Nome é obrigatório")
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
                                        st.success("✅ Atualizado!")
                                        st.rerun()
    
    # TAB 2: Adicionar
    with tab2:
        st.markdown("### ➕ Novo Proprietário")
        
        with st.form("form_adicionar"):
            col1, col2 = st.columns(2)
            
            with col1:
                nome_n = st.text_input("Nome *")
                email_n = st.text_input("Email")
                tel_n = st.text_input("Telemóvel")
                nc_n = st.text_input("Nome Completo")
            
            with col2:
                nif_n = st.text_input("NIF")
                morada_n = st.text_area("Morada", height=100)
                cp_n = st.text_input("Código Postal")
                cidade_n = st.text_input("Cidade")
            
            adicionar = st.form_submit_button("➕ Adicionar", type="primary", use_container_width=True)
            
            if adicionar:
                if not nome_n:
                    st.error("❌ Nome é obrigatório")
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
                        st.success(f"✅ '{nome_n}' adicionado!")
                        st.rerun()

# ------------------------------------------------------------
# ⚙️ Gestão de Utilizadores (Apenas Administrador)
# ------------------------------------------------------------
elif aba == "⚙️ Gestão de Utilizadores":
    st.header("⚙️ Gestão de Utilizadores")
    
    usuarios_df = carregar_usuarios()
    
    tab1, tab2, tab3 = st.tabs(["📋 Lista de Utilizadores", "➕ Adicionar Utilizador", "🔒 Alterar Password"])
    
    # TAB 1: Lista
    with tab1:
        if usuarios_df.empty:
            st.info("ℹ️ Nenhum utilizador cadastrado.")
        else:
            st.markdown(f"### 📋 Total: {len(usuarios_df)} utilizadores")
            
            # Filtros
            col1, col2 = st.columns(2)
            with col1:
                filtro_nivel = st.multiselect(
                    "Filtrar por Nível",
                    options=usuarios_df["nivel"].unique(),
                    default=None
                )
            with col2:
                filtro_status = st.selectbox(
                    "Status",
                    ["Todos", "Ativos", "Inativos"]
                )
            
            usuarios_filtrado = usuarios_df.copy()
            if filtro_nivel:
                usuarios_filtrado = usuarios_filtrado[usuarios_filtrado["nivel"].isin(filtro_nivel)]
            if filtro_status == "Ativos":
                usuarios_filtrado = usuarios_filtrado[usuarios_filtrado["ativo"] == True]
            elif filtro_status == "Inativos":
                usuarios_filtrado = usuarios_filtrado[usuarios_filtrado["ativo"] == False]
            
            st.markdown("---")
            
            for _, usr in usuarios_filtrado.iterrows():
                status_emoji = "✅" if usr['ativo'] else "❌"
                with st.expander(f"{status_emoji} {usr['nome_completo']} (@{usr['username']}) - {usr['nivel']}"):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**ID:** {usr['id']}")
                        st.markdown(f"**Username:** {usr['username']}")
                        st.markdown(f"**Nome:** {usr['nome_completo']}")
                        st.markdown(f"**Nível:** {usr['nivel']}")
                        st.markdown(f"**Status:** {'Ativo' if usr['ativo'] else 'Inativo'}")
                        st.markdown(f"**Criado em:** {usr['created_at']}")
                        if usr['last_login']:
                            st.markdown(f"**Último login:** {usr['last_login']}")
                    
                    with col2:
                        if usr['ativo']:
                            if st.button("🚫 Desativar", key=f"deactivate_{usr['id']}", type="secondary"):
                                if desativar_usuario(usr['id']):
                                    st.success("✅ Utilizador desativado!")
                                    st.rerun()
                        else:
                            if st.button("✅ Ativar", key=f"activate_{usr['id']}", type="primary"):
                                if ativar_usuario(usr['id']):
                                    st.success("✅ Utilizador ativado!")
                                    st.rerun()
    
    # TAB 2: Adicionar
    with tab2:
        st.markdown("### ➕ Adicionar Novo Utilizador")
        
        with st.form("add_usuario"):
            novo_username = st.text_input("Username *", placeholder="sem espaços, minúsculas")
            novo_nome = st.text_input("Nome Completo *")
            novo_nivel = st.selectbox("Nível de Acesso *", ["Administrador", "Gestor", "Visualizador"])
            nova_password = st.text_input("Password *", type="password", placeholder="Mínimo 6 caracteres")
            confirma_password = st.text_input("Confirmar Password *", type="password")
            
            submit = st.form_submit_button("➕ Criar Utilizador", type="primary")
            
            if submit:
                if not novo_username or not novo_nome or not nova_password:
                    st.error("❌ Preencha todos os campos obrigatórios")
                elif len(nova_password) < 6:
                    st.error("❌ Password deve ter pelo menos 6 caracteres")
                elif nova_password != confirma_password:
                    st.error("❌ Passwords não coincidem")
                elif " " in novo_username:
                    st.error("❌ Username não pode conter espaços")
                else:
                    if adicionar_usuario(novo_username, novo_nome, nova_password, novo_nivel, user['id']):
                        st.success(f"✅ Utilizador '{novo_username}' criado com sucesso!")
                        st.info(f"🔐 **Credenciais:**\n\n👤 Username: `{novo_username}`\n\n🔒 Password: `{nova_password}`")
                        # Redirecionar para a lista de utilizadores
                        st.session_state['show_user_tab'] = 0  # Tab lista
                        st.rerun()
        
        st.markdown("---")
        st.info("""
        ### 📋 Níveis de Acesso
        
        **🔴 Administrador:**
        - Acesso total ao sistema
        - Pode adicionar/editar/deletar stock
        - Pode gerir proprietários
        - Pode gerir utilizadores
        - Pode adicionar outros administradores
        
        **🟡 Gestor/Veterinário:**
        - Pode adicionar stock
        - Pode registrar inseminações
        - Pode transferir sêmen (interna e externa)
        - NÃO pode editar ou deletar
        - NÃO pode gerir utilizadores
        
        **🟢 Visualizador:**
        - Pode ver stock
        - Pode ver relatórios
        - NÃO pode adicionar/editar nada
        """)
    
    # TAB 3: Alterar Password
    with tab3:
        st.markdown("### 🔒 Alterar Password de Utilizador")
        
        if not usuarios_df.empty:
            with st.form("change_password"):
                usuario_selecionado = st.selectbox(
                    "Selecionar Utilizador",
                    options=usuarios_df["id"].tolist(),
                    format_func=lambda x: f"{usuarios_df[usuarios_df['id']==x]['nome_completo'].values[0]} (@{usuarios_df[usuarios_df['id']==x]['username'].values[0]})"
                )
                
                nova_senha = st.text_input("Nova Password *", type="password", placeholder="Mínimo 6 caracteres")
                confirma_senha = st.text_input("Confirmar Nova Password *", type="password")
                
                submit_senha = st.form_submit_button("🔄 Alterar Password", type="primary")
                
                if submit_senha:
                    if not nova_senha:
                        st.error("❌ Digite a nova password")
                    elif len(nova_senha) < 6:
                        st.error("❌ Password deve ter pelo menos 6 caracteres")
                    elif nova_senha != confirma_senha:
                        st.error("❌ Passwords não coincidem")
                    else:
                        if alterar_password(usuario_selecionado, nova_senha):
                            usr_nome = usuarios_df[usuarios_df['id']==usuario_selecionado]['nome_completo'].values[0]
                            st.success(f"✅ Password alterada para {usr_nome}!")
                            st.info(f"🔐 Nova password: `{nova_senha}`")

# ------------------------------------------------------------
# Footer
# ------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.markdown("**Embriovet Gestor v3.0**")
st.sidebar.markdown("✅ Sistema com Autenticação")
