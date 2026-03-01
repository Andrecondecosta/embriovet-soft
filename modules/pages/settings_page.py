import streamlit as st
from modules.i18n import t


def run_settings_page(ctx: dict):
    globals().update(ctx)

    st.header(t("settings.title"))
    inject_stock_css()
    inject_reports_css()

    render_zone_title(t("settings.theme_title"), "insem-zone-title")

    current_theme = (app_settings or {}).get("theme_key") or "blue"
    theme_key = st.radio(
        "Tema",
        options=list(THEMES.keys()),
        format_func=lambda k: k.capitalize(),
        index=list(THEMES.keys()).index(current_theme) if current_theme in THEMES else 0,
        horizontal=True,
        key="settings_theme_key",
    )

    preview_color = THEMES.get(theme_key, THEMES["blue"])
    st.markdown(
        f"<div style='width:100%; height:10px; border-radius:6px; background:{preview_color}; border:1px solid #e2e8f0;'></div>",
        unsafe_allow_html=True,
    )

    if st.button(t("settings.save"), type="primary", width="stretch"):
        logo_base64 = app_settings.get("logo_base64") if app_settings else None
        company_name = app_settings.get("company_name") if app_settings else "Sistema"
        primary_color = THEMES.get(theme_key, THEMES["blue"])
        save_app_settings(app_settings["id"], company_name, logo_base64, primary_color, theme_key)
        st.success(t("settings.updated"))
        st.rerun()

    render_zone_title(t("settings.language_title"), "insem-zone-title")
    lang_options = ["pt-PT", "en", "fr", "de"]
    lang_labels = {
        "pt-PT": "Português (Portugal)",
        "en": "English",
        "fr": "Français",
        "de": "Deutsch",
    }
    current_lang = app_settings.get("language", "pt-PT") if app_settings else "pt-PT"
    st.selectbox(
        label=t("settings.language_label"),
        options=lang_options,
        format_func=lambda x: lang_labels.get(x, x),
        key="language_selector",
        index=lang_options.index(current_lang) if current_lang in lang_options else 0,
    )

    if st.button(t("settings.save"), width="stretch", key="settings_save_language"):
        selected_lang = st.session_state.get("language_selector", current_lang)
        update_language(selected_lang)
        st.session_state["lang"] = selected_lang
        st.success(t("settings.lang_updated"))
        st.rerun()