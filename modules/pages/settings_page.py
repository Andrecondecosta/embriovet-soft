import base64
import streamlit as st
from modules.i18n import t


def run_settings_page(ctx: dict):
    globals().update(ctx)

    st.header(t("settings.title"))
    inject_stock_css()
    inject_reports_css()

    render_zone_title(t("settings.branding"), "insem-zone-title")

    current_company = app_settings.get("company_name") if app_settings else "Sistema"
    current_lang = app_settings.get("language", "pt-PT") if app_settings else "pt-PT"
    current_logo = app_settings.get("logo_base64") if app_settings else None
    current_primary = app_settings.get("primary_color") if app_settings else "#1D4ED8"

    if "settings_logo_preview" not in st.session_state:
        st.session_state["settings_logo_preview"] = current_logo

    col_left, col_right = st.columns([1.2, 1])

    with col_left:
        company_name = st.text_input(t("label.company_name"), value=current_company)

        lang_options = ["pt-PT", "en", "fr", "de"]
        lang_labels = {
            "pt-PT": "Português (Portugal)",
            "en": "English",
            "fr": "Français",
            "de": "Deutsch",
        }
        language = st.selectbox(
            label=t("settings.language_label"),
            options=lang_options,
            format_func=lambda x: lang_labels.get(x, x),
            index=lang_options.index(current_lang) if current_lang in lang_options else 0,
        )

        logo_file = st.file_uploader(t("label.logo"), type=["png", "jpg", "jpeg"])
        if logo_file is not None:
            b64 = base64.b64encode(logo_file.getvalue()).decode("utf-8")
            logo_uri = f"data:{logo_file.type};base64,{b64}"
            st.session_state["settings_logo_preview"] = logo_uri

        primary_color = st.text_input(t("label.primary_color_optional"), value=current_primary or "")

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button(t("btn.save_changes"), type="primary", width="stretch"):
                update_branding_settings(
                    company_name,
                    st.session_state.get("settings_logo_preview"),
                    language,
                    primary_color or None,
                )
                st.session_state["company_name"] = company_name
                st.session_state["logo_base64"] = st.session_state.get("settings_logo_preview")
                st.session_state["lang"] = language
                st.session_state["primary_color"] = primary_color or None
                st.success(t("success.saved"))
                st.rerun()
        with btn_col2:
            if st.button(t("btn.restore_defaults"), width="stretch"):
                update_branding_settings("Sistema", None, "pt-PT", "#1D4ED8")
                st.session_state["settings_logo_preview"] = None
                st.session_state["company_name"] = "Sistema"
                st.session_state["lang"] = "pt-PT"
                st.session_state["primary_color"] = "#1D4ED8"
                st.success(t("success.defaults_restored"))
                st.rerun()

    with col_right:
        st.markdown(
            """
            <div style='border:1px solid #e2e8f0; border-radius:10px; padding:12px; background:#f8fafc;'>
                <div style='font-size:.75rem; text-transform:uppercase; letter-spacing:.04em; color:#64748b; margin-bottom:8px;'>{t('common.preview')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        logo_html = ""
        logo_preview = st.session_state.get("settings_logo_preview")
        if logo_preview:
            logo_html = f"<img src='{logo_preview}' style='height:28px; margin-right:10px;'/>"

        st.markdown(
            f"""
            <div style='border:1px solid #e2e8f0; border-radius:10px; padding:12px; background:#ffffff; margin-top:8px;'>
                <div style='display:flex; align-items:center;'>
                    {logo_html}
                    <div style='font-weight:700; font-size:1.0rem;'>{company_name}</div>
                </div>
                <div style='margin-top:12px; border-top:1px solid #e2e8f0; padding-top:10px;'>
                    <div style='font-size:.75rem; color:#64748b; margin-bottom:6px;'>Menu</div>
                    <div style='padding:6px 8px; border-radius:8px; border:1px solid #e2e8f0; margin-bottom:6px; background:#f8fafc;'>🏠 Painel</div>
                    <div style='padding:6px 8px; border-radius:8px; border:1px solid #e2e8f0; margin-bottom:6px;'>📦 Ver Stock</div>
                    <div style='padding:6px 8px; border-radius:8px; border:1px solid #e2e8f0;'>📈 Relatórios</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )