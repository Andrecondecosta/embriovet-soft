"""Repository de Contentores (mapa) — extração pura de `app.py` (Pedido 9).

7 funções copiadas bit-for-bit. Zero alteração de lógica.
"""

from __future__ import annotations

import logging

import streamlit as st

from modules.db import get_connection, invalidate_data_cache, to_py

logger = logging.getLogger(__name__)


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
            invalidate_data_cache()
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
            invalidate_data_cache()
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
            invalidate_data_cache()
            logger.info(f"Posição do contentor atualizada: ID {contentor_id} -> X={x}, Y={y}")
            return True
    except Exception as e:
        logger.error(f"Erro ao atualizar posição do contentor: {e}")
        st.error(f"Erro ao guardar posição do contentor: {e}")
        return False

def atualizar_andar_lote(estoque_id: int, novo_andar: int, novo_canister: int = None) -> bool:
    """Atualiza o andar (e opcionalmente o canister) de um lote de sémen"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            if novo_canister is not None:
                cur.execute("UPDATE estoque_dono SET andar = %s, canister = %s WHERE id = %s", (novo_andar, novo_canister, estoque_id))
            else:
                cur.execute("UPDATE estoque_dono SET andar = %s WHERE id = %s", (novo_andar, estoque_id))
            conn.commit()
            cur.close()
        invalidate_data_cache()
        return True
    except Exception as e:
        logger.error(f"Erro ao atualizar posição de lote: {e}")
        return False


def mover_lotes_por_andar(contentor_id: int, andar_origem: int, andar_destino: int, canister: int = None) -> int:
    """Move todos os lotes de um andar para outro dentro do mesmo contentor. Retorna nº de lotes movidos."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            if canister is not None:
                cur.execute(
                    "UPDATE estoque_dono SET andar = %s WHERE contentor_id = %s AND andar = %s AND canister = %s",
                    (andar_destino, contentor_id, andar_origem, canister)
                )
            else:
                cur.execute(
                    "UPDATE estoque_dono SET andar = %s WHERE contentor_id = %s AND andar = %s",
                    (andar_destino, contentor_id, andar_origem)
                )
            count = cur.rowcount
            conn.commit()
            cur.close()
        invalidate_data_cache()
        return count
    except Exception as e:
        logger.error(f"Erro ao mover lotes por andar: {e}")
        return 0


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
            invalidate_data_cache()
            logger.info(f"Contentor deletado: ID {contentor_id}")
            return True
            
    except Exception as e:
        logger.error(f"Erro ao deletar contentor: {e}")
        st.error(f"Erro ao deletar contentor: {e}")
        return False
