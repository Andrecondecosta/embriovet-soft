"""Página de Estadias e Visitas — gestão de internamentos e visitas dos animais."""

import pandas as pd
import streamlit as st

from modules.components.modal_animal import render_modal_animal
from modules.components.modal_proprietario import render_modal_proprietario
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
            e.animal_id,
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


# ────────────────────────────────────────────────────────────────────────────
# Página principal
# ────────────────────────────────────────────────────────────────────────────
def _render_lista_estadias(df: pd.DataFrame, apenas_activas: bool, key_prefix: str) -> None:
    """Renderiza a lista de estadias com botão 'Ver ficha' em cada linha."""
    if df.empty:
        st.info(
            "Sem estadias ou visitas activas." if apenas_activas
            else "Sem estadias encerradas."
        )
        return

    # Cabeçalho da tabela
    if apenas_activas:
        col_w = [2, 1, 2, 1.5, 1.4, 1.2, 1.3]
        headers = ["Animal", "Tipo", "Proprietário", "Motivo", "Estado", "Dias", ""]
    else:
        col_w = [1.8, 1, 1.8, 1.4, 1.3, 1, 1.2, 1.2]
        headers = ["Animal", "Tipo", "Proprietário", "Motivo", "Estado", "Dias", "Data saída", ""]

    head_cols = st.columns(col_w)
    for i, h in enumerate(headers):
        head_cols[i].markdown(
            f"<div style='font-size:.7rem;color:#94a3b8;text-transform:uppercase;"
            f"letter-spacing:.5px;font-weight:700;'>{h}</div>",
            unsafe_allow_html=True,
        )
    st.markdown(
        "<hr style='border:none;border-top:1px solid #e2e8f0;margin:4px 0 8px;'>",
        unsafe_allow_html=True,
    )

    for _, row in df.iterrows():
        cols = st.columns(col_w)
        cols[0].write(row["animal"])
        cols[1].write(row["tipo"])
        cols[2].write(row["proprietario"])
        cols[3].write(row["motivo"])
        cols[4].write(row["estado"])
        cols[5].write(str(int(row["dias_internado"])) if pd.notna(row["dias_internado"]) else "—")

        if apenas_activas:
            btn_col = cols[6]
        else:
            data_saida = row.get("data_saida")
            cols[6].write(data_saida.strftime("%d/%m/%Y") if pd.notna(data_saida) else "—")
            btn_col = cols[7]

        with btn_col:
            if st.button(
                "Ver ficha",
                key=f"{key_prefix}_ver_{int(row['id'])}",
                width="stretch",
            ):
                st.session_state["ver_animal_id"] = int(row["animal_id"])
                st.session_state["ver_animal_tab"] = 0
                st.rerun()


def run_estadias_page(context: dict):
    """Página de Estadias e Visitas."""

    # ── Orquestração do "wizard" de criação de animal + proprietário ────────
    # (Workaround para a limitação do Streamlit: não permite diálogos
    # aninhados — usamos session_state como fila para abrir/reabrir os
    # modais em reruns sucessivos.)
    if st.session_state.get("abrir_modal_prop_standalone"):
        del st.session_state["abrir_modal_prop_standalone"]
        render_modal_proprietario(
            key="modal_prop_standalone",
            on_success=lambda dono_id, dono_nome: (
                st.session_state.update({
                    "novo_prop_id": dono_id,
                    "novo_prop_nome": dono_nome,
                    "reabrir_modal_animal": True,
                }),
                st.rerun(),
            ),
        )

    if st.session_state.get("reabrir_modal_animal"):
        del st.session_state["reabrir_modal_animal"]
        render_modal_animal(
            key="modal_nova_estadia",
            tipo_default="egua",
            on_success=lambda animal_id, animal_nome, estadia_id: (
                st.session_state.update({
                    "ultima_estadia_criada": estadia_id,
                    "ultimo_animal_criado": animal_id,
                }),
                st.rerun(),
            ),
        )

    # ── Drill-down para ficha do animal ─────────────────────────────────────
    if st.session_state.get("ver_animal_id") is not None:
        if st.button("← Voltar às estadias", key="btn_voltar_estadias"):
            st.session_state.pop("ver_animal_id", None)
            st.session_state.pop("ver_animal_tab", None)
            st.rerun()
        from modules.pages.animal_page import run_animal_page
        run_animal_page(
            st.session_state["ver_animal_id"],
            context,
            st.session_state.get("ver_animal_tab", 0),
        )
        return

    # Cabeçalho com botão à direita
    col_title, col_btn = st.columns([4, 1])
    with col_title:
        st.markdown("## Estadias e Visitas")
    with col_btn:
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        if st.button("+ Nova estadia / visita", type="primary", width="stretch"):
            render_modal_animal(
                key="modal_nova_estadia",
                tipo_default="egua",
                on_success=lambda animal_id, animal_nome, estadia_id: (
                    st.session_state.update({
                        "ultima_estadia_criada": estadia_id,
                        "ultimo_animal_criado": animal_id,
                    }),
                    st.rerun(),
                ),
            )

    # Tabs
    tab_activas, tab_encerradas, tab_calendario = st.tabs(
        ["Activas", "Encerradas", "Calendário"]
    )

    with tab_activas:
        df = _carregar_estadias(apenas_activas=True)
        _render_lista_estadias(df, apenas_activas=True, key_prefix="act")

    with tab_encerradas:
        df = _carregar_estadias(apenas_activas=False)
        _render_lista_estadias(df, apenas_activas=False, key_prefix="enc")

    with tab_calendario:
        st.info("Em desenvolvimento")
