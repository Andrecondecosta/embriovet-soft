import streamlit as st
import pandas as pd
import psycopg2
from psycopg2 import pool
import os
from dotenv import load_dotenv
from contextlib import contextmanager
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()

# Pool de conexões
try:
    connection_pool = psycopg2.pool.SimpleConnectionPool(
        1, 10,
        dbname=os.getenv('DB_NAME', 'embriovet'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '123'),
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432')
    )
    if connection_pool:
        logger.info("✅ Pool de conexões PostgreSQL criado com sucesso")
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

# 📥 Funções de carregamento de dados

def carregar_proprietarios():
    """Carrega lista de proprietarios do banco de dados"""
    try:
        with get_connection() as conn:
            df = pd.read_sql("SELECT * FROM dono ORDER BY nome", conn)
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar proprietarios: {e}")
        st.error(f"Erro ao carregar proprietarios: {e}")
        return pd.DataFrame()

def carregar_estoque():
    """Carrega estoque completo com informações de proprietario"""
    try:
        with get_connection() as conn:
            query = """
                SELECT e.*, d.nome as proprietario_nome 
                FROM estoque_dono e
                LEFT JOIN proprietario d ON e.dono_id = d.id
                ORDER BY e.garanhao, e.id
            """
            df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar estoque: {e}")
        st.error(f"Erro ao carregar estoque: {e}")
        return pd.DataFrame()

def carregar_inseminacoes():
    """Carrega histórico de inseminações"""
    try:
        with get_connection() as conn:
            query = """
                SELECT i.*, d.nome as proprietario_nome
                FROM inseminacoes i
                LEFT JOIN proprietario d ON i.dono_id = d.id
                ORDER BY i.data_inseminacao DESC
            """
            df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar inseminações: {e}")
        st.error(f"Erro ao carregar inseminações: {e}")
        return pd.DataFrame()

def atualizar_proprietario_stock(estoque_id, novo_dono_id):
    """Atualiza o proprietario de um item de estoque"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE estoque_dono SET dono_id = %s WHERE id = %s",
                (novo_dono_id, estoque_id)
            )
            conn.commit()
            cur.close()
            logger.info(f"Proprietário atualizado: estoque_id={estoque_id}, novo_dono_id={novo_dono_id}")
            return True
    except Exception as e:
        logger.error(f"Erro ao atualizar proprietario: {e}")
        st.error(f"Erro ao atualizar proprietario: {e}")
        return False

# 💾 Funções de inserção

def inserir_stock(dados):
    """Insere novo stock no banco de dados"""
    try:
        # Validações
        if not dados.get("Garanhão"):
            st.error("❌ Nome do garanhão é obrigatório")
            return False
        
        if dados.get("Palhetas", 0) < 0:
            st.error("❌ Número de palhetas não pode ser negativo")
            return False
        
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO estoque_dono (
                    garanhao, dono_id, data_embriovet, origem_externa,
                    palhetas_produzidas, qualidade, concentracao, motilidade,
                    local_armazenagem, certificado, dose, observacoes,
                    quantidade_inicial, existencia_atual
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                dados["Garanhão"], dados["Proprietário"], dados["Data"], dados["Origem"],
                dados["Palhetas"], dados["Qualidade"], dados["Concentração"], dados["Motilidade"],
                dados["Local"], dados["Certificado"], dados["Dose"], dados["Observações"],
                dados["Palhetas"], dados["Palhetas"]
            ))
            conn.commit()
            cur.close()
            logger.info(f"Stock inserido: {dados['Garanhão']}")
            return True
    except Exception as e:
        logger.error(f"Erro ao inserir stock: {e}")
        st.error(f"Erro ao inserir stock: {e}")
        return False

def registrar_inseminacao(registro):
    """Registra uma inseminação e atualiza o estoque"""
    try:
        # Validações
        if registro["palhetas"] <= 0:
            st.error("❌ Número de palhetas deve ser maior que zero")
            return False
        
        if not registro.get("egua"):
            st.error("❌ Nome da égua é obrigatório")
            return False
        
        with get_connection() as conn:
            cur = conn.cursor()
            
            # Verificar se há estoque suficiente
            cur.execute(
                "SELECT existencia_atual FROM estoque_dono WHERE id = %s",
                (registro["estoque_id"],)
            )
            result = cur.fetchone()
            
            if not result:
                st.error("❌ Estoque não encontrado")
                return False
            
            existencia_atual = result[0] or 0
            
            if existencia_atual < registro["palhetas"]:
                st.error(f"❌ Estoque insuficiente! Disponível: {existencia_atual} palhetas")
                return False
            
            # Inserir inseminação
            cur.execute("""
                INSERT INTO inseminacoes (garanhao, dono_id, data_inseminacao, egua, protocolo, palhetas_gastas)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                registro["garanhao"], registro["dono_id"], registro["data"],
                registro["egua"], registro["protocolo"], registro["palhetas"]
            ))
            
            # Atualizar estoque
            cur.execute("""
                UPDATE estoque_dono SET existencia_atual = existencia_atual - %s
                WHERE id = %s
            """, (
                registro["palhetas"], registro["estoque_id"]
            ))
            
            conn.commit()
            cur.close()
            logger.info(f"Inseminação registrada: {registro['egua']} - {registro['palhetas']} palhetas")
            return True
    except Exception as e:
        logger.error(f"Erro ao registrar inseminação: {e}")
        st.error(f"Erro ao registrar inseminação: {e}")
        return False

# 🖼️ Interface Streamlit
st.set_page_config(
    page_title=os.getenv('APP_TITLE', 'Gestor Sémen - Embriovet'),
    layout=os.getenv('APP_LAYOUT', 'wide'),
    page_icon="🐴"
)

st.title("🐴 Gestor de Sémen com Múltiplos Proprietários")

# Menu lateral
aba = st.sidebar.radio("Menu", [
    "📦 Ver Estoque", 
    "➕ Adicionar Stock", 
    "📝 Registrar Inseminação", 
    "📈 Relatórios"
])

# Carregar dados
try:
    proprietarios = carregar_proprietarios()
    estoque = carregar_estoque()
    insem = carregar_inseminacoes()
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

if proprietarios.empty:
    st.warning("⚠️ Nenhum proprietario cadastrado. Por favor, cadastre proprietarios primeiro.")

# 📦 Ver Estoque
if aba == "📦 Ver Estoque":
    st.header("📦 Estoque Atual por Garanhão e Proprietário")
    
    if not estoque.empty:
        # Filtro por garanhão
        garanhaos_disponiveis = sorted(estoque["garanhao"].unique())
        filtro = st.selectbox("Filtrar por Garanhão:", garanhaos_disponiveis)
        estoque_filtrado = estoque[estoque["garanhao"] == filtro]

        # Mostrar resumo por proprietario
        st.markdown("### 📊 Resumo por Proprietário")
        resumo_por_proprietario = estoque_filtrado.groupby('proprietario_nome')['existencia_atual'].sum().reset_index()
        resumo_por_proprietario.columns = ['Proprietário', 'Total Palhetas']
        
        cols = st.columns(len(resumo_por_proprietario))
        for idx, (_, row) in enumerate(resumo_por_proprietario.iterrows()):
            with cols[idx]:
                st.metric(
                    label=f"👤 {row['Proprietário']}", 
                    value=f"{int(row['Total Palhetas'])} palhetas"
                )
        
        st.markdown("---")
        st.markdown("### 📦 Lotes Detalhados")

        # Criar dicionário de proprietarios
        proprietarios_dict = dict(zip(proprietarios["id"], proprietarios["nome"]))

        # Exibir cada item do estoque
        for idx, row in estoque_filtrado.iterrows():
            existencia = 0 if pd.isna(row['existencia_atual']) else int(row['existencia_atual'])
            referencia = row['origem_externa'] or row['data_embriovet'] or 'Sem referência'
            proprietario_nome = row.get('proprietario_nome', 'Sem proprietario')
            
            with st.expander(f"📦 {referencia} — **{proprietario_nome}** — {existencia} palhetas"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f"**🏷️ Proprietário Atual:** {proprietario_nome}")
                    st.markdown(f"**📍 Local:** {row['local_armazenagem'] or 'N/A'}")
                    st.markdown(f"**📜 Certificado:** {row['certificado'] or 'N/A'}")
                    st.markdown(f"**✨ Qualidade:** {row['qualidade'] or 0}%")
                    st.markdown(f"**🔬 Concentração:** {row['concentracao'] or 0} milhões/mL")
                    st.markdown(f"**⚡ Motilidade:** {row['motilidade'] or 0}%")
                    if row.get('observacoes'):
                        st.markdown(f"**📝 Observações:** {row['observacoes']}")
                
                with col2:
                    st.markdown("### 🔄 Transferir Proprietário")
                    st.info("Pode transferir estas palhetas para outro proprietario")
                    
                    proprietario_atual = row['dono_id']
                    if not proprietarios.empty:
                        novo_proprietario = st.selectbox(
                            "Novo Proprietário",
                            options=proprietarios["id"].tolist(),
                            format_func=lambda x: proprietarios_dict.get(x, 'Desconhecido'),
                            index=list(proprietarios["id"]).index(proprietario_atual) if proprietario_atual in proprietarios["id"].values else 0,
                            key=f"select_{row['id']}"
                        )
                        
                        if novo_proprietario != proprietario_atual:
                            if st.button("🔄 Transferir para Novo Proprietário", key=f"btn_update_{row['id']}", type="primary"):
                                if atualizar_proprietario_stock(row["id"], novo_proprietario):
                                    st.success(f"✅ {existencia} palhetas transferidas de {proprietario_nome} para {proprietarios_dict[novo_proprietario]}!")
                                    st.rerun()
                        else:
                            st.caption("Selecione um proprietario diferente para transferir")
    else:
        st.info("ℹ️ Nenhum stock cadastrado.")

# ➕ Adicionar Stock
elif aba == "➕ Adicionar Stock":
    st.header("➕ Inserir novo stock com Proprietário")
    
    if proprietarios.empty:
        st.error("❌ É necessário cadastrar proprietarios antes de adicionar stock.")
    else:
        with st.form("novo_stock"):
            garanhao = st.text_input("Garanhão *", help="Nome obrigatório")
            proprietario_nome = st.selectbox("Proprietário do Sémen *", proprietarios["nome"])
            dono_id = proprietarios[proprietarios["nome"] == proprietario_nome]["id"].values[0]

            col1, col2 = st.columns(2)
            with col1:
                data = st.text_input("Data de Produção")
                origem = st.text_input("Origem Externa / Referência")
                palhetas = st.number_input("Palhetas Produzidas *", min_value=0, value=0)
                qualidade = st.number_input("Qualidade (%)", min_value=0, max_value=100, value=0)
                concentracao = st.number_input("Concentração (milhões/mL)", min_value=0, value=0)
            
            with col2:
                motilidade = st.number_input("Motilidade (%)", min_value=0, max_value=100, value=0)
                local = st.text_input("Local Armazenagem")
                certificado = st.selectbox("Certificado?", ["Sim", "Não"])
                dose = st.text_input("Dose")
            
            observacoes = st.text_area("Observações")
            submitted = st.form_submit_button("💾 Salvar")

            if submitted:
                if not garanhao:
                    st.error("❌ Nome do garanhão é obrigatório")
                elif palhetas <= 0:
                    st.error("❌ Número de palhetas deve ser maior que zero")
                else:
                    if inserir_stock({
                        "Garanhão": garanhao,
                        "Proprietário": dono_id,
                        "Data": data,
                        "Origem": origem,
                        "Palhetas": palhetas,
                        "Qualidade": qualidade,
                        "Concentração": concentracao,
                        "Motilidade": motilidade,
                        "Local": local,
                        "Certificado": certificado,
                        "Dose": dose,
                        "Observações": observacoes
                    }):
                        st.success("✅ Stock adicionado com sucesso!")
                        st.rerun()

# 📝 Registrar Inseminação
elif aba == "📝 Registrar Inseminação":
    st.header("📝 Registrar uso de Sémen")
    
    if estoque.empty:
        st.warning("⚠️ Nenhum stock disponível.")
    else:
        # Filtrar apenas estoque com existência > 0
        estoque_disponivel = estoque[estoque["existencia_atual"] > 0]
        
        if estoque_disponivel.empty:
            st.warning("⚠️ Todo o estoque está esgotado.")
        else:
            garanhao = st.selectbox("Garanhão", sorted(estoque_disponivel["garanhao"].unique()))
            estoques_filtrados = estoque_disponivel[estoque_disponivel["garanhao"] == garanhao]
            
            # Mostrar resumo de palhetas por proprietario
            if len(estoques_filtrados) > 0:
                st.markdown("### 📊 Sémen Disponível por Proprietário")
                resumo = estoques_filtrados.groupby('proprietario_nome')['existencia_atual'].sum().reset_index()
                cols = st.columns(len(resumo))
                for idx, (_, row) in enumerate(resumo.iterrows()):
                    with cols[idx]:
                        st.metric(f"👤 {row['proprietario_nome']}", f"{int(row['existencia_atual'])} palhetas")
                st.markdown("---")
            
            # Criar opções de seleção de lote
            st.markdown("### 🎯 Selecionar Lote (DE QUAL DONO)")
            lote_opcoes = {}
            for idx, row in estoques_filtrados.iterrows():
                ref = row['origem_externa'] or row['data_embriovet'] or f"Lote #{row['id']}"
                proprietario_nome = row.get('proprietario_nome', 'Sem proprietario')
                existencia = int(row['existencia_atual'] or 0)
                local = row.get('local_armazenagem', 'N/A')
                lote_opcoes[row['id']] = f"👤 {proprietario_nome} | 📦 {ref} | 📍 {local} ({existencia} palhetas)"
            
            estoque_id = st.selectbox(
                "Selecionar lote de qual proprietario usar:",
                options=list(lote_opcoes.keys()),
                format_func=lambda x: lote_opcoes[x],
                help="Escolha de qual proprietario você quer usar o sémen"
            )
            
            # Obter informações do lote selecionado
            lote_selecionado = estoques_filtrados[estoques_filtrados['id'] == estoque_id].iloc[0]
            proprietario_nome = lote_selecionado.get('proprietario_nome', 'Desconhecido')
            max_palhetas = int(lote_selecionado['existencia_atual'] or 0)
            
            st.info(f"🎯 Você vai usar sémen **do {proprietario_nome}** | Disponível: **{max_palhetas} palhetas**")
            
            col1, col2 = st.columns(2)
            with col1:
                data = st.date_input("Data de Inseminação")
                egua = st.text_input("Égua *", help="Nome obrigatório")
            with col2:
                protocolo = lote_selecionado['data_embriovet'] or lote_selecionado['origem_externa'] or 'N/A'
                palhetas = st.number_input(
                    "Palhetas utilizadas", 
                    min_value=1, 
                    max_value=max_palhetas,
                    value=1
                )

            if st.button("📝 Registrar Inseminação", type="primary"):
                if not egua:
                    st.error("❌ Nome da égua é obrigatório")
                elif palhetas <= 0:
                    st.error("❌ Número de palhetas deve ser maior que zero")
                elif palhetas > max_palhetas:
                    st.error(f"❌ Estoque insuficiente! Disponível: {max_palhetas} palhetas")
                else:
                    if registrar_inseminacao({
                        "garanhao": garanhao,
                        "dono_id": lote_selecionado['dono_id'],
                        "data": data,
                        "egua": egua,
                        "protocolo": protocolo,
                        "palhetas": palhetas,
                        "estoque_id": estoque_id
                    }):
                        st.success(f"✅ Inseminação registrada! Usado sémen do **{proprietario_nome}** ({palhetas} palhetas)")
                        st.balloons()
                        st.rerun()

# 📈 Relatórios
elif aba == "📈 Relatórios":
    st.header("📈 Relatório de Inseminações")
    
    if insem.empty:
        st.info("ℹ️ Nenhuma inseminação registrada ainda.")
    else:
        # Estatísticas gerais
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total de Inseminações", len(insem))
        with col2:
            st.metric("Total de Palhetas Gastas", int(insem['palhetas_gastas'].sum()))
        with col3:
            st.metric("Garanhões Utilizados", insem['garanhao'].nunique())
        with col4:
            st.metric("Proprietários Envolvidos", insem['proprietario_nome'].nunique())
        
        st.markdown("---")
        
        # Análise por Garanhão e Proprietário
        st.markdown("### 📊 Consumo por Garanhão e Proprietário")
        consumo = insem.groupby(['garanhao', 'proprietario_nome'])['palhetas_gastas'].sum().reset_index()
        consumo.columns = ['Garanhão', 'Proprietário', 'Palhetas Gastas']
        consumo = consumo.sort_values('Palhetas Gastas', ascending=False)
        st.dataframe(consumo, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Filtros
        st.markdown("### 🔍 Filtrar Histórico")
        col1, col2 = st.columns(2)
        with col1:
            filtro_garanhao = st.multiselect(
                "Filtrar por Garanhão",
                options=sorted(insem['garanhao'].unique()),
                default=None,
                help="Deixe vazio para ver todos"
            )
        with col2:
            filtro_proprietario = st.multiselect(
                "Filtrar por Proprietário",
                options=sorted(insem['proprietario_nome'].unique()),
                default=None,
                help="Deixe vazio para ver todos"
            )
        
        # Aplicar filtros
        insem_filtrado = insem.copy()
        if filtro_garanhao:
            insem_filtrado = insem_filtrado[insem_filtrado['garanhao'].isin(filtro_garanhao)]
        if filtro_proprietario:
            insem_filtrado = insem_filtrado[insem_filtrado['proprietario_nome'].isin(filtro_proprietario)]
        
        # Mostrar estatísticas filtradas
        if len(insem_filtrado) > 0:
            st.markdown(f"**📋 Mostrando {len(insem_filtrado)} registros**")
        
        # Exibir tabela
        st.markdown("### 📋 Histórico Detalhado")
        st.dataframe(
            insem_filtrado[[
                "garanhao", "proprietario_nome", "data_inseminacao", 
                "egua", "protocolo", "palhetas_gastas"
            ]].rename(columns={
                "garanhao": "Garanhão",
                "proprietario_nome": "Proprietário do Sémen",
                "data_inseminacao": "Data",
                "egua": "Égua",
                "protocolo": "Protocolo",
                "palhetas_gastas": "Palhetas"
            }).sort_values("Data", ascending=False),
            use_container_width=True,
            hide_index=True
        )
        
        # Exemplo de pesquisa
        st.markdown("---")
        st.markdown("### 🔎 Pesquisa Rápida")
        pesquisa = st.text_input("Digite o nome do garanhão ou proprietario para pesquisar:", placeholder="Ex: Retoque")
        
        if pesquisa:
            resultado = insem_filtrado[
                insem_filtrado['garanhao'].str.contains(pesquisa, case=False, na=False) |
                insem_filtrado['proprietario_nome'].str.contains(pesquisa, case=False, na=False)
            ]
            
            if len(resultado) > 0:
                st.success(f"✅ Encontrados {len(resultado)} registros")
                st.dataframe(
                    resultado[[
                        "garanhao", "proprietario_nome", "data_inseminacao", 
                        "egua", "palhetas_gastas"
                    ]].rename(columns={
                        "garanhao": "Garanhão",
                        "proprietario_nome": "Proprietário",
                        "data_inseminacao": "Data",
                        "egua": "Égua",
                        "palhetas_gastas": "Palhetas"
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.warning(f"❌ Nenhum resultado para '{pesquisa}'")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**Embriovet Gestor v2.0**")
st.sidebar.markdown("✅ Todas as correções aplicadas")
