"""Repository de Proprietários (donos) — extração pura de `app.py` (Pedido 9).

6 funções copiadas bit-for-bit. Zero alteração de lógica.
"""

from __future__ import annotations

import logging

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
    """Alterna o status ativo/inativo de um proprietário. Devolve o novo
    valor de `ativo`, ou None se o proprietário não existir ou em caso
    de erro."""
    try:
        prop_id_int = int(proprietario_id)
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT ativo FROM dono WHERE id = %s", (prop_id_int,))
            status_antes = cur.fetchone()
            if not status_antes:
                cur.close()
                logger.error(f"Proprietário com ID {prop_id_int} não encontrado")
                return None

            novo_valor = not status_antes[0]
            cur.execute(
                "UPDATE dono SET ativo = %s WHERE id = %s RETURNING ativo",
                (novo_valor, prop_id_int),
            )
            resultado = cur.fetchone()
            conn.commit()
            cur.close()

        if not resultado:
            logger.error(f"UPDATE não retornou resultado para proprietário {prop_id_int}")
            return None

        invalidate_data_cache()
        return resultado[0]
    except Exception as e:
        logger.error(f"Erro ao alternar status do proprietário {proprietario_id}: {e}")
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
