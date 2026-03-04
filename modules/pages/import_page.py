# /app/modules/pages/import_page.py
# Intelligent Import Wizard — Fase 4 da modularização
import datetime
import unicodedata
import importlib.util
import html as _html_lib
from io import BytesIO
import pandas as pd
from modules.i18n import t

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEMPLATE_COLS = [
    "garanhao",
    "data_embriovet/ref",
    "existencia_atual",
    "dose",
    "motilidade",
    "qualidade",
    "concentracao",
    "cor",
    "proprietario_nome",
    "contentor_codigo",
    "canister",
    "andar",
    "observacoes",
    "certificado",
]

ALIAS_MAP = {
    "garanhao": "garanhao",
    "data_embriovet_ref": "data_ref",
    "data_embriovet": "data_ref",
    "ref": "data_ref",
    "data": "data_ref",
    "existencia_atual": "existencia_atual",
    "existencia": "existencia_atual",
    "palhetas": "existencia_atual",
    "dose": "dose",
    "motilidade": "motilidade",
    "concentracao": "concentracao",
    "concentracao_": "concentracao",
    "cor": "cor",
    "color": "cor",
    "proprietario_nome": "proprietario_nome",
    "proprietario": "proprietario_nome",
    "dono": "proprietario_nome",
    "contentor_codigo": "contentor_codigo",
    "contentor": "contentor_codigo",
    "canister": "canister",
    "andar": "andar",
    "observacoes": "observacoes",
    "certificado": "certificado",
    "qualidade": "qualidade",
}

REQUIRED_COLS = [
    "garanhao",
    "data_ref",
    "existencia_atual",
    "proprietario_nome",
    "contentor_codigo",
    "canister",
    "andar",
]

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_import_page(ctx: dict):
    globals().update(ctx)

    st.header(t("import.title"))
    _inject_import_css()

    step = st.session_state.get("import_wiz_step", 1)
    _render_wizard_nav(step)

    if step == 1:
        _step_upload()
    elif step == 2:
        _step_entities()
    elif step == 3:
        _step_validate()
    elif step == 4:
        _step_report()


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

def _inject_import_css():
    st.markdown(
        """
        <style>
        .import-wiz-nav {
            display: flex; gap: 6px; margin-bottom: 1.4rem;
        }
        .import-wiz-step {
            flex: 1; text-align: center; padding: 7px 4px;
            border-radius: 6px; border: 1.5px solid #e2e8f0;
            font-size: .78rem; font-weight: 600; color: #64748b;
        }
        .import-wiz-step.active {
            border-color: #1D4ED8; background: #1D4ED8; color: white;
        }
        .import-wiz-step.done {
            border-color: #10B981; background: #F0FDF4; color: #065F46;
        }
        .import-zone-title {
            font-size: .78rem; text-transform: uppercase; letter-spacing: .05em;
            color: #64748b; margin: .5rem 0 .35rem 0; font-weight: 700;
        }
        .import-hint {
            font-size: .78rem; color: #475569; margin-bottom: .5rem;
        }
        .import-table-wrap {
            border: 1px solid #e2e8f0; border-radius: 8px;
            overflow-x: auto; max-width: 100%;
        }
        .import-table {
            width: 100%; border-collapse: collapse; font-size: .78rem;
        }
        .import-table th, .import-table td {
            border-bottom: 1px solid #e2e8f0; padding: 4px 6px;
            white-space: nowrap; text-align: left;
        }
        .import-table th {
            position: sticky; top: 0; background: #f1f5f9;
            z-index: 4; font-weight: 700; color: #0f172a;
        }
        .import-error-cell { background: #fee2e2 !important; color: #991b1b; }
        .import-error-icon { margin-left: 4px; font-size: .75rem; color: #dc2626; }
        .entity-resolved-badge {
            display: inline-flex; align-items: center; gap: 6px;
            background: #F0FDF4; border: 1px solid #10B981;
            border-radius: 6px; padding: 5px 10px;
            font-size: .83rem; color: #065F46; margin-bottom: 4px;
        }
        .date-adjusted-note {
            font-size: .74rem; color: #7C3AED;
            background: #EDE9FE; border-radius: 4px; padding: 2px 6px;
            display: inline-block; margin-left: 6px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Wizard nav
# ---------------------------------------------------------------------------

def _render_wizard_nav(step):
    labels = [
        t("import.wizard.step1"),
        t("import.wizard.step2"),
        t("import.wizard.step3"),
        t("import.wizard.step4"),
    ]
    cells = []
    for i, label in enumerate(labels, 1):
        if i < step:
            cls = "import-wiz-step done"
            icon = "✓ "
        elif i == step:
            cls = "import-wiz-step active"
            icon = ""
        else:
            cls = "import-wiz-step"
            icon = ""
        cells.append(f"<div class='{cls}'>{icon}{label}</div>")
    st.markdown(
        f"<div class='import-wiz-nav'>{''.join(cells)}</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalizar_coluna(nome):
    base = str(nome).strip().lower()
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    base = base.replace("/", "_").replace("-", "_").replace(" ", "_")
    return base


def _parse_int(valor):
    try:
        if pd.isna(valor):
            return None
        return int(float(valor))
    except Exception:
        return None


def _parse_float(valor):
    try:
        if pd.isna(valor):
            return None
        return float(valor)
    except Exception:
        return None


def _is_empty(val):
    """Returns True if value is blank/nan/None."""
    if val is None:
        return True
    try:
        if pd.isna(val):
            return True
    except Exception:
        pass
    return str(val).strip().lower() in ("", "nan", "none")


def _gerar_template_xlsx():
    buffer = BytesIO()
    df = pd.DataFrame(columns=TEMPLATE_COLS)
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="importar_semen")
    buffer.seek(0)
    return buffer.getvalue()


def _gerar_template_csv():
    return pd.DataFrame(columns=TEMPLATE_COLS).to_csv(index=False).encode("utf-8")


# ---------------------------------------------------------------------------
# Step 1 — Upload
# ---------------------------------------------------------------------------

def _step_upload():
    xlsx_ready = importlib.util.find_spec("openpyxl") is not None

    # Template downloads
    render_zone_title(t("import.zone.context"), "import-zone-title")
    ctx1, ctx2 = st.columns([3, 1.5])
    with ctx1:
        st.markdown(
            f"<div class='import-hint'>{t('import.hint')}</div>",
            unsafe_allow_html=True,
        )
    with ctx2:
        if xlsx_ready:
            st.download_button(
                t("import.download_xlsx"),
                data=_gerar_template_xlsx(),
                file_name="template_importar_semen.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
                key="dl_xlsx",
            )
        else:
            st.caption(t("import.xlsx_requires"))
        st.download_button(
            t("import.download_csv"),
            data=_gerar_template_csv(),
            file_name="template_importar_semen.csv",
            mime="text/csv",
            width="stretch",
            key="dl_csv",
        )

    render_zone_title(t("import.zone.upload"), "import-zone-title")
    uploaded_file = st.file_uploader(
        t("import.upload_label"), type=["xlsx", "csv"], key="import_uploader"
    )

    if uploaded_file is None:
        st.info(t("import.upload_to_validate"))
        return

    # Parse file
    try:
        if uploaded_file.name.lower().endswith(".csv"):
            raw_df = pd.read_csv(uploaded_file)
        else:
            if not xlsx_ready:
                st.error(t("import.xlsx_install"))
                return
            raw_df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(t("import.read_error", error=e))
        return

    if raw_df.empty:
        st.warning(t("import.file_empty"))
        return

    # Map columns
    col_map = {}
    for col in raw_df.columns:
        key = ALIAS_MAP.get(_normalizar_coluna(col))
        if key and key not in col_map:
            col_map[key] = col

    missing = [c for c in REQUIRED_COLS if c not in col_map]
    if missing:
        st.error(t("import.missing_columns", cols=", ".join(missing)))
        return

    # Build normalized df
    norm_df = pd.DataFrame({key: raw_df[col_map[key]] for key in col_map})
    norm_df["__row"] = raw_df.index + 2
    for opt in ["observacoes", "certificado", "qualidade", "concentracao", "cor", "dose"]:
        if opt not in norm_df.columns:
            norm_df[opt] = ""

    # Rename for display (data_ref → data_embriovet/ref)
    display_df = norm_df.drop(columns=["__row"]).copy()
    display_df = display_df.rename(columns={"data_ref": "data_embriovet/ref"})
    row_numbers = norm_df["__row"].tolist()

    file_id = (uploaded_file.name, getattr(uploaded_file, "size", None))
    if st.session_state.get("import_file_id") != file_id:
        # New file → reset wizard
        st.session_state["import_file_id"] = file_id
        st.session_state["import_parsed_df"] = display_df.copy()
        st.session_state["import_row_numbers"] = row_numbers
        for k in ["import_entity_actions", "import_editor_df", "import_report"]:
            st.session_state.pop(k, None)

    n_linhas = len(raw_df)
    st.success(f"✅ {t('import.file_loaded', count=n_linhas)}")

    # Mini preview
    with st.expander(t("import.preview_title"), expanded=True):
        prev_cols = [
            c for c in ["garanhao", "data_embriovet/ref", "existencia_atual",
                         "proprietario_nome", "contentor_codigo"]
            if c in display_df.columns
        ]
        st.dataframe(display_df[prev_cols].head(5), hide_index=True, width="stretch")

    st.divider()
    if st.button(
        t("import.btn.next_entities"),
        type="primary",
        key="upload_next",
    ):
        st.session_state["import_wiz_step"] = 2
        st.rerun()


# ---------------------------------------------------------------------------
# Step 2 — Entity Resolution
# ---------------------------------------------------------------------------

def _step_entities():
    parsed_df = st.session_state.get("import_parsed_df")
    if parsed_df is None:
        st.warning(t("import.session_expired"))
        if st.button(t("import.btn.back_start"), key="entities_expired_back"):
            st.session_state["import_wiz_step"] = 1
            st.rerun()
        return

    # Load current DB state
    curr_props = carregar_proprietarios(apenas_ativos=False)
    curr_conts = carregar_contentores(apenas_ativos=False)

    existing_owners = {
        str(n).strip().lower(): int(i)
        for i, n in zip(curr_props.get("id", []), curr_props.get("nome", []))
    }
    existing_conts = {
        str(c).strip().upper(): int(i)
        for c, i in zip(curr_conts.get("codigo", []), curr_conts.get("id", []))
    }

    # Detect unknown entities
    unknown_owners = []
    unknown_conts = []
    for _, row in parsed_df.iterrows():
        prop = str(row.get("proprietario_nome", "")).strip()
        if prop and not _is_empty(prop) and prop.lower() not in existing_owners:
            if prop not in unknown_owners:
                unknown_owners.append(prop)
        cont = str(row.get("contentor_codigo", "")).strip()
        if cont and not _is_empty(cont) and cont.upper() not in existing_conts:
            if cont not in unknown_conts:
                unknown_conts.append(cont)

    entity_actions = st.session_state.setdefault("import_entity_actions", {})

    if not unknown_owners and not unknown_conts:
        st.success(t("import.entities.all_ok"))
        _nav_buttons_entities(all_resolved=True)
        return

    st.markdown(f"<div class='import-hint'>{t('import.entities.intro')}</div>", unsafe_allow_html=True)

    # ─── Unknown owners ───────────────────────────────────────────────────
    owners_all_resolved = True
    if unknown_owners:
        st.markdown(f"### {t('import.entities.owners_title', count=len(unknown_owners))}")
        existing_names = curr_props["nome"].tolist() if not curr_props.empty else []
        options_map = ["(Criar como novo)"] + existing_names

        for owner_name in unknown_owners:
            key = f"owner__{owner_name}"
            resolved_info = entity_actions.get(key, {})

            if resolved_info.get("resolved"):
                st.markdown(
                    f"<div class='entity-resolved-badge'>✅ <b>{owner_name}</b> → {resolved_info.get('label', '')}</div>",
                    unsafe_allow_html=True,
                )
            else:
                owners_all_resolved = False
                with st.container():
                    c1, c2, c3 = st.columns([2.5, 3, 1.5])
                    with c1:
                        st.markdown(f"**{owner_name}**")
                        st.caption(t("import.entities.not_found"))
                    with c2:
                        sel = st.selectbox(
                            t("import.entities.action"),
                            options=options_map,
                            key=f"owner_sel__{owner_name}",
                            label_visibility="collapsed",
                        )
                    with c3:
                        st.write("")
                        if st.button(
                            t("import.entities.confirm_btn"),
                            key=f"owner_btn__{owner_name}",
                            type="primary",
                        ):
                            if sel == "(Criar como novo)":
                                prop_id = adicionar_proprietario({
                                    "nome": owner_name, "email": None,
                                    "telemovel": None, "nome_completo": None,
                                    "nif": None, "morada": None,
                                    "codigo_postal": None, "cidade": None,
                                })
                                if prop_id:
                                    entity_actions[key] = {
                                        "resolved": True,
                                        "resolved_id": prop_id,
                                        "label": t("import.entities.created_new", name=owner_name),
                                    }
                                    st.session_state["import_entity_actions"] = entity_actions
                                    st.rerun()
                            else:
                                match = curr_props.loc[curr_props["nome"] == sel, "id"]
                                if not match.empty:
                                    map_id = int(match.iloc[0])
                                    entity_actions[key] = {
                                        "resolved": True,
                                        "resolved_id": map_id,
                                        "label": t("import.entities.mapped_to", name=sel),
                                    }
                                    st.session_state["import_entity_actions"] = entity_actions
                                    st.rerun()
                st.divider()

    # ─── Unknown containers ───────────────────────────────────────────────
    conts_all_resolved = True
    if unknown_conts:
        st.markdown(f"### {t('import.entities.conts_title', count=len(unknown_conts))}")

        for cont_code in unknown_conts:
            key = f"cont__{cont_code}"
            resolved_info = entity_actions.get(key, {})

            if resolved_info.get("resolved"):
                st.markdown(
                    f"<div class='entity-resolved-badge'>✅ <b>{cont_code}</b> → {t('import.entities.cont_created')}</div>",
                    unsafe_allow_html=True,
                )
            else:
                conts_all_resolved = False
                with st.container():
                    c1, c2, c3 = st.columns([2, 3.5, 1.5])
                    with c1:
                        st.markdown(f"**{cont_code}**")
                        st.caption(t("import.entities.not_found"))
                    with c2:
                        desc = st.text_input(
                            t("import.entities.cont_desc"),
                            key=f"cont_desc__{cont_code}",
                            placeholder=t("import.entities.cont_desc_placeholder"),
                        )
                    with c3:
                        st.write("")
                        if st.button(
                            t("import.entities.create_cont_btn"),
                            key=f"cont_btn__{cont_code}",
                            type="primary",
                        ):
                            cont_id = adicionar_contentor({
                                "codigo": cont_code,
                                "descricao": desc or "",
                                "x": 100, "y": 100, "w": 150, "h": 150,
                            })
                            if cont_id:
                                entity_actions[key] = {
                                    "resolved": True,
                                    "resolved_id": cont_id,
                                }
                                st.session_state["import_entity_actions"] = entity_actions
                                st.rerun()
                st.divider()

    all_resolved = owners_all_resolved and conts_all_resolved
    _nav_buttons_entities(all_resolved=all_resolved)


def _nav_buttons_entities(all_resolved: bool):
    st.markdown("")
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button(t("import.btn.previous"), key="entities_prev"):
            st.session_state["import_wiz_step"] = 1
            st.rerun()
    with col2:
        if not all_resolved:
            st.caption(t("import.entities.resolve_all_hint"))
        if st.button(
            t("import.btn.next_validate"),
            type="primary",
            disabled=not all_resolved,
            key="entities_next",
        ):
            st.session_state["import_wiz_step"] = 3
            st.rerun()


# ---------------------------------------------------------------------------
# Step 3 — Validate & Correct
# ---------------------------------------------------------------------------

def _step_validate():
    parsed_df = st.session_state.get("import_parsed_df")
    if parsed_df is None:
        st.warning(t("import.session_expired"))
        if st.button(t("import.btn.back_start"), key="validate_expired_back"):
            st.session_state["import_wiz_step"] = 1
            st.rerun()
        return

    # Reload DB entities (include just-created ones)
    curr_props = carregar_proprietarios(apenas_ativos=False)
    curr_conts = carregar_contentores(apenas_ativos=False)
    entity_actions = st.session_state.get("import_entity_actions", {})

    # Build prop_map (DB + entity_actions overrides)
    prop_map = {
        str(n).strip().lower(): int(i)
        for i, n in zip(curr_props.get("id", []), curr_props.get("nome", []))
    }
    for key, val in entity_actions.items():
        if key.startswith("owner__") and val.get("resolved"):
            owner_name = key[len("owner__"):]
            prop_map[owner_name.lower()] = val["resolved_id"]

    cont_map = {
        str(c).strip().upper(): int(i)
        for c, i in zip(curr_conts.get("codigo", []), curr_conts.get("id", []))
    }

    row_numbers = st.session_state.get("import_row_numbers", [])

    # Init editor df
    if "import_editor_df" not in st.session_state:
        st.session_state["import_editor_df"] = parsed_df.copy()
    editor_df = st.session_state["import_editor_df"]

    # ─── Edit table ───────────────────────────────────────────────────────
    render_zone_title(t("import.zone.upload"), "import-zone-title")
    st.markdown(
        f"<div class='import-hint'>{t('import.rules_hint')}</div>",
        unsafe_allow_html=True,
    )

    FULL_COLS = [
        "garanhao", "data_embriovet/ref", "existencia_atual", "dose",
        "motilidade", "qualidade", "concentracao", "cor",
        "proprietario_nome", "contentor_codigo", "canister", "andar",
        "observacoes", "certificado",
    ]
    COMPACT_COLS = [
        "garanhao", "data_embriovet/ref", "existencia_atual",
        "dose", "motilidade", "qualidade", "concentracao", "cor",
    ]

    compact_view = st.toggle(t("import.compact_view"), value=True, key="validate_compact")
    col_order = COMPACT_COLS if compact_view else FULL_COLS
    col_order = [c for c in col_order if c in editor_df.columns]

    st.caption(t("import.edit_caption"))
    edited_view = st.data_editor(
        editor_df[col_order].copy(),
        key="import_data_editor",
        num_rows="fixed",
        width="stretch",
        hide_index=True,
    )

    # Apply edits back
    updated_df = editor_df.copy()
    for col in edited_view.columns:
        updated_df[col] = edited_view[col]
    st.session_state["import_editor_df"] = updated_df

    # ─── Validate ─────────────────────────────────────────────────────────
    errors_map, erros_df, linhas_validas = _validate_import_df(
        updated_df, row_numbers, cont_map, prop_map
    )

    render_zone_title(t("import.zone.validate"), "import-zone-title")
    total_linhas = len(updated_df)
    total_erros = len(errors_map)
    total_validas = total_linhas - total_erros
    render_kpi_strip([
        (t("import.kpi.lines"), total_linhas),
        (t("import.kpi.valid"), total_validas),
        (t("import.kpi.errors"), total_erros),
    ])

    if erros_df.empty:
        st.success(t("import.validation_ok"))
        # Show date adjustment info
        dates_with_year = sum(
            1 for _, r in updated_df.iterrows()
            if not _is_empty(r.get("data_embriovet/ref"))
        )
        if dates_with_year:
            st.info(t("import.date_adjustment_info", count=dates_with_year))
    else:
        st.warning(t("import.validation_errors"))
        st.dataframe(
            erros_df,
            width="stretch",
            height=min(220, 50 + len(erros_df) * 35),
            hide_index=True,
        )

    # Error highlighting in preview table
    if errors_map:
        _render_error_table(updated_df, col_order, errors_map)

    st.divider()
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button(t("import.btn.previous"), key="validate_prev"):
            st.session_state["import_wiz_step"] = 2
            st.rerun()
    with col2:
        btn_disabled = bool(errors_map) or not linhas_validas
        if st.button(
            t("btn.import"),
            type="primary",
            disabled=btn_disabled,
            key="validate_import_btn",
        ):
            _executar_importacao(linhas_validas)


def _render_error_table(df, columns, error_map):
    sticky_cols = ["garanhao", "data_embriovet/ref", "existencia_atual"]
    df_show = df[columns].fillna("")
    header_cells = []
    for col in columns:
        idx_sticky = sticky_cols.index(col) + 1 if col in sticky_cols else None
        cls = f"import-sticky-{idx_sticky}" if idx_sticky else ""
        label = col.replace("_", " ")
        header_cells.append(f"<th class='{cls}'>{_html_lib.escape(label)}</th>")

    rows_html = []
    for idx, row in df_show.iterrows():
        row_errors = error_map.get(idx, {})
        cells = []
        for col in columns:
            idx_sticky = sticky_cols.index(col) + 1 if col in sticky_cols else None
            classes = [f"import-sticky-{idx_sticky}"] if idx_sticky else []
            msg = row_errors.get(col)
            if msg:
                classes.append("import-error-cell")
            cls = " ".join(classes)
            title_attr = f" title='{_html_lib.escape(msg)}'" if msg else ""
            val = _html_lib.escape(str(row.get(col, "")))
            icon = "<span class='import-error-icon'>⚠</span>" if msg else ""
            cells.append(f"<td class='{cls}'{title_attr}>{val}{icon}</td>")
        rows_html.append(f"<tr>{''.join(cells)}</tr>")

    table_html = f"""
    <div class='import-table-wrap'>
        <table class='import-table'>
            <thead><tr>{''.join(header_cells)}</tr></thead>
            <tbody>{''.join(rows_html)}</tbody>
        </table>
    </div>
    """
    st.markdown(table_html, unsafe_allow_html=True)


def _validate_import_df(df, row_nums, cont_map, prop_map):
    errors = {}
    errors_list = []
    valid_rows = []

    for idx, row in df.iterrows():
        row_num = row_nums[idx] if idx < len(row_nums) else idx + 2

        def add_error(col, msg, _idx=idx):
            errors.setdefault(_idx, {})[col] = msg
            errors_list.append({"linha": row_num, "coluna": col, "erro": msg})

        garanhao = str(row.get("garanhao", "")).strip()
        if _is_empty(garanhao):
            add_error("garanhao", t("import.error.garanhao_required"))

        prop_nome = str(row.get("proprietario_nome", "")).strip()
        if _is_empty(prop_nome):
            add_error("proprietario_nome", t("import.error.owner_required"))

        data_ref = str(row.get("data_embriovet/ref", "")).strip()
        if _is_empty(data_ref):
            add_error("data_embriovet/ref", t("import.error.date_required"))

        palhetas = _parse_int(row.get("existencia_atual"))
        if palhetas is None:
            add_error("existencia_atual", t("import.error.stock_invalid"))
        elif palhetas <= 0:
            add_error("existencia_atual", t("import.error.stock_positive"))

        motilidade = _parse_int(row.get("motilidade"))
        if motilidade is None:
            add_error("motilidade", t("import.error.motility_invalid"))
        elif motilidade < 0 or motilidade > 100:
            add_error("motilidade", t("import.error.motility_range"))

        conc_raw = row.get("concentracao")
        conc_val = None
        if not _is_empty(conc_raw):
            conc_val = _parse_float(conc_raw)
            if conc_val is None:
                add_error("concentracao", t("import.error.concentration_invalid"))

        cont_code = str(row.get("contentor_codigo", "")).strip()
        cont_key = cont_code.upper()
        if _is_empty(cont_code):
            add_error("contentor_codigo", t("import.error.container_required"))
        elif cont_key not in cont_map:
            add_error("contentor_codigo", t("import.error.container_missing"))

        canister = _parse_int(row.get("canister"))
        if canister is None:
            add_error("canister", t("import.error.canister_invalid"))
        elif canister < 1 or canister > 10:
            add_error("canister", t("import.error.canister_range"))

        andar = _parse_int(row.get("andar"))
        if andar is None:
            add_error("andar", t("import.error.floor_invalid"))
        elif andar not in [1, 2]:
            add_error("andar", t("import.error.floor_range"))

        # Optional fields
        dose = str(row.get("dose", "")).strip() if not _is_empty(row.get("dose")) else None
        obs = str(row.get("observacoes", "")).strip() if not _is_empty(row.get("observacoes")) else None
        cert = str(row.get("certificado", "")).strip() if not _is_empty(row.get("certificado")) else None
        qual = str(row.get("qualidade", "")).strip() if not _is_empty(row.get("qualidade")) else None
        cor = str(row.get("cor", "")).strip() if not _is_empty(row.get("cor")) else None

        # Parse date
        data_embriovet = None
        origem_externa = None
        if not _is_empty(data_ref):
            dayfirst = "/" in data_ref or "." in data_ref
            if not dayfirst and "-" in data_ref:
                parts = data_ref.split("-")
                if parts and len(parts[0]) <= 2:
                    dayfirst = True
            parsed = pd.to_datetime(data_ref, errors="coerce", dayfirst=dayfirst)
            if pd.isna(parsed):
                origem_externa = data_ref
            else:
                data_embriovet = parsed.date()

        if idx not in errors:
            prop_id = prop_map.get(prop_nome.lower()) if not _is_empty(prop_nome) else None
            valid_rows.append({
                "linha": row_num,
                "garanhao": garanhao,
                "proprietario_nome": prop_nome,
                "prop_id": prop_id,
                "data_embriovet": data_embriovet,
                "origem_externa": origem_externa,
                "existencia_atual": palhetas,
                "dose": dose,
                "motilidade": motilidade,
                "contentor_id": cont_map.get(cont_key) if not _is_empty(cont_code) else None,
                "contentor_codigo": cont_code,
                "canister": canister,
                "andar": andar,
                "observacoes": obs,
                "certificado": cert,
                "qualidade": qual,
                "concentracao": conc_val,
                "cor": cor,
            })

    return errors, pd.DataFrame(errors_list), valid_rows


# ---------------------------------------------------------------------------
# Import execution
# ---------------------------------------------------------------------------

def _executar_importacao(linhas):
    report_rows = []
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            criado_por = st.session_state.get("user", {}).get("username", "importacao")

            for linha in linhas:
                prop_id = linha.get("prop_id")

                # ── Historical date adjustment ──────────────────────────────
                # data_criacao = Jan 1st of the document's year (not import date)
                data_embriovet = linha.get("data_embriovet")
                if data_embriovet and hasattr(data_embriovet, "year"):
                    data_criacao = datetime.date(data_embriovet.year, 1, 1)
                    date_note = f"data_criacao ajustada para {data_criacao} (1 jan {data_embriovet.year})"
                else:
                    data_criacao = datetime.date.today()
                    date_note = ""

                cur.execute(
                    """
                    INSERT INTO estoque_dono (
                        garanhao, dono_id, data_embriovet, origem_externa,
                        palhetas_produzidas, qualidade, concentracao, motilidade,
                        certificado, dose, observacoes,
                        quantidade_inicial, existencia_atual,
                        contentor_id, canister, andar, cor,
                        criado_por, data_criacao
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    RETURNING id
                    """,
                    (
                        to_py(linha.get("garanhao")),
                        to_py(prop_id),
                        to_py(data_embriovet),
                        to_py(linha.get("origem_externa")),
                        to_py(linha.get("existencia_atual")),
                        to_py(linha.get("qualidade")),
                        to_py(linha.get("concentracao")),
                        to_py(linha.get("motilidade")),
                        to_py(linha.get("certificado")),
                        to_py(linha.get("dose")),
                        to_py(linha.get("observacoes")),
                        to_py(linha.get("existencia_atual")),
                        to_py(linha.get("existencia_atual")),
                        to_py(linha.get("contentor_id")),
                        to_py(linha.get("canister")),
                        to_py(linha.get("andar")),
                        to_py(linha.get("cor")),
                        to_py(criado_por),
                        to_py(data_criacao),
                    ),
                )
                stock_id = cur.fetchone()[0]
                report_rows.append({
                    "linha": linha.get("linha"),
                    "garanhao": linha.get("garanhao"),
                    "proprietario": linha.get("proprietario_nome"),
                    "palhetas": linha.get("existencia_atual"),
                    "status": "✅ Importado",
                    "stock_id": stock_id,
                    "nota": date_note,
                })

            conn.commit()
            cur.close()

        st.session_state["import_report"] = pd.DataFrame(report_rows)
        st.session_state["import_wiz_step"] = 4
        st.rerun()

    except Exception as e:
        logger.error(f"Erro ao importar: {e}")
        st.error(t("import.failed", error=str(e)))
        if report_rows:
            st.session_state["import_report"] = pd.DataFrame(report_rows)


# ---------------------------------------------------------------------------
# Step 4 — Report
# ---------------------------------------------------------------------------

def _step_report():
    report_df = st.session_state.get("import_report", pd.DataFrame())

    if not report_df.empty:
        n_ok = len(report_df[report_df.get("status", pd.Series()) == "✅ Importado"]) \
               if "status" in report_df.columns else len(report_df)
        st.success(t("import.completed", count=n_ok))

        render_zone_title(t("import.report_zone"), "import-zone-title")
        st.dataframe(report_df, width="stretch", hide_index=True)

        # Check if any date adjustments happened
        adjusted = report_df[report_df.get("nota", pd.Series("")) != ""] if "nota" in report_df.columns else pd.DataFrame()
        if not adjusted.empty:
            st.info(
                t("import.date_adjustment_done", count=len(adjusted))
            )

        st.download_button(
            t("import.download_report"),
            data=report_df.to_csv(index=False).encode("utf-8"),
            file_name="relatorio_importacao.csv",
            mime="text/csv",
            key="report_download",
        )
    else:
        st.info(t("import.no_report"))

    st.divider()
    rc1, rc2 = st.columns(2)
    with rc1:
        if st.button(
            t("import.btn.new_import"),
            key="report_new",
        ):
            for k in [
                "import_wiz_step", "import_file_id", "import_parsed_df",
                "import_row_numbers", "import_entity_actions",
                "import_editor_df", "import_report",
            ]:
                st.session_state.pop(k, None)
            st.rerun()
    with rc2:
        if st.button(
            t("import.btn.view_stock"),
            key="report_view_stock",
            type="primary",
        ):
            st.session_state["aba_selecionada"] = t("menu.stock")
            st.rerun()
