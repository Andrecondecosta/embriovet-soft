# Typed page module (Fase 3)

def run_stock_page(ctx: dict):
    globals().update(ctx)
    st.header("Estoque Atual")
    inject_stock_css()
    inject_reports_css()

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

        render_zone_title("Zona de seleção", "stock-zone-title")
        filtro = st.selectbox("Garanhão", garanhaos_disponiveis, index=idx_default, key="stock_garanhao_main")

        render_zone_title("Zona de filtros", "stock-zone-title")
        with st.expander("Filtros de consulta", expanded=False):
            f1, f2, f3 = st.columns(3)
            with f1:
                filtro_props = st.multiselect(
                    "Proprietários",
                    sorted(stock[stock["garanhao"] == filtro]["proprietario_nome"].dropna().unique()),
                    key="stock_filter_props",
                )
            with f2:
                min_palhetas = st.number_input("Mín. palhetas", min_value=0, value=0, step=1, key="stock_filter_min")
            with f3:
                mostrar_sem_stock = st.checkbox("Incluir lotes vazios", value=False, key="stock_filter_zero")

        stock_filtrado = filter_stock_view(
            stock,
            garanhao=filtro,
            owner_filters=filtro_props,
            min_palhetas=min_palhetas,
            include_zero=mostrar_sem_stock,
        )

        transf_hist_all = carregar_transferencias()
        transf_ext_hist_all = carregar_transferencias_externas()

        render_zone_title("Zona de resultados", "stock-zone-title")
        render_kpi_strip(stock_kpis(stock_filtrado, to_py))

        resumo_por_proprietario = summarize_stock_by_owner(stock_filtrado)
        if not resumo_por_proprietario.empty:
            st.dataframe(
                resumo_por_proprietario,
                use_container_width=True,
                hide_index=True,
                height=220,
            )

        with st.expander("Histórico técnico de transferências do garanhão", expanded=False):
            transf_hist, transf_ext_hist = filter_transfer_history(
                transf_hist_all,
                transf_ext_hist_all,
                garanhao=filtro,
                owner_filters=filtro_props,
            )

            cexp1, cexp2 = st.columns(2)
            with cexp1:
                if not transf_hist.empty:
                    csv_ti = safe_pick(transf_hist, ["data_transferencia", "garanhao", "proprietario_origem", "proprietario_destino", "quantidade"])
                    st.download_button(
                        "CSV Internas",
                        csv_ti.to_csv(index=False).encode("utf-8"),
                        f"transferencias_internas_{filtro}.csv",
                        "text/csv",
                        key=f"stock_hist_ti_{filtro}",
                        use_container_width=True,
                    )
            with cexp2:
                if not transf_ext_hist.empty:
                    csv_te = safe_pick(transf_ext_hist, ["data_transferencia", "garanhao", "proprietario_origem", "destinatario_externo", "tipo", "quantidade", "observacoes"])
                    st.download_button(
                        "CSV Externas",
                        csv_te.to_csv(index=False).encode("utf-8"),
                        f"transferencias_externas_{filtro}.csv",
                        "text/csv",
                        key=f"stock_hist_te_{filtro}",
                        use_container_width=True,
                    )

            if not transf_hist.empty:
                ex_ti = safe_pick(transf_hist, ["data_transferencia", "proprietario_origem", "proprietario_destino", "quantidade"]).sort_values("data_transferencia", ascending=False)
                ex_ti.columns = ["Data", "De", "Para", "Palhetas"]
                st.dataframe(ex_ti, use_container_width=True, hide_index=True, height=220)
            if not transf_ext_hist.empty:
                ex_te = safe_pick(transf_ext_hist, ["data_transferencia", "proprietario_origem", "destinatario_externo", "tipo", "quantidade", "observacoes"]).sort_values("data_transferencia", ascending=False)
                ex_te.columns = ["Data", "De", "Para", "Tipo", "Palhetas", "Observações"][:len(ex_te.columns)]
                st.dataframe(ex_te, use_container_width=True, hide_index=True, height=220)

            if transf_hist.empty and transf_ext_hist.empty:
                st.info("Sem transferências para o filtro atual.")

        st.markdown("<div class='stock-table-head'>Lotes Detalhados</div>", unsafe_allow_html=True)

        if stock_filtrado.empty:
            st.info("Sem lotes para o filtro atual.")

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

                    with st.expander("Histórico técnico deste lote", expanded=False):
                        lote_transf_int, lote_transf_ext = filter_lot_transfer_history(
                            transf_hist_all,
                            transf_ext_hist_all,
                            garanhao=row.get("garanhao"),
                            owner_name=proprietario_nome,
                        )

                        if not lote_transf_int.empty:
                            ex_int = safe_pick(
                                lote_transf_int,
                                ["data_transferencia", "proprietario_origem", "proprietario_destino", "quantidade"],
                            ).sort_values("data_transferencia", ascending=False)
                            ex_int.columns = ["Data", "De", "Para", "Palhetas"]
                            st.dataframe(ex_int, use_container_width=True, hide_index=True, height=180)

                        if not lote_transf_ext.empty:
                            ex_ext = safe_pick(
                                lote_transf_ext,
                                ["data_transferencia", "proprietario_origem", "destinatario_externo", "tipo", "quantidade", "observacoes"],
                            ).sort_values("data_transferencia", ascending=False)
                            ex_ext.columns = ["Data", "De", "Para", "Tipo", "Palhetas", "Observações"][:len(ex_ext.columns)]
                            st.dataframe(ex_ext, use_container_width=True, hide_index=True, height=180)

                        if lote_transf_int.empty and lote_transf_ext.empty:
                            st.info("Sem histórico técnico de transferências para este lote.")

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
