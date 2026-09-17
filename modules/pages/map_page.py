# Typed page module (Fase 3)
import json
import logging
import math
import time
from html import escape

import streamlit as st

from modules.i18n import t
from modules.repositories.container_repo import (
    adicionar_contentor,
    atualizar_posicao_contentor,
    deletar_contentor,
    editar_contentor,
    inverter_andares,
)
from modules.repositories.settings_repo import get_app_settings
from modules.repositories.stock_repo import (
    carregar_contentores,
    obter_stock_contentor,
)
from modules.ui_kit import DEFAULT_PRIMARY_COLOR

logger = logging.getLogger(__name__)


def run_map_page(ctx: dict):
    with st.container(key="mapa-page-scope"):
        # Pedido 9 · Fase 2: `ctx` mantido para compat com o router; nada é
        # injetado — imports explícitos no topo cobrem tudo.
        del ctx
        app_settings = get_app_settings() or {}

        # Carregar contentores
        contentores_df = carregar_contentores()

        # Cabeçalho da página
        primary_color = (app_settings or {}).get("primary_color") or DEFAULT_PRIMARY_COLOR

        # RGB da cor primária — usado em rgba() (ex.: sombras do mapa e do
        # tanque redondo). Resistente a cor vazia/inválida (ex.:
        # `primary_color` por preencher numa instalação local nova) — cai
        # para a cor primária por defeito do projeto em vez de rebentar.
        _default_hex = DEFAULT_PRIMARY_COLOR.lstrip('#')

        def hex_to_rgb(h):
            h = (h or "").lstrip('#').strip()
            if len(h) == 3:
                h = ''.join(c * 2 for c in h)
            if len(h) != 6:
                h = _default_hex
            try:
                return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
            except ValueError:
                return tuple(int(_default_hex[i:i+2], 16) for i in (0, 2, 4))

        pr, pg, pb = hex_to_rgb(primary_color)

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

        # Arrumação final: já não há modo "Editar" — clicar num contentor
        # abre sempre o modal (ver + editar nome/descrição + apagar);
        # arrastar está sempre ativo e grava sozinho (ver
        # `mapa_salvar_layout_pendente` mais abaixo, agora acionado pelo
        # próprio arrasto em vez de um botão "Salvar Layout").
        if "mapa_salvar_layout_pendente" not in st.session_state:
            st.session_state["mapa_salvar_layout_pendente"] = False

        if "mapa_salvar_layout_tentativas" not in st.session_state:
            st.session_state["mapa_salvar_layout_tentativas"] = 0

        if "map_bridge_v3_bootstrapped" not in st.session_state:
            st.session_state["map_bridge_v3_bootstrapped"] = False

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
            if not st.session_state.get("map_bridge_v3_bootstrapped", False):
                bridge_boot = streamlit_js_eval(
                js_expressions="""
                    (function(){
                        try {
                            var targetWin = (window.parent && window.parent !== window) ? window.parent : window;
                            var targetDoc = targetWin.document;

                            // Bridge para layout drag-and-drop
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

                            // A lógica de clique (handler + bind + observer + intervalo)
                            // tem de ficar a viver no realm da JANELA PRINCIPAL, não no
                            // realm deste iframe efémero do streamlit_js_eval. Descoberta
                            // ao implementar o tanque redondo (Passo 2/3): o Streamlit
                            // desmonta este iframe no rerun seguinte (ex.: ao trocar de
                            // andar), e a partir daí qualquer addEventListener/
                            // setInterval/MutationObserver registado a partir DAQUI
                            // morre silenciosamente (o browser cancela a execução de
                            // callbacks cujo código pertence a um realm destruído,
                            // mesmo que o alvo/"this" continue a ser a janela
                            // principal — confirmado empiricamente: um contador de
                            // "ticks" do intervalo parava sempre exactamente no rerun
                            // seguinte ao boot). `targetWin.eval(...)` corre este bloco
                            // DENTRO do realm da própria janela principal, que só
                            // morre se o separador fechar.
                            if (!targetWin.__hmBridgeCoreInstalled) {
                                targetWin.__hmBridgeCoreInstalled = true;
                                targetWin.eval(`
                                    (function(){
                                        var targetDoc = document;

                                        function handleHmCellClick(ev) {
                                            ev.stopPropagation();
                                            var cell = ev.currentTarget;
                                            var cId = cell.getAttribute('data-cont');
                                            var c   = cell.getAttribute('data-c');
                                            var a   = cell.getAttribute('data-a');
                                            targetDoc.querySelectorAll('.hm-cell.selected').forEach(function(x){ x.classList.remove('selected'); });
                                            cell.classList.add('selected');

                                            // Passo 3: dentro do modal do tanque redondo, o
                                            // clique troca a visibilidade da info do canister
                                            // (pré-carregada, escondida) — sem round-trip ao
                                            // Python. Fora do modal (uso antigo da grelha),
                                            // mantém-se o comportamento de sempre: realçar +
                                            // scroll até à linha do lote na página.
                                            var dialogScope = cell.closest('[data-testid="stDialog"]');
                                            if (dialogScope) {
                                                dialogScope.querySelectorAll('.tank-info-block').forEach(function(b){ b.style.display = 'none'; });
                                                var alvo = dialogScope.querySelector('.tank-info-block[data-canister-info="' + c + '"]');
                                                if (alvo) { alvo.style.display = 'block'; }
                                            } else {
                                                targetDoc.querySelectorAll('.lote-row.hl').forEach(function(x){ x.classList.remove('hl'); });
                                                var rows = targetDoc.querySelectorAll(
                                                    '.lote-row[data-cont="' + cId + '"][data-c="' + c + '"][data-a="' + a + '"]'
                                                );
                                                rows.forEach(function(r){ r.classList.add('hl'); });
                                                if (rows.length > 0) {
                                                    rows[0].scrollIntoView({behavior:'smooth', block:'center'});
                                                }
                                            }
                                        }

                                        // Garante pointer-events auto em toda a cadeia até .hm-cell
                                        function ensureClickable(cell) {
                                            try {
                                                cell.style.pointerEvents = 'auto';
                                                cell.style.cursor = 'pointer';
                                                cell.style.position = 'relative';
                                                cell.style.zIndex = '5';
                                                var p = cell.parentElement;
                                                var depth = 0;
                                                while (p && depth < 12) {
                                                    var cs = window.getComputedStyle(p);
                                                    if (cs && cs.pointerEvents === 'none') {
                                                        p.style.pointerEvents = 'auto';
                                                    }
                                                    if (p.matches && p.matches('[data-testid="stMarkdownContainer"], [data-testid="stMarkdown"], [data-testid="stElementContainer"], [data-testid="stVerticalBlock"], [data-testid="stHorizontalBlock"]')) {
                                                        p.style.pointerEvents = 'auto';
                                                    }
                                                    p = p.parentElement;
                                                    depth += 1;
                                                }
                                            } catch (e) {}
                                        }

                                        // Passo 3: clicar no resumo do canister (dentro do
                                        // modal) expande/recolhe o detalhe de cada lote —
                                        // também sem round-trip ao Python, mesmo espírito
                                        // do handleHmCellClick.
                                        function handleResumoClick(ev) {
                                            var el = ev.currentTarget;
                                            var c = el.getAttribute('data-canister-resumo');
                                            var scope = el.closest('[data-testid="stDialog"]') || targetDoc;
                                            var detalhe = scope.querySelector('.tank-info-detalhe[data-canister-detalhe="' + c + '"]');
                                            if (detalhe) {
                                                detalhe.style.display = (detalhe.style.display === 'block') ? 'none' : 'block';
                                            }
                                        }

                                        function bindCells(root) {
                                            try {
                                                var scope = root || targetDoc;
                                                var cells = scope.querySelectorAll('.hm-cell');
                                                cells.forEach(function(cell){
                                                    if (cell.__hmBound) return;
                                                    cell.__hmBound = true;
                                                    ensureClickable(cell);
                                                    try {
                                                        cell.addEventListener('click', handleHmCellClick, false);
                                                        cell.addEventListener('touchend', function(e){
                                                            e.preventDefault();
                                                            handleHmCellClick({currentTarget: cell, stopPropagation: function(){}});
                                                        }, {passive: false});
                                                    } catch (e) {}
                                                });
                                                var resumos = scope.querySelectorAll('.tank-info-resumo');
                                                resumos.forEach(function(el){
                                                    if (el.__hmBound) return;
                                                    el.__hmBound = true;
                                                    try { el.addEventListener('click', handleResumoClick, false); } catch (e) {}
                                                });
                                            } catch (e) {}
                                        }

                                        // Clicar (sem arrastar) numa caixa do mapa livre
                                        // (fora deste modal, no components.html do topo
                                        // da página) clica sozinho no botão Streamlit
                                        // real escondido "Ver interior" desse contentor,
                                        // que abre o modal (ver+editar+apagar). Uma
                                        // Promise assíncrona à espera do clique, através
                                        // da fronteira do iframe, foi testada à parte e
                                        // mostrou-se pouco fiável; este auto-clique foi
                                        // validado num spike isolado (20/20 cliques) por
                                        // ser síncrono, sem nada "à espera" entre reruns.
                                        // Largar um contentor arrastado (fim do arrasto,
                                        // ver endPress) usa o mesmo mecanismo para clicar
                                        // num botão escondido que grava a posição sem
                                        // precisar do botão "Salvar Layout".
                                        window.addEventListener('message', function(event){
                                            var data = event && event.data ? event.data : null;
                                            if (!data) return;
                                            var botao = null;
                                            if (data.type === 'CONTENTOR_MOSTRAR_CARTAO') {
                                                botao = targetDoc.querySelector('.st-key-ver_interior_' + data.contId + ' button');
                                            } else if (data.type === 'CONTENTOR_POSICAO_ARRASTADA') {
                                                botao = targetDoc.querySelector('.st-key-map_autosave_trigger button');
                                            } else {
                                                return;
                                            }
                                            if (botao) { botao.click(); }
                                        });

                                        bindCells(targetDoc);
                                        var obs = new MutationObserver(function(mutations){
                                            for (var i = 0; i < mutations.length; i++) {
                                                var m = mutations[i];
                                                if (m.addedNodes && m.addedNodes.length) {
                                                    for (var j = 0; j < m.addedNodes.length; j++) {
                                                        var node = m.addedNodes[j];
                                                        if (node.nodeType !== 1) continue;
                                                        if (node.classList && node.classList.contains('hm-cell')) {
                                                            bindCells(node.parentElement || targetDoc);
                                                        } else if (node.querySelectorAll) {
                                                            bindCells(node);
                                                        }
                                                    }
                                                }
                                            }
                                        });
                                        obs.observe(targetDoc.body, {childList: true, subtree: true});

                                        // Re-bind periódico de segurança, para sempre (não só
                                        // nos primeiros segundos) — o MutationObserver nem
                                        // sempre reage a tempo quando um rerun substitui o
                                        // innerHTML de um bloco inteiro (ex.: trocar de andar
                                        // no tanque redondo, Passo 2/3).
                                        setInterval(function(){ bindCells(targetDoc); }, 500);
                                    })();
                                `);
                            }

                        } catch (e) {}
                        return true;
                    })()
                """,
                key="map_layout_bridge_v3",
                want_output=True,
                )
            if bridge_boot is True:
                st.session_state["map_bridge_v3_bootstrapped"] = True

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
                if st.button("+ Adicionar Primeiro Contentor", type="primary", width="stretch"):
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
                                "garanhao": lote.get('garanhao_nome') or lote.get('garanhao') or "—",
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
                reorganizar = False
                auto_commit_layout = False

                st.markdown(
                    """
                    <style>
                        /* Botões modernos e elegantes — âmbito restrito ao
                           contentor próprio do mapa (.st-key-mapa-page-scope,
                           gerado pelo st.container(key=...) que envolve toda
                           a run_map_page) para nunca vazar para a sidebar
                           nem para os outros separadores da Stock de sémen. */
                        .st-key-mapa-page-scope div[data-testid="stButton"] > button {
                            border-radius: 8px !important;
                            font-weight: 500 !important;
                            font-size: 0.9rem !important;
                            padding: 8px 20px !important;
                            transition: all 0.2s ease !important;
                            border: 1px solid #e2e8f0 !important;
                        }

                        .st-key-mapa-page-scope div[data-testid="stButton"] > button:hover {
                            transform: translateY(-1px) !important;
                            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1) !important;
                        }
                        /* Cor do botão "primary" (ex.: Salvar) vem do override
                           global em `inject_shell_css` (cor da marca) — não
                           hardcodar uma cor aqui. */

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
                            .st-key-mapa-page-scope div[data-testid="stButton"] > button {
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

                        /* Botões escondidos que só existem para o bridge de
                           clique lhes chamar .click() (ver targetWin.eval
                           mais acima) — precisam de estar no DOM e clicáveis
                           para o Streamlit disparar o onClick real, por isso
                           não usamos display:none aqui (alguns browsers não
                           são consistentes a disparar .click() em elementos
                           com display:none); ficam sim fora do ecrã. */
                        div[class*="st-key-ver_interior_"],
                        div[class*="st-key-map_autosave_trigger"] {
                            position: absolute !important;
                            width: 1px !important;
                            height: 1px !important;
                            padding: 0 !important;
                            margin: -1px !important;
                            overflow: hidden !important;
                            clip: rect(0, 0, 0, 0) !important;
                            white-space: nowrap !important;
                            border: 0 !important;
                        }

                        /* Logos e header nativo do Streamlit não devem intercetar cliques
                           sobre as células do heatmap (overlap posicional). */
                        [data-testid="stSidebar"] img,
                        [data-testid="stSidebarContent"] img,
                        .app-topbar-title,
                        [data-testid="stMarkdownContainer"] > div > img,
                        [data-testid="stMarkdown"] img {
                            pointer-events: none !important;
                        }
                        [data-testid="stHeader"] {
                            pointer-events: none !important;
                        }
                        [data-testid="stHeader"] * {
                            pointer-events: auto;
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
                                <span><b>{total_contentores}</b> Contentores</span>
                                <span><b>{int(total_palhetas_geral)}</b> Palhetas</span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    # Botões de ação — arrumação final: tudo sobre um
                    # contentor faz-se ao clicar nele (ver+editar+apagar no
                    # modal) e arrastar grava sozinho a posição (ver
                    # `auto_commit_layout` mais abaixo); a toolbar fica só
                    # com Adicionar e Reorganizar.
                    if is_mobile:
                        btn_m1, btn_m2 = st.columns([1, 1])
                        with btn_m1:
                            criar_novo = st.button("+ Novo", key="map_add_btn_mobile", width="stretch")
                        with btn_m2:
                            reorganizar = st.button("Reorganizar", key="map_reorganize_btn_mobile", width="stretch")
                    else:
                        bar_btn1, bar_btn2 = st.columns([2, 1])
                        with bar_btn1:
                            criar_novo = st.button("+ Adicionar Contentor", key="map_add_btn_desktop", width="stretch")
                        with bar_btn2:
                            reorganizar = st.button("Reorganizar", key="map_reorganize_btn", width="stretch", help="Distribui todos os contentores em grelha automática")

                    # Botão escondido — o bridge de clique chama-lhe .click()
                    # quando um arrasto termina (ver endPress/JS mais
                    # abaixo), para gravar a posição sem precisar de um
                    # "Salvar Layout" manual.
                    auto_commit_layout = st.button("Gravar posição", key="map_autosave_trigger")

                if criar_novo:
                    st.session_state['modal_novo_contentor'] = True
                    st.rerun()

                if reorganizar:
                    # Distribui contentores em grelha automática
                    BOX_W, BOX_H, MARGIN = 115, 110, 10
                    COLS = max(1, min(7, len(contentores_df)))
                    ok = 0
                    for i, (_, row) in enumerate(contentores_df.iterrows()):
                        col_idx = i % COLS
                        row_idx = i // COLS
                        nx = MARGIN + col_idx * BOX_W
                        ny = MARGIN + row_idx * BOX_H
                        if atualizar_posicao_contentor(int(row['id']), nx, ny):
                            ok += 1
                    st.success(t("map.reorganized", count=ok))
                    st.rerun()

                if auto_commit_layout:
                    if not js_eval_disponivel:
                        st.error(t("map.install_dependency"))
                    else:
                        logger.info("Auto-save de posição acionado pelo arrasto")
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
                
                    html, body {
                        height: 100%;
                        margin: 0;
                        padding: 0;
                        overflow: hidden;
                    }
                
                    :root {
                        --primary: """ + primary_color + """;
                        --primary-dark: """ + primary_color + """;
                        --primary-rgb: """ + f"{pr},{pg},{pb}" + """;
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
                        cursor: grab;
                        /* Arrastar está sempre ativo (não só em modo edição);
                           touch-action só aqui (não em #mapa-area inteiro),
                           para o resto do mapa continuar a deixar a página
                           fazer scroll normalmente em mobile. */
                        touch-action: none;
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
                        box-shadow: 0 12px 24px -4px rgba(var(--primary-rgb), 0.3);
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
                    }
                </style>

                <div id="mapa-wrapper" class="__MOBILE_CLASS__">
                    <div id="mapa-area">
                    </div>
                    <div id="mapa-status">__STATUS_TEXT__</div>
                </div>

                <script>
                    const contentores = __CONTENTORES_DATA__;
                    const isMobile = __IS_MOBILE__;
                    const mapaArea = document.getElementById('mapa-area');
                    const statusBar = document.getElementById('mapa-status');

                    // Distância mínima (px) para um gesto passar de "pode ser
                    // clique" a "é arrasto" — maior em touch porque o dedo é
                    // menos preciso do que o rato. Critério escolhido em vez
                    // de tempo de pressão: não obriga a uma pausa antes de
                    // poder começar a arrastar, e um clique lento mas parado
                    // nunca é mal-classificado como arrasto.
                    const DRAG_THRESHOLD_MOUSE = 6;
                    const DRAG_THRESHOLD_TOUCH = 10;

                    let pressInfo = null;
                    let areaScale = 1;
                    let ultimoToqueTs = 0;

                    function computeScale() {
                        const rect = mapaArea.getBoundingClientRect();
                        areaScale = rect.width / (isMobile ? 375 : 900);
                    }

                    function criarContentor(c) {
                        const box = document.createElement('div');
                        box.className = 'cont-box';
                        box.dataset.contId = String(c.id);

                        box.innerHTML = `
                            <div class="cont-codigo">${c.codigo}</div>
                            <div class="cont-qtd">${c.palhetas}</div>
                            <div class="cont-label">palhetas</div>
                        `;

                        const baseW = isMobile ? 80 : 100;
                        const baseH = isMobile ? 80 : 100;
                        box.style.left = (c.x * areaScale) + 'px';
                        box.style.top = (c.y * areaScale) + 'px';
                        box.style.width = baseW + 'px';
                        box.style.height = baseH + 'px';

                        // Arrastar está sempre ativo; um clique sem
                        // movimento (ver startPress/endPress) é que decide
                        // se abre o círculo ou a edição, consoante o modo.
                        box.addEventListener('mousedown', startPress);
                        box.addEventListener('touchstart', startPress, {passive: true});

                        mapaArea.appendChild(box);
                    }

                    function startPress(e) {
                        // Em touch, não faz preventDefault aqui — só quando o
                        // gesto for confirmado como arrasto (ver
                        // onPressMove), para não bloquear o scroll normal da
                        // página num simples toque.
                        const isTouch = !!e.touches;
                        if (isTouch) {
                            ultimoToqueTs = Date.now();
                        } else if (Date.now() - ultimoToqueTs < 500) {
                            // Ignora o mousedown "fantasma" que os browsers
                            // móveis emitem a seguir a um touchend.
                            return;
                        } else {
                            e.preventDefault();
                        }

                        const box = e.currentTarget;
                        const rect = box.getBoundingClientRect();
                        const areaRect = mapaArea.getBoundingClientRect();
                        const clientX = isTouch ? e.touches[0].clientX : e.clientX;
                        const clientY = isTouch ? e.touches[0].clientY : e.clientY;

                        pressInfo = {
                            box: box,
                            contId: box.dataset.contId,
                            startX: clientX,
                            startY: clientY,
                            offsetX: clientX - rect.left,
                            offsetY: clientY - rect.top,
                            areaLeft: areaRect.left,
                            areaTop: areaRect.top,
                            areaW: areaRect.width,
                            areaH: areaRect.height,
                            isDragging: false,
                        };

                        document.addEventListener('mousemove', onPressMove);
                        document.addEventListener('mouseup', endPress);
                        document.addEventListener('touchmove', onPressMove, {passive: false});
                        document.addEventListener('touchend', endPress);
                    }

                    function onPressMove(e) {
                        if (!pressInfo) return;
                        const isTouch = !!e.touches;
                        const clientX = isTouch ? e.touches[0].clientX : e.clientX;
                        const clientY = isTouch ? e.touches[0].clientY : e.clientY;

                        if (!pressInfo.isDragging) {
                            const dx = clientX - pressInfo.startX;
                            const dy = clientY - pressInfo.startY;
                            const limiar = isTouch ? DRAG_THRESHOLD_TOUCH : DRAG_THRESHOLD_MOUSE;
                            if (Math.hypot(dx, dy) < limiar) {
                                // Ainda pode ser um clique — não interfere
                                // com o gesto nativo (scroll da página em
                                // touch) enquanto não tivermos a certeza.
                                return;
                            }
                            pressInfo.isDragging = true;
                            pressInfo.box.classList.add('dragging');
                        }

                        // A partir daqui é arrasto confirmado: passa a
                        // controlar o gesto por completo.
                        e.preventDefault();
                        let newX = clientX - pressInfo.areaLeft - pressInfo.offsetX;
                        let newY = clientY - pressInfo.areaTop - pressInfo.offsetY;

                        newX = Math.max(0, Math.min(newX, pressInfo.areaW - pressInfo.box.offsetWidth));
                        newY = Math.max(0, Math.min(newY, pressInfo.areaH - pressInfo.box.offsetHeight));

                        pressInfo.box.style.left = newX + 'px';
                        pressInfo.box.style.top = newY + 'px';
                    }

                    function endPress(e) {
                        if (!pressInfo) return;
                        const info = pressInfo;
                        pressInfo = null;

                        document.removeEventListener('mousemove', onPressMove);
                        document.removeEventListener('mouseup', endPress);
                        document.removeEventListener('touchmove', onPressMove);
                        document.removeEventListener('touchend', endPress);

                        // Em touchend, preventDefault evita que o browser
                        // emita a seguir os eventos "fantasma" de rato
                        // (mousedown/mouseup/click) para o mesmo toque —
                        // fariam este handler correr uma segunda vez.
                        if (e.type === 'touchend') { e.preventDefault(); }

                        const targetWin = (window.parent && window.parent !== window) ? window.parent : window;

                        if (info.isDragging) {
                            // Fim de arrasto — grava a posição pendente em
                            // localStorage (como já fazia) e pede logo ao
                            // bridge principal para a persistir na BD
                            // (clica num botão Streamlit real escondido —
                            // auto-save, já não precisa do "Salvar Layout").
                            info.box.classList.remove('dragging');
                            const finalX = parseInt(info.box.style.left) / areaScale;
                            const finalY = parseInt(info.box.style.top) / areaScale;
                            try {
                                const layoutData = JSON.parse(targetWin.localStorage.getItem('contentor_layout_pending') || '{}');
                                layoutData[info.contId] = {x: Math.round(finalX), y: Math.round(finalY)};
                                targetWin.localStorage.setItem('contentor_layout_pending', JSON.stringify(layoutData));
                                targetWin.postMessage({ type: 'CONTENTOR_POSICAO_ARRASTADA' }, '*');
                            } catch (err) {
                                console.error('Erro ao salvar posição:', err);
                            }
                        } else {
                            // Clique sem arrasto: pede ao bridge principal
                            // para clicar no botão Streamlit real escondido
                            // "Ver interior" desse contentor, que abre o
                            // modal (ver+editar+apagar) — mecanismo validado
                            // num spike isolado (20/20 cliques) antes de
                            // entrar na app real.
                            targetWin.postMessage({ type: 'CONTENTOR_MOSTRAR_CARTAO', contId: info.contId }, '*');
                        }
                    }

                    window.addEventListener('resize', () => {
                        computeScale();
                        contentores.forEach((c, i) => {
                            const box = mapaArea.children[i];
                            if (box) {
                                box.style.left = (c.x * areaScale) + 'px';
                                box.style.top = (c.y * areaScale) + 'px';
                            }
                        });
                    });

                    computeScale();
                    contentores.forEach(criarContentor);

                    statusBar.textContent = 'Clique num contentor para ver o interior; arraste para reposicionar.';
                </script>
                """
                import streamlit.components.v1 as components
                mapa_render = mapa_html.replace("__CONTENTORES_DATA__", json.dumps(contentores_data, ensure_ascii=False))
                mapa_render = mapa_render.replace("__IS_MOBILE__", "true" if is_mobile else "false")
                mapa_render = mapa_render.replace("__MOBILE_CLASS__", "mobile" if is_mobile else "desktop")
                mapa_render = mapa_render.replace("__STATUS_TEXT__", t("map.status_view"))

                # Renderizar mapa com altura responsiva baseada no nº de contentores
                n_cont = len(contentores_df)
                if is_mobile:
                    map_height = max(260, min(380, n_cont * 60 + 160))
                else:
                    map_height = max(340, min(520, n_cont * 55 + 200))
                st.markdown("<div class='map-workspace'>", unsafe_allow_html=True)
                components.html(mapa_render, height=map_height, scrolling=False)
                st.markdown("</div>", unsafe_allow_html=True)

                # `pr`/`pg`/`pb` já vêm calculados do topo da função
                # (reaproveitados pelo mapa e pelo modal do tanque redondo).

                def build_tank_circle_html(stock_df, andar_sel, cont_id, primary_r, primary_g, primary_b):
                    """Gera o HTML do 'tanque redondo' — os canisters dispostos
                    em anel, mostrando o conteúdo do andar seleccionado.
                    Substitui a grelha Canisters × Andares (Passo 2/3 do
                    redesign dos contentores) — mesma leitura/agrupamento de
                    dados de sempre, só muda o desenho.

                    Reaproveita a classe `hm-cell` (e os atributos data-cont/
                    data-c/data-a) da grelha anterior: o bridge de clique já
                    existente (streamlit_js_eval, ligado via MutationObserver)
                    continua a realçar o slot; dentro do modal (Passo 3), o
                    mesmo clique também troca a info do canister mostrada por
                    baixo — ver `build_canister_info_html`.

                    Devolve (html, canisters) — a lista de canisters é
                    reaproveitada por `build_canister_info_html` para gerar
                    exactamente um bloco de info por slot desenhado.
                    """
                    if stock_df.empty:
                        return "", []

                    # Mesmo agrupamento (canister, andar) → qty de sempre, mas
                    # guardando também os garanhões para mostrar dentro do slot.
                    cell_qty = {}
                    cell_garanhoes = {}
                    for _, r in stock_df.iterrows():
                        c, a = int(r['canister'] or 0), int(r['andar'] or 0)
                        if not c or not a:
                            continue
                        cell_qty[(c, a)] = cell_qty.get((c, a), 0) + int(r['existencia_atual'] or 0)
                        cell_garanhoes.setdefault((c, a), []).append(str(r['garanhao'] or '—'))

                    if not cell_qty:
                        return "", []

                    # Canisters conhecidos do contentor — união dos dois
                    # andares, para o círculo manter sempre a mesma forma ao
                    # trocar de andar (só o conteúdo de cada slot muda).
                    canisters = sorted(set(k[0] for k in cell_qty))
                    n = len(canisters)
                    diametro = 272
                    centro = diametro / 2
                    raio = 100

                    slots_html = ""
                    for i, c in enumerate(canisters):
                        angulo = math.radians(i * (360 / n) - 90)
                        x = centro + raio * math.cos(angulo)
                        y = centro + raio * math.sin(angulo)
                        qty = cell_qty.get((c, andar_sel), 0)
                        garanhoes = cell_garanhoes.get((c, andar_sel), [])

                        if qty > 0:
                            label = escape(garanhoes[0]) if len(garanhoes) == 1 else f"{len(garanhoes)} lotes"
                            bg = f"rgba({primary_r},{primary_g},{primary_b},.16)"
                            border_cor = f"rgba({primary_r},{primary_g},{primary_b},.55)"
                            conteudo = (
                                f"<span class='tank-qty' style='color:rgb({primary_r},{primary_g},{primary_b});'>{qty}</span>"
                                f"<span class='tank-gar'>{label}</span>"
                            )
                            classe = "filled"
                        else:
                            bg = "#f1f5f9"
                            border_cor = "#e2e8f0"
                            conteudo = "<span class='tank-dot'></span>"
                            classe = "empty"

                        slots_html += (
                            f"<div class='hm-cell tank-slot {classe}' "
                            f"data-cont='{cont_id}' data-c='{c}' data-a='{andar_sel}' "
                            f"title='C{c} / A{andar_sel}: {qty} palhetas' "
                            f"style='left:{x:.1f}px;top:{y:.1f}px;background:{bg};border-color:{border_cor};'>"
                            f"<span class='tank-cnum'>C{c}</span>{conteudo}"
                            f"</div>"
                        )

                    n_lotes_andar = int((stock_df['andar'] == andar_sel).sum())

                    html = f"""
                    <div class="tank-wrap">
                      <div class="tank" style="width:{diametro}px;height:{diametro}px;">
                        <div class="tank-center">
                          <div class="tank-center-n">{n_lotes_andar}</div>
                          <div class="tank-center-lbl">{'lote' if n_lotes_andar == 1 else 'lotes'}</div>
                        </div>
                        {slots_html}
                      </div>
                    </div>
                    <div style="text-align:center;font-size:.68rem;color:#94a3b8;margin:4px 0 8px;">
                      Clique num canister para ver os lotes
                    </div>
                    <div class="tank-legend">
                      <span><i class="f"></i> Com sémen</span>
                      <span><i class="e"></i> Vazio neste andar</span>
                    </div>
                    """
                    return html, canisters

                def build_canister_info_html(stock_df, andar_sel, canisters):
                    """Dois blocos de info por canister (Passo 3) — escondidos
                    por defeito. O clique no slot correspondente do tanque
                    redondo mostra o RESUMO (ver handleHmCellClick); clicar no
                    resumo expande o DETALHE — cada lote individual com as
                    medidas (colheita, qualidade, motilidade, concentração).
                    Ambos os níveis são client-side, sem round-trip ao Python
                    (ver handleResumoClick). Só leitura — sem botões de mover,
                    como pedido (as ações continuam na página, fora do modal).
                    Reaproveita os estilos `.lote-row*` já existentes.
                    """
                    blocks = ""
                    for c in canisters:
                        lotes = stock_df[(stock_df['canister'] == c) & (stock_df['andar'] == andar_sel)]
                        if lotes.empty:
                            corpo = "<p class='tank-info-empty'>Vazio neste andar.</p>"
                        else:
                            resumo_rows = ""
                            detalhe_rows = ""
                            for _, lote in lotes.iterrows():
                                gar = escape(str(lote['garanhao'] or '—'))
                                prop = escape(str(lote['proprietario_nome'] or '—'))
                                qty = int(lote['existencia_atual'])
                                ref = escape(str(
                                    lote['origem_externa'] or lote['data_embriovet']
                                    or f"Lote #{int(lote['id'])}"
                                ).split(' ')[0])
                                resumo_rows += (
                                    "<div class='lote-row'>"
                                    "<div class='lote-row-left'>"
                                    f"<span class='lote-garanhao'>{gar}</span>"
                                    f"<span class='lote-meta'>{prop} · {ref} · {qty} palhetas</span>"
                                    "</div>"
                                    "</div>"
                                )
                                colheita = escape(str(lote['data_embriovet'] or '—'))
                                qualidade = escape(str(lote['qualidade'] or '—'))
                                motilidade = int(lote['motilidade'] or 0)
                                concentracao = int(lote['concentracao'] or 0)
                                detalhe_rows += (
                                    "<div class='lote-row lote-row-detalhe'>"
                                    "<div class='lote-row-left'>"
                                    f"<span class='lote-garanhao'>{gar}</span>"
                                    f"<span class='lote-meta'>{prop} · {qty} palhetas</span>"
                                    "<span class='lote-medidas'>"
                                    f"Colheita: {colheita} · Qualidade: {qualidade} · "
                                    f"Motilidade: {motilidade}% · Concentração: {concentracao}M/ml"
                                    "</span>"
                                    "</div>"
                                    "</div>"
                                )
                            corpo = (
                                f"<div class='tank-info-resumo' data-canister-resumo='{c}'>"
                                f"{resumo_rows}"
                                "<span class='tank-info-expand-hint'>Clique para ver o detalhe de cada lote</span>"
                                "</div>"
                                f"<div class='tank-info-detalhe' data-canister-detalhe='{c}' style='display:none;'>"
                                f"{detalhe_rows}"
                                "</div>"
                            )
                        blocks += (
                            f"<div class='tank-info-block' data-canister-info='{c}' style='display:none;'>"
                            f"<div class='tank-info-title'>Canister {c}</div>{corpo}"
                            "</div>"
                        )
                    return blocks

                def _abrir_modal_tanque(cont_id_modal, cod_modal, primary_r, primary_g, primary_b, row_modal):
                    """Modal do tanque redondo — seletor de andar, "Inverter
                    andares", o círculo com a info por canister, e (arrumação
                    final) editar nome/descrição + apagar, tudo no mesmo
                    sítio: é o único lugar onde se age sobre um contentor.

                    Chamada depois do loop de contentores (não dentro dele)
                    para seguir o mesmo padrão já usado nos outros diálogos
                    por item desta app (ex.: `_render_modal_saida` em
                    estadias_page.py) — abrir directo dentro do loop, a meio
                    de um clique, arriscava misturar o `cont_id` de outra
                    iteração. Por isso o botão só marca a intenção em
                    session_state; isto relê o stock fresco.
                    """
                    stock_modal = obter_stock_contentor(cont_id_modal)
                    total_palhetas_modal = int(stock_modal['existencia_atual'].sum()) if not stock_modal.empty else 0

                    @st.dialog(cod_modal, width="large")
                    def _modal():
                        # Sem st.rerun() explícito para ações que devem manter
                        # o modal aberto (ex.: inverter andares, guardar
                        # nome/descrição): confirmado empiricamente que chamar
                        # st.rerun() de dentro de uma função @st.dialog fecha
                        # o modal (o clique do próprio widget já desencadeia
                        # o rerun implícito de que precisamos — chamar outro
                        # por cima é isso que o fecha). Onde é preciso
                        # reflectir dados frescos na mesma passagem, relê-se a
                        # variável local em vez de rerunnar. A única exceção
                        # é "Apagar": aí queremos mesmo fechar o modal e
                        # atualizar o mapa, por isso st.rerun() é intencional.
                        nonlocal stock_modal
                        if stock_modal.empty:
                            st.caption("Nenhum lote neste contentor.")
                        else:
                            andar_key = f"andar_sel_{cont_id_modal}"
                            col_andar, col_inverter = st.columns([2, 1], vertical_alignment="center")
                            with col_andar:
                                with st.container(key=f"andar-toggle-{cont_id_modal}"):
                                    andar_sel = st.radio(
                                        "Andar", [1, 2], format_func=lambda x: f"Andar {x}",
                                        key=andar_key, horizontal=True, label_visibility="collapsed",
                                    )
                            with col_inverter:
                                if st.button("Inverter andares", key=f"inverter_andares_{cont_id_modal}",
                                             help="Troca os lotes do 1º andar para o 2º e vice-versa"):
                                    st.session_state[f'confirmar_inverter_{cont_id_modal}'] = True

                            if st.session_state.get(f'confirmar_inverter_{cont_id_modal}', False):
                                st.warning(
                                    f"Inverter os andares do contentor {cod_modal}? Todos os lotes "
                                    "do 1º andar passam ao 2º e vice-versa. As localizações dos "
                                    "lotes serão atualizadas."
                                )
                                col_conf1, col_conf2 = st.columns([1, 1])
                                with col_conf1:
                                    if st.button("Confirmar", key=f"confirmar_inverter_btn_{cont_id_modal}",
                                                 type="primary", width="stretch"):
                                        resultado = inverter_andares(cont_id_modal)
                                        st.session_state[f'confirmar_inverter_{cont_id_modal}'] = False
                                        if resultado is not False:
                                            st.toast(f"Andares invertidos: {resultado} lote(s) atualizados.", icon="✅")
                                            stock_modal = obter_stock_contentor(cont_id_modal)
                                        else:
                                            st.error("Erro ao inverter andares. Ver logs.")
                                with col_conf2:
                                    if st.button("Cancelar", key=f"cancelar_inverter_btn_{cont_id_modal}", width="stretch"):
                                        st.session_state[f'confirmar_inverter_{cont_id_modal}'] = False

                            circle_html, canisters = build_tank_circle_html(
                                stock_modal, andar_sel, cont_id_modal, primary_r, primary_g, primary_b
                            )
                            if circle_html:
                                st.markdown(circle_html, unsafe_allow_html=True)
                                info_html = build_canister_info_html(stock_modal, andar_sel, canisters)
                                st.markdown(info_html, unsafe_allow_html=True)

                        # Editar nome/descrição + Apagar — vivem aqui dentro
                        # (arrumação final), reaproveitando editar_contentor/
                        # deletar_contentor tal como já eram usados na página.
                        # Recolhido por defeito: o modal abre com o círculo à
                        # vista, o editar só aparece se for pedido.
                        st.divider()
                        with st.expander(t('map.edit_container_title'), expanded=False):
                            with st.form(f"form_editar_modal_{cont_id_modal}"):
                                col_ed1, col_ed2 = st.columns(2)
                                with col_ed1:
                                    novo_codigo = st.text_input(t("label.code"), value=row_modal['codigo'])
                                with col_ed2:
                                    nova_descricao = st.text_input(t("label.description"), value=row_modal['descricao'] or '')

                                pode_apagar = total_palhetas_modal == 0
                                cs1, cs2 = st.columns(2)
                                with cs1:
                                    salvar_edit = st.form_submit_button(t("btn.save"), width="stretch", type="primary")
                                with cs2:
                                    apagar_edit = st.form_submit_button(
                                        "Apagar", width="stretch", disabled=not pode_apagar,
                                        help=None if pode_apagar else t("map.delete_blocked"),
                                    )

                                if apagar_edit:
                                    if deletar_contentor(cont_id_modal):
                                        # Intencional: ação destrutiva, queremos
                                        # mesmo fechar o modal e atualizar o mapa.
                                        st.rerun()
                                if salvar_edit:
                                    if editar_contentor(cont_id_modal, {
                                        'codigo': novo_codigo, 'descricao': nova_descricao,
                                        'x': row_modal['x'], 'y': row_modal['y'],
                                        'w': row_modal['w'], 'h': row_modal['h'],
                                    }):
                                        st.success(t("map.container_updated"))

                    _modal()

                st.markdown(f"""
                <style>
                    .lote-row {{
                        display:flex; align-items:center; justify-content:space-between;
                        background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px;
                        padding:8px 12px; margin-bottom:6px; font-size:.82rem;
                    }}
                    .lote-row-left {{ display:flex; flex-direction:column; gap:2px; }}
                    .lote-garanhao {{ font-weight:700; color:#0f172a; }}
                    .lote-meta {{ color:#64748b; font-size:.75rem; }}

                    /* Heatmap styles (aplicados globalmente a todos os cards) */
                    .hm-grid-wrap {{
                        position: relative;
                        pointer-events: auto !important;
                        isolation: isolate;
                        background: #ffffff;
                    }}
                    .hm-grid-wrap table {{ pointer-events:auto !important; }}
                    .hm-cell {{
                        cursor:pointer !important;
                        border-radius:6px;
                        transition: transform .15s, box-shadow .15s;
                        position: relative;
                        z-index: 2;
                        pointer-events:auto !important;
                        user-select:none;
                        -webkit-tap-highlight-color: rgba({pr},{pg},{pb},.25);
                    }}
                    .hm-cell:hover {{ transform:scale(1.1); box-shadow:0 3px 10px rgba(0,0,0,.18); z-index:3; }}
                    .hm-cell:active {{ transform:scale(0.97); }}
                    .hm-cell.selected {{ outline:2.5px solid rgb({pr},{pg},{pb});
                        box-shadow:0 0 0 4px rgba({pr},{pg},{pb},.22);
                        transform:scale(1.08); z-index:4; }}
                    .lote-row.hl {{ border:2px solid rgb({pr},{pg},{pb}) !important;
                        background:rgba({pr},{pg},{pb},.07) !important;
                        box-shadow:0 2px 8px rgba({pr},{pg},{pb},.15); }}

                    /* Tanque redondo (Passo 2/3) — os slots herdam .hm-cell
                       (cursor, transition, pointer-events, bridge de clique)
                       e ficam aqui só as regras que a mudam de grelha→anel:
                       posicionamento absoluto e o hover/selected com
                       translate(-50%,-50%) para não perder a centragem.
                       Como estas regras vêm DEPOIS de .hm-cell no mesmo
                       <style>, ganham em empate de especificidade. */
                    .tank-wrap {{ display:flex; justify-content:center; padding:8px 0 2px; }}
                    .tank {{
                        position:relative; margin:0 auto; border-radius:50%;
                        border:2px solid #e2e8f0;
                        background:radial-gradient(circle at 50% 50%, #f8fafc 0%, #f8fafc 62%, transparent 63%);
                    }}
                    .tank-center {{
                        position:absolute; top:50%; left:50%; transform:translate(-50%,-50%);
                        text-align:center; pointer-events:none;
                    }}
                    .tank-center-n {{ font-size:1.2rem; font-weight:800; color:#0f172a; }}
                    .tank-center-lbl {{
                        font-size:.6rem; font-weight:700; text-transform:uppercase;
                        letter-spacing:.6px; color:#94a3b8;
                    }}
                    .tank-slot {{
                        position:absolute !important;
                        transform:translate(-50%,-50%);
                        width:64px; height:64px; border-radius:50%;
                        border:2px solid #e2e8f0;
                        display:flex; flex-direction:column; align-items:center; justify-content:center;
                        text-align:center; line-height:1.1; font-size:.6rem; padding:3px;
                        background:#f1f5f9; color:#cbd5e1;
                    }}
                    .tank-slot:hover {{
                        transform:translate(-50%,-50%) scale(1.1);
                        box-shadow:0 3px 10px rgba(0,0,0,.18); z-index:3;
                    }}
                    .tank-slot.selected {{
                        outline:2.5px solid rgb({pr},{pg},{pb});
                        box-shadow:0 0 0 4px rgba({pr},{pg},{pb},.22);
                        transform:translate(-50%,-50%) scale(1.08); z-index:4;
                    }}
                    .tank-cnum {{
                        position:absolute; top:-9px; left:50%; transform:translateX(-50%);
                        background:#0f172a; color:#fff; font-size:.58rem; font-weight:700;
                        border-radius:8px; padding:1px 5px; white-space:nowrap;
                    }}
                    .tank-qty {{ font-weight:800; font-size:.8rem; }}
                    .tank-gar {{
                        font-weight:700; font-size:.6rem; white-space:nowrap;
                        overflow:hidden; text-overflow:ellipsis; max-width:52px;
                    }}
                    .tank-dot {{ width:6px; height:6px; border-radius:50%; background:#cbd5e1; }}
                    .tank-legend {{ margin-top:2px; display:flex; flex-wrap:wrap; justify-content:center; gap:12px; }}
                    .tank-legend span {{ display:inline-flex; align-items:center; gap:5px; font-size:.65rem; color:#64748b; }}
                    .tank-legend i {{ width:11px; height:11px; border-radius:50%; display:inline-block; border:1.5px solid #e2e8f0; }}
                    .tank-legend i.f {{ background:rgba({pr},{pg},{pb},.16); border-color:rgba({pr},{pg},{pb},.55); }}
                    .tank-legend i.e {{ background:#f1f5f9; }}
                    @media(max-width:480px) {{
                        .tank {{ width:220px !important; height:220px !important; }}
                        .tank-slot {{ width:54px; height:54px; }}
                    }}

                    /* Info do canister dentro do modal (Passo 3) — escondida
                       por defeito, o clique no slot troca-lhe a visibilidade
                       via JS. Reaproveita .lote-row* já existentes. */
                    .tank-info-block {{
                        margin-top:14px; padding-top:12px; border-top:1px solid #e2e8f0;
                    }}
                    .tank-info-title {{
                        font-size:.7rem; font-weight:700; text-transform:uppercase;
                        letter-spacing:1px; color:#94a3b8; margin-bottom:8px;
                    }}
                    .tank-info-empty {{ font-size:.82rem; color:#94a3b8; margin:0; }}
                    .tank-info-resumo {{
                        cursor:pointer; border-radius:8px; padding:2px;
                        transition:background .15s;
                    }}
                    .tank-info-resumo:hover {{ background:#f8fafc; }}
                    .tank-info-expand-hint {{
                        display:block; font-size:.68rem; color:#94a3b8; margin:4px 2px 0;
                    }}
                    .tank-info-detalhe {{
                        margin-top:8px; padding-top:8px; border-top:1px dashed #e2e8f0;
                    }}
                    .lote-row-detalhe {{ flex-direction:column; align-items:flex-start; }}
                    .lote-row-detalhe .lote-row-left {{ width:100%; }}
                    .lote-medidas {{ color:#94a3b8; font-size:.7rem; margin-top:2px; }}

                    /* Seletor de andar — pill-tabs (mesmo padrão do
                       separador Stock de sémen: esconde o círculo do rádio
                       nativo, sublinha/realça a opção activa). */
                    div[class*="st-key-andar-toggle-"] [role="radiogroup"] {{
                        display:inline-flex; background:#f8fafc; border:1px solid #e2e8f0;
                        border-radius:10px; padding:3px; gap:2px;
                    }}
                    div[class*="st-key-andar-toggle-"] [role="radiogroup"] > label {{
                        margin:0 !important; padding:5px 12px !important; border-radius:8px !important;
                        cursor:pointer;
                    }}
                    div[class*="st-key-andar-toggle-"] [role="radiogroup"] > label > div:first-child {{
                        display:none !important;
                    }}
                    div[class*="st-key-andar-toggle-"] [role="radiogroup"] > label p {{
                        font-size:.8rem !important; font-weight:600 !important; color:#64748b !important; margin:0 !important;
                    }}
                    div[class*="st-key-andar-toggle-"] [role="radiogroup"] > label:has(input:checked) {{
                        background:#fff; box-shadow:0 1px 2px rgba(0,0,0,.08);
                    }}
                    div[class*="st-key-andar-toggle-"] [role="radiogroup"] > label:has(input:checked) p {{
                        color:#0f172a !important;
                    }}
                </style>
                """, unsafe_allow_html=True)

                # Arrumação final: a página já não mostra cartões por
                # contentor — só o mapa. Cada contentor tem um botão "Ver
                # interior" real mas escondido (CSS acima), que o clique na
                # caixa correspondente aciona via bridge (ver mapa_html).
                # Abre o modal — que já reúne ver, editar nome/descrição e
                # apagar, tudo no mesmo sítio.
                for _, row in contentores_df.iterrows():
                    cont_id = int(row['id'])
                    if st.button("Ver interior", key=f"ver_interior_{cont_id}"):
                        st.session_state["abrir_modal_tanque_id"] = cont_id
                        st.rerun()

                # Feito depois do loop, não dentro dele: dentro do loop,
                # `cont_id` já teria avançado para outra iteração por altura
                # do clique ser processado. O botão só marca a intenção.
                if st.session_state.get("abrir_modal_tanque_id"):
                    cont_id_modal = int(st.session_state.pop("abrir_modal_tanque_id"))
                    linha_modal = contentores_df[contentores_df['id'] == cont_id_modal]
                    if not linha_modal.empty:
                        row_modal = linha_modal.iloc[0]
                        _abrir_modal_tanque(cont_id_modal, row_modal['codigo'], pr, pg, pb, row_modal)

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
                                        st.markdown(f"  - {lote.get('garanhao_nome') or lote['garanhao']} | {lote['proprietario_nome']} | {int(lote['existencia_atual'])} palhetas | {ref}")
