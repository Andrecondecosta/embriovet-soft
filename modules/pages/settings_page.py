import base64
import pandas as pd
import streamlit as st

from modules.db import get_connection
from modules.i18n import t


# ────────────────────────────────────────────────────────────────────────────
# Alojamentos — helpers DB
# ────────────────────────────────────────────────────────────────────────────
TIPOS_ALOJAMENTO = ["box", "paddock", "outro"]


def _carregar_alojamentos_admin() -> pd.DataFrame:
    sql = """
        SELECT id, tipo, nome, capacidade, ativo, observacoes
        FROM alojamentos
        ORDER BY ativo DESC, tipo, nome
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn)


def _inserir_alojamento(dados: dict) -> int | None:
    sql = """
        INSERT INTO alojamentos (tipo, nome, capacidade, observacoes, ativo)
        VALUES (%(tipo)s, %(nome)s, %(capacidade)s, %(observacoes)s, TRUE)
        RETURNING id
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, dados)
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        return new_id


def _atualizar_alojamento(aloj_id: int, dados: dict) -> bool:
    sql = """
        UPDATE alojamentos SET
            tipo = %(tipo)s,
            nome = %(nome)s,
            capacidade = %(capacidade)s,
            observacoes = %(observacoes)s
        WHERE id = %(id)s
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, {**dados, "id": aloj_id})
        conn.commit()
        cur.close()
    return True


def _toggle_ativo_alojamento(aloj_id: int) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE alojamentos SET ativo = NOT ativo WHERE id = %s",
            (aloj_id,),
        )
        conn.commit()
        cur.close()


# ────────────────────────────────────────────────────────────────────────────
# Alojamentos — formulário "novo" + edição inline + lista
# ────────────────────────────────────────────────────────────────────────────
def _render_form_novo_alojamento() -> None:
    with st.expander("+ Novo alojamento", expanded=False):
        with st.form("form_novo_alojamento", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                nome = st.text_input("Nome *", key="nv_aloj_nome")
                tipo = st.selectbox("Tipo", options=TIPOS_ALOJAMENTO, key="nv_aloj_tipo")
            with c2:
                capacidade = st.number_input(
                    "Capacidade", min_value=1, max_value=999, value=1, step=1,
                    key="nv_aloj_capacidade",
                )
                observacoes = st.text_input(
                    "Observações (opcional)", key="nv_aloj_obs",
                )
            submit = st.form_submit_button("Guardar", type="primary", width="stretch")
            if submit:
                if not nome.strip():
                    st.error("O nome é obrigatório.")
                else:
                    try:
                        new_id = _inserir_alojamento({
                            "tipo": tipo,
                            "nome": nome.strip(),
                            "capacidade": int(capacidade),
                            "observacoes": observacoes.strip() or None,
                        })
                        st.success(f"Alojamento criado (#{new_id}).")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")


def _render_form_editar_alojamento(row: dict) -> None:
    aid = int(row["id"])
    with st.form(f"form_edit_aloj_{aid}"):
        c1, c2 = st.columns(2)
        with c1:
            nome = st.text_input("Nome *", value=row.get("nome") or "")
            tipo_idx = TIPOS_ALOJAMENTO.index(row["tipo"]) if row.get("tipo") in TIPOS_ALOJAMENTO else 0
            tipo = st.selectbox("Tipo", options=TIPOS_ALOJAMENTO, index=tipo_idx)
        with c2:
            capacidade = st.number_input(
                "Capacidade", min_value=1, max_value=999,
                value=int(row.get("capacidade") or 1), step=1,
            )
            observacoes = st.text_input(
                "Observações (opcional)", value=row.get("observacoes") or "",
            )
        b1, b2 = st.columns(2)
        with b1:
            guardar = st.form_submit_button("Guardar", type="primary", width="stretch")
        with b2:
            cancelar = st.form_submit_button("Cancelar", width="stretch")
        if cancelar:
            st.session_state[f"aloj_edit_{aid}"] = False
            st.rerun()
        if guardar:
            if not nome.strip():
                st.error("O nome é obrigatório.")
                return
            try:
                _atualizar_alojamento(aid, {
                    "tipo": tipo,
                    "nome": nome.strip(),
                    "capacidade": int(capacidade),
                    "observacoes": observacoes.strip() or None,
                })
                st.session_state[f"aloj_edit_{aid}"] = False
                st.success("Atualizado.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")


def _render_tab_alojamentos() -> None:
    st.markdown("### Alojamentos")
    st.caption("Gerir boxes, paddocks e outros locais.")

    _render_form_novo_alojamento()
    st.markdown("---")

    df = _carregar_alojamentos_admin()
    if df.empty:
        st.info("Sem alojamentos registados.")
        return

    # Cabeçalho
    head = st.columns([2.2, 1.2, 1.2, 1.4, 1.2, 1.2])
    for i, h in enumerate(["Nome", "Tipo", "Capacidade", "Estado", "", ""]):
        head[i].markdown(
            f"<div style='font-size:.7rem;color:#94a3b8;text-transform:uppercase;"
            f"letter-spacing:.5px;font-weight:700;'>{h}</div>",
            unsafe_allow_html=True,
        )
    st.markdown(
        "<hr style='border:none;border-top:1px solid #e2e8f0;margin:4px 0 8px;'>",
        unsafe_allow_html=True,
    )

    for _, row in df.iterrows():
        aid = int(row["id"])
        editing = st.session_state.get(f"aloj_edit_{aid}", False)

        cols = st.columns([2.2, 1.2, 1.2, 1.4, 1.2, 1.2])
        cols[0].write(row["nome"])
        cols[1].write(row["tipo"])
        cols[2].write(int(row["capacidade"] or 0))
        estado_txt = "Activo" if row["ativo"] else "Inactivo"
        estado_cor = "#16a34a" if row["ativo"] else "#94a3b8"
        cols[3].markdown(
            f"<span style='color:{estado_cor};font-weight:600;'>{estado_txt}</span>",
            unsafe_allow_html=True,
        )

        with cols[4]:
            label_toggle = "Inactivo" if row["ativo"] else "Activo"
            if st.button(label_toggle, key=f"toggle_aloj_{aid}", width="stretch"):
                _toggle_ativo_alojamento(aid)
                st.rerun()

        with cols[5]:
            if st.button("Editar", key=f"edit_aloj_{aid}", width="stretch"):
                st.session_state[f"aloj_edit_{aid}"] = True
                st.rerun()

        if editing:
            _render_form_editar_alojamento(row.to_dict())


def run_settings_page(ctx: dict):
    globals().update(ctx)

    st.header(t("settings.title"))

    tab_geral, tab_alojamentos = st.tabs(["Geral", "Alojamentos"])

    with tab_geral:
        _run_settings_geral()

    with tab_alojamentos:
        _render_tab_alojamentos()


def _run_settings_geral():
    inject_stock_css()
    inject_reports_css()

    render_zone_title(t("settings.branding"), "insem-zone-title")

    current_company = app_settings.get("company_name") if app_settings else t("common.system")
    current_lang = app_settings.get("language", "pt-PT") if app_settings else "pt-PT"
    current_logo = app_settings.get("logo_base64") if app_settings else None
    current_primary = app_settings.get("primary_color") if app_settings else "#1D4ED8"

    if "settings_logo_preview" not in st.session_state:
        st.session_state["settings_logo_preview"] = current_logo

    col_left, col_right = st.columns([1.2, 1])

    with col_left:
        company_name = st.text_input(t("label.company_name"), value=current_company)

        lang_options = ["pt-PT", "en", "fr", "de", "zz"]
        lang_labels = {
            "pt-PT": t("language.pt_pt"),
            "en": t("language.en"),
            "fr": t("language.fr"),
            "de": t("language.de"),
            "zz": t("language.zz"),
        }
        language = st.selectbox(
            label=t("settings.language_label"),
            options=lang_options,
            format_func=lambda x: lang_labels.get(x, x),
            index=lang_options.index(current_lang) if current_lang in lang_options else 0,
        )
        qa_mode_value = st.toggle(
            t("settings.qa_mode"),
            value=st.session_state.get("i18n_qa_mode", False),
            key="settings_i18n_qa_mode",
        )
        st.session_state["i18n_qa_mode"] = qa_mode_value

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
                update_branding_settings(t("common.system"), None, "pt-PT", "#1D4ED8")
                st.session_state["settings_logo_preview"] = None
                st.session_state["company_name"] = t("common.system")
                st.session_state["lang"] = "pt-PT"
                st.session_state["primary_color"] = "#1D4ED8"
                st.success(t("success.defaults_restored"))
                st.rerun()

    with col_right:
        st.markdown(
            f"""
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
                    <div style='font-size:.75rem; color:#64748b; margin-bottom:6px;'>{t('common.menu')}</div>
                    <div style='padding:6px 8px; border-radius:8px; border:1px solid #e2e8f0; margin-bottom:6px; background:#f8fafc;'>{t('menu.dashboard')}</div>
                    <div style='padding:6px 8px; border-radius:8px; border:1px solid #e2e8f0; margin-bottom:6px;'>{t('menu.stock')}</div>
                    <div style='padding:6px 8px; border-radius:8px; border:1px solid #e2e8f0;'>{t('menu.reports')}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )