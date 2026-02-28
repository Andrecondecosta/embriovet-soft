import pandas as pd
import streamlit as st


def run_insemination_page(ctx):
    globals().update(ctx)

    st.header("Registrar Inseminação")
    inject_stepper_css()

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
    if "insem_garanhao_modal" not in st.session_state:
        st.session_state["insem_garanhao_modal"] = None
    if "insem_prop_modal" not in st.session_state:
        st.session_state["insem_prop_modal"] = "Todos"

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
        st.warning("Nenhum lote disponível para inseminação.")
        return

    if st.session_state["insem_garanhao_modal"] is None:
        st.session_state["insem_garanhao_modal"] = sorted(stock_disponivel["garanhao"].dropna().unique())[0]

    @st.dialog("Selecionar lotes", width="large")
    def abrir_modal_lotes():
        st.markdown("<div class='insem-modal-head'>Filtros</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            gar_opts = sorted(stock_disponivel["garanhao"].dropna().unique())
            idx_g = gar_opts.index(st.session_state["insem_garanhao_modal"]) if st.session_state["insem_garanhao_modal"] in gar_opts else 0
            gar_sel = st.selectbox("Garanhão", gar_opts, index=idx_g, key="insem_modal_garanhao")
        with c2:
            base_prop = stock_disponivel[stock_disponivel["garanhao"] == gar_sel]
            prop_opts = ["Todos"] + sorted(base_prop["proprietario_nome"].dropna().unique())
            idx_p = prop_opts.index(st.session_state.get("insem_prop_modal", "Todos")) if st.session_state.get("insem_prop_modal", "Todos") in prop_opts else 0
            prop_sel = st.selectbox("Proprietário", prop_opts, index=idx_p, key="insem_modal_prop")

        st.session_state["insem_garanhao_modal"] = gar_sel
        st.session_state["insem_prop_modal"] = prop_sel

        modal_df = stock_disponivel[stock_disponivel["garanhao"] == gar_sel].copy()
        if prop_sel != "Todos":
            modal_df = modal_df[modal_df["proprietario_nome"] == prop_sel]

        if "data_embriovet" in modal_df.columns:
            modal_df["_ord"] = pd.to_datetime(modal_df["data_embriovet"], errors="coerce")
            modal_df = modal_df.sort_values("_ord", ascending=False)

        if modal_df.empty:
            st.info("Sem lotes para os filtros selecionados.")
            return

        st.markdown("<div class='insem-modal-head'>Lotes</div>", unsafe_allow_html=True)

        header_cols = st.columns([2.4, 1.8, 1.2, 0.8, 0.6])
        with header_cols[0]:
            st.markdown("<div class='insem-modal-head'>Lote</div>", unsafe_allow_html=True)
        with header_cols[1]:
            st.markdown("<div class='insem-modal-head'>Localização</div>", unsafe_allow_html=True)
        with header_cols[2]:
            st.markdown("<div class='insem-modal-head'>Motilidade / Dose</div>", unsafe_allow_html=True)
        with header_cols[3]:
            st.markdown("<div class='insem-modal-head'>Disponível</div>", unsafe_allow_html=True)
        with header_cols[4]:
            st.markdown("<div class='insem-modal-head'>Selecionar</div>", unsafe_allow_html=True)

        for _, row in modal_df.iterrows():
            lote = lote_payload(row)
            sid = lote["stock_id"]

            row_cols = st.columns([2.4, 1.8, 1.2, 0.8, 0.6])
            with row_cols[0]:
                st.caption(f"{lote['ref']}")
            with row_cols[1]:
                st.caption(lote["local"])
            with row_cols[2]:
                st.caption(f"M {lote['motilidade']}% · D {lote['dose']}")
            with row_cols[3]:
                st.caption(f"Disp {lote['max_disponivel']}")
            with row_cols[4]:
                sel_key = f"insem_modal_sel_{sid}"
                default_checked = bool(st.session_state.get(sel_key, False) or str(sid) in st.session_state["insem_linhas"])
                st.checkbox(
                    "Selecionar",
                    key=sel_key,
                    value=default_checked,
                    label_visibility="collapsed",
                )

        b1, b2 = st.columns([2, 1])
        with b1:
            if st.button("Confirmar seleção", type="primary", key="insem_modal_confirmar", width="stretch"):
                selecionados_ids = []
                for key, val in st.session_state.items():
                    if key.startswith("insem_modal_sel_") and val:
                        try:
                            selecionados_ids.append(int(key.split("insem_modal_sel_")[-1]))
                        except Exception:
                            continue

                if not selecionados_ids:
                    st.warning("Selecione pelo menos um lote.")
                    return

                selecionados_df = stock_disponivel[stock_disponivel["id"].isin(selecionados_ids)].copy()
                if selecionados_df.empty:
                    st.warning("Nenhum lote selecionado disponível.")
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
            if st.button("Fechar", key="insem_modal_cancelar", width="stretch"):
                st.rerun()

    render_zone_title("Zona de seleção", "insem-zone-title")
    csel1, csel2, csel3 = st.columns([2, 2, 1.5])
    with csel1:
        data_insem = st.date_input("Data da inseminação", key="insem_data")
    with csel2:
        egua = st.text_input("Égua *", key="insem_egua")
    with csel3:
        if st.button("Selecionar lotes", key="insem_btn_open_modal", width="stretch"):
            abrir_modal_lotes()

    render_zone_title("Linhas da inseminação", "insem-zone-title")
    linhas = st.session_state["insem_linhas"]

    if not linhas:
        st.info("Nenhum lote selecionado. Clique em 'Selecionar lotes'.")
    else:
        for sid in list(linhas.keys()):
            linha = linhas[sid]
            max_disp = int(linha.get("max_disponivel", 0))
            qtd = int(linha.get("qty", 0))

            st.markdown("<div class='insem-line'>", unsafe_allow_html=True)
            step_key = f"insem_step_{sid}"
            if step_key not in st.session_state:
                st.session_state[step_key] = qtd

            l1, l2, lval, lminus, lplus, l4 = st.columns([3.0, 1.1, 0.7, 0.5, 0.5, 0.8])
            with l1:
                st.markdown(f"<div class='insem-lote-main'>{linha['ref']} · {linha['local']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='insem-lote-sub'>{linha['proprietario_nome']} · Disp {max_disp}</div>", unsafe_allow_html=True)
            with l2:
                qtd_display = int(st.session_state.get(step_key, qtd) or 0)
                st.markdown(f"<div class='insem-lote-sub'>Qtd</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='insem-lote-main'>{qtd_display}</div>", unsafe_allow_html=True)

            qtd_val, _ = render_stepper(
                [lval, lminus, lplus],
                step_key,
                min_value=0,
                max_value=max_disp,
            )

            if qtd_val != qtd:
                if qtd_val == 0:
                    linhas.pop(sid, None)
                    st.session_state.pop(step_key, None)
                else:
                    linhas[sid]["qty"] = int(qtd_val)
                st.session_state["insem_linhas"] = linhas

            with l4:
                st.button(
                    "✕",
                    key=f"insem_line_remove_{sid}",
                    width="stretch",
                    on_click=remover_linha,
                    args=(sid,),
                )
            st.markdown("</div>", unsafe_allow_html=True)

        badd1, badd2 = st.columns([2, 2])
        with badd1:
            if st.button("Adicionar linha", key="insem_btn_add_line", width="stretch"):
                abrir_modal_lotes()
        with badd2:
            total_palhetas = sum(int(v.get("qty", 0)) for v in linhas.values())
            st.markdown(f"<div class='insem-lote-main'>Total: {total_palhetas} palhetas</div>", unsafe_allow_html=True)

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
    if st.button("Registrar inseminação", type="primary", key="btn_registrar_insem_final", width="stretch"):
        linhas_finais = [v for v in st.session_state["insem_linhas"].values() if int(v.get("qty", 0)) > 0]
        if not linhas_finais:
            st.error("Selecione pelo menos uma linha de lote.")
        elif not egua:
            st.error("Nome da égua é obrigatório.")
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

            ok = registrar_inseminacao_multiplas(registros, data_insem, egua)
            if ok:
                st.success("Inseminação registrada com sucesso.")
                st.session_state["insem_linhas"] = {}
                st.rerun()
