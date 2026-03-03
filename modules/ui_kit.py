import streamlit as st
from modules.i18n import t


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
            section.main > div.block-container {
                padding-top: 0.8rem;
                padding-bottom: 1.4rem;
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


def render_stepper(cols, key, min_value=0, max_value=None, invalid_tooltip=""):
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
    color = primary_color or "#1D4ED8"
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
            .reports-kpi-item b {{
                color: var(--primary) !important;
            }}
            a {{
                color: var(--primary) !important;
            }}
            .stButton > button[data-testid="baseButton-primary"] {{
                background-color: var(--primary) !important;
                border-color: var(--primary) !important;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(app_settings, user_info):
    company_name = (app_settings or {}).get("company_name") or "Sistema"
    logo = (app_settings or {}).get("logo_base64")

    st.markdown("<div id='topbar-anchor'></div>", unsafe_allow_html=True)
    col_left, col_right = st.columns([5, 2])
    with col_left:
        if logo:
            st.markdown(
                f"""
                <div style='display:flex; align-items:center; gap:10px;'>
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
                <div style='display:flex; align-items:center; gap:10px;'>
                    <div style='width:28px; height:28px; border-radius:6px; background:var(--bg); border:1px solid var(--border); display:flex; align-items:center; justify-content:center; font-size:.75rem; color:var(--muted);'>
                        {initials}
                    </div>
                    <div class='app-topbar-title'>{company_name}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with col_right:
        st.markdown("<div class='app-topbar-actions'>", unsafe_allow_html=True)
        settings_clicked = st.button(t("header.settings"), width="content", key="topbar_settings")
        logout_clicked = st.button(t("header.logout"), width="content", key="topbar_logout")
        st.markdown("</div>", unsafe_allow_html=True)

    return settings_clicked, logout_clicked


def render_sidebar(app_settings, user_info, menu_items, active_key):
    company_name = (app_settings or {}).get("company_name") or "Sistema"
    logo = (app_settings or {}).get("logo_base64")
    user_name = (user_info or {}).get("nome") or "Utilizador"
    nivel = (user_info or {}).get("nivel") or ""

    st.sidebar.markdown(
        "<div class='sidebar-brand'>",
        unsafe_allow_html=True,
    )
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

    idx = menu_items.index(active_key) if active_key in menu_items else 0
    aba = st.sidebar.radio("Menu", menu_items, index=idx, label_visibility="collapsed")
    return aba


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
