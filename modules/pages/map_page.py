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
                    /* Reduzir padding global para dar mais espaço ao mapa */
                    .main .block-container {
                        padding-top: 0.5rem !important;
                        max-width: 100% !important;
                    }
                    
                    /* Botões modernos e elegantes */
                    div[data-testid="stButton"] > button {
                        border-radius: 8px !important;
                        font-weight: 500 !important;
                        font-size: 0.9rem !important;
                        padding: 8px 20px !important;
                        transition: all 0.2s ease !important;
                        border: 1px solid #e2e8f0 !important;
                    }
                    
                    div[data-testid="stButton"] > button:hover {
                        transform: translateY(-1px) !important;
                        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1) !important;
                    }
                    
                    /* Botão primário (Salvar) */
                    div[data-testid="stButton"] > button[kind="primary"] {
                        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
                        border: none !important;
                        color: white !important;
                        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3) !important;
                    }
                    
                    div[data-testid="stButton"] > button[kind="primary"]:hover {
                        box-shadow: 0 6px 20px rgba(59, 130, 246, 0.4) !important;
                    }
                    
                    /* Toolbar premium */
                    .map-toolbar-shell {
                        border: 1px solid #e2e8f0;
                        border-radius: 10px;
                        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
                        padding: 12px 16px;
                        margin-bottom: 12px;
                        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
                    }
                    
                    .map-toolbar-kpis {
                        display: flex;
                        gap: 16px;
                        align-items: center;
                        font-size: 0.85rem;
                        color: #64748b;
                    }
                    
                    .map-toolbar-kpis b {
                        color: #0f172a;
                        font-weight: 600;
                    }
                    
                    /* Container do mapa - altura otimizada */
                    .map-workspace {
                        max-height: 65vh;
                        overflow: hidden;
                        border-radius: 12px;
                        border: 1px solid #e2e8f0;
                        background: #ffffff;
                        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
                    }
                    
                    /* Mobile responsive */
                    @media (max-width: 900px) {
                        .main .block-container {
                            padding-left: 8px !important;
                            padding-right: 8px !important;
                            padding-top: 0.3rem !important;
                        }
                        
                        div[data-testid="stButton"] > button {
                            min-height: 38px !important;
                            font-size: 0.85rem !important;
                            padding: 6px 12px !important;
                        }
                        
                        .map-toolbar-shell {
                            padding: 8px 12px;
                            margin-bottom: 8px;
                            border-radius: 8px;
                        }
                        
                        .map-toolbar-kpis {
                            font-size: 0.75rem;
                            gap: 10px;
                            flex-wrap: wrap;
                        }
                        
                        .map-workspace {
                            max-height: 55vh;
                            border-radius: 8px;
                        }
                        
                        div[data-testid="stAppViewContainer"] h1 {
                            font-size: 1.5rem !important;
                            margin-bottom: 0.5rem !important;
                        }
                    }
                    
                    /* Esconder elementos técnicos */
                    div[data-testid="stElementContainer"]:has(iframe[title*="streamlit_js_eval"]) {
                        height: 0 !important;
                        min-height: 0 !important;
                        margin: 0 !important;
                        padding: 0 !important;
                        overflow: hidden !important;
                        display: none !important;
                    }
                    
                    iframe[title*="streamlit_js_eval"] {
                        height: 0 !important;
                        min-height: 0 !important;
                        display: none !important;
                    }
                    
                    /* Painel de detalhes elegante */
                    .contentor-detail-panel {
                        background: white;
                        border-radius: 10px;
                        padding: 16px;
                        border: 1px solid #e2e8f0;
                        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
                    }
                </style>
                """,
                unsafe_allow_html=True,
            )

            with st.container():
                # Toolbar com KPIs
                st.markdown(
                    f"""
                    <div class='map-toolbar-shell'>
                        <div class='map-toolbar-kpis'>
                            <span>📍 <b>{total_contentores}</b> Contentores</span>
                            <span>🧬 <b>{int(total_palhetas_geral)}</b> Palhetas</span>
                            <span>{'✏️ Modo Edição' if st.session_state['mapa_modo_edicao'] else '👁️ Visualização'}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                
                # Botões de ação
                if is_mobile:
                    btn_m1, btn_m2, btn_m3 = st.columns([1, 1, 1])
                    with btn_m1:
                        criar_novo = st.button("➕ Novo", key="map_add_btn_mobile", use_container_width=True)
                    with btn_m2:
                        if st.session_state["mapa_modo_edicao"]:
                            salvar_layout = st.button("💾 Salvar", key="map_save_btn_mobile", type="primary", use_container_width=True)
                        else:
                            ativar_edicao = st.button("✏️ Editar", key="map_edit_btn_mobile", use_container_width=True)
                    with btn_m3:
                        if st.session_state["mapa_modo_edicao"]:
                            cancelar_edicao = st.button("❌ Cancelar", key="map_cancel_btn_mobile", use_container_width=True)
                else:
                    bar_btn1, bar_btn2, bar_btn3, bar_btn4 = st.columns([1.5, 1.5, 1.5, 2])
                    with bar_btn1:
                        criar_novo = st.button("➕ Adicionar Contentor", key="map_add_btn_desktop", use_container_width=True)
                    with bar_btn2:
                        if st.session_state["mapa_modo_edicao"]:
                            salvar_layout = st.button("💾 Salvar Layout", key="map_save_btn_desktop", type="primary", use_container_width=True)
                        else:
                            ativar_edicao = st.button("✏️ Editar Mapa", key="map_edit_btn_desktop", use_container_width=True)
                    with bar_btn3:
                        if st.session_state["mapa_modo_edicao"]:
                            cancelar_edicao = st.button("❌ Cancelar Edição", key="map_cancel_btn_desktop", use_container_width=True)

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
                            st.toast(t("map.no_changes_to_save"), icon="ℹ️")
                        st.rerun()
                    except Exception as e:
                        st.session_state["mapa_salvar_layout_pendente"] = False
                        st.session_state["mapa_salvar_layout_tentativas"] = 0
                        logger.error(f"Erro ao salvar layout do mapa: {e}")
                        st.toast(t("map.save_failed"), icon="❌")
                else:
                    st.session_state["mapa_salvar_layout_tentativas"] = int(st.session_state.get("mapa_salvar_layout_tentativas", 0)) + 1
                    if st.session_state["mapa_salvar_layout_tentativas"] > 4:
                        st.session_state["mapa_salvar_layout_pendente"] = False
                        st.session_state["mapa_salvar_layout_tentativas"] = 0
                        st.toast(t("map.read_positions_failed"), icon="⚠️")

            if st.session_state["mapa_modo_edicao"] and is_mobile:
                pass

            if st.session_state.get("move_feedback"):
                st.toast(st.session_state.pop("move_feedback"), icon="✅")
            if st.session_state.get("move_feedback_erro"):
                st.toast(st.session_state.pop("move_feedback_erro"), icon="⚠️")

            mapa_html = """
            <style>
                * {
                    box-sizing: border-box;
                    margin: 0;
                    padding: 0;
                }
                
                :root {
                    --primary: #3b82f6;
                    --primary-dark: #2563eb;
                    --bg-main: #ffffff;
                    --bg-canvas: #f8fafc;
                    --border: #e2e8f0;
                    --border-dark: #cbd5e1;
                    --text: #0f172a;
                    --text-muted: #64748b;
                    --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                    --shadow-lg: 0 10px 25px -3px rgba(0, 0, 0, 0.1);
                }

                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
                    background: var(--bg-main);
                    overflow: hidden;
                }

                #mapa-wrapper {
                    width: 100%;
                    height: 100%;
                    display: flex;
                    flex-direction: column;
                    background: var(--bg-canvas);
                }

                #mapa-area {
                    position: relative;
                    width: 100%;
                    flex: 1;
                    background: var(--bg-main);
                    background-image:
                        linear-gradient(var(--border) 1px, transparent 1px),
                        linear-gradient(90deg, var(--border) 1px, transparent 1px);
                    background-size: 40px 40px;
                    overflow: hidden;
                    touch-action: none;
                }

                .cont-box {
                    position: absolute;
                    background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
                    border: 2px solid var(--primary);
                    border-radius: 12px;
                    box-shadow: var(--shadow);
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    padding: 12px;
                    user-select: none;
                    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
                    min-width: 100px;
                    min-height: 100px;
                }

                .cont-box.clickable {
                    cursor: pointer;
                }

                .cont-box.draggable {
                    cursor: grab;
                }

                .cont-box.dragging {
                    cursor: grabbing !important;
                    opacity: 0.85;
                    z-index: 1000;
                    box-shadow: var(--shadow-lg);
                    transform: scale(1.05) rotate(2deg);
                }

                .cont-box:hover {
                    transform: translateY(-4px) scale(1.02);
                    box-shadow: 0 12px 24px -4px rgba(59, 130, 246, 0.3);
                    border-color: var(--primary-dark);
                    z-index: 100;
                }

                .cont-codigo {
                    font-size: 0.875rem;
                    font-weight: 700;
                    color: var(--primary-dark);
                    margin-bottom: 4px;
                    letter-spacing: 0.5px;
                    text-transform: uppercase;
                }

                .cont-qtd {
                    font-size: 2rem;
                    font-weight: 800;
                    color: var(--text);
                    line-height: 1;
                    margin-bottom: 2px;
                }

                .cont-label {
                    font-size: 0.65rem;
                    color: var(--text-muted);
                    text-transform: uppercase;
                    letter-spacing: 0.8px;
                    font-weight: 600;
                }

                #mapa-status {
                    padding: 8px 16px;
                    background: var(--bg-main);
                    border-top: 1px solid var(--border);
                    font-size: 0.75rem;
                    color: var(--text-muted);
                    text-align: center;
                    font-weight: 500;
                }

                /* Modal Overlay */
                #inv-overlay {
                    position: fixed;
                    inset: 0;
                    background: rgba(0, 0, 0, 0.6);
                    backdrop-filter: blur(4px);
                    display: none;
                    z-index: 2000;
                    animation: fadeIn 0.2s ease;
                }

                #inv-overlay.visible {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 20px;
                }

                /* Modal Panel Premium */
                #inv-panel {
                    background: var(--bg-main);
                    border-radius: 16px;
                    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
                    width: 100%;
                    max-width: 600px;
                    max-height: 85vh;
                    overflow: hidden;
                    display: flex;
                    flex-direction: column;
                    animation: slideUp 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                }

                @keyframes fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }

                @keyframes slideUp {
                    from {
                        opacity: 0;
                        transform: translateY(20px) scale(0.95);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0) scale(1);
                    }
                }

                /* Modal Header */
                .inv-header {
                    padding: 20px 24px;
                    border-bottom: 1px solid var(--border);
                    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
                    color: white;
                }

                .inv-header h2 {
                    font-size: 1.5rem;
                    font-weight: 700;
                    margin-bottom: 4px;
                }

                .inv-header p {
                    font-size: 0.875rem;
                    opacity: 0.9;
                }

                /* Modal Body */
                .inv-body {
                    padding: 24px;
                    overflow-y: auto;
                    flex: 1;
                }

                .inv-section {
                    margin-bottom: 24px;
                }

                .inv-section-title {
                    font-size: 0.75rem;
                    font-weight: 700;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    color: var(--text-muted);
                    margin-bottom: 12px;
                }

                .inv-lote {
                    background: var(--bg-canvas);
                    border: 1px solid var(--border);
                    border-radius: 10px;
                    padding: 12px 16px;
                    margin-bottom: 8px;
                    transition: all 0.2s ease;
                }

                .inv-lote:hover {
                    border-color: var(--primary);
                    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
                    transform: translateX(4px);
                }

                .inv-lote-row {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    gap: 12px;
                    font-size: 0.875rem;
                }

                .inv-lote-label {
                    color: var(--text-muted);
                    font-weight: 500;
                }

                .inv-lote-value {
                    color: var(--text);
                    font-weight: 600;
                }

                /* Modal Footer */
                .inv-footer {
                    padding: 16px 24px;
                    border-top: 1px solid var(--border);
                    background: var(--bg-canvas);
                }

                .btn-close {
                    width: 100%;
                    padding: 12px 24px;
                    background: var(--primary);
                    color: white;
                    border: none;
                    border-radius: 10px;
                    font-size: 0.95rem;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.2s ease;
                }

                .btn-close:hover {
                    background: var(--primary-dark);
                    transform: translateY(-2px);
                    box-shadow: 0 8px 16px rgba(59, 130, 246, 0.3);
                }

                /* Mobile Optimizations */
                @media (max-width: 640px) {
                    .cont-box {
                        min-width: 80px;
                        min-height: 80px;
                        padding: 8px;
                        border-radius: 8px;
                    }

                    .cont-codigo {
                        font-size: 0.75rem;
                    }

                    .cont-qtd {
                        font-size: 1.5rem;
                    }

                    .cont-label {
                        font-size: 0.6rem;
                    }

                    #inv-panel {
                        max-width: 100%;
                        border-radius: 12px 12px 0 0;
                    }

                    .inv-header h2 {
                        font-size: 1.25rem;
                    }

                    .inv-body {
                        padding: 16px;
                    }

                    .inv-lote-row {
                        font-size: 0.8rem;
                    }
                }
            </style>

            <div id="mapa-wrapper" class="__MOBILE_CLASS__">
                <div id="mapa-area">"""
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
            status_text = (
                t("map.status_edit")
                if st.session_state["mapa_modo_edicao"]
                else t("map.status_view")
            )
            mapa_render = mapa_render.replace("__STATUS_TEXT__", status_text)

            # Renderizar mapa com altura otimizada e responsiva
            st.markdown("<div class='map-workspace'>", unsafe_allow_html=True)
            if is_mobile:
                components.html(mapa_render, height=450, scrolling=False)
            else:
                components.html(mapa_render, height=550, scrolling=False)
            st.markdown("</div>", unsafe_allow_html=True)

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
