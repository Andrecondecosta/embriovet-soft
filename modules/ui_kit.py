import streamlit as st


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
                border: 1px solid #dbe4ee;
                background: #f8fafc;
                color: #334155;
                border-radius: 8px;
                padding: 4px 9px;
                font-size: 0.78rem;
                white-space: nowrap;
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
