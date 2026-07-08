"""Repository de stock — funções de dados extraídas de `app.py`.

Contém:
- Leituras com `@st.cache_data`: `carregar_proprietarios`, `carregar_stock`,
  `carregar_transferencias`, `carregar_transferencias_externas`,
  `carregar_contentores`.
- Leituras sem cache: `carregar_inseminacoes`, `obter_stock_contentor`.
- Escritas de stock: `inserir_stock`, `editar_stock`, `deletar_stock`.
- 3 funções de transferência: `transferir_palhetas_parcial` (alias
  `transferir_stock_interno`), `transferir_stock_interno_com_localizacao`,
  `transferir_palhetas_externo` (alias `transferir_stock_externo`).

**Extração pura** — a lógica é bit-for-bit igual à antiga versão em
`app.py`. A única diferença é a resolução de nomes: `logger`, `to_py`,
`invalidate_data_cache`, `t` e `get_or_create_garanhao` passam a ser
importados no topo deste módulo. `atualizar_status_proprietarios`
mantém-se em `app.py` (ainda é usada por outros fluxos) e é resolvida
por lazy import onde necessário para evitar ciclos.
"""

from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

from modules.db import get_connection, invalidate_data_cache, to_py
from modules.i18n import t
from modules.repositories.animal_repo import get_or_create_garanhao

logger = logging.getLogger(__name__)


# ============================================================
# Leituras
# ============================================================

@st.cache_data(ttl=60)
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


@st.cache_data(ttl=60)
def carregar_stock(apenas_ativos=True):
    """Carrega stock completo com informações de proprietario, contentor
    e nome canónico do garanhão (via FK `animal_id` → `animais.nome`).

    Adiciona a coluna `garanhao_nome` — usada pela UI em vez de `garanhao`
    (texto legado). `COALESCE(a.nome, e.garanhao)` mantém retro-compat
    para lotes cujo `animal_id` ainda não foi sincronizado.
    """
    try:
        with get_connection() as conn:
            query = """
                SELECT e.*,
                       d.nome as proprietario_nome,
                       c.codigo as contentor_codigo,
                       COALESCE(a.nome, e.garanhao) as garanhao_nome
                FROM estoque_dono e
                LEFT JOIN dono d ON e.dono_id = d.id
                LEFT JOIN contentores c ON e.contentor_id = c.id
                LEFT JOIN animais a ON a.id = e.animal_id
                WHERE e.existencia_atual > 0
            """
            if apenas_ativos:
                query += " AND d.ativo = TRUE"
            query += " ORDER BY garanhao_nome, e.id"
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


@st.cache_data(ttl=60)
def carregar_transferencias():
    """Carrega histórico de transferências (com nome canónico do garanhão via FK)."""
    try:
        with get_connection() as conn:
            query = """
                SELECT t.*,
                       COALESCE(a.nome, e.garanhao) as garanhao,
                       d1.nome as proprietario_origem,
                       d2.nome as proprietario_destino
                FROM transferencias t
                LEFT JOIN estoque_dono e ON t.estoque_id = e.id
                LEFT JOIN animais a ON a.id = e.animal_id
                LEFT JOIN dono d1 ON t.proprietario_origem_id = d1.id
                LEFT JOIN dono d2 ON t.proprietario_destino_id = d2.id
                ORDER BY t.data_transferencia DESC
            """
            df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar transferências: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def carregar_transferencias_externas():
    """Carrega histórico de transferências externas (vendas/envios) com
    o nome canónico do garanhão via FK.
    """
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
            
            # Verifica se `garanhao` já existe (colunas variam entre schemas
            # legados); em qualquer caso preferimos o nome canónico via FK.
            cur = conn.cursor()
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'transferencias_externas'"
            )
            cols = {r[0] for r in cur.fetchall()}
            cur.close()

            estoque_join = ""
            garanhao_expr = "NULL"
            if "estoque_id" in cols:
                estoque_join = (
                    "LEFT JOIN estoque_dono e ON te.estoque_id = e.id "
                    "LEFT JOIN animais a ON a.id = e.animal_id "
                )
                garanhao_expr = "COALESCE(a.nome, e.garanhao)"
            elif "garanhao" in cols:
                garanhao_expr = "te.garanhao"

            # Se `garanhao` já vem por `te.*`, evitamos duplicar a coluna
            # com o mesmo nome (senão o pandas rebenta com
            # `cannot reindex on axis with duplicate labels`).
            if "garanhao" in cols:
                te_columns = ", ".join(
                    f"te.{c}" for c in cols if c != "garanhao"
                )
                te_select = f"{te_columns}, {garanhao_expr} AS garanhao"
            else:
                te_select = f"te.*, {garanhao_expr} AS garanhao"

            query = f"""
                SELECT {te_select},
                       d.nome as proprietario_origem
                FROM transferencias_externas te
                {estoque_join}
                LEFT JOIN dono d ON te.proprietario_origem_id = d.id
                ORDER BY te.data_transferencia DESC
            """
            df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar transferências externas: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
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


def obter_stock_contentor(contentor_id):
    """Obtém informações de stock de um contentor específico
    (nome do garanhão via FK `animais`, fallback ao texto legado)."""
    try:
        with get_connection() as conn:
            query = """
                SELECT 
                    e.id,
                    COALESCE(a.nome, e.garanhao) AS garanhao,
                    d.nome as proprietario_nome,
                    e.canister,
                    e.andar,
                    e.existencia_atual,
                    e.qualidade,
                    e.data_embriovet,
                    e.origem_externa
                FROM estoque_dono e
                LEFT JOIN dono d ON e.dono_id = d.id
                LEFT JOIN animais a ON a.id = e.animal_id
                WHERE e.contentor_id = %s AND e.existencia_atual > 0
                ORDER BY e.canister, e.andar, garanhao
            """
            df = pd.read_sql_query(query, conn, params=(contentor_id,))
        return df
    except Exception as e:
        logger.error(f"Erro ao obter stock do contentor: {e}")
        return pd.DataFrame()


# ============================================================
# Escritas de stock
# ============================================================

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
            username = st.session_state.get('user', {}).get('username', 'desconhecido')

            # Resolver animal_id do garanhão (cria em `animais` se necessário)
            animal_id = get_or_create_garanhao(dados.get("Garanhão"))

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
                username,
                animal_id,
            )

            cur.execute(
                """
                INSERT INTO estoque_dono (
                    garanhao, dono_id, data_embriovet, origem_externa,
                    palhetas_produzidas, qualidade, concentracao, motilidade,
                    certificado, dose, observacoes,
                    quantidade_inicial, existencia_atual,
                    contentor_id, canister, andar, cor,
                    criado_por, data_criacao, animal_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
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
            invalidate_data_cache()
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
            invalidate_data_cache()
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
            invalidate_data_cache()
            return True
    except Exception as e:
        logger.error(f"Erro ao deletar stock: {e}")
        st.error(f"Erro ao deletar stock: {e}")
        return False


# ============================================================
# Transferências
# ============================================================

def transferir_palhetas_parcial(stock_origem_id, proprietario_destino_id, quantidade, operation_id=None):
    """Transfere quantidade parcial de palhetas para outro proprietário"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            # Buscar dados do lote origem
            cur.execute("""
                SELECT garanhao, dono_id, existencia_atual, data_embriovet, origem_externa,
                       qualidade, concentracao, motilidade, local_armazenagem, certificado, dose, observacoes, cor,
                       contentor_id, canister, andar, animal_id
                FROM estoque_dono WHERE id = %s
            """, (to_py(stock_origem_id),))
            
            origem = cur.fetchone()
            if not origem:
                st.error(t("error.origin_lot_not_found"))
                return False
            
            (garanhao, prop_origem_id, exist_atual, data_emb, origem_ext, 
             qual, conc, mot, local, cert, dose, obs, cor, contentor_id, canister, andar, animal_id) = origem
            
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
                        contentor_id, canister, andar, animal_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    to_py(garanhao), to_py(proprietario_destino_id), to_py(data_emb), to_py(origem_ext),
                    quantidade_int, to_py(qual), to_py(conc), to_py(mot),
                    to_py(local), to_py(cert), to_py(dose), to_py(obs),
                    quantidade_int, quantidade_int, to_py(cor),
                    to_py(contentor_id), to_py(canister), to_py(andar),
                    to_py(animal_id)
                ))
            
            # Registrar transferência
            cur.execute("""
                INSERT INTO transferencias (
                    estoque_id, proprietario_origem_id, proprietario_destino_id,
                    quantidade, data_transferencia, utilizador, operation_id
                ) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s)
            """, (to_py(stock_origem_id), to_py(prop_origem_id), to_py(proprietario_destino_id), quantidade_int,
                  st.session_state.get('user', {}).get('username', '—'), operation_id))
            
            conn.commit()
            cur.close()
            
            # Verificar e desativar proprietários com stock = 0
            # Lazy import para evitar ciclo com app.py.
            from app import atualizar_status_proprietarios
            atualizar_status_proprietarios()
            invalidate_data_cache()
            
            logger.info(f"Transferência: {quantidade_int} palhetas de {prop_origem_id} para {proprietario_destino_id}")
            return True
            
    except Exception as e:
        logger.error(f"Erro ao transferir palhetas: {e}")
        st.error(f"Erro ao transferir palhetas: {e}")
        return False


# Alias para compatibilidade
transferir_stock_interno = transferir_palhetas_parcial


def transferir_stock_interno_com_localizacao(prop_origem_id, prop_destino_id, stock_origem_id, quantidade,
                                              contentor_id_novo, canister_novo, andar_novo, operation_id=None):
    """Transfere palhetas para outro proprietário e muda a localização"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            
            # Buscar dados do lote origem
            cur.execute("""
                SELECT garanhao, dono_id, existencia_atual, data_embriovet, origem_externa,
                       qualidade, concentracao, motilidade, local_armazenagem, certificado, dose, observacoes, cor,
                       animal_id
                FROM estoque_dono WHERE id = %s
            """, (to_py(stock_origem_id),))
            
            origem = cur.fetchone()
            if not origem:
                st.error(t("error.origin_lot_not_found"))
                return False
            
            (garanhao, prop_origem_db, exist_atual, data_emb, origem_ext, 
             qual, conc, mot, local, cert, dose, obs, cor, animal_id) = origem
            
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
                        contentor_id, canister, andar, animal_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    to_py(garanhao), to_py(prop_destino_id), to_py(data_emb), to_py(origem_ext),
                    quantidade_int, to_py(qual), to_py(conc), to_py(mot),
                    to_py(local), to_py(cert), to_py(dose), to_py(obs),
                    quantidade_int, quantidade_int, to_py(cor),
                    to_py(contentor_id_novo), to_py(canister_novo), to_py(andar_novo),
                    to_py(animal_id)
                ))
            
            # Registrar transferência na tabela de transferências
            cur.execute("""
                INSERT INTO transferencias (
                    estoque_id, proprietario_origem_id, proprietario_destino_id,
                    quantidade, data_transferencia, utilizador, operation_id
                ) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s)
            """, (to_py(stock_origem_id), to_py(prop_origem_db), to_py(prop_destino_id), quantidade_int,
                  st.session_state.get('user', {}).get('username', '—'), operation_id))
            
            conn.commit()
            cur.close()
            
            # Verificar e desativar proprietários com stock = 0
            # Lazy import para evitar ciclo com app.py.
            from app import atualizar_status_proprietarios
            atualizar_status_proprietarios()
            invalidate_data_cache()
            
            logger.info(f"Transferência com mudança de local: {quantidade_int} palhetas de {prop_origem_id} para {prop_destino_id}")
            return True
            
    except Exception as e:
        logger.error(f"Erro ao transferir palhetas com nova localização: {e}")
        st.error(f"Erro ao transferir palhetas: {e}")
        return False


def transferir_palhetas_externo(stock_origem_id, destinatario_externo, quantidade, tipo="Venda", observacoes="", operation_id=None):
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
                    data_transferencia, utilizador, operation_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s)
            """, (
                to_py(stock_origem_id), 
                to_py(prop_origem_id), 
                to_py(garanhao),
                to_py(destinatario_externo), 
                quantidade_int,
                to_py(tipo),
                to_py(observacoes),
                st.session_state.get('user', {}).get('username', '—'),
                operation_id
            ))
            
            conn.commit()
            cur.close()
            
            # Verificar e desativar proprietários com stock = 0
            # Lazy import para evitar ciclo com app.py.
            from app import atualizar_status_proprietarios
            atualizar_status_proprietarios()
            invalidate_data_cache()
            
            logger.info(f"Transferência externa: {quantidade_int} palhetas para {destinatario_externo}")
            return True
            
    except Exception as e:
        logger.error(f"Erro ao transferir para externo: {e}")
        st.error(f"Erro ao transferir para externo: {e}")
        return False


# Alias para compatibilidade
transferir_stock_externo = transferir_palhetas_externo
