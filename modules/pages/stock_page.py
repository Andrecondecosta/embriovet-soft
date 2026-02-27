# Typed page module (Fase 3)

def run_stock_page(ctx: dict):
    globals().update(ctx)
        st.stop()

    if aba == "📈 Relatórios":
        run_reports_page({**globals(), **locals()})
        st.stop()

    # ------------------------------------------------------------
    # 📦 Ver Stock
    # ------------------------------------------------------------

    # ------------------------------------------------------------
    # 🗺️ Mapa dos Contentores
    # ------------------------------------------------------------
    if aba == "🗺️ Mapa dos Contentores":
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
            st.warning("Dependência em falta: execute `pip install streamlit-js-eval` para salvar layout do mapa.")
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
            st.markdown("### Adicionar Novo Contentor")

            with st.form("form_novo_contentor"):
                col_form1, col_form2 = st.columns([1, 1])

                with col_form1:
                    codigo = st.text_input(
                        "Código do Contentor *", 
                        placeholder="Ex: CT-01, A1, EMB01",
                        help="Identificador único alfanumérico"
                    )

                with col_form2:
                    descricao = st.text_input("Descrição (opcional)", placeholder="Localização ou notas")

                col_submit1, col_submit2 = st.columns([1, 1])
                with col_submit1:
                    submitted = st.form_submit_button("Criar Contentor", use_container_width=True)
                with col_submit2:
                    cancelar = st.form_submit_button("Cancelar", use_container_width=True)

                if cancelar:
                    st.session_state['modal_novo_contentor'] = False
                    st.rerun()

                if submitted:
                    if not codigo:
                        st.error("Código é obrigatório")
                    else:
                        if codigo in contentores_df['codigo'].values:
                            st.error(f"Já existe um contentor com o código '{codigo}'")
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
                                st.success(f"Contentor '{codigo}' criado com sucesso")
                                st.session_state['modal_novo_contentor'] = False
                                st.rerun()

        # Área do mapa
        if contentores_df.empty:
            st.info("Nenhum contentor cadastrado. Utilize 'Novo Contentor' para começar.")
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
                        st.markdown("<div class='map-tech-context'>Sistema de localização física e inventário de sémen equino</div>", unsafe_allow_html=True)
                        st.markdown(
                            f"<div class='map-toolbar-shell'><div class='map-toolbar-kpis'><span><b>{total_contentores}</b> contentores</span><span><b>{int(total_palhetas_geral)}</b> palhetas</span></div></div>",
                            unsafe_allow_html=True,
                        )

                        btn_m1, btn_m2, btn_m3 = st.columns([1, 1, 1])
                        with btn_m1:
                            criar_novo = st.button("Adicionar", key="map_add_btn_mobile", use_container_width=True)
                        with btn_m2:
                            if st.session_state["mapa_modo_edicao"]:
                                salvar_layout = st.button("Salvar", key="map_save_btn_mobile", type="primary", use_container_width=True)
                            else:
                                ativar_edicao = st.button("Editar mapa", key="map_edit_btn_mobile", use_container_width=True)
                        with btn_m3:
                            if st.session_state["mapa_modo_edicao"]:
                                cancelar_edicao = st.button("Cancelar", key="map_cancel_btn_mobile", use_container_width=True)
                    else:
                        st.markdown(
                            f"<div class='map-toolbar-shell'><div class='map-toolbar-kpis'><span class='map-tech-context-inline'>Sistema de localização física e inventário de sémen equino</span><span><b>{total_contentores}</b> contentores</span><span><b>{int(total_palhetas_geral)}</b> palhetas</span><span>{'modo edição ativo' if st.session_state['mapa_modo_edicao'] else 'modo normal'}</span></div></div>",
                            unsafe_allow_html=True,
                        )
                        bar_btn1, bar_btn2, bar_btn3 = st.columns([1, 1, 1])
                        with bar_btn1:
                            criar_novo = st.button("Adicionar contentor", key="map_add_btn_desktop", use_container_width=True)
                        with bar_btn2:
                            if st.session_state["mapa_modo_edicao"]:
                                salvar_layout = st.button("Salvar layout", key="map_save_btn_desktop", type="primary", use_container_width=True)
                            else:
                                ativar_edicao = st.button("Editar mapa", key="map_edit_btn_desktop", use_container_width=True)
                        with bar_btn3:
                            if st.session_state["mapa_modo_edicao"]:
                                cancelar_edicao = st.button("Cancelar edição", key="map_cancel_btn_desktop", use_container_width=True)

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
                        st.error("Para salvar layout no mapa, instale: pip install streamlit-js-eval")
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
                                st.toast(f"Layout guardado ({atualizados} contentor(es))", icon="✅")
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
                st.markdown("<div class='inv-contentores-head'>Inventário de Contentores</div>", unsafe_allow_html=True)

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
                            if st.button("Editar", key=f"edit_{row['id']}", use_container_width=True):
                                st.session_state[f'modal_editar_{row["id"]}'] = True
                                st.rerun()

                            pode_apagar = int(total_palhetas) == 0
                            if st.button(
                                "Apagar",
                                key=f"del_{row['id']}",
                                use_container_width=True,
                                disabled=not pode_apagar,
                                help="Só é possível apagar quando o contentor não tem stock"
                            ):
                                if deletar_contentor(row['id']):
                                    st.success(f"Contentor '{row['codigo']}' apagado")
                                    st.rerun()
                            if not pode_apagar:
                                st.caption("Apagar bloqueado: contentor com stock")

                        if not stock_contentor.empty:
                            st.markdown("**Lotes:**")
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
                                st.markdown("#### Editar Contentor")

                                col_edit1, col_edit2 = st.columns(2)
                                with col_edit1:
                                    novo_codigo = st.text_input("Código", value=row['codigo'])
                                with col_edit2:
                                    nova_descricao = st.text_input("Descrição", value=row['descricao'] or '')

                                col_btn_edit1, col_btn_edit2 = st.columns(2)
                                with col_btn_edit1:
                                    salvar = st.form_submit_button("Salvar", use_container_width=True)
                                with col_btn_edit2:
                                    cancelar_edit = st.form_submit_button("Cancelar", use_container_width=True)

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
                                        st.success("Contentor atualizado")
                                        st.session_state[f'modal_editar_{row["id"]}'] = False
                                        st.rerun()

            else:
                # MODO LISTA (mantido para compatibilidade)
                st.markdown("### Lista de Contentores")

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

        st.stop()

    if aba == "📦 Ver Stock":
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
    elif aba == "➕ Adicionar Stock":
        st.header("➕ Inserir novo stock com Proprietário")

        if proprietarios.empty:
            st.warning("⚠️ Nenhum proprietário cadastrado.")
            if st.button("➕ Adicionar Primeiro Proprietário", type="primary"):
                modal_adicionar_proprietario()
        else:
            # Carregar contentores
            contentores_df = carregar_contentores()

            if contentores_df.empty:
                st.warning("⚠️ Nenhum contentor cadastrado. Por favor, crie contentores primeiro no Mapa.")
            else:
                # Botão + fora do form
                if st.button("➕ Novo Proprietário", key="btn_add_prop_stock", help="Adicionar novo proprietário"):
                    modal_adicionar_proprietario()

                with st.form("novo_stock"):
                    garanhao = st.text_input("Garanhão *", help="Nome obrigatório")

                    # Verificar se há proprietário recém-adicionado
                    if 'novo_proprietario_id' in st.session_state:
                        idx_default = list(proprietarios["id"]).index(st.session_state['novo_proprietario_id'])
                    else:
                        idx_default = 0

                    proprietario_nome = st.selectbox("Proprietário do Sémen *", proprietarios["nome"], index=idx_default)

                    dono_id = int(proprietarios.loc[proprietarios["nome"] == proprietario_nome, "id"].iloc[0])

                    col1, col2 = st.columns(2)
                    with col1:
                        data = st.text_input("Data de Produção")
                        origem = st.text_input("Origem Externa / Referência")
                        palhetas = st.number_input("Palhetas Produzidas *", min_value=0, value=0)
                        qualidade = st.number_input("Qualidade (%)", min_value=0, max_value=100, value=0)
                        concentracao = st.number_input("Concentração (milhões/mL)", min_value=0, value=0)

                    with col2:
                        motilidade = st.number_input("Motilidade (%)", min_value=0, max_value=100, value=0)
                        certificado = st.selectbox("Certificado?", ["Sim", "Não"])
                        dose = st.text_input("Dose")

                    st.markdown("---")
                    st.subheader("📍 Localização Física")

                    col_loc1, col_loc2, col_loc3 = st.columns(3)
                    with col_loc1:
                        contentor_selecionado = st.selectbox(
                            "Contentor *",
                            options=contentores_df["codigo"].tolist(),
                            help="Selecione o contentor onde o sémen será armazenado"
                        )
                        contentor_id = int(contentores_df.loc[contentores_df["codigo"] == contentor_selecionado, "id"].iloc[0])

                    with col_loc2:
                        canister = st.selectbox(
                            "Canister *",
                            options=list(range(1, 11)),
                            help="Número do canister (1-10)"
                        )

                    with col_loc3:
                        andar = st.radio(
                            "Andar *",
                            options=[1, 2],
                            format_func=lambda x: f"{x}º",
                            horizontal=True,
                            help="Nível dentro do canister"
                        )

                    observacoes = st.text_area("Observações", help="Informações adicionais (opcional)")
                    submitted = st.form_submit_button("💾 Salvar")

                    if submitted:
                        palhetas_int = int(to_py(palhetas) or 0)

                        if not garanhao:
                            st.error("❌ Nome do garanhão é obrigatório")
                        elif palhetas_int <= 0:
                            st.error("❌ Número de palhetas deve ser maior que zero")
                        else:
                            ok = inserir_stock(
                                {
                                    "Garanhão": garanhao,
                                    "Proprietário": dono_id,
                                    "Data": data,
                                    "Origem": origem,
                                    "Palhetas": palhetas_int,
                                    "Qualidade": int(to_py(qualidade) or 0),
                                    "Concentração": int(to_py(concentracao) or 0),
                                    "Motilidade": int(to_py(motilidade) or 0),
                                    "Certificado": certificado,
                                    "Dose": dose,
                                    "Contentor": contentor_id,
                                    "Canister": canister,
                                    "Andar": andar,
                                    "Observações": observacoes,
                                }
                            )
                            if ok:
                                st.success("✅ Stock adicionado com sucesso!")
                                # Marcar que usou o proprietário
                                if 'novo_proprietario_id' in st.session_state:
                                    st.session_state['novo_proprietario_usado'] = True
                                # Mudar aba para Ver Stock
                                st.session_state['aba_selecionada'] = "📦 Ver Stock"
                                st.rerun()

    # ------------------------------------------------------------
    # 📝 Registrar Inseminação
    # ------------------------------------------------------------
