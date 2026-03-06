import pandas as pd
import streamlit as st
from modules.i18n import t


def run_insemination_page(ctx):
    globals().update(ctx)

    st.header(t("insemination.title"))
    inject_stepper_css()

    # Mostrar aviso se estiver em modo de edição
    if st.session_state.get('edit_insemination_id'):
        st.info("📝 **Modo de Edição** - Modifique os dados e clique em 'Atualizar Inseminação'")

    st.markdown(
        """
        <style>
            .insem-zone-title {
                font-size: .78rem;
                text-transform: uppercase;
                letter-spacing: .05em;
                color: #64748b;
                margin: .2rem 0 .35rem 0;
                font-weight: 700;
            }
            .insem-line {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                background: #f8fafc;
                padding: 6px 8px;
                margin-bottom: 6px;
            }
            .insem-lote-main {
                font-size: .9rem;
                font-weight: 600;
                color: #0f172a;
            }
            .insem-lote-sub {
                font-size: .76rem;
                color: #64748b;
                margin-top: 2px;
            }
            .insem-modal-head {
                font-size: .75rem;
                text-transform: uppercase;
                color: #64748b;
                letter-spacing: .04em;
                margin: .2rem 0;
            }
            .insem-summary-bar {
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
            .insem-summary-item {
                display: flex;
                align-items: baseline;
                gap: 6px;
                font-weight: 600;
            }
            .insem-summary-label {
                text-transform: uppercase;
                letter-spacing: .05em;
                font-size: .68rem;
                color: #64748b;
            }
            .insem-summary-value {
                font-size: .9rem;
                color: #0f172a;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if "insem_linhas" not in st.session_state:
        st.session_state["insem_linhas"] = {}
    if "insem_garanhao_principal" not in st.session_state:
        st.session_state["insem_garanhao_principal"] = None
    if "insem_prop_principal" not in st.session_state:
        st.session_state["insem_prop_principal"] = None
    if "insem_show_success" not in st.session_state:
        st.session_state["insem_show_success"] = False

    # Detectar modo de edição
    edit_mode = False
    insemination_data = None
    if st.session_state.get('edit_insemination_id'):
        edit_mode = True
        insemination_id = st.session_state['edit_insemination_id']
        
        # Carregar dados da inseminação
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT i.id, i.garanhao, i.egua, i.dono_id, i.palhetas_gastas, 
                           i.data_inseminacao, d.nome as proprietario_nome, i.observacoes
                    FROM inseminacoes i
                    LEFT JOIN dono d ON i.dono_id = d.id
                    WHERE i.id = %s
                """, (insemination_id,))
                row = cur.fetchone()
                if row:
                    insemination_data = {
                        'id': row[0],
                        'garanhao': row[1],
                        'egua': row[2],
                        'dono_id': row[3],
                        'palhetas_gastas': row[4],
                        'data_inseminacao': row[5],
                        'proprietario_nome': row[6],
                        'observacoes': row[7] or '',
                    }
                    
                    # Pré-preencher estado
                    if 'insem_egua' not in st.session_state:
                        st.session_state['insem_egua'] = insemination_data['egua']
                    if 'insem_data' not in st.session_state:
                        st.session_state['insem_data'] = insemination_data['data_inseminacao']
                    if 'insem_observacoes' not in st.session_state:
                        st.session_state['insem_observacoes'] = insemination_data['observacoes']
                    st.session_state["insem_garanhao_principal"] = insemination_data['garanhao']
                    st.session_state["insem_prop_principal"] = insemination_data['proprietario_nome']
                    
                    # Buscar lotes usados nesta inseminação
                    # Como não temos histórico dos lotes específicos, vamos buscar lotes disponíveis do mesmo garanhão/proprietário
                    cur.execute("""
                        SELECT id, existencia_atual, data_embriovet, origem_externa, 
                               contentor_id, canister, andar
                        FROM estoque_dono
                        WHERE garanhao = %s AND dono_id = %s AND existencia_atual > 0
                        ORDER BY id DESC
                        LIMIT 1
                    """, (insemination_data['garanhao'], insemination_data['dono_id']))
                    
                    lote = cur.fetchone()
                    if lote and 'insem_linhas' not in st.session_state:
                        st.session_state['insem_linhas'] = {
                            str(lote[0]): {
                                'stock_id': lote[0],
                                'garanhao': insemination_data['garanhao'],
                                'ref': f"{lote[2] or lote[3]}",
                                'local': f"C{lote[4] or '?'} Can{lote[5] or '?'} A{lote[6] or '?'}",
                                'max_disponivel': int(lote[1]),
                                'qty': insemination_data['palhetas_gastas'],
                                'dono_id': insemination_data['dono_id'],
                                'proprietario_nome': insemination_data['proprietario_nome']
                            }
                        }
                cur.close()
        except Exception as e:
            st.error(f"Erro ao carregar dados da inseminação: {e}")
            st.session_state.pop('edit_insemination_id', None)
            edit_mode = False

    @st.dialog(t("insemination.success_title"), width="small")
    def show_success_dialog():
        st.markdown(t("insemination.success_msg"))
        if st.button(t("btn.ok"), type="primary", width="stretch"):
            # Limpar estado de edição
            st.session_state.pop('edit_insemination_id', None)
            # Limpar outros estados (incluindo observacoes e data)
            st.session_state["insem_linhas"] = {}
            st.session_state["insem_egua"] = ""
            st.session_state["insem_garanhao_principal"] = None
            st.session_state["insem_prop_principal"] = None
            st.session_state.pop("insem_observacoes", None)
            st.session_state.pop("insem_data", None)
            for k in list(st.session_state.keys()):
                if k.startswith("insem_modal_qtd_") or k.startswith("insem_step_") or k.startswith("insem_line_input_") or k.startswith("insem_modal_sel_"):
                    st.session_state.pop(k, None)
            st.session_state["insem_show_success"] = False
            st.rerun()

    if st.session_state["insem_show_success"]:
        show_success_dialog()

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
            "motilidade": int(to_py(row.get("motilidade")) or 0),
            "dose": to_py(row.get("dose")) or "—",
            "cor": to_py(row.get("cor")) or "",
            "concentracao": int(to_py(row.get("concentracao")) or 0),
            "protocolo": row.get("data_embriovet") or row.get("origem_externa") or "N/A",
            "max_disponivel": int(to_py(row.get("existencia_atual")) or 0),
        }

    def remover_linha(lote_id):
        sid = str(lote_id)
        linhas = st.session_state["insem_linhas"]
        linhas.pop(sid, None)
        st.session_state["insem_linhas"] = linhas
        st.session_state.pop(f"insem_line_input_{sid}", None)
        st.session_state.pop(f"insem_step_{sid}", None)

    stock_disponivel = stock[stock["existencia_atual"] > 0].copy() if not stock.empty else pd.DataFrame()
    if stock_disponivel.empty:
        st.warning(t("insemination.no_lotes_available"))
        return

    # Inicializar garanhao padrão se necessário
    if st.session_state["insem_garanhao_principal"] is None:
        garanhaos_unicos = sorted(stock_disponivel["garanhao"].dropna().unique())
        if garanhaos_unicos:
            st.session_state["insem_garanhao_principal"] = garanhaos_unicos[0]

    @st.dialog(t("insemination.select_lots_title"), width="large")
    def abrir_modal_lotes():
        # Usar filtros da página principal
        gar_sel = st.session_state.get("insem_garanhao_principal")
        prop_sel = st.session_state.get("insem_prop_principal")
        
        if not gar_sel:
            st.warning(t("warning.select_garanhao_first"))
            return
        
        # Filtrar lotes
        modal_df = stock_disponivel[stock_disponivel["garanhao"] == gar_sel].copy()
        if prop_sel:  # Se proprietário foi selecionado
            modal_df = modal_df[modal_df["proprietario_nome"] == prop_sel]

        if "data_embriovet" in modal_df.columns:
            modal_df["_ord"] = pd.to_datetime(modal_df["data_embriovet"], errors="coerce")
            modal_df = modal_df.sort_values("_ord", ascending=False)

        if modal_df.empty:
            st.info(t("insemination.no_lotes_for_filters"))
            return

        st.markdown(f"<div class='insem-modal-head'>{t('insemination.lotes')}</div>", unsafe_allow_html=True)

        header_cols = st.columns([2.0, 1.5, 1.8, 0.8, 0.6])
        with header_cols[0]:
            st.markdown(f"<div class='insem-modal-head'>{t('label.lote')}</div>", unsafe_allow_html=True)
        with header_cols[1]:
            st.markdown(f"<div class='insem-modal-head'>{t('label.location')}</div>", unsafe_allow_html=True)
        with header_cols[2]:
            st.markdown(f"<div class='insem-modal-head'>{t('label.characteristics')}</div>", unsafe_allow_html=True)
        with header_cols[3]:
            st.markdown(f"<div class='insem-modal-head'>{t('label.available')}</div>", unsafe_allow_html=True)
        with header_cols[4]:
            st.markdown(f"<div class='insem-modal-head'>{t('btn.select')}</div>", unsafe_allow_html=True)

        for _, row in modal_df.iterrows():
            lote = lote_payload(row)
            sid = lote["stock_id"]

            row_cols = st.columns([2.0, 1.5, 1.8, 0.8, 0.6])
            with row_cols[0]:
                st.caption(f"{lote['ref']}")
            with row_cols[1]:
                st.caption(lote["local"])
            with row_cols[2]:
                # Motilidade, Dose, Cor, Concentração
                caracteristicas = []
                caracteristicas.append(f"M {lote['motilidade']}%")
                caracteristicas.append(f"D {lote['dose']}")
                if lote.get('cor'):
                    caracteristicas.append(f"Cor: {lote['cor']}")
                if lote.get('concentracao') and lote.get('concentracao') > 0:
                    caracteristicas.append(f"{lote['concentracao']}M/ml")
                st.caption(" · ".join(caracteristicas))
            with row_cols[3]:
                st.caption(t("insemination.available_value", value=lote['max_disponivel']))
            with row_cols[4]:
                sel_key = f"insem_modal_sel_{sid}"
                default_checked = bool(st.session_state.get(sel_key, False) or str(sid) in st.session_state["insem_linhas"])
                st.checkbox(
                    t("btn.select"),
                    key=sel_key,
                    value=default_checked,
                    label_visibility="collapsed",
                )

        b1, b2 = st.columns([2, 1])
        with b1:
            if st.button(t("btn.confirm_selection"), type="primary", key="insem_modal_confirmar", width="stretch"):
                selecionados_ids = []
                for key, val in st.session_state.items():
                    if key.startswith("insem_modal_sel_") and val:
                        try:
                            selecionados_ids.append(int(key.split("insem_modal_sel_")[-1]))
                        except Exception:
                            continue

                if not selecionados_ids:
                    st.warning(t("warning.select_one_lot"))
                    return

                selecionados_df = stock_disponivel[stock_disponivel["id"].isin(selecionados_ids)].copy()
                if selecionados_df.empty:
                    st.warning(t("insemination.no_lotes_selected"))
                    return

                linhas = st.session_state["insem_linhas"]
                for _, row in selecionados_df.iterrows():
                    lote = lote_payload(row)
                    sid = str(lote["stock_id"])
                    if sid not in linhas:
                        linhas[sid] = {
                            **lote,
                            "qty": 1,
                        }

                st.session_state["insem_linhas"] = linhas
                st.rerun()
        with b2:
            if st.button(t("btn.close"), key="insem_modal_cancelar", width="stretch"):
                st.rerun()

    # PÁGINA PRINCIPAL - NOVO FLUXO
    render_zone_title(t("insemination.zone_selection"), "insem-zone-title")
    
    # 1. CAVALO
    garanhaos_disponiveis = sorted(stock_disponivel["garanhao"].dropna().unique())
    idx_gar = 0
    if st.session_state["insem_garanhao_principal"] and st.session_state["insem_garanhao_principal"] in garanhaos_disponiveis:
        idx_gar = garanhaos_disponiveis.index(st.session_state["insem_garanhao_principal"])
    
    garanhao_selecionado = st.selectbox(
        t("label.garanhao"),
        garanhaos_disponiveis,
        index=idx_gar,
        key="insem_garanhao_main"
    )
    
    # Se mudou o cavalo, limpar seleção de proprietário e lotes
    if garanhao_selecionado != st.session_state["insem_garanhao_principal"]:
        st.session_state["insem_garanhao_principal"] = garanhao_selecionado
        st.session_state["insem_prop_principal"] = None
        st.session_state["insem_linhas"] = {}
        st.rerun()
    
    # 2. PROPRIETÁRIO (filtrado pelo cavalo)
    stock_cavalo = stock_disponivel[stock_disponivel["garanhao"] == garanhao_selecionado]
    proprietarios_com_stock = sorted(stock_cavalo["proprietario_nome"].dropna().unique())
    prop_opts = [t("common.all")] + proprietarios_com_stock
    
    idx_prop = 0
    if st.session_state["insem_prop_principal"] and st.session_state["insem_prop_principal"] in proprietarios_com_stock:
        idx_prop = prop_opts.index(st.session_state["insem_prop_principal"])
    
    proprietario_selecionado = st.selectbox(
        t("label.owner"),
        prop_opts,
        index=idx_prop,
        key="insem_prop_main"
    )
    
    # Atualizar estado do proprietário
    if proprietario_selecionado == t("common.all"):
        st.session_state["insem_prop_principal"] = None
    else:
        if proprietario_selecionado != st.session_state["insem_prop_principal"]:
            st.session_state["insem_prop_principal"] = proprietario_selecionado
            st.session_state["insem_linhas"] = {}  # Limpar lotes ao mudar proprietário
            st.rerun()
    
    # 3. BOTÃO SELECIONAR LOTES
    if st.button(t("btn.select_lots"), key="insem_btn_open_modal", type="secondary", width="stretch"):
        abrir_modal_lotes()
    
    st.markdown("---")
    
    # 4. LOTES SELECIONADOS COM QUANTIDADE EDITÁVEL
    render_zone_title(t("insemination.lines_title"), "insem-zone-title")
    linhas = st.session_state["insem_linhas"]

    if not linhas:
        st.info(t("insemination.no_lotes_selected_hint"))
    else:
        for sid in list(linhas.keys()):
            linha = linhas[sid]
            max_disp = int(linha.get("max_disponivel", 0))
            qtd = int(linha.get("qty", 0))

            st.markdown("<div class='insem-line'>", unsafe_allow_html=True)
            step_key = f"insem_step_{sid}"
            # Apenas inicializar se não existir
            if step_key not in st.session_state:
                st.session_state[step_key] = qtd

            l1, l2, linput, l4 = st.columns([3.0, 1.5, 1.9, 0.8])
            with l1:
                st.markdown(f"<div class='insem-lote-main'>{linha['ref']} · {linha['local']}</div>", unsafe_allow_html=True)
                st.markdown(
                    f"<div class='insem-lote-sub'>{linha['proprietario_nome']} · {t('insemination.available_inline', value=max_disp)}</div>",
                    unsafe_allow_html=True,
                )
            with l2:
                st.markdown(f"<div class='insem-lote-sub'>{t('label.quantity')}</div>", unsafe_allow_html=True)

            # Campo de input digitável (sem botões +/- extras)
            with linput:
                new_qtd = st.number_input(
                    "Quantidade",
                    min_value=0,
                    max_value=max_disp,
                    step=1,
                    key=step_key,
                    label_visibility="collapsed",
                )
                qtd_val = new_qtd

            if qtd_val != qtd:
                if qtd_val == 0:
                    linhas.pop(sid, None)
                    st.session_state.pop(step_key, None)
                else:
                    linhas[sid]["qty"] = int(qtd_val)
                st.session_state["insem_linhas"] = linhas

            with l4:
                st.button(
                    t("btn.remove"),
                    key=f"insem_line_remove_{sid}",
                    width="stretch",
                    on_click=remover_linha,
                    args=(sid,),
                )
            st.markdown("</div>", unsafe_allow_html=True)

        badd1, badd2 = st.columns([2, 2])
        with badd1:
            if st.button(t("btn.add_line"), key="insem_btn_add_line", width="stretch"):
                abrir_modal_lotes()
        with badd2:
            total_palhetas = sum(int(v.get("qty", 0)) for v in linhas.values())
            st.markdown(
                f"<div class='insem-lote-main'>{t('label.total')}: {total_palhetas} {t('label.straws')}</div>",
                unsafe_allow_html=True,
            )
    
    st.markdown("---")
    
    # 5. ÉGUA, DATA E OBSERVAÇÕES
    render_zone_title(t("insemination.zone_details"), "insem-zone-title")
    c1, c2 = st.columns(2)
    with c1:
        egua = st.text_input(t("label.mare"), key="insem_egua")
    with c2:
        data_insem = st.date_input(t("label.insemination_date"), key="insem_data")
    
    observacoes = st.text_area(
        "Observações",
        key="insem_observacoes",
        placeholder="Notas adicionais sobre esta inseminação (opcional)...",
        height=80,
    )
    
    # RESUMO E BOTÃO FINAL
    total_palhetas = sum(int(v.get("qty", 0)) for v in linhas.values())
    total_linhas = sum(1 for v in linhas.values() if int(v.get("qty", 0)) > 0)
    st.markdown(
        f"""
        <div class='insem-summary-bar'>
            <div class='insem-summary-item'>
                <span class='insem-summary-label'>Total palhetas</span>
                <span class='insem-summary-value'>{total_palhetas}</span>
            </div>
            <div class='insem-summary-item'>
                <span class='insem-summary-label'>Lotes</span>
                <span class='insem-summary-value'>{total_linhas}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")
    btn_text = "🔄 Atualizar Inseminação" if edit_mode else t("btn.register_insemination")
    if st.button(btn_text, type="primary", key="btn_registrar_insem_final", width="stretch"):
        linhas_finais = [v for v in st.session_state["insem_linhas"].values() if int(v.get("qty", 0)) > 0]
        if not linhas_finais:
            st.error(t("error.select_lot_line"))
        elif not egua:
            st.error(t("error.mare_required"))
        else:
            registros = []
            for l in linhas_finais:
                registros.append(
                    {
                        "garanhao": l.get("garanhao"),
                        "dono_id": l.get("dono_id"),
                        "protocolo": l.get("protocolo"),
                        "palhetas": int(l.get("qty", 0)),
                        "stock_id": int(l.get("stock_id")),
                    }
                )

            ok = registrar_inseminacao_multiplas(
                registros, 
                data_insem, 
                egua, 
                insemination_data['id'] if edit_mode and insemination_data else None,
                observacoes=observacoes or None
            )
            if ok:
                # Limpar modo de edição
                st.session_state.pop('edit_insemination_id', None)
                st.session_state["insem_show_success"] = True
                st.rerun()
