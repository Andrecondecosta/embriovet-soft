"""Repository de Proprietários (donos) — extração pura de `app.py` (Pedido 9).

6 funções copiadas bit-for-bit. Zero alteração de lógica.

Anomalia registada (para relatório final, NÃO corrigida):
- `alternar_status_proprietario` NÃO usa `get_connection()` — abre conexão
  psycopg2 directa com env vars e autocommit=True. Comportamento
  intencional documentado no código original (força commit imediato).
  Ficaria mais coerente migrar para `get_connection()` num refactor
  posterior de "design"; aqui só copiamos.
"""

from __future__ import annotations

import logging
import os
import traceback

import psycopg2
import streamlit as st

from modules.db import get_connection, invalidate_data_cache, to_py

logger = logging.getLogger(__name__)


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
            invalidate_data_cache()
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
            invalidate_data_cache()
            
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
            invalidate_data_cache()
            logger.info(f"Proprietário editado: ID {proprietario_id}")
            return True
    except Exception as e:
        logger.error(f"Erro ao editar proprietário: {e}")
        return False


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
            invalidate_data_cache()
            logger.info(f"Proprietário atualizado: stock_id={stock_id}, novo_dono_id={novo_dono_id}")
            return True
    except Exception as e:
        logger.error(f"Erro ao atualizar proprietario: {e}")
        st.error(f"Erro ao atualizar proprietario: {e}")
        return False


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
            invalidate_data_cache()
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
            invalidate_data_cache()
            logger.info(f"Proprietário deletado: ID {proprietario_id}")
            return True

    except Exception as e:
        logger.error(f"Erro ao deletar proprietário: {e}")
        st.error(f"Erro ao deletar proprietário: {e}")
        return False
