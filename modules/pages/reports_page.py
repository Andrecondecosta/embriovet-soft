import pandas as pd


def _filtrar_stock_por_periodo(df, data_inicio, data_fim):
    if df.empty:
        return df

    col_data = "data_criacao" if "data_criacao" in df.columns else "data_embriovet"
    if col_data not in df.columns:
        return df

    out = df.copy()
    out[col_data] = pd.to_datetime(out[col_data], errors="coerce")
    if data_inicio:
        out = out[out[col_data] >= pd.to_datetime(data_inicio)]
    if data_fim:
        out = out[out[col_data] <= pd.to_datetime(data_fim)]
    return out


def run_reports_page(ctx: dict):
    st = ctx["st"]
    to_py = ctx["to_py"]
    inject_reports_css = ctx["inject_reports_css"]
    render_zone_title = ctx["render_zone_title"]
    render_kpi_strip = ctx["render_kpi_strip"]
    safe_pick = ctx["safe_pick"]
    carregar_stock = ctx["carregar_stock"]
    carregar_inseminacoes = ctx["carregar_inseminacoes"]
    carregar_transferencias = ctx["carregar_transferencias"]
    carregar_transferencias_externas = ctx["carregar_transferencias_externas"]
    carregar_proprietarios = ctx["carregar_proprietarios"]
    carregar_contentores = ctx["carregar_contentores"]
    aplicar_filtro_data = ctx["aplicar_filtro_data"]
    gerar_pdf_garanhao = ctx["gerar_pdf_garanhao"]

    st.header("Relatórios")
    inject_reports_css()

    stock = carregar_stock()
    insem = carregar_inseminacoes()
    transf = carregar_transferencias()
    transf_ext = carregar_transferencias_externas()
    proprietarios = carregar_proprietarios()
    contentores = carregar_contentores()

    render_zone_title("Zona de seleção")
    modo = st.radio(
        "Tipo de análise",
        ["Garanhão", "Proprietário", "Contentor / Localização", "Histórico Geral"],
        horizontal=True,
        label_visibility="collapsed",
        key="rel_modo",
    )

    garanhao_sel = None
    prop_sel = None
    contentor_sel = None
    tipo_hist = None

    if modo == "Garanhão" and not stock.empty:
        garanhao_sel = st.selectbox("Selecionar garanhão", sorted(stock["garanhao"].dropna().unique()), key="rel_sel_g")
    elif modo == "Proprietário" and not proprietarios.empty:
        prop_sel = st.selectbox(
            "Selecionar proprietário",
            proprietarios["id"].tolist(),
            format_func=lambda x: proprietarios[proprietarios["id"] == x]["nome"].values[0],
            key="rel_sel_p",
        )
    elif modo == "Contentor / Localização" and not contentores.empty:
        contentor_sel = st.selectbox(
            "Selecionar contentor",
            contentores["id"].tolist(),
            format_func=lambda x: contentores[contentores["id"] == x]["codigo"].values[0],
            key="rel_sel_c",
        )
    elif modo == "Histórico Geral":
        tipo_hist = st.radio(
            "Tipo de histórico",
            ["Inseminações", "Transferências Internas", "Transferências Externas", "Stock Completo"],
            horizontal=True,
            label_visibility="collapsed",
            key="rel_tipo_hist",
        )

    render_zone_title("Zona de filtros")
    filtros = {}
    with st.expander("Filtros de análise", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            usar_periodo = st.checkbox("Aplicar período", value=False, key="rel_periodo_flag")
        with c2:
            data_inicio = st.date_input("Data início", value=None, key="rel_periodo_ini") if usar_periodo else None
        with c3:
            data_fim = st.date_input("Data fim", value=None, key="rel_periodo_fim") if usar_periodo else None

        if data_inicio and data_fim and data_inicio > data_fim:
            st.warning("Período inválido")
            data_inicio, data_fim = None, None

        if modo == "Garanhão" and garanhao_sel:
            base = stock[stock["garanhao"] == garanhao_sel]
            filtros["prop"] = st.multiselect("Proprietários", sorted(base["proprietario_nome"].dropna().unique()) if not base.empty else [], key="rel_f_g_prop")
        elif modo == "Proprietário" and prop_sel:
            base = stock[stock["dono_id"] == prop_sel] if not stock.empty else pd.DataFrame()
            filtros["gar"] = st.multiselect("Garanhões", sorted(base["garanhao"].dropna().unique()) if not base.empty else [], key="rel_f_p_gar")
        elif modo == "Contentor / Localização" and contentor_sel:
            base = stock[stock["contentor_id"] == contentor_sel] if (not stock.empty and "contentor_id" in stock.columns) else pd.DataFrame()
            f1, f2, f3, f4 = st.columns(4)
            with f1:
                filtros["gar"] = st.multiselect("Garanhões", sorted(base["garanhao"].dropna().unique()) if not base.empty else [], key="rel_f_c_gar")
            with f2:
                filtros["prop"] = st.multiselect("Proprietários", sorted(base["proprietario_nome"].dropna().unique()) if not base.empty else [], key="rel_f_c_prop")
            with f3:
                filtros["can"] = st.multiselect("Canister", sorted(base["canister"].dropna().unique()) if (not base.empty and "canister" in base.columns) else [], key="rel_f_c_can")
            with f4:
                filtros["and"] = st.multiselect("Andar", sorted(base["andar"].dropna().unique()) if (not base.empty and "andar" in base.columns) else [], key="rel_f_c_and")

    if usar_periodo and (data_inicio or data_fim):
        if not insem.empty:
            insem = aplicar_filtro_data(insem, "data_inseminacao", data_inicio, data_fim)
        if not transf.empty:
            transf = aplicar_filtro_data(transf, "data_transferencia", data_inicio, data_fim)
        if not transf_ext.empty:
            transf_ext = aplicar_filtro_data(transf_ext, "data_transferencia", data_inicio, data_fim)
        stock = _filtrar_stock_por_periodo(stock, data_inicio, data_fim)

    render_zone_title("Zona de resultados")

    if modo == "Garanhão" and garanhao_sel:
        s = stock[stock["garanhao"] == garanhao_sel] if not stock.empty else pd.DataFrame()
        if filtros.get("prop"):
            s = s[s["proprietario_nome"].isin(filtros["prop"])]
        i = insem[insem["garanhao"] == garanhao_sel] if not insem.empty else pd.DataFrame()
        t = transf[transf["garanhao"] == garanhao_sel] if not transf.empty else pd.DataFrame()
        te = transf_ext[transf_ext["garanhao"] == garanhao_sel] if not transf_ext.empty else pd.DataFrame()

        left, right = st.columns([6, 2])
        with left:
            st.markdown(f"<div class='reports-results-head'><strong>Garanhão:</strong> {garanhao_sel}</div>", unsafe_allow_html=True)
        with right:
            csv = f"=== GARANHÃO: {garanhao_sel} ===\n\n"
            for nome, df in {
                "Stock": safe_pick(s, ["proprietario_nome", "data_embriovet", "existencia_atual", "qualidade"]),
                "Inseminações": safe_pick(i, ["data_inseminacao", "egua", "proprietario_nome", "palhetas_gastas"]),
                "Transferências Internas": safe_pick(t, ["data_transferencia", "proprietario_origem", "proprietario_destino", "quantidade"]),
                "Transferências Externas": safe_pick(te, ["data_transferencia", "proprietario_origem", "destinatario_externo", "quantidade", "tipo"]),
            }.items():
                if not df.empty:
                    csv += f"\n{nome}:\n{df.to_csv(index=False)}\n"
            st.download_button("CSV", csv.encode("utf-8"), f"garanhao_{garanhao_sel}.csv", "text/csv", width="stretch", key="rel_csv_g")
            pdf = gerar_pdf_garanhao(garanhao_sel, s, i, t, te)
            if pdf:
                st.download_button("PDF", pdf, f"garanhao_{garanhao_sel}.pdf", "application/pdf", width="stretch", key="rel_pdf_g")

        render_kpi_strip([
            ("palhetas em stock", int(to_py(s["existencia_atual"].sum()) or 0) if not s.empty else 0),
            ("inseminações", len(i)),
            ("transf. internas", len(t)),
            ("transf. externas", len(te)),
        ])
        if not s.empty:
            st.dataframe(safe_pick(s, ["proprietario_nome", "data_embriovet", "existencia_atual", "qualidade"]).sort_values("existencia_atual", ascending=False), width="stretch", hide_index=True, height=350)
        if not i.empty:
            st.dataframe(safe_pick(i, ["data_inseminacao", "egua", "proprietario_nome", "palhetas_gastas"]).sort_values("data_inseminacao", ascending=False), width="stretch", hide_index=True, height=300)

    elif modo == "Proprietário" and prop_sel:
        nome = proprietarios[proprietarios["id"] == prop_sel]["nome"].values[0]
        s = stock[stock["dono_id"] == prop_sel] if not stock.empty else pd.DataFrame()
        if filtros.get("gar"):
            s = s[s["garanhao"].isin(filtros["gar"])] if not s.empty else s
        i = insem[insem["dono_id"] == prop_sel] if not insem.empty else pd.DataFrame()
        t_in = transf[transf["proprietario_destino_id"] == prop_sel] if not transf.empty else pd.DataFrame()
        t_out = transf[transf["proprietario_origem_id"] == prop_sel] if not transf.empty else pd.DataFrame()

        left, right = st.columns([6, 2])
        with left:
            st.markdown(f"<div class='reports-results-head'><strong>Proprietário:</strong> {nome}</div>", unsafe_allow_html=True)
        with right:
            csv = safe_pick(s, ["garanhao", "existencia_atual", "qualidade", "data_embriovet"])
            st.download_button("CSV", csv.to_csv(index=False).encode("utf-8"), f"proprietario_{nome}.csv", "text/csv", width="stretch", key="rel_csv_p")

        render_kpi_strip([
            ("palhetas em stock", int(to_py(s["existencia_atual"].sum()) or 0) if not s.empty else 0),
            ("inseminações", len(i)),
            ("transf. recebidas", len(t_in)),
            ("transf. enviadas", len(t_out)),
        ])
        if not s.empty:
            st.dataframe(safe_pick(s, ["garanhao", "data_embriovet", "existencia_atual", "qualidade"]).sort_values("existencia_atual", ascending=False), width="stretch", hide_index=True, height=350)

    elif modo == "Contentor / Localização" and contentor_sel:
        s = stock[stock["contentor_id"] == contentor_sel].copy() if (not stock.empty and "contentor_id" in stock.columns) else pd.DataFrame()
        if filtros.get("gar"):
            s = s[s["garanhao"].isin(filtros["gar"])] if not s.empty else s
        if filtros.get("prop"):
            s = s[s["proprietario_nome"].isin(filtros["prop"])] if not s.empty else s
        if filtros.get("can") and "canister" in s.columns:
            s = s[s["canister"].isin(filtros["can"])]
        if filtros.get("and") and "andar" in s.columns:
            s = s[s["andar"].isin(filtros["and"])]

        info = contentores[contentores["id"] == contentor_sel].iloc[0]
        st.markdown(f"<div class='reports-results-head'><strong>Contentor:</strong> {info['codigo']} | <strong>Descrição:</strong> {info.get('descricao') or '—'}</div>", unsafe_allow_html=True)
        render_kpi_strip([
            ("lotes", len(s)),
            ("palhetas", int(to_py(s["existencia_atual"].sum()) or 0) if not s.empty else 0),
            ("canisters", s["canister"].nunique() if (not s.empty and "canister" in s.columns) else 0),
        ])
        if not s.empty:
            st.dataframe(safe_pick(s, ["proprietario_nome", "garanhao", "existencia_atual", "canister", "andar", "data_embriovet", "data_criacao"]), width="stretch", hide_index=True, height=420)
        else:
            st.info("Sem dados para os filtros atuais.")

    elif modo == "Histórico Geral" and tipo_hist:
        if tipo_hist == "Inseminações":
            d = insem.copy()
            st.dataframe(safe_pick(d, ["data_inseminacao", "garanhao", "egua", "proprietario_nome", "palhetas_gastas"]).sort_values("data_inseminacao", ascending=False) if not d.empty else d, width="stretch", hide_index=True, height=620)
        elif tipo_hist == "Transferências Internas":
            d = transf.copy()
            st.dataframe(safe_pick(d, ["data_transferencia", "garanhao", "proprietario_origem", "proprietario_destino", "quantidade"]).sort_values("data_transferencia", ascending=False) if not d.empty else d, width="stretch", hide_index=True, height=620)
        elif tipo_hist == "Transferências Externas":
            d = transf_ext.copy()
            st.dataframe(safe_pick(d, ["data_transferencia", "garanhao", "proprietario_origem", "destinatario_externo", "tipo", "quantidade", "observacoes"]).sort_values("data_transferencia", ascending=False) if not d.empty else d, width="stretch", hide_index=True, height=620)
        else:
            d = stock.copy()
            st.dataframe(safe_pick(d, ["proprietario_nome", "garanhao", "data_embriovet", "data_criacao", "existencia_atual", "qualidade", "local_armazenagem"]).sort_values("existencia_atual", ascending=False) if not d.empty else d, width="stretch", hide_index=True, height=620)
