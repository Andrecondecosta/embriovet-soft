"""Página de detalhe de um animal — Resumo, Diário clínico, Historial reprodutivo, Estadias."""

from datetime import date, datetime

import pandas as pd
import streamlit as st

from modules.db import get_connection


# ────────────────────────────────────────────────────────────────────────────
# Helpers de acesso à BD
# ────────────────────────────────────────────────────────────────────────────
def _carregar_animal(animal_id: int) -> dict | None:
    sql = """
        SELECT id, nome, tipo, raca, data_nascimento, numero_registo, dono_id,
               pelagem, altura, peso, pai, mae, avo_paterno, avo_materno,
               chip, observacoes, is_receptora, ativo
        FROM animais
        WHERE id = %s
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (animal_id,))
        row = cur.fetchone()
        if not row:
            cur.close()
            return None
        cols = [d[0] for d in cur.description]
        cur.close()
        return dict(zip(cols, row))


def _atualizar_animal(animal_id: int, dados: dict) -> bool:
    sql = """
        UPDATE animais SET
            nome = %(nome)s,
            tipo = %(tipo)s,
            raca = %(raca)s,
            data_nascimento = %(data_nascimento)s,
            numero_registo = %(numero_registo)s,
            pelagem = %(pelagem)s,
            altura = %(altura)s,
            peso = %(peso)s,
            chip = %(chip)s,
            pai = %(pai)s,
            mae = %(mae)s,
            avo_paterno = %(avo_paterno)s,
            avo_materno = %(avo_materno)s,
            observacoes = %(observacoes)s,
            is_receptora = %(is_receptora)s,
            updated_at = NOW()
        WHERE id = %(id)s
    """
    dados = {**dados, "id": animal_id}
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, dados)
        conn.commit()
        cur.close()
    return True


def _carregar_estadias_do_animal(animal_id: int) -> pd.DataFrame:
    sql = """
        SELECT
            e.tipo_registo,
            e.motivo,
            e.estado,
            e.data_entrada,
            e.data_saida,
            EXTRACT(
                DAY FROM (COALESCE(e.data_saida::timestamp, NOW()) - e.data_entrada)
            )::int AS dias
        FROM estadias e
        WHERE e.animal_id = %s
        ORDER BY e.data_entrada DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=(animal_id,))


# ────────────────────────────────────────────────────────────────────────────
# Helpers de apresentação
# ────────────────────────────────────────────────────────────────────────────
TIPOS_ANIMAL = ["egua", "garanhao", "receptora"]


def _calcular_idade(data_nasc) -> str:
    if not data_nasc:
        return "—"
    if isinstance(data_nasc, datetime):
        data_nasc = data_nasc.date()
    hoje = date.today()
    anos = hoje.year - data_nasc.year - ((hoje.month, hoje.day) < (data_nasc.month, data_nasc.day))
    if anos < 1:
        meses = (hoje.year - data_nasc.year) * 12 + hoje.month - data_nasc.month
        if hoje.day < data_nasc.day:
            meses -= 1
        return f"{max(meses, 0)} meses"
    return f"{anos} ano" + ("s" if anos != 1 else "")


def _campo(label: str, valor) -> None:
    """Renderiza um par label/valor em formato compacto."""
    txt = "—" if valor is None or (isinstance(valor, str) and not valor.strip()) else str(valor)
    st.markdown(
        f"<div style='margin-bottom:8px;'>"
        f"<div style='font-size:.7rem;color:#94a3b8;text-transform:uppercase;"
        f"letter-spacing:.5px;font-weight:600;'>{label}</div>"
        f"<div style='font-size:.95rem;color:#0f172a;font-weight:500;'>{txt}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ────────────────────────────────────────────────────────────────────────────
# Tab Resumo + form de edição
# ────────────────────────────────────────────────────────────────────────────
def _render_form_editar(animal: dict) -> None:
    with st.form(f"form_editar_animal_{animal['id']}"):
        st.markdown("#### Editar ficha")

        c1, c2 = st.columns(2)
        with c1:
            nome = st.text_input("Nome", value=animal.get("nome") or "")
            tipo_idx = TIPOS_ANIMAL.index(animal.get("tipo")) if animal.get("tipo") in TIPOS_ANIMAL else 0
            tipo = st.selectbox("Tipo", options=TIPOS_ANIMAL, index=tipo_idx)
            raca = st.text_input("Raça", value=animal.get("raca") or "")
            pelagem = st.text_input("Pelagem", value=animal.get("pelagem") or "")
            altura = st.number_input(
                "Altura (cm)", min_value=0.0, max_value=999.9, step=0.1,
                value=float(animal.get("altura") or 0),
            )
            peso = st.number_input(
                "Peso (kg)", min_value=0.0, max_value=99999.9, step=0.1,
                value=float(animal.get("peso") or 0),
            )
        with c2:
            chip = st.text_input("Chip", value=animal.get("chip") or "")
            numero_registo = st.text_input("Número de registo", value=animal.get("numero_registo") or "")
            data_nascimento = st.date_input(
                "Data de nascimento",
                value=animal.get("data_nascimento") or None,
            )
            is_receptora = st.checkbox("É receptora", value=bool(animal.get("is_receptora")))

        st.markdown("##### Pedigree")
        c3, c4 = st.columns(2)
        with c3:
            pai = st.text_input("Pai", value=animal.get("pai") or "")
            avo_paterno = st.text_input("Avô paterno", value=animal.get("avo_paterno") or "")
        with c4:
            mae = st.text_input("Mãe", value=animal.get("mae") or "")
            avo_materno = st.text_input("Avô materno", value=animal.get("avo_materno") or "")

        observacoes = st.text_area("Observações", value=animal.get("observacoes") or "")

        bcol1, bcol2 = st.columns(2)
        with bcol1:
            guardar = st.form_submit_button("Guardar alterações", type="primary", width="stretch")
        with bcol2:
            cancelar = st.form_submit_button("Cancelar", width="stretch")

        if cancelar:
            st.session_state[f"animal_edit_{animal['id']}"] = False
            st.rerun()

        if guardar:
            if not nome.strip():
                st.error("O nome é obrigatório.")
                return
            try:
                _atualizar_animal(animal["id"], {
                    "nome": nome.strip(),
                    "tipo": tipo,
                    "raca": raca.strip() or None,
                    "data_nascimento": data_nascimento,
                    "numero_registo": numero_registo.strip() or None,
                    "pelagem": pelagem.strip() or None,
                    "altura": float(altura) if altura else None,
                    "peso": float(peso) if peso else None,
                    "chip": chip.strip() or None,
                    "pai": pai.strip() or None,
                    "mae": mae.strip() or None,
                    "avo_paterno": avo_paterno.strip() or None,
                    "avo_materno": avo_materno.strip() or None,
                    "observacoes": observacoes.strip() or None,
                    "is_receptora": bool(is_receptora),
                })
                st.success("Ficha atualizada.")
                st.session_state[f"animal_edit_{animal['id']}"] = False
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao atualizar: {e}")


def _render_tab_resumo(animal: dict) -> None:
    edit_key = f"animal_edit_{animal['id']}"

    if st.session_state.get(edit_key, False):
        _render_form_editar(animal)
        return

    # Cabeçalho com botão de edição
    col_head, col_btn = st.columns([4, 1])
    with col_btn:
        if st.button("Editar ficha", key=f"btn_edit_{animal['id']}", type="primary", width="stretch"):
            st.session_state[edit_key] = True
            st.rerun()

    # Grupo Identificação
    st.markdown("#### Identificação")
    g1, g2, g3 = st.columns(3)
    with g1:
        _campo("Nome", animal.get("nome"))
        _campo("Tipo", animal.get("tipo"))
        _campo("Raça", animal.get("raca"))
    with g2:
        _campo("Pelagem", animal.get("pelagem"))
        altura = animal.get("altura")
        peso = animal.get("peso")
        _campo("Altura (cm)", f"{altura}" if altura is not None else None)
        _campo("Peso (kg)", f"{peso}" if peso is not None else None)
    with g3:
        _campo("Chip", animal.get("chip"))
        _campo("Número de registo", animal.get("numero_registo"))
        dn = animal.get("data_nascimento")
        dn_txt = dn.strftime("%d/%m/%Y") if dn else "—"
        _campo("Data nascimento", f"{dn_txt} ({_calcular_idade(dn)})" if dn else "—")

    st.markdown("---")

    # Grupo Pedigree
    st.markdown("#### Pedigree")
    p1, p2 = st.columns(2)
    with p1:
        _campo("Pai", animal.get("pai"))
        _campo("Avô paterno", animal.get("avo_paterno"))
    with p2:
        _campo("Mãe", animal.get("mae"))
        _campo("Avô materno", animal.get("avo_materno"))


# ────────────────────────────────────────────────────────────────────────────
# Tab Estadias
# ────────────────────────────────────────────────────────────────────────────
def _render_tab_estadias(animal_id: int) -> None:
    df = _carregar_estadias_do_animal(animal_id)
    if df.empty:
        st.info("Sem estadias registadas para este animal.")
        return

    view = df.rename(columns={
        "tipo_registo": "Tipo registo",
        "motivo": "Motivo",
        "estado": "Estado",
        "data_entrada": "Data entrada",
        "data_saida": "Data saída",
        "dias": "Dias",
    })
    st.dataframe(view, width="stretch", hide_index=True)


# ────────────────────────────────────────────────────────────────────────────
# Página principal
# ────────────────────────────────────────────────────────────────────────────
def run_animal_page(animal_id: int, context: dict, tab_inicial: int = 0):
    """Página de detalhe de um animal com 4 tabs."""

    animal = _carregar_animal(animal_id)
    if not animal:
        st.error(f"Animal #{animal_id} não encontrado.")
        return

    st.markdown(f"## {animal.get('nome') or 'Animal sem nome'}")

    nomes_tabs = ["Resumo", "Diário clínico", "Historial reprodutivo", "Estadias"]
    # Honrar tab inicial: o Streamlit não permite seleccionar tab por código,
    # mas guardamos a preferência em session_state para uso futuro.
    st.session_state[f"animal_{animal_id}_tab_inicial"] = tab_inicial

    tab_resumo, tab_clinico, tab_repro, tab_estadias = st.tabs(nomes_tabs)

    with tab_resumo:
        _render_tab_resumo(animal)

    with tab_clinico:
        st.info("Em desenvolvimento — Fase 2")

    with tab_repro:
        st.info("Em desenvolvimento — Fase 2")

    with tab_estadias:
        _render_tab_estadias(animal_id)
