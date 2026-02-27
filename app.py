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
