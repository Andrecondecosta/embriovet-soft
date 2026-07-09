"""View extraída de `app.py` (Pedido 9 · Fase 1) — bit-for-bit.

Elimina o padrão `sys.modules['__main__']` do último ciclo. As
dependências (`st`, `t`, `logger`, funções de repositórios, componentes)
são importadas explicitamente no topo — nenhuma vem por injeção de
contexto.
"""

from __future__ import annotations

import logging
import streamlit as st

from modules.i18n import t
from modules.db import to_py, get_connection, invalidate_data_cache
from modules.repositories.stock_repo import (
    inserir_stock, carregar_stock, carregar_contentores,
    carregar_proprietarios,
)
from modules.repositories.owner_repo import (
    adicionar_proprietario, editar_proprietario, deletar_proprietario,
    atualizar_status_proprietarios, alternar_status_proprietario,
    atualizar_proprietario_stock,
)
from modules.services.auth_service import (
    carregar_usuarios, adicionar_usuario, ativar_usuario, desativar_usuario,
    alterar_password, verificar_permissao,
)
from modules.ui_kit import (
    inject_add_stock_form_css, inject_stock_css, inject_reports_css,
    render_zone_title, render_kpi_strip,
)
from modules.components.modal_proprietario import modal_adicionar_proprietario

logger = logging.getLogger(__name__)



def _render_users_view():
    """Bloco 'Gestão de Utilizadores' — antigo `elif aba == t('menu.users')`
    convertido em função para o separador 'Utilizadores' das Definições.
    Apenas visível ao Administrador (filtro feito pelo orquestrador).
    """
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

# --- Fim das vistas legadas ---

# Router de páginas (Pedido 7: 6 destinos)
# ------------------------------------------------------------
