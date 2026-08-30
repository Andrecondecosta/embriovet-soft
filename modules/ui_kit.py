import streamlit as st
from modules.i18n import t

# Cor primária por defeito do projeto (marca EmbrioVet). Única fonte de
# verdade para qualquer fallback de `app_settings.primary_color` vazio
# ou inválido — nenhum outro sítio do código deve hardcodar um hex à
# parte desta constante.
DEFAULT_PRIMARY_COLOR = "#E85D4A"


def inject_all_css_consolidated():
    """Injetar TODO o CSS em um único bloco para evitar containers vazios"""
    st.markdown(
        """
        <style>
            /* Design System Global */
            :root {
                --ds-font-size: 0.9rem;
                --ds-radius: 8px;
                --ds-radius-sm: 6px;
                --ds-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
                --ds-shadow-sm: 0 2px 8px rgba(15, 23, 42, 0.06);
                --ds-spacing: 0.7rem;
            }
            html, body, [data-testid="stAppViewContainer"] {
                font-size: 14px;
                color: #0f172a;
            }
            /* Ocultar apenas Deploy e menu — manter botões de controlo da sidebar */
            [data-testid="stDeployButton"],
            [data-testid="stDecoration"],
            #MainMenu { display: none !important; }
            /* Espaçamento normal no topo */
            [data-testid="stMain"] > .stMainBlockContainer,
            [data-testid="stMain"] > .block-container,
            [data-testid="stMainBlockContainer"],
            .stMainBlockContainer,
            .block-container {
                padding-top: 60px !important;
                padding-bottom: 1.4rem;
            }
            /* SOLUÇÃO DEFINITIVA: remover containers de injeção CSS do flex flow via
               position:absolute — elementos absolute não criam gap no flexbox.
               Emotion não conflitua com position (só com display), portanto ganha esta regra.
               Estrutura real: .stMarkdown > div > [data-testid="stMarkdownContainer"] > style */
            .stElementContainer:has([data-testid="stMarkdownContainer"] > style),
            .stMarkdown:has([data-testid="stMarkdownContainer"] > style),
            /* Também remover iframes de altura 0 (scroll-to-top, JS components) */
            .stElementContainer:has(iframe[height="0"]) {
                position: absolute !important;
                width: 0 !important;
                height: 0 !important;
                min-height: 0 !important;
                max-height: 0 !important;
                margin: 0 !important;
                padding: 0 !important;
                overflow: hidden !important;
                pointer-events: none !important;
                visibility: hidden !important;
            }
            /* Containers verdadeiramente vazios */
            div[data-testid="stElementContainer"]:empty,
            div[data-testid="stVerticalBlock"]:empty,
            .stElementContainer:empty {
                display: none !important;
                height: 0px !important;
                min-height: 0px !important;
                max-height: 0px !important;
                margin: 0px !important;
                padding: 0px !important;
                overflow: hidden !important;
            }
            .stButton > button,
            .stDownloadButton > button,
            .stTextInput input,
            .stSelectbox select,
            .stTextArea textarea,
            .stNumberInput input,
            .stDateInput input {
                border-radius: var(--ds-radius) !important;
            }
            .stCard, .app-card {
                border-radius: var(--ds-radius) !important;
                box-shadow: var(--ds-shadow-sm);
            }
            .stMarkdown {
                line-height: 1.45;
            }

            /* Prevenir zoom automático no iOS/Android ao focar inputs (font-size >= 16px) */
            @media (max-width: 992px) {
                input[type="text"],
                input[type="number"],
                input[type="email"],
                input[type="password"],
                input[type="tel"],
                input[type="search"],
                input[type="date"],
                textarea,
                select,
                .stTextInput input,
                .stNumberInput input,
                .stDateInput input,
                .stTextArea textarea,
                .stSelectbox select {
                    font-size: 16px !important;
                    touch-action: manipulation;
                }
            }

            /* Reports CSS */
            .reports-zone-title {
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: .05em;
                color: #64748b;
                margin: 0.25rem 0 0.35rem 0;
                font-weight: 700;
            }
            .reports-kpi-strip {
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
                margin: 0.35rem 0 0.6rem 0;
            }
            .reports-kpi-item {
                border: 1px solid #e2e8f0;
                background: #ffffff;
                color: #334155;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 0.78rem;
                white-space: nowrap;
                box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
            }
            .reports-kpi-item b { color: #0f172a; }
            .reports-results-head {
                margin-top: 0.2rem;
                margin-bottom: 0.15rem;
            }
            
            /* Stock CSS */
            .stock-zone-title {
                font-size: .78rem;
                text-transform: uppercase;
                letter-spacing: .05em;
                color: #64748b;
                margin: .2rem 0 .35rem 0;
                font-weight: 700;
            }
            .stock-toolbar {
                border: 1px solid #dbe4ee;
                border-radius: 8px;
                background: #f8fafc;
                padding: 6px 8px;
                margin-bottom: 6px;
            }
            .stock-table-head {
                font-size: .95rem;
                font-weight: 600;
                color: #0f172a;
                margin: .2rem 0 .25rem 0;
            }
            
            /* Stepper CSS */
            .stepper-value {
                font-weight: 600;
                font-size: .85rem;
                padding: 2px 6px;
                text-align: center;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                background: #f8fafc;
                min-width: 32px;
            }
            .stepper-value.invalid {
                color: #b91c1c;
                border-color: #fecaca;
                background: #fee2e2;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_design_system():
    st.markdown(
        """
        <style>
            :root {
                --ds-font-size: 0.9rem;
                --ds-radius: 8px;
                --ds-radius-sm: 6px;
                --ds-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
                --ds-shadow-sm: 0 2px 8px rgba(15, 23, 42, 0.06);
                --ds-spacing: 0.7rem;
            }
            html, body, [data-testid="stAppViewContainer"] {
                font-size: 14px;
                color: #0f172a;
            }
            /* Ocultar apenas Deploy e menu — manter botões de controlo da sidebar */
            [data-testid="stDeployButton"],
            [data-testid="stDecoration"],
            #MainMenu { display: none !important; }
            /* Header compacto mas visível (contém os botões da sidebar) */
            [data-testid="stToolbar"] {
                background: transparent !important;
                box-shadow: none !important;
            }
            [data-testid="stMain"] > .stMainBlockContainer,
            [data-testid="stMain"] > .block-container,
            [data-testid="stMainBlockContainer"],
            .stMainBlockContainer,
            .block-container {
                padding-top: 60px !important;
                padding-bottom: 1.4rem;
            }
            .stElementContainer:has([data-testid="stMarkdownContainer"] > style),
            .stMarkdown:has([data-testid="stMarkdownContainer"] > style),
            .stElementContainer:has(iframe[height="0"]) {
                position: absolute !important;
                width: 0 !important;
                height: 0 !important;
                min-height: 0 !important;
                max-height: 0 !important;
                margin: 0 !important;
                padding: 0 !important;
                overflow: hidden !important;
                pointer-events: none !important;
                visibility: hidden !important;
            }
            div[data-testid="stElementContainer"]:empty,
            div[data-testid="stVerticalBlock"]:empty,
            .stElementContainer:empty {
                display: none !important;
                height: 0px !important;
                min-height: 0px !important;
                max-height: 0px !important;
                margin: 0px !important;
                padding: 0px !important;
                overflow: hidden !important;
            }
            .stButton > button,
            .stDownloadButton > button,
            .stTextInput input,
            .stSelectbox select,
            .stTextArea textarea,
            .stNumberInput input,
            .stDateInput input {
                border-radius: var(--ds-radius) !important;
            }
            .stCard, .app-card {
                border-radius: var(--ds-radius) !important;
                box-shadow: var(--ds-shadow-sm);
            }
            .stMarkdown {
                line-height: 1.45;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_reports_css():
    st.markdown(
        """
        <style>
            .reports-zone-title {
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: .05em;
                color: #64748b;
                margin: 0.25rem 0 0.35rem 0;
                font-weight: 700;
            }
            .reports-kpi-strip {
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
                margin: 0.35rem 0 0.6rem 0;
            }
            .reports-kpi-item {
                border: 1px solid #e2e8f0;
                background: #ffffff;
                color: #334155;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 0.78rem;
                white-space: nowrap;
                box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
            }
            .reports-kpi-item b { color: #0f172a; }
            .reports-results-head {
                margin-top: 0.2rem;
                margin-bottom: 0.15rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_stock_css():
    st.markdown(
        """
        <style>
            .stock-zone-title {
                font-size: .78rem;
                text-transform: uppercase;
                letter-spacing: .05em;
                color: #64748b;
                margin: .2rem 0 .35rem 0;
                font-weight: 700;
            }
            .stock-toolbar {
                border: 1px solid #dbe4ee;
                border-radius: 8px;
                background: #f8fafc;
                padding: 6px 8px;
                margin-bottom: 6px;
            }
            .stock-table-head {
                font-size: .95rem;
                font-weight: 600;
                color: #0f172a;
                margin: .2rem 0 .25rem 0;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_stepper_css():
    st.markdown(
        """
        <style>
            .stepper-value {
                font-weight: 600;
                font-size: .85rem;
                padding: 2px 6px;
                text-align: center;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                background: #f8fafc;
                min-width: 32px;
            }
            .stepper-value.invalid {
                color: #b91c1c;
                border-color: #fecaca;
                background: #fee2e2;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_add_stock_form_css(primary_color=DEFAULT_PRIMARY_COLOR):
    st.markdown(
        f"""
        <style>
        /* ═══════════════════════════════════════
           ADD STOCK — Premium Form Design
        ═══════════════════════════════════════ */

        /* Section header — accent left border */
        .form-section-header {{
            display: flex;
            align-items: center;
            gap: 7px;
            color: #475569;
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.07em;
            border-left: 3px solid {primary_color};
            padding-left: 9px;
            margin: 0 0 12px 0;
            line-height: 1.4;
        }}

        /* Section card — subtle card around each group */
        .form-card {{
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 16px 18px 6px 18px;
            margin-bottom: 10px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        }}

        /* Main Streamlit form container — borderless, transparent */
        [data-testid="stForm"] {{
            border: none !important;
            background: transparent !important;
            padding: 0 !important;
        }}

        /* Input & selectbox labels — condensed uppercase */
        [data-testid="stForm"] .stTextInput label p,
        [data-testid="stForm"] .stSelectbox label p,
        [data-testid="stForm"] .stNumberInput label p,
        [data-testid="stForm"] .stTextArea label p,
        [data-testid="stForm"] .stRadio label p {{
            font-size: 0.72rem !important;
            font-weight: 700 !important;
            color: #64748b !important;
            text-transform: uppercase !important;
            letter-spacing: 0.05em !important;
            margin-bottom: 3px !important;
        }}

        /* Inputs — stronger border + subtle focus ring */
        [data-testid="stForm"] input,
        [data-testid="stForm"] textarea,
        [data-testid="stForm"] .stSelectbox > div > div {{
            border-radius: 7px !important;
        }}
        [data-testid="stForm"] input:focus {{
            border-color: {primary_color} !important;
            box-shadow: 0 0 0 3px {primary_color}22 !important;
        }}

        /* Number input — center align value */
        [data-testid="stForm"] [data-testid="stNumberInput"] input {{
            text-align: center !important;
            font-weight: 600 !important;
            font-size: 1rem !important;
        }}

        /* Radio floor — pill style */
        [data-testid="stForm"] [data-testid="stRadio"] > div {{
            gap: 8px;
        }}
        [data-testid="stForm"] [data-testid="stRadio"] label {{
            background: #f8fafc;
            border: 1.5px solid #e2e8f0;
            border-radius: 6px;
            padding: 4px 14px !important;
            font-weight: 600 !important;
            font-size: .85rem !important;
            transition: all .15s;
        }}
        [data-testid="stForm"] [data-testid="stRadio"] label:has(input:checked) {{
            background: {primary_color}18 !important;
            border-color: {primary_color} !important;
            color: {primary_color} !important;
        }}

        /* Submit button — full-width primary */
        [data-testid="stFormSubmitButton"] button {{
            background: {primary_color} !important;
            border-color: {primary_color} !important;
            color: #fff !important;
            font-weight: 700 !important;
            font-size: 0.92rem !important;
            height: 44px !important;
            border-radius: 8px !important;
            letter-spacing: 0.03em;
            transition: opacity 0.15s ease, transform 0.1s ease;
            margin-top: 6px;
        }}
        [data-testid="stFormSubmitButton"] button:hover {{
            opacity: 0.88 !important;
            transform: translateY(-1px);
        }}
        [data-testid="stFormSubmitButton"] button:active {{
            transform: translateY(0);
        }}

        /* "+ Novo Proprietário" button — outline style */
        [data-testid="stButton"][id="btn_add_prop_stock"] button,
        div:has(+ div [data-testid="stForm"]) button {{
            border: 1.5px solid {primary_color} !important;
            color: {primary_color} !important;
            background: transparent !important;
            font-size: 0.78rem !important;
            font-weight: 600 !important;
            border-radius: 6px !important;
            padding: 4px 12px !important;
            transition: background .15s;
        }}

        /* Observations section gap */
        .form-obs {{
            margin-top: 4px;
        }}

        /* Max width for the form area */
        .main [data-testid="stForm"] {{
            max-width: 860px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )




def render_stepper(cols, key, min_value=0, max_value=None, invalid_tooltip="", editable=False):
    if key not in st.session_state:
        st.session_state[key] = min_value

    def step(delta):
        current = int(st.session_state.get(key, 0) or 0)
        next_val = current + delta
        if min_value is not None:
            next_val = max(min_value, next_val)
        if max_value is not None and delta > 0:
            next_val = min(max_value, next_val)
        st.session_state[key] = next_val

    value = int(st.session_state.get(key, 0) or 0)
    invalid = max_value is not None and value > max_value
    tooltip = invalid_tooltip if invalid and invalid_tooltip else ""
    cls = "stepper-value invalid" if invalid else "stepper-value"

    if editable:
        # Modo editável: input + botões -/+
        input_col, minus_col, plus_col = cols
        
        with minus_col:
            st.button(
                "−",
                key=f"{key}_minus",
                on_click=step,
                args=(-1,),
                disabled=min_value is not None and value <= min_value,
                help="Diminuir",
                width="stretch",
            )
        with input_col:
            new_value = st.number_input(
                "Quantidade",
                min_value=min_value if min_value is not None else 0,
                max_value=max_value if max_value is not None else 9999,
                value=value,
                step=1,
                key=f"{key}_input",
                label_visibility="collapsed",
            )
            if new_value != value:
                st.session_state[key] = new_value
        with plus_col:
            st.button(
                "+",
                key=f"{key}_plus",
                on_click=step,
                args=(1,),
                disabled=max_value is not None and value >= max_value,
                help="Aumentar",
                width="stretch",
            )
    else:
        # Modo original: display + botões -/+
        value_col, minus_col, plus_col = cols

        with value_col:
            st.markdown(f"<div class='{cls}' title='{tooltip}'>{value}</div>", unsafe_allow_html=True)
        with minus_col:
            st.button(
                "−",
                key=f"{key}_minus",
                on_click=step,
                args=(-1,),
                disabled=min_value is not None and value <= min_value,
                help="Diminuir quantidade",
                width="stretch",
            )
        with plus_col:
            st.button(
                "+",
                key=f"{key}_plus",
                on_click=step,
                args=(1,),
                disabled=max_value is not None and value >= max_value,
                help="Aumentar quantidade",
                width="stretch",
            )

    return value, invalid


def inject_shell_css(primary_color: str | None):
    color = primary_color or DEFAULT_PRIMARY_COLOR
    st.markdown(
        f"""
        <style>
            :root {{
                --radius: 8px;
                --border: #e2e8f0;
                --muted: #64748b;
                --bg: #f8fafc;
                --text: #0f172a;
                --primary: {color};
            }}
            [data-testid="stSidebar"] {{
                background: var(--bg);
                border-right: 1px solid var(--border);
            }}
            .sidebar-shell {{
                background: #f8fafc;
                padding: 14px 12px;
                border-radius: 14px;
                border: 1px solid var(--border);
                box-shadow: 0 10px 25px rgba(15, 23, 42, 0.04);
            }}
            .sidebar-brand {{
                padding: 12px 12px 8px 12px;
                border-bottom: 1px solid var(--border);
            }}
            .sidebar-brand-title {{
                font-weight: 700;
                color: var(--text);
                position: relative;
                margin: 0;
            }}
            .sidebar-user-card {{
                margin: 10px 12px;
                padding: 10px;
                border: 1px solid var(--border);
                border-radius: var(--radius);
                background: #ffffff;
                box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
            }}
            .sidebar-user-name {{
                font-size: .85rem;
                font-weight: 600;
                color: var(--text);
            }}
            .sidebar-user-chip {{
                display: inline-block;
                font-size: .7rem;
                padding: 2px 6px;
                border-radius: 999px;
                background: #eef2f7;
                color: var(--muted);
                margin-top: 4px;
            }}
            [data-testid="stSidebar"] [role="radiogroup"] label {{
                border: 1px solid transparent;
                border-radius: var(--radius);
                padding: 6px 8px;
                margin: 2px 8px;
                color: var(--text);
            }}
            [data-testid="stSidebar"] [role="radiogroup"] label:hover {{
                background: #f1f5f9;
                border-color: var(--border);
            }}
            [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {{
                background: #eef2ff;
                border-color: rgba(37, 99, 235, 0.3);
                color: var(--primary);
                position: relative;
            }}
            [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked)::before {{
                content: "";
                position: absolute;
                left: 0;
                top: 6px;
                bottom: 6px;
                width: 3px;
                border-radius: 3px;
                background: var(--primary);
            }}
            #topbar-anchor {{ height: 0; }}
            /* Injetores de JS invisíveis (padding-top forçado; scroll+
               colapso da sidebar ao navegar) — têm de sair do fluxo do
               stVerticalBlock (display:flex; gap:14px), que conta os
               seus filhos para o gap mesmo com altura 0. O hack antigo
               (`.stElementContainer:has(iframe[height="0"])`, acima)
               não apanha isto: o Streamlit já não põe o atributo
               `height` no HTML do iframe. Isto NÃO deve apanhar o
               componente do mapa (`components.html(mapa_render,...)`,
               em map_page.py) — esse é visível e tem altura real,
               não usa `st.container(key=...)`, por isso fica de fora.

               `st.container(key=...)` gera DOIS níveis: um
               `stLayoutWrapper` exterior (o filho real do flex — este
               é que precisa do position:absolute) e o `stVerticalBlock`
               com a classe `st-key-*` lá dentro. Esconder só o interior
               não chega — o exterior continua a contar para o gap. */
            .st-key-js-padding-top-forcer,
            .st-key-js-nav-scroll-collapse,
            [data-testid="stLayoutWrapper"]:has(> .st-key-js-padding-top-forcer),
            [data-testid="stLayoutWrapper"]:has(> .st-key-js-nav-scroll-collapse) {{
                position: absolute !important;
                width: 0 !important;
                height: 0 !important;
                min-height: 0 !important;
                max-height: 0 !important;
                margin: 0 !important;
                padding: 0 !important;
                overflow: hidden !important;
                pointer-events: none !important;
                visibility: hidden !important;
            }}
            #topbar-anchor + div [data-testid="stHorizontalBlock"] {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0 16px;
                height: 56px;
                border-bottom: 1px solid var(--border);
                background: #ffffff;
                margin-bottom: 10px;
            }}
            .app-topbar-title {{
                font-size: 1.05rem;
                font-weight: 700;
                color: var(--text);
            }}
            .app-topbar-actions .stButton > button {{
                font-size: .78rem;
                padding: 4px 10px;
                height: 32px;
            }}
            div[data-testid="stElementContainer"] {{
                margin-bottom: 0.35rem;
            }}
            .reports-kpi-item b {{
                color: var(--primary) !important;
            }}
            a {{
                color: var(--primary) !important;
            }}
            /* Override único e global de botões/tabs "primary" — fonte
               única de verdade para a cor da marca em toda a app.
               `kind="primary"` é o atributo real gerado pelo Streamlit
               nesta versão (não `data-testid="baseButton-primary"`,
               que nunca correspondia a nada). */
            div[data-testid="stButton"] > button[kind="primary"],
            div[data-testid="stFormSubmitButton"] > button[kind="primary"] {{
                background-color: var(--primary) !important;
                border-color: var(--primary) !important;
            }}
            [data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {{
                color: var(--primary) !important;
            }}
            [data-testid="stTabs"] div[data-baseweb="tab-highlight"] {{
                background-color: var(--primary) !important;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _pesquisa_global(termo: str) -> dict:
    """Executa as 3 queries de pesquisa global e devolve {animais, donos, garanhoes}.

    Limites: 3 animais + 3 proprietários + 2 garanhões (máx 8 resultados).
    Ordenação: nome exacto primeiro, depois parciais por ordem alfabética.
    """
    from modules.db import get_connection
    if not termo or len(termo.strip()) < 3:
        return {"animais": [], "donos": [], "garanhoes": []}
    termo_clean = termo.strip()
    like = f"%{termo_clean}%"
    out = {"animais": [], "donos": [], "garanhoes": []}
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT a.id, a.nome, a.tipo, d.nome AS proprietario "
                "FROM animais a "
                "LEFT JOIN dono d ON a.dono_id = d.id "
                "WHERE a.ativo = TRUE AND LOWER(a.nome) LIKE LOWER(%s) "
                "ORDER BY (LOWER(a.nome) = LOWER(%s)) DESC, LOWER(a.nome) "
                "LIMIT 3",
                (like, termo_clean),
            )
            out["animais"] = [
                {
                    "id": int(r[0]),
                    "nome": r[1],
                    "tipo": r[2],
                    "proprietario": r[3],
                }
                for r in cur.fetchall()
            ]

            cur.execute(
                "SELECT id, nome FROM dono "
                "WHERE LOWER(nome) LIKE LOWER(%s) OR nif LIKE %s "
                "ORDER BY (LOWER(nome) = LOWER(%s)) DESC, LOWER(nome) "
                "LIMIT 3",
                (like, like, termo_clean),
            )
            out["donos"] = [{"id": int(r[0]), "nome": r[1]} for r in cur.fetchall()]

            cur.execute(
                "SELECT nome, palhetas FROM ("
                "  SELECT COALESCE(a.nome, ed.garanhao) AS nome, "
                "         SUM(ed.existencia_atual)::int AS palhetas "
                "  FROM estoque_dono ed "
                "  LEFT JOIN animais a ON a.id = ed.animal_id "
                "  WHERE ed.existencia_atual > 0 "
                "  GROUP BY COALESCE(a.nome, ed.garanhao) "
                ") t "
                "WHERE LOWER(nome) LIKE LOWER(%s) "
                "ORDER BY (LOWER(nome) = LOWER(%s)) DESC, nome "
                "LIMIT 2",
                (like, termo_clean),
            )
            out["garanhoes"] = [
                {"nome": r[0], "palhetas": int(r[1])}
                for r in cur.fetchall()
                if r[0]
            ]
            cur.close()
    except Exception:
        pass
    return out


def _inject_pesquisa_dropdown_css() -> None:
    """Injecta o CSS do dropdown da pesquisa global.

    O Streamlit re-renderiza o DOM em cada rerun, pelo que injectamos o CSS
    sempre que esta função é chamada (não há benefício em fazer cache).
    """
    st.markdown(
        """
        <style>
        /* Container do dropdown — flutua absolutamente abaixo da barra de
           pesquisa, sem alterar o fluxo do resto da página. */
        [data-testid="stVerticalBlock"]:has(
            > [data-testid="stElementContainer"]:first-child .pg-dropdown-anchor
        ) {
            background: #F8F9FA !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 0 0 6px 6px !important;
            padding: 4px 0 !important;
            max-height: 220px !important;
            overflow-y: auto !important;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07) !important;
            margin-top: -8px !important;
            margin-bottom: 12px !important;
        }
        /* Botões dentro do dropdown */
        [data-testid="stVerticalBlock"]:has(
            > [data-testid="stElementContainer"]:first-child .pg-dropdown-anchor
        ) [data-testid="stButton"] > button {
            background: transparent !important;
            border: none !important;
            text-align: left !important;
            padding: 6px 12px !important;
            font-size: 12px !important;
            line-height: 1.3 !important;
            height: auto !important;
            min-height: 0 !important;
            justify-content: flex-start !important;
            color: #1e293b !important;
            border-radius: 0 !important;
            box-shadow: none !important;
            font-weight: 400 !important;
            width: 100% !important;
        }
        [data-testid="stVerticalBlock"]:has(
            > [data-testid="stElementContainer"]:first-child .pg-dropdown-anchor
        ) [data-testid="stButton"] > button:hover {
            background: #E9ECEF !important;
            color: #0f172a !important;
        }
        [data-testid="stVerticalBlock"]:has(
            > [data-testid="stElementContainer"]:first-child .pg-dropdown-anchor
        ) > [data-testid="stElementContainer"] {
            margin-bottom: 0 !important;
            margin-top: 0 !important;
        }
        .pg-no-results {
            padding: 8px 12px;
            color: #94a3b8;
            font-style: italic;
            font-size: 11px;
        }
        .pg-dropdown-anchor {
            display: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_resultados_pesquisa(termo: str, resultados: dict) -> None:
    """Renderiza os resultados num dropdown discreto colado à barra de pesquisa."""
    _inject_pesquisa_dropdown_css()

    total = (
        len(resultados["animais"])
        + len(resultados["donos"])
        + len(resultados["garanhoes"])
    )

    with st.container():
        # Anchor invisível usado pelo CSS `:has()` para identificar o
        # container do dropdown e estilizar o seu conteúdo.
        st.markdown(
            "<div class='pg-dropdown-anchor'></div>",
            unsafe_allow_html=True,
        )

        if total == 0:
            st.markdown(
                f"<div class='pg-no-results'>Sem resultados para “{termo}”</div>",
                unsafe_allow_html=True,
            )
            return

        emoji_animal = {
            "garanhao": "🐴",
            "egua": "🐎",
            "receptora": "🤰",
        }

        # Animais
        for a in resultados["animais"]:
            prop = a.get("proprietario") or "—"
            emoji = emoji_animal.get(a.get("tipo"), "🐎")
            if st.button(
                f"{emoji}  {a['nome']} ({prop})",
                key=f"pg_animal_{a['id']}",
                width="stretch",
            ):
                st.session_state["ver_animal_id"] = a["id"]
                st.session_state["aba_selecionada"] = "Estadias e Visitas"
                st.session_state["pesquisa_global_limpar"] = True
                st.rerun()

        # Proprietários
        for d in resultados["donos"]:
            if st.button(
                f"👥  {d['nome']}",
                key=f"pg_dono_{d['id']}",
                width="stretch",
            ):
                st.session_state["ver_proprietario_id"] = d["id"]
                st.session_state["aba_selecionada"] = "Proprietários"
                st.session_state["pesquisa_global_limpar"] = True
                st.rerun()

        # Garanhões com stock
        for g in resultados["garanhoes"]:
            label = f"🐴  {g['nome']} — {g['palhetas']} palhetas"
            if st.button(
                label,
                key=f"pg_gar_{g['nome']}",
                width="stretch",
            ):
                st.session_state["aba_selecionada"] = "Stock de sémen"
                st.session_state["pesquisa_global_garanhao"] = g["nome"]
                st.session_state["pesquisa_global_limpar"] = True
                st.rerun()


def render_header(app_settings, user_info):
    company_name = (app_settings or {}).get("company_name") or "Sistema"
    logo = (app_settings or {}).get("logo_base64")

    st.markdown("<div id='topbar-anchor'></div>", unsafe_allow_html=True)

    # Layout: marca à esquerda, barra de pesquisa no centro, utilizador à direita
    col_brand, col_search, col_user = st.columns([3, 4, 2])

    with col_brand:
        if logo:
            st.markdown(
                f"""
                <div style='display:flex; align-items:center; gap:10px; padding: 4px 0 8px 0;'>
                    <img src='{logo}' style='height:28px;'/>
                    <div class='app-topbar-title'>{company_name}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            initials = "".join([p[0] for p in company_name.split()[:2] if p]) or "S"
            st.markdown(
                f"""
                <div style='display:flex; align-items:center; gap:10px; padding: 4px 0 8px 0;'>
                    <div style='width:28px; height:28px; border-radius:6px; background:var(--bg); border:1px solid var(--border); display:flex; align-items:center; justify-content:center; font-size:.75rem; color:var(--muted);'>
                        {initials}
                    </div>
                    <div class='app-topbar-title'>{company_name}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with col_search:
        # Limpar o campo (vindo de um click anterior) ANTES de instanciar o widget,
        # caso contrário o Streamlit lança StreamlitAPIException.
        if st.session_state.get("pesquisa_global_limpar"):
            del st.session_state["pesquisa_global_limpar"]
            st.session_state["pesquisa_global"] = ""

        st.text_input(
            "Pesquisa global",
            key="pesquisa_global",
            placeholder="🔍 Pesquisar animal, proprietário...",
            label_visibility="collapsed",
        )

    with col_user:
        nome = (user_info or {}).get("nome") or ""
        if nome:
            st.markdown(
                f"<div style='text-align:right;padding:8px 4px;font-size:.82rem;"
                f"color:#475569;'>{nome}</div>",
                unsafe_allow_html=True,
            )

    # Resultados da pesquisa (apenas se >= 3 caracteres)
    termo = st.session_state.get("pesquisa_global", "") or ""
    if len(termo.strip()) >= 3:
        resultados = _pesquisa_global(termo)
        _render_resultados_pesquisa(termo, resultados)

    return False, False


def render_sidebar(app_settings, user_info, menu_principal, menu_secundario, active_key):
    import streamlit as st

    company_name = (app_settings or {}).get("company_name") or "Sistema"
    logo = (app_settings or {}).get("logo_base64")
    user_name = (user_info or {}).get("nome") or "Utilizador"
    nivel = (user_info or {}).get("nivel") or ""

    st.sidebar.markdown("<div class='sidebar-brand'>", unsafe_allow_html=True)
    if logo:
        st.sidebar.markdown(
            f"<img src='{logo}' style='max-width:100%; height:40px; object-fit:contain; margin-bottom:6px;'/>",
            unsafe_allow_html=True,
        )
    else:
        initials = "".join([p[0] for p in company_name.split()[:2] if p]) or "S"
        st.sidebar.markdown(
            f"<div style='width:40px; height:40px; border-radius:8px; background:#ffffff; border:1px solid var(--border); display:flex; align-items:center; justify-content:center; color:var(--muted); font-weight:700; margin-bottom:6px;'>{initials}</div>",
            unsafe_allow_html=True,
        )
    st.sidebar.markdown(f"<div class='sidebar-brand-title'>{company_name}</div>", unsafe_allow_html=True)
    st.sidebar.markdown("</div>", unsafe_allow_html=True)

    st.sidebar.markdown(
        f"""
        <div class='sidebar-user-card'>
            <div class='sidebar-user-name'>{user_name}</div>
            <div class='sidebar-user-chip'>{nivel}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Prefixos/chaves de estado específicas de página a limpar na navegação
    _PAGE_STATE_PREFIXES = ("insem_", "transfer_edit_", "stock_filter_")
    _PAGE_STATE_EXACT = {"edit_insemination_id", "edit_transfer_id", "edit_transfer_type",
                         "edit_transfer_source_type", "redirecionar_ver_stock"}

    def _clear_page_state():
        """Remove session state específico de páginas para garantir início limpo."""
        to_del = [
            k for k in list(st.session_state.keys())
            if any(k.startswith(p) for p in _PAGE_STATE_PREFIXES) or k in _PAGE_STATE_EXACT
        ]
        for k in to_del:
            del st.session_state[k]

    # Inicializar _nav_last_active ANTES de renderizar widgets
    if not st.session_state.get("_nav_last_active"):
        default = menu_principal[0] if menu_principal else (menu_secundario[0] if menu_secundario else None)
        st.session_state["_nav_last_active"] = default

    # Consumir redirect externo
    redirect_target = st.session_state.pop("_nav_redirect_active", None)
    if redirect_target:
        st.session_state["_nav_last_active"] = redirect_target

    current_page = st.session_state["_nav_last_active"]

    # ---- Menu Principal: botões estilizados ----
    for item in menu_principal:
        is_active = current_page == item
        btn_style = "primary" if is_active else "secondary"
        if st.sidebar.button(item, key=f"_nav_pri_{item}", width="stretch", type=btn_style):
            _clear_page_state()
            st.session_state["_nav_last_active"] = item
            st.session_state["aba_selecionada"] = item
            st.session_state["_just_navigated"] = True
            st.rerun()

    # ---- Menu Secundário: botões dentro do expander ----
    if menu_secundario:
        expanded = current_page in menu_secundario
        with st.sidebar.expander("Mais opções", expanded=expanded):
            for item in menu_secundario:
                is_active = current_page == item
                label = f"▶ {item}" if is_active else item
                btn_type = "primary" if is_active else "secondary"
                if st.button(label, key=f"_nav_sec_{item}", width="stretch", type=btn_type):
                    _clear_page_state()
                    st.session_state["_nav_last_active"] = item
                    st.session_state["aba_selecionada"] = item
                    st.session_state["_just_navigated"] = True
                    st.rerun()

    # ---- Terminar Sessão (fundo da sidebar) ----
    st.sidebar.markdown("---")
    logout_clicked = st.sidebar.button(
        t("header.logout"),
        key="_sidebar_logout",
        width="stretch",
        type="secondary",
    )

    return st.session_state["_nav_last_active"], logout_clicked


def render_zone_title(title: str, cls: str = "reports-zone-title"):
    st.markdown(f"<div class='{cls}'>{title}</div>", unsafe_allow_html=True)


def render_kpi_strip(items):
    content = "".join(
        [f"<div class='reports-kpi-item'><b>{valor}</b> {nome}</div>" for nome, valor in items]
    )
    st.markdown(f"<div class='reports-kpi-strip'>{content}</div>", unsafe_allow_html=True)


def safe_pick(df, cols):
    if df.empty:
        return df
    return df[[c for c in cols if c in df.columns]].copy()


# ============================================================
# Design System v2 — proposta (tokens + componentes base)
#
# Aditivo: convive com o CSS antigo (inject_all_css_consolidated,
# inject_reports_css, render_kpi_strip, etc.) sem os alterar nem
# remover — nenhuma página deixa de funcionar. Uma página só passa a
# usar isto quando for explicitamente migrada (por agora: só
# reports_page.py, como exemplo).
#
# Direção: técnica/densa, não "amigável" — uma cor de marca (vermelho
# #E85D4A) + neutros para tudo o resto. Sem gradientes, sem cards
# decorativos, sem emoji como iconografia.
# ============================================================

def inject_design_tokens():
    """Tokens do design system (cor, tipografia, espaçamento) +
    classes utilitárias dos componentes base. Prefixo `--ds-`/`ds-`
    para nunca colidir com as variáveis/classes antigas."""
    st.markdown(
        f"""
        <style>
            :root {{
                --ds-primary: {DEFAULT_PRIMARY_COLOR};
                --ds-primary-hover: #cf503f;
                --ds-primary-tint: #fbeae7;
                --ds-primary-tint-strong: #f3c9c1;

                --ds-gray-50:  #f8fafc;
                --ds-gray-100: #f1f5f9;
                --ds-gray-200: #e2e8f0;
                --ds-gray-300: #cbd5e1;
                --ds-gray-400: #94a3b8;
                --ds-gray-500: #64748b;
                --ds-gray-600: #475569;
                --ds-gray-700: #334155;
                --ds-gray-800: #1e293b;
                --ds-gray-900: #0f172a;

                --ds-text-xs: .72rem;
                --ds-text-sm: .82rem;
                --ds-text-base: .9rem;
                --ds-text-md: 1rem;
                --ds-text-lg: 1.25rem;
                --ds-text-xl: 1.75rem;

                --ds-space-1: 4px;
                --ds-space-2: 8px;
                --ds-space-3: 12px;
                --ds-space-4: 16px;
                --ds-space-5: 24px;

                --ds-radius-sm: 4px;
                --ds-radius: 8px;
            }}

            /* Cabeçalho de página — denso, sem gradiente/card */
            .ds-page-header {{
                display: flex;
                align-items: baseline;
                gap: var(--ds-space-3);
                padding-bottom: var(--ds-space-3);
                margin-bottom: var(--ds-space-4);
                border-bottom: 1px solid var(--ds-gray-200);
            }}
            .ds-page-header h1 {{
                font-size: var(--ds-text-lg);
                font-weight: 700;
                color: var(--ds-gray-900);
                margin: 0;
                letter-spacing: -.01em;
            }}
            .ds-page-header .ds-subtitle {{
                font-size: var(--ds-text-sm);
                color: var(--ds-gray-500);
            }}

            /* Zona/secção — usar via render_zone_title(title, "ds-zone-title") */
            .ds-zone-title {{
                font-size: var(--ds-text-xs);
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: .06em;
                color: var(--ds-gray-500);
                margin: var(--ds-space-3) 0 var(--ds-space-2) 0;
            }}

            /* KPI denso — número + label, sem card/borda */
            .ds-kpi-row {{
                display: flex;
                gap: var(--ds-space-5);
                flex-wrap: wrap;
                margin-bottom: var(--ds-space-3);
            }}
            .ds-kpi {{
                display: flex;
                flex-direction: column;
                gap: 2px;
            }}
            .ds-kpi-value {{
                font-size: var(--ds-text-xl);
                font-weight: 700;
                color: var(--ds-gray-900);
                line-height: 1;
                font-variant-numeric: tabular-nums;
            }}
            .ds-kpi-label {{
                font-size: var(--ds-text-xs);
                text-transform: uppercase;
                letter-spacing: .05em;
                color: var(--ds-gray-500);
            }}

            /* Pill de estado — só 3 níveis, só marca + neutros */
            .ds-pill {{
                display: inline-flex;
                align-items: center;
                padding: 2px 8px;
                border-radius: 999px;
                font-size: var(--ds-text-xs);
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: .03em;
                border: 1px solid transparent;
            }}
            .ds-pill--ok {{
                background: var(--ds-gray-100);
                color: var(--ds-gray-600);
                border-color: var(--ds-gray-200);
            }}
            .ds-pill--aviso {{
                background: var(--ds-primary-tint);
                color: var(--ds-gray-800);
                border-color: var(--ds-primary-tint-strong);
            }}
            .ds-pill--critico {{
                background: var(--ds-primary);
                color: #ffffff;
            }}

            /* Tabela densa — aplica-se ao st.dataframe nativo */
            [data-testid="stDataFrame"] {{
                font-size: var(--ds-text-sm);
            }}
            [data-testid="stDataFrame"] [role="columnheader"] {{
                font-size: var(--ds-text-xs) !important;
                text-transform: uppercase;
                letter-spacing: .04em;
                color: var(--ds-gray-500) !important;
                font-weight: 700 !important;
                background: var(--ds-gray-50) !important;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str, subtitle: str | None = None) -> None:
    """Cabeçalho de página do design system v2 — título + subtítulo
    opcional numa linha, sem decoração. Requer `inject_design_tokens()`
    já ter corrido na página."""
    sub_html = f"<span class='ds-subtitle'>{subtitle}</span>" if subtitle else ""
    st.markdown(
        f"<div class='ds-page-header'><h1>{title}</h1>{sub_html}</div>",
        unsafe_allow_html=True,
    )


def render_kpi_row(items) -> None:
    """Fila de KPIs densa — número + label, sem card/borda. Alternativa
    a `render_kpi_strip` (que se mantém, ainda usada por quem não
    migrou) para páginas já no design system v2."""
    content = "".join(
        f"<div class='ds-kpi'><div class='ds-kpi-value'>{valor}</div>"
        f"<div class='ds-kpi-label'>{nome}</div></div>"
        for nome, valor in items
    )
    st.markdown(f"<div class='ds-kpi-row'>{content}</div>", unsafe_allow_html=True)


def render_status_pill(label: str, level: str = "ok") -> str:
    """Devolve o HTML de uma pill de estado (`ok`/`aviso`/`critico`) —
    compor dentro de `st.markdown(..., unsafe_allow_html=True)`, não
    faz render direto (para poder ser embutida em linha/tabela)."""
    assert level in ("ok", "aviso", "critico"), f"nível inválido: {level!r}"
    return f"<span class='ds-pill ds-pill--{level}'>{label}</span>"
