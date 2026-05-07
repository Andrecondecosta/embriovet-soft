"""Página de Estadias e Visitas — gestão de internamentos e visitas dos animais."""

from datetime import date

import pandas as pd
import streamlit as st

from modules.db import get_connection


# ────────────────────────────────────────────────────────────────────────────
# Helpers de acesso à BD
# ────────────────────────────────────────────────────────────────────────────
def _carregar_estadias(apenas_activas: bool) -> pd.DataFrame:
    """Carrega estadias activas (data_saida IS NULL) ou encerradas."""
    where = "e.data_saida IS NULL" if apenas_activas else "e.data_saida IS NOT NULL"
    sql = f"""
        SELECT
            e.id,
            a.nome                                       AS animal,
            e.tipo_registo                               AS tipo,
            d.nome                                       AS proprietario,
            e.motivo,
            e.estado,
            e.data_entrada,
            e.data_saida,
            EXTRACT(DAY FROM (NOW() - e.data_entrada))::int AS dias_internado
        FROM estadias e
        JOIN animais a ON a.id = e.animal_id
        JOIN dono    d ON d.id = e.dono_id
        WHERE {where}
        ORDER BY e.data_entrada DESC, e.id DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn)


def _pesquisar_animais(termo: str) -> pd.DataFrame:
    """Devolve animais cujo nome contém o termo (case-insensitive)."""
    if not termo or not termo.strip():
        return pd.DataFrame(columns=["id", "nome", "tipo"])
    sql = """
        SELECT id, nome, tipo
        FROM animais
        WHERE ativo = TRUE AND LOWER(nome) LIKE LOWER(%s)
        ORDER BY nome
        LIMIT 30
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=(f"%{termo.strip()}%",))


def _carregar_donos_ativos() -> pd.DataFrame:
    sql = "SELECT id, nome FROM dono WHERE ativo = TRUE ORDER BY nome"
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn)


def _carregar_alojamentos_ativos() -> pd.DataFrame:
    sql = "SELECT id, nome, tipo, capacidade FROM alojamentos WHERE ativo = TRUE ORDER BY tipo, nome"
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn)


def _criar_estadia(dados: dict) -> int | None:
    """Insere nova estadia e devolve o id criado."""
    sql = """
        INSERT INTO estadias (
            tipo_registo, animal_id, alojamento_id, dono_id,
            data_entrada, motivo, estado, criado_por
        ) VALUES (%(tipo_registo)s, %(animal_id)s, %(alojamento_id)s, %(dono_id)s,
                  %(data_entrada)s, %(motivo)s, %(estado)s, %(criado_por)s)
        RETURNING id
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, dados)
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        return new_id


# ────────────────────────────────────────────────────────────────────────────
# Modal: nova estadia / visita
# ────────────────────────────────────────────────────────────────────────────
MOTIVOS = ["inseminacao", "colheita", "diagnostico", "tratamento", "embriao"]
TIPOS_REGISTO = ["estadia", "visita"]


def _render_modal_nova_estadia():
    st.markdown("### + Nova estadia / visita")

    # Pesquisa de animal — fora do form para reagir a cada keystroke
    termo = st.text_input(
        "Pesquisar animal por nome",
        key="estadia_pesquisa_animal",
        placeholder="Escreva o nome do animal…",
    )
    animais_df = _pesquisar_animais(termo)

    if termo and animais_df.empty:
        st.warning("Sem animais activos com esse nome.")

    animal_options = (
        {f"{r['nome']} ({r['tipo']})": int(r["id"]) for _, r in animais_df.iterrows()}
        if not animais_df.empty else {}
    )
    animal_label = st.selectbox(
        "Animal",
        options=list(animal_options.keys()) if animal_options else ["—"],
        key="estadia_animal_select",
        disabled=not animal_options,
    )
    animal_id = animal_options.get(animal_label) if animal_options else None

    donos_df = _carregar_donos_ativos()
    aloj_df = _carregar_alojamentos_ativos()

    with st.form("form_nova_estadia", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            tipo_registo = st.selectbox(
                "Tipo de registo",
                options=TIPOS_REGISTO,
                key="estadia_tipo_registo",
            )
        with col2:
            motivo = st.selectbox(
                "Motivo",
                options=MOTIVOS,
                key="estadia_motivo",
            )

        col3, col4 = st.columns(2)
        with col3:
            dono_options = (
                {r["nome"]: int(r["id"]) for _, r in donos_df.iterrows()}
                if not donos_df.empty else {}
            )
            dono_label = st.selectbox(
                "Proprietário",
                options=list(dono_options.keys()) if dono_options else ["—"],
                key="estadia_dono",
                disabled=not dono_options,
            )
            dono_id = dono_options.get(dono_label) if dono_options else None

        with col4:
            data_entrada = st.date_input(
                "Data de entrada",
                value=date.today(),
                key="estadia_data_entrada",
            )

        aloj_options = (
            {f"{r['tipo']} — {r['nome']}": int(r["id"]) for _, r in aloj_df.iterrows()}
            if not aloj_df.empty else {}
        )
        aloj_label = st.selectbox(
            "Alojamento" + (" *" if tipo_registo == "estadia" else " (opcional)"),
            options=["—"] + list(aloj_options.keys()),
            key="estadia_alojamento",
        )
        alojamento_id = aloj_options.get(aloj_label) if aloj_label != "—" else None

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            submit = st.form_submit_button("Guardar", type="primary", width="stretch")
        with col_btn2:
            cancelar = st.form_submit_button("Cancelar", width="stretch")

        if cancelar:
            st.session_state["modal_nova_estadia"] = False
            st.rerun()

        if submit:
            erros = []
            if animal_id is None:
                erros.append("Selecciona um animal.")
            if dono_id is None:
                erros.append("Selecciona um proprietário.")
            if tipo_registo == "estadia" and alojamento_id is None:
                erros.append("Estadias exigem alojamento.")

            if erros:
                for e in erros:
                    st.error(e)
                return

            estado_inicial = "internado" if tipo_registo == "estadia" else "visitante"
            criado_por = (st.session_state.get("user") or {}).get("username") or ""

            novo_id = _criar_estadia({
                "tipo_registo": tipo_registo,
                "animal_id": animal_id,
                "alojamento_id": alojamento_id,
                "dono_id": dono_id,
                "data_entrada": data_entrada,
                "motivo": motivo,
                "estado": estado_inicial,
                "criado_por": criado_por[:50],
            })

            if novo_id:
                st.success(f"Registo criado (#{novo_id}).")
                st.session_state["modal_nova_estadia"] = False
                st.rerun()


# ────────────────────────────────────────────────────────────────────────────
# Página principal
# ────────────────────────────────────────────────────────────────────────────
def run_estadias_page(context: dict):
    """Página de Estadias e Visitas."""

    # Cabeçalho com botão à direita
    col_title, col_btn = st.columns([4, 1])
    with col_title:
        st.markdown("## Estadias e Visitas")
    with col_btn:
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        if st.button("+ Nova estadia / visita", type="primary", width="stretch"):
            st.session_state["modal_nova_estadia"] = True
            st.rerun()

    # Modal
    if st.session_state.get("modal_nova_estadia", False):
        with st.container(border=True):
            _render_modal_nova_estadia()
        st.markdown("---")

    # Tabs
    tab_activas, tab_encerradas, tab_calendario = st.tabs(
        ["Activas", "Encerradas", "Calendário"]
    )

    with tab_activas:
        df = _carregar_estadias(apenas_activas=True)
        if df.empty:
            st.info("Sem estadias ou visitas activas.")
        else:
            view = df[[
                "animal", "tipo", "proprietario", "motivo", "estado", "dias_internado"
            ]].rename(columns={
                "animal": "Animal",
                "tipo": "Tipo",
                "proprietario": "Proprietário",
                "motivo": "Motivo",
                "estado": "Estado",
                "dias_internado": "Dias internado",
            })
            st.dataframe(view, width="stretch", hide_index=True)

    with tab_encerradas:
        df = _carregar_estadias(apenas_activas=False)
        if df.empty:
            st.info("Sem estadias encerradas.")
        else:
            view = df[[
                "animal", "tipo", "proprietario", "motivo", "estado", "dias_internado", "data_saida"
            ]].rename(columns={
                "animal": "Animal",
                "tipo": "Tipo",
                "proprietario": "Proprietário",
                "motivo": "Motivo",
                "estado": "Estado",
                "dias_internado": "Dias internado",
                "data_saida": "Data saída",
            })
            st.dataframe(view, width="stretch", hide_index=True)

    with tab_calendario:
        st.info("Em desenvolvimento")
