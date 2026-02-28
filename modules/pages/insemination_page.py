# Módulo: Registrar Inseminação - Design Técnico Consistente

def run_insemination_page(ctx: dict):
    """
    Página redesenhada para registrar inseminação.
    Layout: Contexto → Tabela de linhas (dominante) → Ações
    """
    globals().update(ctx)
    
    inject_insemination_css()
    
    # Estado da sessão
    if "insem_linhas" not in st.session_state:
        st.session_state["insem_linhas"] = {}
    if "insem_garanhao_modal" not in st.session_state:
        st.session_state["insem_garanhao_modal"] = None
    if "insem_prop_modal" not in st.session_state:
        st.session_state["insem_prop_modal"] = "Todos"
    
    # Dados disponíveis
    stock_disponivel = stock[stock["existencia_atual"] > 0].copy() if not stock.empty else pd.DataFrame()
    
    if stock_disponivel.empty:
        st.warning("ℹ️ Nenhum lote disponível para inseminação.")
        return
    
    # Inicializar garanhão modal
    if st.session_state["insem_garanhao_modal"] is None:
        st.session_state["insem_garanhao_modal"] = sorted(stock_disponivel["garanhao"].dropna().unique())[0]
    
    # ============================================================
    # FUNÇÕES AUXILIARES
    # ============================================================
    
    def lote_ref(row):
        """Retorna a referência do lote"""
        return row.get("origem_externa") or row.get("data_embriovet") or f"Lote #{row.get('id')}"
    
    def lote_local(row):
        """Retorna a localização formatada"""
        contentor = row.get("contentor_codigo") or row.get("local_armazenagem") or "SEM-CONTENTOR"
        can = row.get("canister")
        andr = row.get("andar")
        if pd.notna(can) and pd.notna(andr):
            return f"{contentor} | C{int(can)} | {int(andr)}º"
        return str(contentor)
    
    def lote_payload(row):
        """Cria payload do lote"""
        return {
            "stock_id": int(row.get("id")),
            "garanhao": row.get("garanhao"),
            "dono_id": to_py(row.get("dono_id")),
            "proprietario_nome": row.get("proprietario_nome") or "—",
            "ref": lote_ref(row),
            "local": lote_local(row),
            "motilidade": int(to_py(row.get("motilidade")) or 0),
            "dose": to_py(row.get("dose")) or "—",
            "protocolo": row.get("data_embriovet") or row.get("origem_externa") or "N/A",
            "max_disponivel": int(to_py(row.get("existencia_atual")) or 0),
        }
    
    def limpar_qtd_modal(ids_validos):
        """Limpa quantidades do modal"""
        for sid in ids_validos:
            key = f"insem_modal_qtd_{sid}"
            if key in st.session_state:
                st.session_state[key] = 0
    
    # ============================================================
    # MODAL DE SELEÇÃO DE LOTES (Vista de Inventário)
    # ============================================================
    
    @st.dialog("Inventário", width="large")
    def abrir_modal_lotes():
        """Modal redesenhado como vista de inventário técnico"""
        
        # Filtros compactos numa linha horizontal
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            gar_opts = sorted(stock_disponivel["garanhao"].dropna().unique())
            idx_g = gar_opts.index(st.session_state["insem_garanhao_modal"]) if st.session_state["insem_garanhao_modal"] in gar_opts else 0
            gar_sel = st.selectbox("Garanhão", gar_opts, index=idx_g, key="insem_modal_garanhao", label_visibility="collapsed", help="Filtrar por garanhão")
        with c2:
            base_prop = stock_disponivel[stock_disponivel["garanhao"] == gar_sel]
            prop_opts = ["Todos"] + sorted(base_prop["proprietario_nome"].dropna().unique())
            idx_p = prop_opts.index(st.session_state.get("insem_prop_modal", "Todos")) if st.session_state.get("insem_prop_modal", "Todos") in prop_opts else 0
            prop_sel = st.selectbox("Proprietário", prop_opts, index=idx_p, key="insem_modal_prop", label_visibility="collapsed", help="Filtrar por proprietário")
        with c3:
            st.markdown("<div style='padding-top:.35rem; font-size:.75rem; color:#64748b; text-transform:uppercase;'>Lotes Disponíveis</div>", unsafe_allow_html=True)
        
        st.session_state["insem_garanhao_modal"] = gar_sel
        st.session_state["insem_prop_modal"] = prop_sel
        
        # Filtrar dados
        modal_df = stock_disponivel[stock_disponivel["garanhao"] == gar_sel].copy()
        if prop_sel != "Todos":
            modal_df = modal_df[modal_df["proprietario_nome"] == prop_sel]
        
        if "data_embriovet" in modal_df.columns:
            modal_df["_ord"] = pd.to_datetime(modal_df["data_embriovet"], errors="coerce")
            modal_df = modal_df.sort_values("_ord", ascending=False)
        
        if modal_df.empty:
            st.info("ℹ️ Sem lotes para os filtros selecionados.")
            return
        
        # Cabeçalho da tabela técnica
        st.markdown(
            """
            <div style='display:flex; gap:.5rem; padding:.4rem .5rem; background:#f1f5f9; 
                        border-radius:6px; font-size:.7rem; font-weight:700; 
                        text-transform:uppercase; color:#64748b; margin:.5rem 0;'>
                <div style='flex:2.2;'>Lote</div>
                <div style='flex:1.6;'>Localização</div>
                <div style='flex:0.9;'>Motil.</div>
                <div style='flex:0.8;'>Dose</div>
                <div style='flex:0.9;'>Disp.</div>
                <div style='flex:1.8; text-align:center;'>Qtd a usar</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Linhas da tabela densa
        lote_ids = []
        for _, row in modal_df.iterrows():
            lote = lote_payload(row)
            sid = lote["stock_id"]
            lote_ids.append(sid)
            
            existente = st.session_state["insem_linhas"].get(str(sid), {}).get("qty", 0)
            restante = max(0, lote["max_disponivel"] - int(existente))
            
            q_key = f"insem_modal_qtd_{sid}"
            if q_key not in st.session_state:
                st.session_state[q_key] = 0
            if st.session_state[q_key] > restante:
                st.session_state[q_key] = restante
            
            row_cols = st.columns([2.2, 1.6, 0.9, 0.8, 0.9, 1.8])
            with row_cols[0]:
                st.markdown(f"<div style='font-size:.8rem; padding-top:.35rem;'>{lote['ref']}</div>", unsafe_allow_html=True)
            with row_cols[1]:
                st.markdown(f"<div style='font-size:.75rem; color:#64748b; padding-top:.4rem;'>{lote['local']}</div>", unsafe_allow_html=True)
            with row_cols[2]:
                st.markdown(f"<div style='font-size:.75rem; padding-top:.4rem;'>{lote['motilidade']}%</div>", unsafe_allow_html=True)
            with row_cols[3]:
                st.markdown(f"<div style='font-size:.75rem; padding-top:.4rem;'>{lote['dose']}</div>", unsafe_allow_html=True)
            with row_cols[4]:
                st.markdown(f"<div style='font-size:.75rem; padding-top:.4rem;'>{restante}</div>", unsafe_allow_html=True)
            with row_cols[5]:
                q1, q2, q3 = st.columns([1, 1, 1])
                with q1:
                    if st.button("−", key=f"insem_mod_minus_{sid}", use_container_width=True, disabled=st.session_state[q_key] <= 0):
                        st.session_state[q_key] = max(0, int(st.session_state[q_key]) - 1)
                        st.rerun()
                with q2:
                    st.markdown(f"<div style='text-align:center; padding-top:.35rem; font-size:.85rem; font-weight:600;'>{int(st.session_state[q_key])}</div>", unsafe_allow_html=True)
                with q3:
                    if st.button("+", key=f"insem_mod_plus_{sid}", use_container_width=True, disabled=int(st.session_state[q_key]) >= restante):
                        st.session_state[q_key] = min(restante, int(st.session_state[q_key]) + 1)
                        st.rerun()
        
        # Footer técnico com ações discretas
        st.markdown("<div style='height:.5rem;'></div>", unsafe_allow_html=True)
        b1, b2, b3 = st.columns([1, 1, 2])
        with b1:
            if st.button("Confirmar", type="primary", key="insem_modal_usar", use_container_width=True):
                selecionados = []
                for _, row in modal_df.iterrows():
                    sid = int(row.get("id"))
                    qty = int(st.session_state.get(f"insem_modal_qtd_{sid}", 0) or 0)
                    if qty > 0:
                        selecionados.append((lote_payload(row), qty))
                
                if not selecionados:
                    st.warning("⚠️ Selecione pelo menos um lote.")
                    return
                
                linhas = st.session_state["insem_linhas"]
                for lote, qtd_add in selecionados:
                    sid = str(lote["stock_id"])
                    qtd_existente = int(linhas.get(sid, {}).get("qty", 0))
                    nova_qtd = qtd_existente + qtd_add
                    if nova_qtd > lote["max_disponivel"]:
                        st.error(f"❌ Quantidade excede o disponível para {lote['ref']}")
                        return
                
                for lote, qtd_add in selecionados:
                    sid = str(lote["stock_id"])
                    if sid in linhas:
                        linhas[sid]["qty"] = int(linhas[sid]["qty"]) + qtd_add
                    else:
                        linhas[sid] = {**lote, "qty": int(qtd_add)}
                
                limpar_qtd_modal(lote_ids)
                st.session_state["insem_linhas"] = linhas
                st.rerun()
        with b2:
            if st.button("Fechar", key="insem_modal_cancelar", use_container_width=True):
                st.rerun()
        with b3:
            st.markdown("<div style='padding-top:.5rem; font-size:.75rem; color:#64748b; text-align:right;'>Selecione lotes e confirme</div>", unsafe_allow_html=True)
    
    # ============================================================
    # ZONA 1: CONTEXTO (Data + Égua) - Compacto e Horizontal
    # ============================================================
    
    st.header("Registrar Consumo de Stock")
    render_zone_title("Contexto da inseminação", "insem-zone-title")
    
    csel1, csel2 = st.columns([1, 2])
    with csel1:
        data_insem = st.date_input("Data", key="insem_data", label_visibility="collapsed", help="Data da inseminação")
    with csel2:
        egua = st.text_input("Égua *", key="insem_egua", placeholder="Nome da égua", label_visibility="collapsed")
    
    # ============================================================
    # ZONA 2: TABELA DE LINHAS DA INSEMINAÇÃO (Elemento Dominante)
    # ============================================================
    
    render_zone_title("Lotes selecionados", "insem-zone-title")
    
    linhas = st.session_state["insem_linhas"]
    
    if not linhas:
        # Estado vazio discreto (linha informativa)
        st.markdown(
            """
            <div style='padding:.6rem 1rem; background:#f8fafc; border:1px solid #e2e8f0; 
                        border-radius:6px; font-size:.8rem; color:#64748b; text-align:center;'>
                Nenhum lote selecionado. Use o botão abaixo para adicionar.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        # Cabeçalho da tabela técnica (consistente com Ver Stock)
        st.markdown(
            """
            <div style='display:flex; gap:.5rem; padding:.4rem .5rem; background:#f1f5f9; 
                        border-radius:6px 6px 0 0; font-size:.7rem; font-weight:700; 
                        text-transform:uppercase; color:#64748b;'>
                <div style='flex:2.5;'>Lote</div>
                <div style='flex:2;'>Localização</div>
                <div style='flex:1;'>Disponível</div>
                <div style='flex:1.5;'>Quantidade</div>
                <div style='flex:0.6;'></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Linhas da tabela
        for sid in list(linhas.keys()):
            linha = linhas[sid]
            max_disp = int(linha.get("max_disponivel", 0))
            qtd = int(linha.get("qty", 0))
            
            st.markdown(
                """
                <div style='display:flex; gap:.5rem; padding:.5rem .5rem; background:#ffffff; 
                            border:1px solid #e2e8f0; border-top:none; font-size:.8rem;'>
                """,
                unsafe_allow_html=True,
            )
            
            l1, l2, l3, l4, l5 = st.columns([2.5, 2, 1, 1.5, 0.6])
            with l1:
                st.markdown(f"<div style='padding-top:.25rem; font-weight:600;'>{linha['ref']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:.7rem; color:#64748b;'>{linha['proprietario_nome']}</div>", unsafe_allow_html=True)
            with l2:
                st.markdown(f"<div style='padding-top:.35rem; font-size:.75rem; color:#64748b;'>{linha['local']}</div>", unsafe_allow_html=True)
            with l3:
                st.markdown(f"<div style='padding-top:.35rem; font-size:.75rem;'>{max_disp}</div>", unsafe_allow_html=True)
            with l4:
                novo_qtd = st.number_input(
                    "Qtd",
                    min_value=0,
                    max_value=max(max_disp, 0),
                    value=qtd,
                    step=1,
                    key=f"insem_line_input_{sid}",
                    label_visibility="collapsed",
                )
                if int(novo_qtd) != qtd:
                    if int(novo_qtd) == 0:
                        del linhas[sid]
                    else:
                        linhas[sid]["qty"] = int(novo_qtd)
                    st.session_state["insem_linhas"] = linhas
                    st.rerun()
            with l5:
                if st.button("✕", key=f"insem_line_remove_{sid}", use_container_width=True, help="Remover lote"):
                    del linhas[sid]
                    st.session_state["insem_linhas"] = linhas
                    st.rerun()
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        # Footer da tabela com total
        total_palhetas = sum(int(v.get("qty", 0)) for v in linhas.values())
        st.markdown(
            f"""
            <div style='padding:.5rem .5rem; background:#f8fafc; border:1px solid #e2e8f0; 
                        border-top:none; border-radius:0 0 6px 6px; font-size:.8rem; 
                        font-weight:600; text-align:right; color:#0f172a;'>
                Total: {total_palhetas} palhetas
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    # Botão discreto para adicionar mais lotes
    st.markdown("<div style='height:.5rem;'></div>", unsafe_allow_html=True)
    if st.button("+ Adicionar lotes", key="insem_btn_add_line"):
        abrir_modal_lotes()
    
    # ============================================================
    # ZONA 3: AÇÕES DISCRETAS NO FINAL
    # ============================================================
    
    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
    render_zone_title("Finalizar registo", "insem-zone-title")
    
    c_action1, c_action2, c_action3 = st.columns([1, 1, 2])
    with c_action1:
        if st.button("Confirmar Inseminação", type="primary", key="btn_registrar_insem_final", use_container_width=True):
            linhas_finais = [v for v in st.session_state["insem_linhas"].values() if int(v.get("qty", 0)) > 0]
            if not linhas_finais:
                st.error("❌ Selecione pelo menos um lote.")
            elif not egua:
                st.error("❌ Nome da égua é obrigatório.")
            else:
                registros = []
                for l in linhas_finais:
                    registros.append({
                        "garanhao": l.get("garanhao"),
                        "dono_id": l.get("dono_id"),
                        "protocolo": l.get("protocolo"),
                        "palhetas": int(l.get("qty", 0)),
                        "stock_id": int(l.get("stock_id")),
                    })
                
                ok = registrar_inseminacao_multiplas(registros, data_insem, egua)
                if ok:
                    st.success("✅ Inseminação registrada com sucesso.")
                    st.session_state["insem_linhas"] = {}
                    st.rerun()
    with c_action2:
        if st.button("Limpar seleção", key="insem_btn_limpar", use_container_width=True):
            st.session_state["insem_linhas"] = {}
            st.rerun()
    with c_action3:
        st.markdown("<div style='padding-top:.5rem; font-size:.75rem; color:#64748b; text-align:right;'>Verifique os dados antes de confirmar</div>", unsafe_allow_html=True)


def inject_insemination_css():
    """Injeta CSS técnico e consistente para a página de inseminação"""
    import streamlit as st
    st.markdown(
        """
        <style>
            .insem-zone-title {
                font-size: .78rem;
                text-transform: uppercase;
                letter-spacing: .05em;
                color: #64748b;
                margin: 1rem 0 .5rem 0;
                font-weight: 700;
                border-bottom: 1px solid #e2e8f0;
                padding-bottom: .3rem;
            }
            
            /* Botões discretos e consistentes */
            .stButton button {
                font-size: .8rem;
                padding: .4rem .8rem;
                border-radius: 6px;
            }
            
            /* Inputs compactos */
            .stDateInput, .stTextInput, .stNumberInput {
                font-size: .85rem;
            }
            
            /* Remover espaçamento extra */
            .block-container {
                padding-top: 2rem;
                padding-bottom: 1rem;
            }
            
            /* Consistência com outras páginas */
            div[data-testid="stExpander"] {
                border: 1px solid #e2e8f0;
                border-radius: 6px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
