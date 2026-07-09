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



def _render_owners_view():
    """Bloco 'Gestão de Proprietários' — antigo `elif aba == t('menu.owners')`
    convertido em função para o separador 'Proprietários' das Definições.
    """
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

# Gestão de Utilizadores (movido para Definições · Utilizadores)
# ------------------------------------------------------------
