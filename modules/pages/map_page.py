# Typed page module (Fase 3)
from modules.i18n import t

def run_map_page(ctx: dict):
    globals().update(ctx)
    # Carregar contentores
    contentores_df = carregar_contentores()

    if "mapa_modo_edicao" not in st.session_state:
        st.session_state["mapa_modo_edicao"] = False

    if "mapa_layout_reader_tick" not in st.session_state:
        st.session_state["mapa_layout_reader_tick"] = 0

    if "mapa_salvar_layout_pendente" not in st.session_state:
        st.session_state["mapa_salvar_layout_pendente"] = False

    if "mapa_salvar_layout_tentativas" not in st.session_state:
        st.session_state["mapa_salvar_layout_tentativas"] = 0

    if "map_bridge_bootstrapped" not in st.session_state:
        st.session_state["map_bridge_bootstrapped"] = False

    try:
        from streamlit_js_eval import streamlit_js_eval
        js_eval_disponivel = True
    except Exception:
        streamlit_js_eval = None
        js_eval_disponivel = False

    if not js_eval_disponivel:
        st.warning(t("map.missing_dependency"))
    else:
        bridge_boot = None
        if not st.session_state.get("map_bridge_bootstrapped", False):
            bridge_boot = streamlit_js_eval(
            js_expressions="""
                (function(){
                    try {
                        var targetWin = (window.parent && window.parent !== window) ? window.parent : window;
                        if (!targetWin.__contentorLayoutBridgeInstalled) {
                            targetWin.__contentorLayoutBridgeInstalled = true;
                            targetWin.addEventListener('message', function(event){
                                var data = event && event.data ? event.data : null;
                                if (!data || typeof data !== 'object') return;

                                if (data.type === 'CONTENTOR_LAYOUT_UPDATE') {
                                    try {
                                        var atual = JSON.parse(targetWin.localStorage.getItem('contentor_layout_pending') || '{}');
                                        atual[String(data.id)] = {
                                            x: parseInt(data.x, 10) || 0,
                                            y: parseInt(data.y, 10) || 0
                                        };
                                        targetWin.localStorage.setItem('contentor_layout_pending', JSON.stringify(atual));
                                    } catch (e) {}
                                }

                                if (data.type === 'CONTENTOR_LAYOUT_CLEAR') {
                                    try { targetWin.localStorage.removeItem('contentor_layout_pending'); } catch (e) {}
                                }
                            });
                        }
                    } catch (e) {}
                    return true;
                })()
            """,
            key="map_layout_bridge_bootstrap",
            want_output=True,
            )
        if bridge_boot is True:
            st.session_state["map_bridge_bootstrapped"] = True

    if "map_largura_viewport" not in st.session_state:
        st.session_state["map_largura_viewport"] = None

    if js_eval_disponivel and st.session_state["map_largura_viewport"] is None:
        largura_viewport_once = streamlit_js_eval(
            js_expressions='window.innerWidth',
            key='map_viewport_width_once',
            want_output=True,
        )
        if largura_viewport_once is not None:
            try:
                st.session_state["map_largura_viewport"] = int(largura_viewport_once)
            except Exception:
                st.session_state["map_largura_viewport"] = 1200

    largura_viewport = st.session_state.get("map_largura_viewport")
    is_mobile = bool(largura_viewport) and int(largura_viewport) < 900
    modo_visualizacao = True

    layout_pending_raw = None
    if st.session_state.get("mapa_salvar_layout_pendente", False) and js_eval_disponivel:
        layout_pending_raw = streamlit_js_eval(
            js_expressions='(function(){try{return window.parent.localStorage.getItem("contentor_layout_pending")}catch(e){return window.localStorage.getItem("contentor_layout_pending")}})()',
            key="map_layout_pending_reader",
            want_output=True,
        )

    # Modal para adicionar contentor - design limpo
    if st.session_state.get('modal_novo_contentor', False):
        st.markdown("---")
        st.markdown(f"### {t('map.add_container_title')}")

        with st.form("form_novo_contentor"):
            col_form1, col_form2 = st.columns([1, 1])

            with col_form1:
                codigo = st.text_input(
                    t("map.container_code_required"), 
                    placeholder=t("map.container_code_placeholder"),
                    help=t("map.container_code_help")
                )

            with col_form2:
                descricao = st.text_input(t("map.container_description_optional"), placeholder=t("map.container_description_placeholder"))

            col_submit1, col_submit2 = st.columns([1, 1])
            with col_submit1:
                submitted = st.form_submit_button(t("btn.create_container"), width="stretch")
            with col_submit2:
                cancelar = st.form_submit_button(t("btn.cancel"), width="stretch")

            if cancelar:
                st.session_state['modal_novo_contentor'] = False
                st.rerun()

            if submitted:
                if not codigo:
                    st.error(t("map.container_code_required_error"))
                else:
                    if codigo in contentores_df['codigo'].values:
                        st.error(t("map.container_code_exists", code=codigo))
                    else:
                        import random
                        contentor_id = adicionar_contentor({
                            'codigo': codigo,
                            'descricao': descricao,
                            'x': random.randint(100, 600),
                            'y': random.randint(100, 350),
                            'w': 90,
                            'h': 90
                        })
                        if contentor_id:
                        st.success(t("map.container_created", code=codigo))
                            st.session_state['modal_novo_contentor'] = False
                            st.rerun()

    # Área do mapa
    if contentores_df.empty:
        st.info(t("map.no_containers"))
    else:
        if modo_visualizacao:
            total_contentores = len(contentores_df)
            total_palhetas_geral = 0
            contentores_data = []

            for _, row in contentores_df.iterrows():
                stock_contentor = obter_stock_contentor(row['id'])
                total_palhetas = int(stock_contentor['existencia_atual'].sum()) if not stock_contentor.empty else 0
                total_palhetas_geral += total_palhetas

                lotes = []
                if not stock_contentor.empty:
                    for _, lote in stock_contentor.iterrows():
                        observacao = ""
                        if isinstance(lote.get('qualidade'), str) and lote.get('qualidade'):
                            observacao = lote.get('qualidade')
                        elif isinstance(lote.get('origem_externa'), str) and lote.get('origem_externa'):
                            observacao = lote.get('origem_externa')

                        lotes.append({
                            "garanhao": lote.get('garanhao') or "—",
                            "proprietario": lote.get('proprietario_nome') or "—",
                            "quantidade": int(lote.get('existencia_atual') or 0),
                            "canister": int(lote.get('canister') or 0),
                            "andar": int(lote.get('andar') or 0),
                            "observacoes": observacao,
                        })

                contentores_data.append({
                    "id": int(row['id']),
                    "codigo": row['codigo'],
                    "descricao": row['descricao'] or "",
                    "x": int(row['x']),
                    "y": int(row['y']),
                    "w": max(80, int(row['w'])),
                    "h": max(80, int(row['h'])),
                    "palhetas": total_palhetas,
                    "lotes": lotes,
                })

            criar_novo = False
            ativar_edicao = False
            cancelar_edicao = False
            salvar_layout = False

            st.markdown(
                """
                <style>
                    .main .block-container {
                        padding-top: 0.35rem !important;
                    }
                    @media (max-width: 900px) {
                        .main .block-container {
                            padding-left: 0 !important;
                            padding-right: 0 !important;
                            padding-top: 0.1rem !important;
                        }
                        div[data-testid="stHeadingWithActionElements"] {
                            margin-bottom: 0.1rem !important;
                            padding-bottom: 0 !important;
                        }
                        div[data-testid="stAppViewContainer"] h1 {
                            font-size: 1.72rem !important;
                            line-height: 1.03 !important;
                            margin-top: 0 !important;
                            margin-bottom: 0.1rem !important;
                        }
                        div[data-testid="stHorizontalBlock"] {
                            gap: 0.35rem !important;
                        }
                        div[data-testid="stButton"] > button {
                            min-height: 2.35rem !important;
                            font-size: 0.95rem !important;
                            padding-top: 0.3rem !important;
                            padding-bottom: 0.3rem !important;
                        }
                    }
                    div[data-testid="stElementContainer"]:has(iframe[title*="streamlit_js_eval"]) {
                        height: 0 !important;
                        min-height: 0 !important;
                        margin: 0 !important;
                        padding: 0 !important;
                        overflow: hidden !important;
                    }
                    iframe[title*="streamlit_js_eval"] {
                        height: 0 !important;
                        min-height: 0 !important;
                        border: 0 !important;
                        margin: 0 !important;
                    }
                    .map-tech-context {
                        font-size: 12px;
                        color: #64748b;
                        line-height: 1.45;
                        margin-top: 0;
                        margin-bottom: 2px;
                    }
                    .map-tech-context-inline {
                        font-size: 11px;
                        color: #64748b;
                        opacity: 0.95;
                    }
                    .map-toolbar-shell {
                        border: 1px solid #d1d5db;
                        border-radius: 8px;
                        background: #f8fafc;
                        padding: 6px 10px;
                        margin-bottom: 4px;
                        position: sticky;
                        top: 0;
                        z-index: 80;
                        backdrop-filter: blur(4px);
                    }
                    .map-toolbar-kpis {
                        display: flex;
                        gap: 10px;
                        align-items: center;
                        font-size: 11px;
                        color: #475569;
                    }
                    @media (max-width: 900px) {
                        .map-tech-context {
                            font-size: 10px;
                            line-height: 1.2;
                            margin-bottom: 1px;
                        }
                        .map-toolbar-shell {
                            padding: 4px 7px;
                            margin-bottom: 2px;
                            border-radius: 6px;
                        }
                        .map-toolbar-kpis {
                            font-size: 10px;
                            gap: 6px;
                            flex-wrap: wrap;
                        }
                    }
                    .map-toolbar-kpis b {
                        color: #0f172a;
                    }
                    div[data-testid="stVerticalBlock"]:has(.map-toolbar-shell) {
                        background: transparent;
                        border: none;
                        border-radius: 0;
                        padding: 0;
                        margin: 0;
                    }
                </style>
                """,
                unsafe_allow_html=True,
            )

            with st.container():
                if is_mobile:
                    st.markdown(f"<div class='map-tech-context'>{t('map.tech_context')}</div>", unsafe_allow_html=True)
                    st.markdown(
                        f"<div class='map-toolbar-shell'><div class='map-toolbar-kpis'><span><b>{total_contentores}</b> contentores</span><span><b>{int(total_palhetas_geral)}</b> palhetas</span></div></div>",
                        unsafe_allow_html=True,
                    )

                    btn_m1, btn_m2, btn_m3 = st.columns([1, 1, 1])
                    with btn_m1:
                        criar_novo = st.button(t("btn.add"), key="map_add_btn_mobile", width="stretch")
                    with btn_m2:
                        if st.session_state["mapa_modo_edicao"]:
                            salvar_layout = st.button(t("btn.save"), key="map_save_btn_mobile", type="primary", width="stretch")
                        else:
                            ativar_edicao = st.button(t("map.edit_map"), key="map_edit_btn_mobile", width="stretch")
                    with btn_m3:
                        if st.session_state["mapa_modo_edicao"]:
                            cancelar_edicao = st.button(t("btn.cancel"), key="map_cancel_btn_mobile", width="stretch")
                else:
                    st.markdown(
                        f"<div class='map-toolbar-shell'><div class='map-toolbar-kpis'><span class='map-tech-context-inline'>Sistema de localização física e inventário de sémen equino</span><span><b>{total_contentores}</b> contentores</span><span><b>{int(total_palhetas_geral)}</b> palhetas</span><span>{'modo edição ativo' if st.session_state['mapa_modo_edicao'] else 'modo normal'}</span></div></div>",
                        unsafe_allow_html=True,
                    )
                    bar_btn1, bar_btn2, bar_btn3 = st.columns([1, 1, 1])
                    with bar_btn1:
                        criar_novo = st.button(t("map.add_container_button"), key="map_add_btn_desktop", width="stretch")
                    with bar_btn2:
                        if st.session_state["mapa_modo_edicao"]:
                            salvar_layout = st.button(t("map.save_layout"), key="map_save_btn_desktop", type="primary", width="stretch")
                        else:
                            ativar_edicao = st.button(t("map.edit_map"), key="map_edit_btn_desktop", width="stretch")
                    with bar_btn3:
                        if st.session_state["mapa_modo_edicao"]:
                            cancelar_edicao = st.button(t("map.cancel_edit"), key="map_cancel_btn_desktop", width="stretch")

            if criar_novo:
                st.session_state['modal_novo_contentor'] = True
                st.rerun()

            if ativar_edicao:
                st.session_state["mapa_modo_edicao"] = True
                if js_eval_disponivel:
                    streamlit_js_eval(
                        js_expressions='(function(){try{window.parent.localStorage.removeItem("contentor_layout_pending")}catch(e){window.localStorage.removeItem("contentor_layout_pending")}})()',
                        key=f"clear_layout_pending_start_{int(time.time() * 1000)}"
                    )
                st.session_state["mapa_salvar_layout_pendente"] = False
                st.session_state["mapa_salvar_layout_tentativas"] = 0
                st.rerun()

            if cancelar_edicao:
                st.session_state["mapa_modo_edicao"] = False
                if js_eval_disponivel:
                    streamlit_js_eval(
                        js_expressions='(function(){try{window.parent.localStorage.removeItem("contentor_layout_pending")}catch(e){window.localStorage.removeItem("contentor_layout_pending")}})()',
                        key=f"clear_layout_pending_cancel_{int(time.time() * 1000)}"
                    )
                st.session_state["mapa_salvar_layout_pendente"] = False
                st.session_state["mapa_salvar_layout_tentativas"] = 0
                st.rerun()

            if salvar_layout:
                if not js_eval_disponivel:
                    st.error(t("map.install_dependency"))
                else:
                    logger.info("Salvar layout acionado pelo utilizador")
                    st.session_state["mapa_salvar_layout_pendente"] = True
                    st.session_state["mapa_salvar_layout_tentativas"] = 0
                    st.rerun()

            if st.session_state.get("mapa_salvar_layout_pendente", False):
                logger.info(f"Processando save pendente (tentativa={st.session_state.get('mapa_salvar_layout_tentativas', 0)})")
                if layout_pending_raw and layout_pending_raw != "null":
                    try:
                        layout_data = layout_pending_raw if isinstance(layout_pending_raw, dict) else json.loads(str(layout_pending_raw))

                        if isinstance(layout_data, dict) and "output" in layout_data:
                            output_value = layout_data.get("output")
                            if isinstance(output_value, dict):
                                layout_data = output_value
                            elif isinstance(output_value, str) and output_value.strip():
                                layout_data = json.loads(output_value)

                        if not isinstance(layout_data, dict) or len(layout_data) == 0:
                            raise ValueError("Payload de layout vazio")

                        atualizados = 0
                        atualizados_ids = []

                        for _, row in contentores_df.iterrows():
                            cid = str(int(row['id']))
                            pos = layout_data.get(cid)
                            if pos is None:
                                try:
                                    pos = layout_data.get(int(cid))
                                except Exception:
                                    pos = None
                            if not isinstance(pos, dict):
                                continue

                            novo_x = int(pos.get("x", int(row['x'])))
                            novo_y = int(pos.get("y", int(row['y'])))
                            largura = max(1, int(row['w']))
                            altura = max(1, int(row['h']))
                            novo_x = max(0, min(novo_x, 900 - largura))
                            novo_y = max(0, min(novo_y, 550 - altura))

                            if novo_x != int(row['x']) or novo_y != int(row['y']):
                                if atualizar_posicao_contentor(int(row['id']), novo_x, novo_y):
                                    atualizados += 1
                                    atualizados_ids.append(cid)

                        streamlit_js_eval(
                            js_expressions='(function(){try{window.parent.localStorage.removeItem("contentor_layout_pending")}catch(e){window.localStorage.removeItem("contentor_layout_pending")}})()',
                            key=f"clear_layout_pending_save_{int(time.time() * 1000)}"
                        )

                        st.session_state["mapa_salvar_layout_pendente"] = False
                        st.session_state["mapa_salvar_layout_tentativas"] = 0
                        st.session_state["mapa_modo_edicao"] = False

                        if atualizados > 0:
                            st.toast(t("map.layout_saved", count=atualizados), icon="✅")
                        else:
                            st.toast("Sem alterações para guardar", icon="ℹ️")
                        st.rerun()
                    except Exception as e:
                        st.session_state["mapa_salvar_layout_pendente"] = False
                        st.session_state["mapa_salvar_layout_tentativas"] = 0
                        logger.error(f"Erro ao salvar layout do mapa: {e}")
                        st.toast("Falha ao salvar layout", icon="❌")
                else:
                    st.session_state["mapa_salvar_layout_tentativas"] = int(st.session_state.get("mapa_salvar_layout_tentativas", 0)) + 1
                    if st.session_state["mapa_salvar_layout_tentativas"] > 4:
                        st.session_state["mapa_salvar_layout_pendente"] = False
                        st.session_state["mapa_salvar_layout_tentativas"] = 0
                        st.toast("Não foi possível ler as posições alteradas", icon="⚠️")

            if st.session_state["mapa_modo_edicao"] and is_mobile:
                pass

            if st.session_state.get("move_feedback"):
                st.toast(st.session_state.pop("move_feedback"), icon="✅")
            if st.session_state.get("move_feedback_erro"):
                st.toast(st.session_state.pop("move_feedback_erro"), icon="⚠️")

            mapa_html = """
            <style>
                :root {
                    --map-bg: #f4f6f8;
                    --map-border: #cbd5e1;
                    --card-bg: #f8fafc;
                    --card-border: #475569;
                    --text-main: #0f172a;
                    --text-muted: #64748b;
                }

                #mapa-wrapper {
                    position: relative;
                    width: 100%;
                    border: 1px solid var(--map-border);
                    border-radius: 8px;
                    background: var(--map-bg);
                    padding: 10px;
                    overflow: hidden;
                    font-family: 'Courier New', monospace;
                }

                #mapa-wrapper.mobile {
                    padding: 4px;
                    border-radius: 6px;
                    margin-bottom: 2px;
                }

                #mapa-area {
                    position: relative;
                    width: min(100%, 720px);
                    margin: 0 auto;
                    aspect-ratio: 900 / 550;
                    border: 2px solid #64748b;
                    background: #fff;
                    background-image:
                        linear-gradient(rgba(15,23,42,.05) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(15,23,42,.05) 1px, transparent 1px);
                    background-size: 50px 50px;
                    overflow: hidden;
                }

                #mapa-wrapper.mobile #mapa-area {
                    width: 100%;
                    max-width: 100%;
                    margin: 0;
                }

                .cont-box {
                    position: absolute;
                    border: 2px solid var(--card-border);
                    background: var(--card-bg);
                    color: var(--text-main);
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    user-select: none;
                    transition: box-shadow .2s ease, transform .2s ease;
                }

                .cont-box.clickable {
                    cursor: pointer;
                }

                .cont-box.draggable {
                    cursor: move;
                }

                .cont-box:hover {
                    box-shadow: 0 8px 16px rgba(2, 6, 23, .14);
                    transform: translateY(-1px);
                    z-index: 50;
                }

                .cont-box.dragging {
                    opacity: .9;
                    z-index: 999;
                }

                .cont-codigo {
                    font-size: 12px;
                    font-weight: 700;
                    margin-bottom: 3px;
                }

                .cont-qtd {
                    font-size: 20px;
                    font-weight: 800;
                    line-height: 1;
                }

                .cont-label {
                    font-size: 10px;
                    color: var(--text-muted);
                    text-transform: uppercase;
                    letter-spacing: .3px;
                }

                .mobile .cont-codigo {
                    font-size: 11px;
                }

                .mobile .cont-qtd {
                    font-size: 18px;
                }

                .mobile .cont-label {
                    font-size: 9px;
                }

                #mapa-status {
                    margin-top: 8px;
                    font-size: 11px;
                    color: var(--text-muted);
                }

                .mobile #mapa-status {
                    margin-top: 4px;
                    font-size: 10px;
                    line-height: 1.1;
                }

                #inv-overlay {
                    position: absolute;
                    inset: 0;
                    background: rgba(15, 23, 42, .28);
                    display: none;
                    z-index: 2000;
                }

                #inv-panel {
                    position: absolute;
                    top: 0;
                    right: 0;
                    width: 360px;
                    height: 100%;
                    background: #fff;
                    border-left: 1px solid #d1d5db;
                    padding: 14px;
                    overflow-y: auto;
                }

                .mobile #inv-panel {
                    width: 100%;
                    border-left: none;
                }

                .inv-head {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    margin-bottom: 10px;
                }

                .inv-title {
                    font-size: 16px;
                    font-weight: 700;
                    color: #111827;
                }

                .inv-close {
                    border: 1px solid #cbd5e1;
                    background: #fff;
                    border-radius: 6px;
                    padding: 4px 8px;
                    cursor: pointer;
                }

                .inv-summary {
                    font-size: 12px;
                    color: #334155;
                    margin-bottom: 10px;
                }

                .inv-lote {
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                    padding: 8px;
                    margin-bottom: 8px;
                    background: #f8fafc;
                    font-size: 12px;
                    line-height: 1.35;
                }
            </style>

            <div id="mapa-wrapper" class="__MOBILE_CLASS__">
                <div id="mapa-area"></div>
                <div id="mapa-status">__STATUS_TEXT__</div>

                <div id="inv-overlay">
                    <div id="inv-panel"></div>
                </div>
            </div>

            <script>
                const contentores = __CONTENTORES_DATA__;
                const isEditMode = __EDIT_MODE__;
                const isMobile = __IS_MOBILE__;
                const baseW = 900;
                const baseH = 550;

                const wrapper = document.getElementById('mapa-wrapper');
                const mapaArea = document.getElementById('mapa-area');
                const statusBar = document.getElementById('mapa-status');
                const invOverlay = document.getElementById('inv-overlay');
                const invPanel = document.getElementById('inv-panel');

                let scale = 1;
                let draggedEl = null;
                let draggedMeta = null;
                let offsetX = 0;
                let offsetY = 0;
                let moved = false;
                let lastPersistAt = 0;

                function esc(v) {
                    return String(v ?? '').replace(/[&<>"']/g, (c) => ({
                        '&': '&amp;',
                        '<': '&lt;',
                        '>': '&gt;',
                        '"': '&quot;',
                        "'": '&#39;'
                    }[c]));
                }

                function computeScale() {
                    const rect = mapaArea.getBoundingClientRect();
                    scale = rect.width / baseW;
                    if (!scale || scale <= 0) scale = 1;
                }

                function openInventory(cont) {
                    const lotes = Array.isArray(cont.lotes) ? cont.lotes : [];
                    const lotesHtml = lotes.length === 0
                        ? '<div class="inv-lote">Sem lotes neste contentor.</div>'
                        : lotes.map(l => `
                            <div class="inv-lote">
                                <b>Garanhão:</b> ${esc(l.garanhao)}<br/>
                                <b>Proprietário:</b> ${esc(l.proprietario)}<br/>
                                <b>Quantidade:</b> ${esc(l.quantidade)}<br/>
                                <b>Canister:</b> ${esc(l.canister)} | <b>Andar:</b> ${esc(l.andar)}<br/>
                                <b>Observações:</b> ${esc(l.observacoes || '—')}
                            </div>
                        `).join('');

                    invPanel.innerHTML = `
                        <div class="inv-head">
                            <div class="inv-title">${esc(cont.codigo)}</div>
                            <button class="inv-close" id="inv-close-btn">Fechar</button>
                        </div>
                        <div class="inv-summary">
                            <b>Total de palhetas:</b> ${esc(cont.palhetas)}<br/>
                            <b>Total de lotes:</b> ${esc(lotes.length)}
                        </div>
                        ${lotesHtml}
                    `;

                    invOverlay.style.display = 'block';
                    const closeBtn = document.getElementById('inv-close-btn');
                    if (closeBtn) closeBtn.addEventListener('click', closeInventory);
                }

                function closeInventory() {
                    invOverlay.style.display = 'none';
                }

                invOverlay.addEventListener('click', (e) => {
                    if (e.target === invOverlay) closeInventory();
                });

                function guardarPosicaoPendente(id, x, y) {
                    try {
                        let storageRef = window.localStorage;
                        try {
                            if (window.parent && window.parent.localStorage) {
                                storageRef = window.parent.localStorage;
                            }
                        } catch (e) {
                            storageRef = window.localStorage;
                        }

                        const atual = JSON.parse(storageRef.getItem('contentor_layout_pending') || '{}');
                        atual[String(id)] = { x, y };
                        storageRef.setItem('contentor_layout_pending', JSON.stringify(atual));

                        try {
                            if (window.parent && window.parent.postMessage) {
                                window.parent.postMessage({
                                    type: 'CONTENTOR_LAYOUT_UPDATE',
                                    id: id,
                                    x: x,
                                    y: y
                                }, '*');
                            }
                        } catch (e) {}

                        statusBar.textContent = 'Alteração pendente.';
                    } catch (err) {
                        console.error('Erro ao guardar posição pendente:', err);
                        statusBar.textContent = 'Falha ao guardar posição pendente.';
                    }
                }

                function criarContentor(cont) {
                    const div = document.createElement('div');
                    div.className = `cont-box ${isEditMode ? 'draggable' : 'clickable'}`;
                    div.id = `cont-${cont.id}`;

                    const wPx = Math.max(40, Math.round(cont.w * scale));
                    const hPx = Math.max(40, Math.round(cont.h * scale));
                    const xPx = Math.round(cont.x * scale);
                    const yPx = Math.round(cont.y * scale);

                    div.style.width = wPx + 'px';
                    div.style.height = hPx + 'px';
                    div.style.left = xPx + 'px';
                    div.style.top = yPx + 'px';

                    div.innerHTML = `
                        <div class="cont-codigo">${esc(cont.codigo)}</div>
                        <div class="cont-qtd">${esc(cont.palhetas)}</div>
                        <div class="cont-label">palhetas</div>
                    `;

                    div.addEventListener('mousedown', (e) => {
                        if (!isEditMode) return;
                        if (e.button !== 0) return;
                        moved = false;
                        draggedEl = div;
                        draggedMeta = cont;
                        draggedEl.classList.add('dragging');

                        const rect = draggedEl.getBoundingClientRect();
                        offsetX = e.clientX - rect.left;
                        offsetY = e.clientY - rect.top;
                        e.preventDefault();
                    });

                    div.addEventListener('click', () => {
                        if (isEditMode) return;
                        openInventory(cont);
                    });

                    mapaArea.appendChild(div);
                }

                document.addEventListener('mousemove', (e) => {
                    if (!draggedEl || !isEditMode) return;
                    moved = true;

                    const mapRect = mapaArea.getBoundingClientRect();
                    let x = e.clientX - mapRect.left - offsetX;
                    let y = e.clientY - mapRect.top - offsetY;

                    const w = parseInt(draggedEl.style.width, 10);
                    const h = parseInt(draggedEl.style.height, 10);
                    x = Math.max(0, Math.min(x, mapRect.width - w));
                    y = Math.max(0, Math.min(y, mapRect.height - h));

                    draggedEl.style.left = Math.round(x) + 'px';
                    draggedEl.style.top = Math.round(y) + 'px';
                    statusBar.textContent = `Movendo... X=${Math.round(x / scale)} | Y=${Math.round(y / scale)}`;

                    const now = Date.now();
                    if (draggedMeta && (now - lastPersistAt) > 180) {
                        const xCanonLive = Math.max(0, Math.min(Math.round(x / scale), baseW - draggedMeta.w));
                        const yCanonLive = Math.max(0, Math.min(Math.round(y / scale), baseH - draggedMeta.h));
                        guardarPosicaoPendente(draggedMeta.id, xCanonLive, yCanonLive);
                        lastPersistAt = now;
                    }
                });

                document.addEventListener('mouseup', () => {
                    if (!draggedEl || !isEditMode || !draggedMeta) return;

                    const xPx = parseInt(draggedEl.style.left, 10);
                    const yPx = parseInt(draggedEl.style.top, 10);
                    const xCanon = Math.max(0, Math.min(Math.round(xPx / scale), baseW - draggedMeta.w));
                    const yCanon = Math.max(0, Math.min(Math.round(yPx / scale), baseH - draggedMeta.h));

                    draggedEl.classList.remove('dragging');
                    draggedEl = null;

                    guardarPosicaoPendente(draggedMeta.id, xCanon, yCanon);

                    draggedMeta = null;
                });

                computeScale();
                contentores.forEach(criarContentor);

                if (!isEditMode) {
                    statusBar.textContent = 'Clique num contentor para ver o inventário.';
                }
            </script>
            """

            import streamlit.components.v1 as components
            mapa_render = mapa_html.replace("__CONTENTORES_DATA__", json.dumps(contentores_data, ensure_ascii=False))
            mapa_render = mapa_render.replace("__EDIT_MODE__", "true" if st.session_state["mapa_modo_edicao"] else "false")
            mapa_render = mapa_render.replace("__IS_MOBILE__", "true" if is_mobile else "false")
            mapa_render = mapa_render.replace("__MOBILE_CLASS__", "mobile" if is_mobile else "desktop")
            mapa_render = mapa_render.replace(
                "__STATUS_TEXT__",
                "Arraste os contentores e salve o layout." if st.session_state["mapa_modo_edicao"] else "Clique num contentor para ver inventário."
            )

            if is_mobile:
                components.html(mapa_render, height=355)
            else:
                components.html(mapa_render, height=505)

            # Mostrar lista de contentores abaixo do mapa
            st.markdown(f"<div class='inv-contentores-head'>{t('map.inventory_title')}</div>", unsafe_allow_html=True)

            for idx, row in contentores_df.iterrows():
                stock_contentor = obter_stock_contentor(row['id'])
                total_palhetas = stock_contentor['existencia_atual'].sum() if not stock_contentor.empty else 0
                total_lotes = len(stock_contentor)

                # Design técnico limpo
                with st.expander(f"**{row['codigo']}** — {int(total_palhetas)} palhetas, {total_lotes} lotes"):
                    col_det1, col_det2, col_det3 = st.columns([2, 2, 1])

                    with col_det1:
                        st.markdown(f"**Código:** {row['codigo']}")
                        st.markdown(f"**Descrição:** {row['descricao'] or '—'}")
                        st.markdown(f"**Posição:** X={row['x']}, Y={row['y']}")

                    with col_det2:
                        st.markdown(f"**Total Palhetas:** {int(total_palhetas)}")
                        st.markdown(f"**Total Lotes:** {total_lotes}")

                    with col_det3:
                        if st.button(t("btn.edit"), key=f"edit_{row['id']}", width="stretch"):
                            st.session_state[f'modal_editar_{row["id"]}'] = True
                            st.rerun()

                        pode_apagar = int(total_palhetas) == 0
                        if st.button(
                            "Apagar",
                            key=f"del_{row['id']}",
                            width="stretch",
                            disabled=not pode_apagar,
                            help="Só é possível apagar quando o contentor não tem stock"
                        ):
                            if deletar_contentor(row['id']):
                                st.success(f"Contentor '{row['codigo']}' apagado")
                                st.rerun()
                        if not pode_apagar:
                            st.caption(t("map.delete_blocked"))

                    if not stock_contentor.empty:
                        st.markdown(f"**{t('label.lots')}:**")
                        for canister in sorted(stock_contentor['canister'].unique()):
                            stock_canister = stock_contentor[stock_contentor['canister'] == canister]
                            for andar in sorted(stock_canister['andar'].unique()):
                                stock_andar = stock_canister[stock_canister['andar'] == andar]
                                for _, lote in stock_andar.iterrows():
                                    ref = lote['origem_externa'] or lote['data_embriovet'] or '—'
                                    st.text(f"Can.{canister} / {andar}º | {lote['garanhao']} | {lote['proprietario_nome']} | {int(lote['existencia_atual'])}p | {ref}")

                    # Modal edição
                    if st.session_state.get(f'modal_editar_{row["id"]}', False):
                        st.markdown("---")
                        with st.form(f"form_editar_{row['id']}"):
                            st.markdown(f"#### {t('map.edit_container_title')}")

                            col_edit1, col_edit2 = st.columns(2)
                            with col_edit1:
                                novo_codigo = st.text_input(t("label.code"), value=row['codigo'])
                            with col_edit2:
                                nova_descricao = st.text_input(t("label.description"), value=row['descricao'] or '')

                            col_btn_edit1, col_btn_edit2 = st.columns(2)
                            with col_btn_edit1:
                                salvar = st.form_submit_button(t("btn.save"), width="stretch")
                            with col_btn_edit2:
                                cancelar_edit = st.form_submit_button(t("btn.cancel"), width="stretch")

                            if cancelar_edit:
                                st.session_state[f'modal_editar_{row["id"]}'] = False
                                st.rerun()

                            if salvar:
                                if editar_contentor(row['id'], {
                                    'codigo': novo_codigo,
                                    'descricao': nova_descricao,
                                    'x': row['x'],
                                    'y': row['y'],
                                    'w': row['w'],
                                    'h': row['h']
                                }):
                                    st.success(t("map.container_updated"))
                                    st.session_state[f'modal_editar_{row["id"]}'] = False
                                    st.rerun()

        else:
            # MODO LISTA (mantido para compatibilidade)
            st.markdown(f"### {t('map.container_list')}")

            for idx, row in contentores_df.iterrows():
                stock_contentor = obter_stock_contentor(row['id'])
                total_palhetas = stock_contentor['existencia_atual'].sum() if not stock_contentor.empty else 0
                total_lotes = len(stock_contentor)

                with st.expander(f"**{row['codigo']}** — {int(total_palhetas)} palhetas, {total_lotes} lotes"):
                    st.markdown(f"**Descrição:** {row['descricao'] or '—'}")
                    st.markdown(f"**Total de palhetas:** {int(total_palhetas)}")
                    st.markdown(f"**Total de lotes:** {total_lotes}")

                    if not stock_contentor.empty:
                        st.markdown("---")
                        for canister in sorted(stock_contentor['canister'].unique()):
                            st.markdown(f"**Canister {canister}:**")
                            stock_canister = stock_contentor[stock_contentor['canister'] == canister]

                            for andar in sorted(stock_canister['andar'].unique()):
                                st.markdown(f"  *{andar}º Andar:*")
                                stock_andar = stock_canister[stock_canister['andar'] == andar]

                                for _, lote in stock_andar.iterrows():
                                    ref = lote['origem_externa'] or lote['data_embriovet'] or '—'
                                    st.markdown(f"  - {lote['garanhao']} | {lote['proprietario_nome']} | {int(lote['existencia_atual'])} palhetas | {ref}")
