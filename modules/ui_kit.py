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

    with cols[0]:
        st.button(
            "−",
            key=f"{key}_minus",
            on_click=step,
            args=(-1,),
            disabled=min_value is not None and value <= min_value,
            help="Diminuir quantidade",
        )
    with cols[1]:
        st.markdown(f"<div class='{cls}' title='{tooltip}'>{value}</div>", unsafe_allow_html=True)
    with cols[2]:
        st.button(
            "+",
            key=f"{key}_plus",
            on_click=step,
            args=(1,),
            disabled=max_value is not None and value >= max_value,
            help="Aumentar quantidade",
        )

    st.components.v1.html(
        """
        <script>
        (function() {
            const setLabel = (label, title) => {
                const btns = window.parent.document.querySelectorAll(
                    `button[aria-label="${label}"], button[title="${title}"]`
                );
                btns.forEach(btn => {
                    if (!btn.innerText || !btn.innerText.trim()) {
                        btn.innerText = label;
                    }
                });
            };
            setLabel("−", "Diminuir quantidade");
            setLabel("+", "Aumentar quantidade");
        })();
        </script>
        """,
        height=0,
    )

    return value, invalid


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
