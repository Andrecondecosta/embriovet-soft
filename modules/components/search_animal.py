"""Componente universal de pesquisa de animais.

Uso típico:
    from modules.components.search_animal import render_search_animal

    render_search_animal(
        key="search_animal_main",
        tipo_filter=None,                    # ou "egua" / "garanhao" / "receptora"
        label="Pesquisar animal",
        on_select=lambda aid, nome, prop: st.session_state.update(...),
    )
"""

from __future__ import annotations

from typing import Callable, Optional

import pandas as pd
import streamlit as st

from modules.db import get_connection


# ────────────────────────────────────────────────────────────────────────────
# Acesso à BD
# ────────────────────────────────────────────────────────────────────────────

def _query_animais(termo: str, tipo_filter: Optional[str]) -> pd.DataFrame:
    """Pesquisa por nome (LIKE case-insensitive) com filtro opcional de tipo."""
    sql = """
        SELECT a.id, a.nome, a.tipo, d.nome AS proprietario
        FROM animais a
        LEFT JOIN dono d ON a.dono_id = d.id
        WHERE a.ativo = TRUE
          AND LOWER(a.nome) LIKE LOWER(%s)
    """
    params: list = [f"%{termo.strip()}%"]
    if tipo_filter:
        sql += " AND a.tipo = %s"
        params.append(tipo_filter)
    sql += " ORDER BY LOWER(a.nome) LIMIT 50"
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=tuple(params))


def _query_animais_completos(tipo_filter: Optional[str]) -> pd.DataFrame:
    """Lista completa de animais (para o modal "Todos os animais") incluindo
    raça e estado actual derivado de estadias activas."""
    sql = """
        SELECT
            a.id,
            a.nome,
            a.tipo,
            a.raca,
            d.nome AS proprietario,
            -- estado actual: internado/visitante se houver estadia/visita activa,
            -- caso contrário 'livre'
            COALESCE(
                (
                    SELECT
                        CASE
                            WHEN e.tipo_registo = 'estadia' THEN 'internado'
                            WHEN e.tipo_registo = 'visita'  THEN 'visitante'
                            ELSE 'livre'
                        END
                    FROM estadias e
                    WHERE e.animal_id = a.id
                      AND e.data_saida IS NULL
                    ORDER BY e.data_entrada DESC, e.id DESC
                    LIMIT 1
                ),
                'livre'
            ) AS estado_actual
        FROM animais a
        LEFT JOIN dono d ON a.dono_id = d.id
        WHERE a.ativo = TRUE
    """
    params: tuple = ()
    if tipo_filter:
        sql += " AND a.tipo = %s"
        params = (tipo_filter,)
    sql += " ORDER BY LOWER(a.nome)"
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)


# ────────────────────────────────────────────────────────────────────────────
# Helpers de UI
# ────────────────────────────────────────────────────────────────────────────

def _fmt_animal_option(row: pd.Series) -> str:
    """Sempre 'Nome (Proprietário)'."""
    nome = str(row["nome"]) if pd.notna(row["nome"]) else "—"
    prop = str(row["proprietario"]) if pd.notna(row["proprietario"]) else "—"
    return f"{nome} ({prop})"


def _badge_estado(estado: str) -> str:
    cores = {
        "internado": ("#dc2626", "#fee2e2"),
        "visitante": ("#0891b2", "#cffafe"),
        "livre":     ("#475569", "#f1f5f9"),
    }
    fg, bg = cores.get(estado, cores["livre"])
    return (
        f"<span style='display:inline-block;padding:1px 8px;border-radius:9999px;"
        f"font-size:.68rem;font-weight:700;color:{fg};background:{bg};"
        f"text-transform:uppercase;letter-spacing:.4px;'>{estado}</span>"
    )


# ────────────────────────────────────────────────────────────────────────────
# Modal "Todos os animais"
# ────────────────────────────────────────────────────────────────────────────

def _render_modal_todos_animais(
    key: str,
    tipo_filter: Optional[str],
    on_select: Optional[Callable[[int, str, Optional[str]], None]],
) -> None:
    @st.dialog("Todos os animais", width="large")
    def _modal() -> None:
        df = _query_animais_completos(tipo_filter)

        if df.empty:
            st.info("Sem animais registados.")
            return

        # Tabs por tipo (respeita tipo_filter se definido)
        if tipo_filter:
            tabs = [tipo_filter]
            tab_objs = st.tabs([tipo_filter.capitalize()])
        else:
            tabs = ["todos", "egua", "garanhao", "receptora"]
            tab_objs = st.tabs(["Todos", "Éguas", "Garanhões", "Receptoras"])

        for i, t in enumerate(tabs):
            sub = df if t == "todos" else df[df["tipo"] == t]
            with tab_objs[i]:
                if sub.empty:
                    st.caption("Sem registos nesta categoria.")
                    continue

                # Cabeçalho
                col_w = [2.4, 2.0, 1.4, 1.2, 1.0]
                heads = ["Animal", "Proprietário", "Raça", "Estado", ""]
                head_cols = st.columns(col_w)
                for j, h in enumerate(heads):
                    head_cols[j].markdown(
                        f"<div style='font-size:.7rem;color:#94a3b8;"
                        f"text-transform:uppercase;letter-spacing:.5px;"
                        f"font-weight:700;'>{h}</div>",
                        unsafe_allow_html=True,
                    )
                st.markdown(
                    "<hr style='border:none;border-top:1px solid #e2e8f0;"
                    "margin:4px 0 6px;'>",
                    unsafe_allow_html=True,
                )

                for _, row in sub.iterrows():
                    cols = st.columns(col_w)
                    cols[0].write(row["nome"] or "—")
                    cols[1].write(
                        f"({row['proprietario']})" if pd.notna(row["proprietario"])
                        else "(—)"
                    )
                    cols[2].write(row["raca"] if pd.notna(row["raca"]) else "—")
                    cols[3].markdown(
                        _badge_estado(row["estado_actual"] or "livre"),
                        unsafe_allow_html=True,
                    )
                    if cols[4].button(
                        "Escolher",
                        key=f"{key}_pick_{int(row['id'])}_{t}",
                        width="stretch",
                    ):
                        if on_select is not None:
                            try:
                                on_select(
                                    int(row["id"]),
                                    str(row["nome"]) if pd.notna(row["nome"]) else "",
                                    str(row["proprietario"])
                                    if pd.notna(row["proprietario"]) else None,
                                )
                            except Exception as exc:  # pragma: no cover
                                st.warning(f"Selecção feita, mas callback falhou: {exc}")
                        st.rerun()

    _modal()


# ────────────────────────────────────────────────────────────────────────────
# Componente principal
# ────────────────────────────────────────────────────────────────────────────

def render_search_animal(
    key: str,
    tipo_filter: Optional[str] = None,
    label: str = "Pesquisar animal",
    on_select: Optional[Callable[[int, str, Optional[str]], None]] = None,
) -> Optional[dict]:
    """Componente universal de pesquisa de animais.

    Devolve o animal seleccionado como `{"id", "nome", "proprietario"}` ou
    `None` se nenhum estiver seleccionado. Adicionalmente, se `on_select`
    estiver definido, é invocado quando o utilizador escolhe um animal.

    Parâmetros
    ----------
    key : str
        Prefixo único para os widgets (necessário se o componente for usado
        em vários sítios na mesma página).
    tipo_filter : Optional[str]
        Restringe à `egua` / `garanhao` / `receptora`. `None` = todos os tipos.
    label : str
        Etiqueta do `text_input`.
    on_select : Optional[Callable[[int, str, Optional[str]], None]]
        Callback `(animal_id, animal_nome, proprietario_nome)` invocado ao
        seleccionar um animal (via auto-pick, selectbox ou modal).
    """

    # Estado: lista todos / dispatch de modal
    open_modal_flag = f"{key}_open_modal"
    if st.session_state.get(open_modal_flag):
        del st.session_state[open_modal_flag]
        _render_modal_todos_animais(key, tipo_filter, on_select)

    # Linha: text_input + botão 📋
    col_in, col_btn = st.columns([6, 1])
    with col_in:
        termo = st.text_input(
            label,
            key=f"{key}_termo",
            placeholder="Escreva pelo menos 2 caracteres…",
            label_visibility="visible",
        )
    with col_btn:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if st.button(
            "📋",
            key=f"{key}_btn_lista",
            help="Ver todos os animais",
            width="stretch",
        ):
            st.session_state[open_modal_flag] = True
            st.rerun()

    termo_clean = (termo or "").strip()
    if len(termo_clean) < 2:
        return _animal_seleccionado(key)

    # Pesquisa
    df = _query_animais(termo_clean, tipo_filter)

    if df.empty:
        st.caption(f"Sem resultados para “{termo_clean}”.")
        return _animal_seleccionado(key)

    # Auto-selecção quando há um único resultado
    if len(df) == 1:
        row = df.iloc[0]
        sel = {
            "id": int(row["id"]),
            "nome": str(row["nome"]),
            "proprietario": (
                str(row["proprietario"]) if pd.notna(row["proprietario"]) else None
            ),
        }
        st.session_state[f"{key}_selected"] = sel
        st.success(f"Selecionado automaticamente: **{_fmt_animal_option(row)}**")
        if on_select is not None and st.session_state.get(f"{key}_last_auto") != sel["id"]:
            st.session_state[f"{key}_last_auto"] = sel["id"]
            try:
                on_select(sel["id"], sel["nome"], sel["proprietario"])
            except Exception as exc:  # pragma: no cover
                st.warning(f"Selecção feita, mas callback falhou: {exc}")
        return sel

    # Selectbox com múltiplos resultados — formato "Nome (Proprietário)"
    opcoes = [None] + df["id"].tolist()

    def _fmt(idx: Optional[int]) -> str:
        if idx is None:
            return "— Selecionar animal —"
        row = df.loc[df["id"] == idx]
        if row.empty:
            return f"#{idx}"
        return _fmt_animal_option(row.iloc[0])

    selected_id = st.selectbox(
        "Resultados",
        opcoes,
        format_func=_fmt,
        key=f"{key}_select",
    )

    if selected_id is not None:
        row = df.loc[df["id"] == selected_id].iloc[0]
        sel = {
            "id": int(row["id"]),
            "nome": str(row["nome"]),
            "proprietario": (
                str(row["proprietario"]) if pd.notna(row["proprietario"]) else None
            ),
        }
        st.session_state[f"{key}_selected"] = sel
        if on_select is not None and st.session_state.get(f"{key}_last_pick") != sel["id"]:
            st.session_state[f"{key}_last_pick"] = sel["id"]
            try:
                on_select(sel["id"], sel["nome"], sel["proprietario"])
            except Exception as exc:  # pragma: no cover
                st.warning(f"Selecção feita, mas callback falhou: {exc}")
        return sel

    return _animal_seleccionado(key)


def _animal_seleccionado(key: str) -> Optional[dict]:
    return st.session_state.get(f"{key}_selected")
