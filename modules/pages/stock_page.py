# Typed page module (Fase 3)
from modules.i18n import t

def run_stock_page(ctx: dict):
    globals().update(ctx)
    st.header(t("stock.title"))
    inject_stock_css()
    inject_reports_css()
    inject_stepper_css()
    
    # CSS para reduzir fonte dos expanders
    st.markdown(
        """
        <style>
            /* Reduzir fonte do título do expander para caber mais informação */
            div[data-testid="stExpander"] summary p {
                font-size: 0.85rem !important;
                line-height: 1.3 !important;
            }
            div[data-testid="stExpander"] summary {
                padding: 8px 12px !important;
            }
        </style>
        """,
        unsafe_allow_html=True
    )

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

        render_zone_title(t("stock.zone.selection"), "stock-zone-title")
        filtro = st.selectbox(t("label.garanhao"), garanhaos_disponiveis, index=idx_default, key="stock_garanhao_main")

        render_zone_title(t("stock.zone.filters"), "stock-zone-title")
        with st.expander(t("stock.filters_title"), expanded=False):
            f1, f2, f3 = st.columns(3)
            with f1:
                filtro_props = st.multiselect(
                    t("label.owner_plural"),
                    sorted(stock[stock["garanhao"] == filtro]["proprietario_nome"].dropna().unique()),
                    key="stock_filter_props",
                )
            with f2:
                min_palhetas = st.number_input(t("stock.min_straws"), min_value=0, value=0, step=1, key="stock_filter_min")
            with f3:
                mostrar_sem_stock = st.checkbox(t("stock.include_empty"), value=False, key="stock_filter_zero")

        stock_filtrado = filter_stock_view(
            stock,
            garanhao=filtro,
            owner_filters=filtro_props,
            min_palhetas=min_palhetas,
            include_zero=mostrar_sem_stock,
        )

        transf_hist_all = carregar_transferencias()
        transf_ext_hist_all = carregar_transferencias_externas()

        render_zone_title(t("stock.zone.results"), "stock-zone-title")
        render_kpi_strip(stock_kpis(stock_filtrado, to_py))

        resumo_por_proprietario = summarize_stock_by_owner(stock_filtrado)
        if not resumo_por_proprietario.empty:
                st.dataframe(
                    resumo_por_proprietario,
                    width="stretch",
                    hide_index=True,
                    height=220,
                )

        with st.expander(t("stock.transfer_history"), expanded=False):
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
                        t("stock.csv_internal"),
                        csv_ti.to_csv(index=False).encode("utf-8"),
                        f"transferencias_internas_{filtro}.csv",
                        "text/csv",
                        key=f"stock_hist_ti_{filtro}",
                        width="stretch",
                    )
            with cexp2:
                if not transf_ext_hist.empty:
                    csv_te = safe_pick(transf_ext_hist, ["data_transferencia", "garanhao", "proprietario_origem", "destinatario_externo", "tipo", "quantidade", "observacoes"])
                    st.download_button(
                        t("stock.csv_external"),
                        csv_te.to_csv(index=False).encode("utf-8"),
                        f"transferencias_externas_{filtro}.csv",
                        "text/csv",
                        key=f"stock_hist_te_{filtro}",
                        width="stretch",
                    )

            if not transf_hist.empty:
                ex_ti = safe_pick(transf_hist, ["data_transferencia", "proprietario_origem", "proprietario_destino", "quantidade"]).sort_values("data_transferencia", ascending=False)
                ex_ti.columns = [t("label.date"), t("label.from"), t("label.to"), t("label.straws")] 
                st.dataframe(ex_ti, width="stretch", hide_index=True, height=220)
            if not transf_ext_hist.empty:
                ex_te = safe_pick(transf_ext_hist, ["data_transferencia", "proprietario_origem", "destinatario_externo", "tipo", "quantidade", "observacoes"]).sort_values("data_transferencia", ascending=False)
                ex_te.columns = [t("label.date"), t("label.from"), t("label.to"), t("label.type"), t("label.straws"), t("label.notes")] [:len(ex_te.columns)]
                st.dataframe(ex_te, width="stretch", hide_index=True, height=220)

            if transf_hist.empty and transf_ext_hist.empty:
                st.info(t("stock.no_transfers"))

        st.markdown(f"<div class='stock-table-head'>{t('stock.lots_detailed')}</div>", unsafe_allow_html=True)

        if stock_filtrado.empty:
            st.info(t("stock.no_lots_filter"))

        proprietarios_dict = dict(zip(proprietarios["id"], proprietarios["nome"]))

        for _, row in stock_filtrado.iterrows():
            existencia = 0 if pd.isna(row.get("existencia_atual")) else int(to_py(row.get("existencia_atual")) or 0)
            referencia = row.get("origem_externa") or row.get("data_embriovet") or t("common.no_reference")
            proprietario_nome = row.get("proprietario_nome", t("common.no_owner"))
            
            # Buscar localização
            localizacao = "—"
            if row.get('contentor_codigo'):
                contentor = row.get('contentor_codigo')
                canister = row.get('canister')
                andar = row.get('andar')
                if pd.notna(canister) and pd.notna(andar):
                    localizacao = f"{contentor}/C{int(canister)}/A{int(andar)}"
                else:
                    localizacao = contentor
            elif row.get('local_armazenagem'):
                localizacao = row.get('local_armazenagem')
            
            # Motilidade, Concentração e Cor
            motilidade = int(to_py(row.get("motilidade")) or 0)
            concentracao = int(to_py(row.get("concentracao")) or 0)
            cor = to_py(row.get("cor")) or "—"
            
            # Criar título do expander com todas as informações
            info_extra = f"📍 {localizacao} | 🎨 {cor} | 📊 M:{motilidade}% | 🧬 {concentracao}M/ml"

            # Verificar se é o lote recém-adicionado para abrir automaticamente
            expanded = (stock_id_expandir == row["id"]) if stock_id_expandir else False

            with st.expander(
                f"{referencia} | {proprietario_nome} | {existencia} pal. | {info_extra}",
                expanded=expanded
            ):

                # Tabs: Mostrar conforme permissões
                if verificar_permissao('Administrador'):
                    # Admin vê: Detalhes, Editar
                    tab1, tab2 = st.tabs([t("stock.tab.details"), t("stock.tab.edit")])
                    tab3 = None
                else:
                    # Gestor e Visualizador vêem apenas: Detalhes
                    tab1 = st.tabs([t("stock.tab.details")])[0]
                    tab2 = None
                    tab3 = None

                # TAB 1: Detalhes
                with tab1:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**🏷️ {t('label.owner')}:** {proprietario_nome}")

                        # Localização estruturada
                        if row.get('contentor_id'):
                            try:
                                contentor_query = f"SELECT codigo FROM contentores WHERE id = {int(row['contentor_id'])}"
                                with get_connection() as conn:
                                    contentor_df = pd.read_sql_query(contentor_query, conn)
                                    if not contentor_df.empty:
                                        contentor_codigo = contentor_df.iloc[0]['codigo']
                                        canister_num = row.get('canister', t('common.na'))
                                        andar_num = row.get('andar', t('common.na'))
                                        st.markdown(f"**📍 {t('label.location')}:** {contentor_codigo} | {t('label.canister')} {canister_num} | {andar_num}º")
                                    else:
                                        st.markdown(f"**📍 {t('label.location')}:** {t('common.na')}")
                            except Exception:
                                st.markdown(f"**📍 {t('label.location')}:** {t('common.na')}")
                        else:
                            st.markdown(f"**📍 {t('label.location')}:** {t('common.na')}")

                        st.markdown(f"**📜 {t('stock.certificate_label')}:** {row.get('certificado') or t('common.na')}")
                        st.markdown(f"**✨ {t('stock.quality_label')}:** {row.get('qualidade') or '—'}")
                        st.markdown(f"**🎨 {t('stock.color')}:** {row.get('cor') or '—'}")
                    with col2:
                        st.markdown(f"**🔬 {t('stock.concentration_label')}:** {row.get('concentracao') or 0} {t('stock.million_ml')}")
                        st.markdown(f"**⚡ {t('stock.motility_label')}:** {row.get('motilidade') or 0}%")
                        st.markdown(f"**💊 {t('stock.dose_label')}:** {row.get('dose') or t('common.na')}")
                        if row.get("observacoes"):
                            st.markdown(f"**📝 {t('label.notes')}:** {row.get('observacoes')}")

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
                                st.markdown(f"**📅 {t('stock.created_at_label')}:** {data_criacao.strftime('%d/%m/%Y %H:%M')}")
                            except Exception:
                                st.markdown(f"**📅 {t('stock.created_at_label')}:** {row.get('data_criacao')}")
                    with audit_col2:
                        if row.get("criado_por"):
                            st.markdown(f"**👤 {t('stock.created_by_label')}:** {row.get('criado_por')}")

                    with st.expander(t("stock.lot_history"), expanded=False):
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
                            st.dataframe(ex_int, width="stretch", hide_index=True, height=180)

                        if not lote_transf_ext.empty:
                            ex_ext = safe_pick(
                                lote_transf_ext,
                                ["data_transferencia", "proprietario_origem", "destinatario_externo", "tipo", "quantidade", "observacoes"],
                            ).sort_values("data_transferencia", ascending=False)
                            ex_ext.columns = ["Data", "De", "Para", "Tipo", "Palhetas", "Observações"][:len(ex_ext.columns)]
                            st.dataframe(ex_ext, width="stretch", hide_index=True, height=180)

                        if lote_transf_int.empty and lote_transf_ext.empty:
                            st.info(t("stock.no_transfer_history_lot"))

                # TAB 2: Editar (Apenas Admin)
                if tab2 is not None:
                    with tab2:
                        st.markdown(f"### {t('stock.edit_title')}")

                        # Botão + para adicionar proprietário
                        if st.button(t("stock.new_owner"), key=f"btn_add_prop_edit_{row['id']}", help=t("stock.new_owner_help")):
                            modal_adicionar_proprietario()

                        # Carregar contentores para edição
                        contentores_df_edit = carregar_contentores()

                        with st.form(key=f"edit_form_{row['id']}"):
                            edit_garanhao = st.text_input(t("label.garanhao"), value=row.get("garanhao", ""))

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
                                t("label.owner"),
                                options=proprietarios["id"].tolist(),
                                format_func=lambda x: proprietarios_dict.get(x, "Desconhecido"),
                                index=idx_prop,
                                key=f"edit_prop_{row['id']}"
                            )

                            col1, col2 = st.columns(2)
                            with col1:
                                edit_data = st.text_input(t("stock.prod_date"), value=row.get("data_embriovet") or "")
                                edit_origem = st.text_input(t("stock.external_origin"), value=row.get("origem_externa") or "")
                                edit_palhetas = st.number_input(t("stock.straws_produced"), min_value=0, value=int(to_py(row.get("palhetas_produzidas")) or 0))
                                edit_existencia = st.number_input(t("stock.current_stock"), min_value=0, value=existencia)
                                edit_qualidade = st.text_input(t("stock.quality_text"), value=row.get("qualidade") or "")

                            with col2:
                                edit_concentracao = st.number_input(t("stock.concentration"), min_value=0, value=int(to_py(row.get("concentracao")) or 0))
                                edit_motilidade = st.number_input(t("stock.motility_pct"), min_value=0, max_value=100, value=int(to_py(row.get("motilidade")) or 0))
                                edit_certificado = st.selectbox(t("stock.certificate"), [t("common.yes"), t("common.no")], index=0 if row.get("certificado") == "Sim" else 1)
                                edit_dose = st.text_input(t("stock.dose"), value=row.get("dose") or "")
                                edit_cor = st.text_input(t("stock.color"), value=row.get("cor") or "")

                            st.markdown("---")
                            st.subheader(t("stock.location_title"))

                            if not contentores_df_edit.empty:
                                col_loc1, col_loc2, col_loc3 = st.columns(3)

                                # Contentor atual
                                contentor_atual_id = row.get("contentor_id")
                                idx_contentor = 0
                                if contentor_atual_id and contentor_atual_id in contentores_df_edit["id"].values:
                                    idx_contentor = list(contentores_df_edit["id"]).index(contentor_atual_id)

                                with col_loc1:
                                    edit_contentor_codigo = st.selectbox(
                                        t("label.container_required"),
                                        options=contentores_df_edit["codigo"].tolist(),
                                        index=idx_contentor,
                                        key=f"edit_cont_{row['id']}"
                                    )
                                    edit_contentor_id = int(contentores_df_edit.loc[contentores_df_edit["codigo"] == edit_contentor_codigo, "id"].iloc[0])

                                with col_loc2:
                                    canister_raw = to_py(row.get("canister"))
                                    try:
                                        canister_atual = int(canister_raw) if canister_raw is not None else 1
                                    except Exception:
                                        canister_atual = 1
                                    idx_canister = max(0, min(9, canister_atual - 1))
                                    edit_canister = st.selectbox(
                                        t("label.canister_required"),
                                        options=list(range(1, 11)),
                                        index=idx_canister,
                                        key=f"edit_can_{row['id']}"
                                    )

                                with col_loc3:
                                    andar_raw = to_py(row.get("andar"))
                                    try:
                                        andar_atual = int(andar_raw) if andar_raw is not None else 1
                                    except Exception:
                                        andar_atual = 1
                                    idx_andar = 0 if andar_atual == 1 else 1
                                    edit_andar = st.radio(
                                        t("label.floor_required"),
                                        options=[1, 2],
                                        format_func=lambda x: f"{x}º",
                                        horizontal=True,
                                        index=idx_andar,
                                        key=f"edit_and_{row['id']}"
                                    )
                            else:
                                st.warning(t("stock.no_containers"))
                                edit_contentor_id = None
                                edit_canister = 1
                                edit_andar = 1

                            edit_obs = st.text_area(t("label.notes"), value=row.get("observacoes") or "")

                            submit_edit = st.form_submit_button(t("btn.save_changes"), type="primary")

                            if submit_edit:
                                if editar_stock(row["id"], {
                                    "garanhao": edit_garanhao,
                                    "dono_id": edit_proprietario,
                                    "data": edit_data,
                                    "origem": edit_origem,
                                    "palhetas_produzidas": edit_palhetas,
                                    "qualidade": edit_qualidade,
                                    "concentracao": edit_concentracao,
                                    "cor": edit_cor,
                                    "motilidade": edit_motilidade,
                                    "contentor_id": edit_contentor_id,
                                    "canister": edit_canister,
                                    "andar": edit_andar,
                                    "certificado": edit_certificado,
                                    "dose": edit_dose,
                                    "observacoes": edit_obs,
                                    "existencia": edit_existencia
                                }):
                                    st.success(t("stock.updated_success"))
                                    # Marcar que usou
                                    if 'novo_proprietario_id' in st.session_state:
                                        st.session_state['novo_proprietario_usado'] = True
                                    st.rerun()

    else:
        st.info(t("stock.none_registered"))

# ------------------------------------------------------------
# ➕ Adicionar Stock
# ------------------------------------------------------------
