"""View extraída de `app.py` (Pedido 9 · Fase 1) — bit-for-bit.

Elimina o padrão `sys.modules['__main__']` do último ciclo. As
dependências (`st`, `t`, `logger`, funções de repositórios, componentes)
são importadas explicitamente no topo — nenhuma vem por injeção de
contexto.
"""

from __future__ import annotations

import logging
import pandas as pd
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


NAV_STOCK_SEMEN = "Stock de sémen"  # espelho de app.py (Pedido 7)

def _render_add_stock_view():
    # Preamble (Pedido 9): dependências injetadas antes por globals(); 
    # agora resolvidas explicitamente.
    from modules.repositories.settings_repo import get_app_settings
    app_settings = get_app_settings() or {}
    proprietarios = carregar_proprietarios()

    """Form 'Adicionar lote' — antigo bloco `elif aba == t('menu.add_stock')`
    convertido em função para ser invocado pelo orquestrador de
    'Stock de sémen' (Pedido 7). Lógica inalterada.
    """
    st.header(t("add_stock.title"))
    primary = (app_settings or {}).get("primary_color") or "#E85D4A"
    inject_add_stock_form_css(primary_color=primary)

    # Banner de contexto quando a entrada vem duma colheita agendada
    # (Pedido 8). O prefill é consumido apenas após o guardar do lote.
    _colheita_ctx = st.session_state.get("colheita_garanhao_prefill")
    if _colheita_ctx:
        col_msg, col_x = st.columns([7, 1])
        with col_msg:
            st.info(
                f"🐎 A registar produção da **colheita agendada** para "
                f"**{_colheita_ctx.get('garanhao_nome') or 'garanhão'}**. "
                f"Ao guardar, a tarefa será marcada como concluída."
            )
        with col_x:
            if st.button("Cancelar", key="colheita-prefill-cancel"):
                st.session_state.pop("colheita_garanhao_prefill", None)
                st.rerun()

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
            # Carregar garanhões (para selectbox de identificação)
            with get_connection() as _cx:
                garanhoes_df = pd.read_sql_query(
                    "SELECT id, nome FROM animais "
                    "WHERE tipo = 'garanhao' AND ativo = TRUE "
                    "ORDER BY LOWER(nome)",
                    _cx,
                )

            # ── Orquestração do modal "Novo garanhão" ────────────────────
            # Usa o mesmo padrão do proprietário: session_state flag → rerun
            # → renderiza o modal_animal (que não pode ser aninhado noutro).
            if st.session_state.get("abrir_modal_novo_garanhao"):
                del st.session_state["abrir_modal_novo_garanhao"]
                from modules.components.modal_animal import render_modal_animal
                def _on_garanhao_criado(animal_id, animal_nome, estadia_id):
                    st.session_state["novo_animal_id"] = int(animal_id)
                    st.session_state["novo_animal_nome"] = animal_nome
                    st.rerun()
                render_modal_animal(
                    key="modal_novo_garanhao_stock",
                    tipo_default="garanhao",
                    tipo_locked=True,
                    on_success=_on_garanhao_criado,
                )

            # ── Sub-orquestração: quando o utilizador clica "+ Novo
            # proprietário" DENTRO do modal do animal, o próprio modal
            # activa `abrir_modal_prop_standalone` — fica ao dono da página
            # abrir o modal do proprietário aqui. Depois, o novo dono fica
            # imediatamente disponível no selectbox "Proprietário do sémen".
            if st.session_state.get("abrir_modal_prop_standalone"):
                del st.session_state["abrir_modal_prop_standalone"]
                from modules.components.modal_proprietario import render_modal_proprietario
                def _on_prop_criado(dono_id, dono_nome):
                    st.session_state["novo_prop_id"] = dono_id
                    st.session_state["novo_prop_nome"] = dono_nome
                    # Bridge para o selectbox "Proprietário do sémen":
                    st.session_state["novo_proprietario_id"] = dono_id
                    st.session_state["reabrir_modal_animal"] = True
                    st.rerun()
                render_modal_proprietario(
                    key="modal_prop_standalone_stock",
                    on_success=_on_prop_criado,
                )

            if st.session_state.get("reabrir_modal_animal"):
                del st.session_state["reabrir_modal_animal"]
                from modules.components.modal_animal import render_modal_animal
                def _on_garanhao_criado2(animal_id, animal_nome, estadia_id):
                    st.session_state["novo_animal_id"] = int(animal_id)
                    st.session_state["novo_animal_nome"] = animal_nome
                    st.rerun()
                render_modal_animal(
                    key="modal_novo_garanhao_stock",
                    tipo_default="garanhao",
                    tipo_locked=True,
                    on_success=_on_garanhao_criado2,
                )

            # ── Identificação do Garanhão (FORA do form para permitir
            # pré-selecção de garanhão recém-criado via session_state) ────
            st.markdown('<div class="form-card"><div class="form-section-header">🐴 Identificação</div>', unsafe_allow_html=True)
            col_id1, col_id_btn, col_id2 = st.columns([3, 1, 3])
            with col_id1:
                # Selectbox por id (permite pré-seleccionar via novo_animal_id
                # ou via `colheita_garanhao_prefill` — Pedido 8).
                garanhao_ids = garanhoes_df["id"].tolist()
                # Se acabámos de criar um garanhão, força a pré-selecção
                novo_id = st.session_state.get("novo_animal_id")
                # Prefill de colheita agendada (Pedido 8): não fazer pop
                # aqui — só depois de guardar o lote (para poder concluir
                # a tarefa correspondente).
                colheita_prefill = st.session_state.get("colheita_garanhao_prefill")
                default_idx = 0
                if novo_id is not None and int(novo_id) in garanhao_ids:
                    default_idx = garanhao_ids.index(int(novo_id))
                elif colheita_prefill and int(colheita_prefill.get("animal_id") or 0) in garanhao_ids:
                    default_idx = garanhao_ids.index(int(colheita_prefill["animal_id"]))

                def _fmt_garanhao(gid):
                    r = garanhoes_df.loc[garanhoes_df["id"] == gid]
                    return str(r.iloc[0]["nome"]) if not r.empty else f"#{gid}"

                if not garanhao_ids:
                    st.info("Sem garanhões — clique em '➕ Novo garanhão' para criar.")
                    garanhao = ""
                else:
                    gid_sel = st.selectbox(
                        t("label.garanhao_required"),
                        options=garanhao_ids,
                        index=default_idx,
                        format_func=_fmt_garanhao,
                        help=t("add_stock.required_name"),
                        key="add_stock_garanhao_select",
                    )
                    garanhao = _fmt_garanhao(gid_sel)
                    # Limpa o marcador de pré-selecção só depois de aplicar
                    if novo_id is not None:
                        st.session_state.pop("novo_animal_id", None)
                        st.session_state.pop("novo_animal_nome", None)

            with col_id_btn:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button(
                    "➕ Novo garanhão",
                    key="btn_novo_garanhao_stock",
                    help="Criar novo garanhão",
                    width="stretch",
                ):
                    st.session_state["abrir_modal_novo_garanhao"] = True
                    st.rerun()
            with col_id2:
                # Verificar se há proprietário recém-adicionado
                if 'novo_proprietario_id' in st.session_state:
                    try:
                        idx_default = list(proprietarios["id"]).index(st.session_state['novo_proprietario_id'])
                    except ValueError:
                        idx_default = 0
                else:
                    idx_default = 0
                proprietario_nome = st.selectbox(
                    t("add_stock.owner_semen"), proprietarios["nome"],
                    index=idx_default, key="add_stock_prop_select",
                )
                dono_id = int(proprietarios.loc[proprietarios["nome"] == proprietario_nome, "id"].iloc[0])
            st.markdown('</div>', unsafe_allow_html=True)
            
            with st.form("novo_stock"):
                # SEÇÃO 2: DADOS TÉCNICOS
                st.markdown('<div class="form-card"><div class="form-section-header">🔬 Dados Técnicos</div>', unsafe_allow_html=True)
                col_tec1, col_tec2, col_tec3, col_tec4 = st.columns(4)
                
                with col_tec1:
                    motilidade = st.number_input(t("stock.motility_pct"), min_value=0, max_value=100, value=0)
                with col_tec2:
                    concentracao = st.number_input(t("stock.concentration"), min_value=0, value=0)
                with col_tec3:
                    qualidade = st.text_input(t("stock.quality_text"))
                with col_tec4:
                    cor = st.text_input(t("stock.color"))
                
                col_tec5, col_tec6 = st.columns(2)
                with col_tec5:
                    certificado = st.selectbox(t("stock.certificate"), [t("common.yes"), t("common.no")])
                with col_tec6:
                    dose = st.text_input(t("stock.dose"))
                st.markdown('</div>', unsafe_allow_html=True)

                # SEÇÃO 3: PRODUÇÃO
                st.markdown('<div class="form-card"><div class="form-section-header">📦 Produção</div>', unsafe_allow_html=True)
                col_prod1, col_prod2, col_prod3 = st.columns(3)
                
                with col_prod1:
                    data = st.text_input(t("stock.prod_date"))
                with col_prod2:
                    palhetas = st.number_input(t("stock.straws_produced"), min_value=0, value=0)
                with col_prod3:
                    origem = st.text_input(t("stock.external_origin"))
                st.markdown('</div>', unsafe_allow_html=True)

                # SEÇÃO 4: LOCALIZAÇÃO
                st.markdown('<div class="form-card"><div class="form-section-header">📍 Localização no Contentor</div>', unsafe_allow_html=True)
                
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
                st.markdown('</div>', unsafe_allow_html=True)

                # OBSERVAÇÕES E SUBMIT
                st.markdown('<div class="form-card"><div class="form-section-header">💬 Observações</div>', unsafe_allow_html=True)
                observacoes = st.text_area(t("label.notes"), help=t("add_stock.notes_help"), label_visibility="collapsed")
                st.markdown('</div>', unsafe_allow_html=True)

                submitted = st.form_submit_button(t("btn.save"), type="primary", width="stretch")

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
                            # Se o guardar foi despoletado por uma colheita
                            # agendada (Pedido 8), conclui a tarefa.
                            _colheita_prefill = st.session_state.pop(
                                "colheita_garanhao_prefill", None
                            )
                            if _colheita_prefill and _colheita_prefill.get("tarefa_id"):
                                try:
                                    from modules.repositories.colheita_repo import (
                                        concluir_colheita,
                                    )
                                    concluir_colheita(
                                        int(_colheita_prefill["tarefa_id"]),
                                        utilizador=st.session_state.get(
                                            "user", {}
                                        ).get("username", "sistema"),
                                    )
                                except Exception as _e:
                                    logger.warning(
                                        f"Não foi possível concluir a colheita: {_e}"
                                    )
                            # Redirect para o separador "Lotes" do novo
                            # Stock de sémen (Pedido 7).
                            st.session_state['aba_selecionada'] = NAV_STOCK_SEMEN
                            st.session_state['stock_semen_tab'] = "Lotes"
                            st.rerun()


# ------------------------------------------------------------

# Owners e Users management (moved to Definições em Pedido 7).
# As funções abaixo são invocadas pelos separadores de
# `modules.pages.definicoes_page`.
# ------------------------------------------------------------
