# Typed page module (Fase 3)
from modules.i18n import t

def run_map_page(ctx: dict):
    globals().update(ctx)
    # Carregar contentores
    contentores_df = carregar_contentores()

    # Cabeçalho da página
    primary_color = (app_settings or {}).get("primary_color") or "#1D4ED8"
    st.markdown(
        f"""
        <style>
            .map-page-header {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 12px 16px;
                background: linear-gradient(135deg, #f8fafc 0%, #ffffff 100%);
                margin-bottom: 10px;
                box-shadow: 0 2px 8px rgba(15,23,42,0.05);
            }}
            .map-page-title {{
                font-size: 1rem;
                font-weight: 700;
                color: #0f172a;
                margin: 0;
            }}
            .map-page-subtitle {{
                font-size: .75rem;
                color: #64748b;
                margin-top: 2px;
            }}
            .map-empty-state {{
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 60px 40px;
                border: 2px dashed #e2e8f0;
                border-radius: 12px;
                text-align: center;
                color: #64748b;
                margin-top: 20px;
            }}
            .map-empty-icon {{
                font-size: 3rem;
                margin-bottom: 16px;
                opacity: 0.6;
            }}
            .map-empty-title {{
                font-size: 1rem;
                font-weight: 600;
                color: #334155;
                margin-bottom: 8px;
            }}
            .map-empty-text {{
                font-size: .85rem;
                color: #94a3b8;
                max-width: 320px;
            }}
        </style>
        <div class='map-page-header'>
            <div>
                <div class='map-page-title'>Mapa dos Contentores</div>
                <div class='map-page-subtitle'>Gerir localizações físicas e stock por contentor</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
        # Botão para adicionar mesmo sem contentores
        col_empty1, col_empty2, col_empty3 = st.columns([1, 2, 1])
        with col_empty2:
            st.markdown(
                """
                <div class='map-empty-state'>
                    <div class='map-empty-icon'>&#128230;</div>
                    <div class='map-empty-title'>Nenhum contentor registado</div>
                    <div class='map-empty-text'>Adicione o primeiro contentor para começar a gerir as localizações físicas do seu stock.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("")
            if st.button("+ Adicionar Primeiro Contentor", type="primary", use_container_width=True):
                st.session_state['modal_novo_contentor'] = True
                st.rerun()
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
                <div id="mapa-area">
                </div>
                <div id="mapa-status">__STATUS_TEXT__</div>
            </div>

            <!-- Modal de Inventário Premium -->
            <div id="inv-overlay">
                <div id="inv-panel">
                    <div class="inv-header">
                        <h2 id="inv-titulo">Contentor</h2>
                        <p id="inv-subtitulo"></p>
                    </div>
                    <div class="inv-body" id="inv-body"></div>
                    <div class="inv-footer">
                        <button class="btn-close" onclick="fecharModal()">Fechar</button>
                    </div>
                </div>
            </div>

            <script>
                const contentores = __CONTENTORES_DATA__;
                const isEditMode = __EDIT_MODE__;
                const isMobile = __IS_MOBILE__;
                const mapaArea = document.getElementById('mapa-area');
                const statusBar = document.getElementById('mapa-status');
                const invOverlay = document.getElementById('inv-overlay');
                const invPanel = document.getElementById('inv-panel');
                const invBody = document.getElementById('inv-body');
                const invTitulo = document.getElementById('inv-titulo');
                const invSubtitulo = document.getElementById('inv-subtitulo');

                let dragInfo = null;
                let areaScale = 1;

                function computeScale() {
                    const rect = mapaArea.getBoundingClientRect();
                    areaScale = rect.width / (isMobile ? 375 : 900);
                }

                function criarContentor(c) {
                    const box = document.createElement('div');
                    box.className = 'cont-box';
                    if (!isEditMode) box.classList.add('clickable');
                    if (isEditMode) box.classList.add('draggable');

                    box.innerHTML = `
                        <div class="cont-codigo">${c.codigo}</div>
                        <div class="cont-qtd">${c.total_palhetas}</div>
                        <div class="cont-label">palhetas</div>
                    `;

                    const baseW = isMobile ? 80 : 100;
                    const baseH = isMobile ? 80 : 100;
                    box.style.left = (c.pos_x * areaScale) + 'px';
                    box.style.top = (c.pos_y * areaScale) + 'px';
                    box.style.width = baseW + 'px';
                    box.style.height = baseH + 'px';

                    if (isEditMode) {
                        box.addEventListener('mousedown', startDrag);
                        box.addEventListener('touchstart', startDrag, {passive: false});
                    } else {
                        box.addEventListener('click', () => mostrarInventario(c));
                    }

                    mapaArea.appendChild(box);
                }

                function startDrag(e) {
                    e.preventDefault();
                    const box = e.currentTarget;
                    box.classList.add('dragging');
                    const rect = box.getBoundingClientRect();
                    const areaRect = mapaArea.getBoundingClientRect();
                    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
                    const clientY = e.touches ? e.touches[0].clientY : e.clientY;

                    dragInfo = {
                        box: box,
                        offsetX: clientX - rect.left,
                        offsetY: clientY - rect.top,
                        areaLeft: areaRect.left,
                        areaTop: areaRect.top,
                        areaW: areaRect.width,
                        areaH: areaRect.height
                    };

                    document.addEventListener('mousemove', onDrag);
                    document.addEventListener('mouseup', endDrag);
                    document.addEventListener('touchmove', onDrag, {passive: false});
                    document.addEventListener('touchend', endDrag);
                }

                function onDrag(e) {
                    if (!dragInfo) return;
                    e.preventDefault();
                    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
                    const clientY = e.touches ? e.touches[0].clientY : e.clientY;

                    let newX = clientX - dragInfo.areaLeft - dragInfo.offsetX;
                    let newY = clientY - dragInfo.areaTop - dragInfo.offsetY;

                    newX = Math.max(0, Math.min(newX, dragInfo.areaW - dragInfo.box.offsetWidth));
                    newY = Math.max(0, Math.min(newY, dragInfo.areaH - dragInfo.box.offsetHeight));

                    dragInfo.box.style.left = newX + 'px';
                    dragInfo.box.style.top = newY + 'px';
                }

                function endDrag(e) {
                    if (!dragInfo) return;
                    dragInfo.box.classList.remove('dragging');
                    
                    const finalX = parseInt(dragInfo.box.style.left) / areaScale;
                    const finalY = parseInt(dragInfo.box.style.top) / areaScale;

                    try {
                        const layoutData = JSON.parse(localStorage.getItem('contentor_layout_pending') || '{}');
                        const codigo = dragInfo.box.querySelector('.cont-codigo').textContent;
                        layoutData[codigo] = {x: Math.round(finalX), y: Math.round(finalY)};
                        localStorage.setItem('contentor_layout_pending', JSON.stringify(layoutData));
                    } catch (err) {
                        console.error('Erro ao salvar posição:', err);
                    }

                    document.removeEventListener('mousemove', onDrag);
                    document.removeEventListener('mouseup', endDrag);
                    document.removeEventListener('touchmove', onDrag);
                    document.removeEventListener('touchend', endDrag);
                    dragInfo = null;
                }

                function mostrarInventario(cont) {
                    invTitulo.textContent = `Contentor ${cont.codigo}`;
                    invSubtitulo.textContent = `${cont.total_palhetas} palhetas no total`;
                    
                    let html = '<div class="inv-section"><div class="inv-section-title">📦 Lotes de Sémen</div>';
                    
                    if (cont.lotes && cont.lotes.length > 0) {
                        cont.lotes.forEach(lote => {
                            html += `
                                <div class="inv-lote">
                                    <div class="inv-lote-row">
                                        <span class="inv-lote-label">🐴 Garanhão:</span>
                                        <span class="inv-lote-value">${lote.garanhao}</span>
                                    </div>
                                    <div class="inv-lote-row">
                                        <span class="inv-lote-label">👤 Proprietário:</span>
                                        <span class="inv-lote-value">${lote.proprietario}</span>
                                    </div>
                                    <div class="inv-lote-row">
                                        <span class="inv-lote-label">📍 Localização:</span>
                                        <span class="inv-lote-value">C${lote.canister} / A${lote.andar}</span>
                                    </div>
                                    <div class="inv-lote-row">
                                        <span class="inv-lote-label">🧬 Palhetas:</span>
                                        <span class="inv-lote-value">${lote.palhetas}</span>
                                    </div>
                                </div>
                            `;
                        });
                    } else {
                        html += '<p style="color: var(--text-muted); text-align: center; padding: 20px;">Nenhum lote neste contentor</p>';
                    }
                    
                    html += '</div>';
                    invBody.innerHTML = html;
                    invOverlay.classList.add('visible');
                }

                function fecharModal() {
                    invOverlay.classList.remove('visible');
                }

                invOverlay.addEventListener('click', (e) => {
                    if (e.target === invOverlay) fecharModal();
                });

                window.addEventListener('resize', () => {
                    computeScale();
                    contentores.forEach((c, i) => {
                        const box = mapaArea.children[i];
                        if (box) {
                            box.style.left = (c.pos_x * areaScale) + 'px';
                            box.style.top = (c.pos_y * areaScale) + 'px';
                        }
                    });
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
