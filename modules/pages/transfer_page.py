from modules.i18n import t
import streamlit as st
import pandas as pd


def run_transfer_page(ctx):
    globals().update(ctx)
    
    # DEBUG: Verificar se as funções existem no contexto
    import inspect
    if 'transferir_stock_interno' in globals():
        sig = inspect.signature(globals()['transferir_stock_interno'])
        st.sidebar.write(f"🔍 DEBUG interno: {sig}")
    if 'transferir_stock_externo' in globals():
        sig = inspect.signature(globals()['transferir_stock_externo'])
        st.sidebar.write(f"🔍 DEBUG externo: {sig}")

    st.header(t("transfer.title"))

    st.markdown(
        """
        <style>
            .transfer-zone-title {
                font-size: .78rem;
                text-transform: uppercase;
                letter-spacing: .05em;
                color: #64748b;
                margin: .2rem 0 .35rem 0;
                font-weight: 700;
            }
            .transfer-line {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                background: #f8fafc;
                padding: 6px 8px;
                margin-bottom: 6px;
            }
            .transfer-lote-main {
                font-size: .9rem;
                font-weight: 600;
                color: #0f172a;
            }
            .transfer-lote-sub {
                font-size: .76rem;
                color: #64748b;
                margin-top: 2px;
            }
            .transfer-summary-bar {
                display: flex;
                align-items: center;
                gap: 16px;
                background: #eef2f7;
                border: 1px solid #e2e8f0;
                padding: 8px 12px;
                border-radius: 8px;
                font-size: .78rem;
                color: #1f2937;
            }
            .transfer-summary-item {
                display: flex;
                align-items: baseline;
                gap: 6px;
                font-weight: 600;
            }
            .transfer-summary-label {
                text-transform: uppercase;
                letter-spacing: .05em;
                font-size: .68rem;
                color: #64748b;
            }
            .transfer-summary-value {
                font-size: .9rem;
                color: #0f172a;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if "transfer_linhas" not in st.session_state:
        st.session_state["transfer_linhas"] = {}
    if "transfer_garanhao" not in st.session_state:
        st.session_state["transfer_garanhao"] = None
    if "transfer_proprietario" not in st.session_state:
        st.session_state["transfer_proprietario"] = None
    if "transfer_show_success" not in st.session_state:
        st.session_state["transfer_show_success"] = False

    def to_py(val):
        if pd.isna(val):
            return None
        return val

    def lote_ref(row):
        return row.get("origem_externa") or row.get("data_embriovet") or f"Lote #{row.get('id')}"

    def lote_local(row):
        contentor = row.get("contentor_codigo") or row.get("local_armazenagem") or "SEM-CONTENTOR"
        can = row.get("canister")
        andr = row.get("andar")
        if pd.notna(can) and pd.notna(andr):
            return f"{contentor} / C{int(can)} / A{int(andr)}"
        return str(contentor)

    def lote_payload(row):
        return {
            "stock_id": int(row.get("id")),
            "garanhao": row.get("garanhao"),
            "dono_id": to_py(row.get("dono_id")),
            "proprietario_nome": row.get("proprietario_nome") or "—",
            "ref": lote_ref(row),
            "local": lote_local(row),
            "max_disponivel": int(to_py(row.get("existencia_atual")) or 0),
        }

    def remover_linha(lote_id):
        sid = str(lote_id)
        linhas = st.session_state["transfer_linhas"]
        linhas.pop(sid, None)
        st.session_state["transfer_linhas"] = linhas
        st.session_state.pop(f"transfer_step_{sid}", None)

    stock_disponivel = stock[stock["existencia_atual"] > 0].copy() if not stock.empty else pd.DataFrame()
    if stock_disponivel.empty:
        st.warning(t("transfer.no_stock_available"))
        return

    # Inicializar garanhao padrão se necessário
    if st.session_state["transfer_garanhao"] is None:
        garanhaos_unicos = sorted(stock_disponivel["garanhao"].dropna().unique())
        if garanhaos_unicos:
            st.session_state["transfer_garanhao"] = garanhaos_unicos[0]

    @st.dialog(t("transfer.success_title"), width="small")
    def show_success_dialog():
        st.markdown(t("transfer.success_msg"))
        if st.button(t("btn.ok"), type="primary", width="stretch"):
            st.session_state["transfer_linhas"] = {}
            st.session_state["transfer_garanhao"] = None
            st.session_state["transfer_proprietario"] = None
            for k in list(st.session_state.keys()):
                if k.startswith("transfer_step_") or k.startswith("transfer_modal_sel_"):
                    st.session_state.pop(k, None)
            st.session_state["transfer_show_success"] = False
            st.rerun()

    if st.session_state["transfer_show_success"]:
        show_success_dialog()

    @st.dialog(t("transfer.select_lots_title"), width="large")
    def abrir_modal_lotes():
        gar_sel = st.session_state.get("transfer_garanhao")
        prop_sel = st.session_state.get("transfer_proprietario")
        
        if not gar_sel:
            st.warning(t("warning.select_garanhao_first"))
            return
        
        # Filtrar lotes
        modal_df = stock_disponivel[stock_disponivel["garanhao"] == gar_sel].copy()
        if prop_sel:
            modal_df = modal_df[modal_df["proprietario_nome"] == prop_sel]

        if "data_embriovet" in modal_df.columns:
            modal_df["_ord"] = pd.to_datetime(modal_df["data_embriovet"], errors="coerce")
            modal_df = modal_df.sort_values("_ord", ascending=False)

        if modal_df.empty:
            st.info(t("transfer.no_lotes_for_filters"))
            return

        st.markdown(f"<div class='transfer-zone-title'>{t('transfer.available_lots')}</div>", unsafe_allow_html=True)

        header_cols = st.columns([2.5, 1.8, 0.8, 0.6])
        with header_cols[0]:
            st.markdown(f"<div class='transfer-zone-title'>{t('label.lote')}</div>", unsafe_allow_html=True)
        with header_cols[1]:
            st.markdown(f"<div class='transfer-zone-title'>{t('label.location')}</div>", unsafe_allow_html=True)
        with header_cols[2]:
            st.markdown(f"<div class='transfer-zone-title'>{t('label.available')}</div>", unsafe_allow_html=True)
        with header_cols[3]:
            st.markdown(f"<div class='transfer-zone-title'>{t('btn.select')}</div>", unsafe_allow_html=True)

        for _, row in modal_df.iterrows():
            lote = lote_payload(row)
            sid = lote["stock_id"]

            row_cols = st.columns([2.5, 1.8, 0.8, 0.6])
            with row_cols[0]:
                st.caption(f"{lote['ref']}")
            with row_cols[1]:
                st.caption(lote["local"])
            with row_cols[2]:
                st.caption(f"{lote['max_disponivel']} pal.")
            with row_cols[3]:
                sel_key = f"transfer_modal_sel_{sid}"
                default_checked = bool(st.session_state.get(sel_key, False) or str(sid) in st.session_state["transfer_linhas"])
                st.checkbox(
                    t("btn.select"),
                    key=sel_key,
                    value=default_checked,
                    label_visibility="collapsed",
                )

        b1, b2 = st.columns([2, 1])
        with b1:
            if st.button(t("btn.confirm_selection"), type="primary", key="transfer_modal_confirmar", width="stretch"):
                selecionados_ids = []
                for key, val in st.session_state.items():
                    if key.startswith("transfer_modal_sel_") and val:
                        try:
                            selecionados_ids.append(int(key.split("transfer_modal_sel_")[-1]))
                        except Exception:
                            continue

                if not selecionados_ids:
                    st.warning(t("warning.select_one_lot"))
                    return

                selecionados_df = stock_disponivel[stock_disponivel["id"].isin(selecionados_ids)].copy()
                if selecionados_df.empty:
                    st.warning(t("transfer.no_lotes_selected"))
                    return

                linhas = st.session_state["transfer_linhas"]
                for _, row in selecionados_df.iterrows():
                    lote = lote_payload(row)
                    sid = str(lote["stock_id"])
                    if sid not in linhas:
                        linhas[sid] = {
                            **lote,
                            "qty": 1,
                        }

                st.session_state["transfer_linhas"] = linhas
                st.rerun()
        with b2:
            if st.button(t("btn.close"), key="transfer_modal_cancelar", width="stretch"):
                st.rerun()

    # PÁGINA PRINCIPAL - FLUXO DE TRANSFERÊNCIA
    render_zone_title(t("transfer.zone_selection"), "transfer-zone-title")
    
    # 1. CAVALO
    garanhaos_disponiveis = sorted(stock_disponivel["garanhao"].dropna().unique())
    idx_gar = 0
    if st.session_state["transfer_garanhao"] and st.session_state["transfer_garanhao"] in garanhaos_disponiveis:
        idx_gar = garanhaos_disponiveis.index(st.session_state["transfer_garanhao"])
    
    garanhao_selecionado = st.selectbox(
        t("label.garanhao"),
        garanhaos_disponiveis,
        index=idx_gar,
        key="transfer_garanhao_main"
    )
    
    if garanhao_selecionado != st.session_state["transfer_garanhao"]:
        st.session_state["transfer_garanhao"] = garanhao_selecionado
        st.session_state["transfer_proprietario"] = None
        st.session_state["transfer_linhas"] = {}
        st.rerun()
    
    # 2. PROPRIETÁRIO
    stock_cavalo = stock_disponivel[stock_disponivel["garanhao"] == garanhao_selecionado]
    proprietarios_com_stock = sorted(stock_cavalo["proprietario_nome"].dropna().unique())
    prop_opts = [t("common.all")] + proprietarios_com_stock
    
    idx_prop = 0
    if st.session_state["transfer_proprietario"] and st.session_state["transfer_proprietario"] in proprietarios_com_stock:
        idx_prop = prop_opts.index(st.session_state["transfer_proprietario"])
    
    proprietario_selecionado = st.selectbox(
        t("label.owner"),
        prop_opts,
        index=idx_prop,
        key="transfer_prop_main"
    )
    
    if proprietario_selecionado == t("common.all"):
        st.session_state["transfer_proprietario"] = None
    else:
        if proprietario_selecionado != st.session_state["transfer_proprietario"]:
            st.session_state["transfer_proprietario"] = proprietario_selecionado
            st.session_state["transfer_linhas"] = {}
            st.rerun()
    
    # 3. BOTÃO SELECIONAR LOTES
    if st.button(t("btn.select_lots"), key="transfer_btn_open_modal", type="secondary", width="stretch"):
        abrir_modal_lotes()
    
    st.markdown("---")
    
    # 4. LOTES SELECIONADOS COM QUANTIDADE
    render_zone_title(t("transfer.selected_lots"), "transfer-zone-title")
    linhas = st.session_state["transfer_linhas"]

    if not linhas:
        st.info(t("transfer.no_lotes_selected_hint"))
    else:
        for sid in list(linhas.keys()):
            linha = linhas[sid]
            max_disp = int(linha.get("max_disponivel", 0))
            qtd = int(linha.get("qty", 0))

            st.markdown("<div class='transfer-line'>", unsafe_allow_html=True)
            step_key = f"transfer_step_{sid}"
            # Apenas inicializar se não existir
            if step_key not in st.session_state:
                st.session_state[step_key] = qtd

            l1, l2, linput, l4 = st.columns([3.0, 1.5, 1.9, 0.8])
            with l1:
                st.markdown(f"<div class='transfer-lote-main'>{linha['ref']} · {linha['local']}</div>", unsafe_allow_html=True)
                st.markdown(
                    f"<div class='transfer-lote-sub'>{linha['proprietario_nome']} · Disponível: {max_disp}</div>",
                    unsafe_allow_html=True,
                )
            with l2:
                st.markdown(f"<div class='transfer-lote-sub'>{t('label.quantity')}</div>", unsafe_allow_html=True)

            with linput:
                # Usar o session_state como fonte única de verdade
                new_qtd = st.number_input(
                    "Quantidade",
                    min_value=0,
                    max_value=max_disp,
                    step=1,
                    key=step_key,
                    label_visibility="collapsed",
                )
                qtd_val = new_qtd
                # Reduzir altura do campo usando CSS inline
                st.markdown(
                    """
                    <style>
                    div[data-testid="stNumberInput"] input {
                        height: 38px !important;
                        padding: 4px 8px !important;
                    }
                    </style>
                    """,
                    unsafe_allow_html=True
                )

            if qtd_val != qtd:
                if qtd_val == 0:
                    linhas.pop(sid, None)
                    st.session_state.pop(step_key, None)
                else:
                    linhas[sid]["qty"] = int(qtd_val)
                st.session_state["transfer_linhas"] = linhas

            with l4:
                st.button(
                    t("btn.remove"),
                    key=f"transfer_line_remove_{sid}",
                    width="stretch",
                    on_click=remover_linha,
                    args=(sid,),
                )
            st.markdown("</div>", unsafe_allow_html=True)

        badd1, badd2 = st.columns([2, 2])
        with badd1:
            if st.button(t("btn.add_line"), key="transfer_btn_add_line", width="stretch"):
                abrir_modal_lotes()
        with badd2:
            total_palhetas = sum(int(v.get("qty", 0)) for v in linhas.values())
            st.markdown(
                f"<div class='transfer-lote-main'>{t('label.total')}: {total_palhetas} {t('label.straws')}</div>",
                unsafe_allow_html=True,
            )
    
    st.markdown("---")
    
    # 5. DESTINO DA TRANSFERÊNCIA
    if linhas:
        render_zone_title(t("transfer.destination"), "transfer-zone-title")
        
        tipo_transferencia = st.radio(
            t("transfer.type"),
            [t("transfer.internal"), t("transfer.external")],
            key="transfer_tipo"
        )
        
        if tipo_transferencia == t("transfer.internal"):
            # Transferência Interna
            st.markdown(f"**{t('transfer.destination_owner')}**")
            
            # Botão para adicionar novo proprietário
            if st.button(t("stock.new_owner"), key="transfer_btn_new_owner"):
                modal_adicionar_proprietario()
            
            prop_destino_opts = sorted(proprietarios["nome"].tolist())
            proprietario_destino = st.selectbox(
                t("transfer.destination_owner"),
                prop_destino_opts,
                key="transfer_dest_interno",
                label_visibility="collapsed"
            )
            
            # Perguntar se muda de localização
            st.markdown("---")
            muda_localizacao = st.radio(
                t("transfer.change_location"),
                [t("transfer.keep_location"), t("transfer.new_location")],
                key="transfer_muda_loc",
                horizontal=True
            )
            
            contentor_id_destino = None
            canister_destino = None
            andar_destino = None
            
            if muda_localizacao == t("transfer.new_location"):
                st.markdown(f"**{t('transfer.new_location_details')}**")
                
                # Buscar contentores
                contentores_list = contentores["codigo"].tolist() if not contentores.empty else []
                if contentores_list:
                    contentor_codigo = st.selectbox(
                        t("label.container"),
                        contentores_list,
                        key="transfer_contentor"
                    )
                    contentor_id_destino = contentores[contentores["codigo"] == contentor_codigo]["id"].iloc[0]
                else:
                    st.warning(t("transfer.no_containers"))
                
                c1, c2 = st.columns(2)
                with c1:
                    canister_destino = st.number_input(
                        t("label.canister"),
                        min_value=1,
                        max_value=20,
                        value=1,
                        key="transfer_canister"
                    )
                with c2:
                    andar_destino = st.number_input(
                        t("label.floor"),
                        min_value=1,
                        max_value=20,
                        value=1,
                        key="transfer_andar"
                    )
            
            st.markdown("---")
            if st.button(t("btn.execute_transfer"), type="primary", width="stretch"):
                linhas_finais = [v for v in st.session_state["transfer_linhas"].values() if int(v.get("qty", 0)) > 0]
                if not linhas_finais:
                    st.error(t("error.select_lot_line"))
                elif not proprietario_destino:
                    st.error(t("transfer.error_no_destination"))
                elif muda_localizacao == t("transfer.new_location") and not contentor_id_destino:
                    st.error(t("transfer.error_no_container"))
                else:
                    # Executar transferência interna
                    dest_id = proprietarios[proprietarios["nome"] == proprietario_destino]["id"].iloc[0]
                    sucesso = True
                    for linha in linhas_finais:
                        origem_id = linha["dono_id"]
                        stock_id = linha["stock_id"]
                        qtd = linha["qty"]
                        
                        if origem_id == dest_id:
                            st.error(f"Erro: Origem e destino são iguais para o lote {linha['ref']}")
                            sucesso = False
                            continue
                        
                        try:
                            # Se muda localização, passar novos parâmetros
                            if muda_localizacao == t("transfer.new_location"):
                                st.write(f"DEBUG: Chamando com_localizacao - Args: origem={origem_id}, dest={dest_id}, stock={stock_id}, qty={qtd}")
                                transferir_stock_interno_com_localizacao(
                                    origem_id, dest_id, stock_id, qtd,
                                    contentor_id_destino, canister_destino, andar_destino
                                )
                            else:
                                st.write(f"DEBUG: Chamando interno - Args: stock={stock_id}, dest={dest_id}, qty={qtd}")
                                transferir_stock_interno(stock_id, dest_id, qtd)
                        except Exception as e:
                            st.error(f"Erro ao transferir {linha['ref']}: {e}")
                            sucesso = False
                    
                    if sucesso:
                        st.session_state["transfer_show_success"] = True
                        st.rerun()
        
        else:
            # Transferência Externa
            destinatario_externo = st.text_input(
                t("transfer.external_recipient"),
                key="transfer_dest_externo"
            )
            
            # Motivo da transferência
            motivo = st.selectbox(
                t("transfer.reason"),
                [t("stock.type.sale"), t("stock.type.donation"), t("stock.type.export"), t("stock.type.other")],
                key="transfer_motivo"
            )
            
            # Observações
            observacoes = st.text_area(
                t("label.notes"),
                key="transfer_observacoes",
                height=80
            )
            
            if st.button(t("btn.execute_transfer"), type="primary", width="stretch"):
                linhas_finais = [v for v in st.session_state["transfer_linhas"].values() if int(v.get("qty", 0)) > 0]
                if not linhas_finais:
                    st.error(t("error.select_lot_line"))
                elif not destinatario_externo:
                    st.error(t("transfer.error_no_recipient"))
                else:
                    # Executar transferência externa
                    sucesso = True
                    for linha in linhas_finais:
                        stock_id = linha["stock_id"]
                        qtd = linha["qty"]
                        
                        try:
                            st.write(f"DEBUG: Chamando externo - Args: stock={stock_id}, dest={destinatario_externo}, qty={qtd}, tipo={motivo}, obs={observacoes}")
                            transferir_stock_externo(stock_id, destinatario_externo, qtd, motivo, observacoes)
                        except Exception as e:
                            st.error(f"Erro ao transferir {linha['ref']}: {e}")
                            sucesso = False
                    
                    if sucesso:
                        st.session_state["transfer_show_success"] = True
                        st.rerun()
