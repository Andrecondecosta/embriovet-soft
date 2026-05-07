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


def _criar_animal(dados: dict) -> int | None:
    """Insere novo animal e devolve o id criado."""
    sql = """
        INSERT INTO animais (nome, tipo, raca, data_nascimento, numero_registo, dono_id)
        VALUES (%(nome)s, %(tipo)s, %(raca)s, %(data_nascimento)s, %(numero_registo)s, %(dono_id)s)
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
TIPOS_ANIMAL = ["egua", "garanhao", "receptora"]


def _render_modal_nova_estadia():
    st.markdown("### + Nova estadia / visita")

    # Pesquisa de animal — fora do form para reagir a cada keystroke
    termo = st.text_input(
        "Pesquisar animal por nome",
        key="estadia_pesquisa_animal",
        placeholder="Escreva o nome do animal…",
    )
    animais_df = _pesquisar_animais(termo)

    # Sinaliza se vamos criar animal novo (termo escrito mas sem matches)
    criar_novo_animal = bool(termo and termo.strip()) and animais_df.empty
    if criar_novo_animal:
        st.info(
            f"Não existe nenhum animal chamado “{termo.strip()}”. "
            "Preencha os dados abaixo para o criar automaticamente ao guardar."
        )

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
        # ── Campos extra para criar animal novo (apenas se necessário) ──
        novo_animal_tipo = None
        novo_animal_raca = None
        novo_animal_data_nasc = None
        novo_animal_num_reg = None
        if criar_novo_animal:
            st.markdown("#### Novo animal")
            cna1, cna2 = st.columns(2)
            with cna1:
                novo_animal_tipo = st.selectbox(
                    "Tipo *",
                    options=TIPOS_ANIMAL,
                    key="estadia_novo_animal_tipo",
                )
                novo_animal_raca = st.text_input(
                    "Raça (opcional)",
                    key="estadia_novo_animal_raca",
                )
            with cna2:
                novo_animal_data_nasc = st.date_input(
                    "Data de nascimento (opcional)",
                    value=None,
                    key="estadia_novo_animal_data_nasc",
                )
                novo_animal_num_reg = st.text_input(
                    "Número de registo (opcional)",
                    key="estadia_novo_animal_num_reg",
                )
            st.markdown("---")

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
            if not criar_novo_animal and animal_id is None:
                erros.append("Selecciona um animal (ou escreva um nome novo para o criar).")
            if criar_novo_animal and not novo_animal_tipo:
                erros.append("Indica o tipo do novo animal.")
            if dono_id is None:
                erros.append("Selecciona um proprietário.")
            if tipo_registo == "estadia" and alojamento_id is None:
                erros.append("Estadias exigem alojamento.")

            if erros:
                for e in erros:
                    st.error(e)
                return

            # Se for animal novo, cria-o primeiro e usa o id devolvido
            if criar_novo_animal:
                try:
                    animal_id = _criar_animal({
                        "nome": termo.strip(),
                        "tipo": novo_animal_tipo,
                        "raca": (novo_animal_raca or None),
                        "data_nascimento": novo_animal_data_nasc,
                        "numero_registo": (novo_animal_num_reg or None),
                        "dono_id": dono_id,
                    })
                except Exception as e:
                    st.error(f"Erro ao criar animal: {e}")
                    return
                if not animal_id:
                    st.error("Não foi possível criar o animal.")
                    return
                st.toast(f"Animal '{termo.strip()}' criado.", icon="✅")

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
        _render_lista_estadias(df, apenas_activas=True, key_prefix="act")

    with tab_encerradas:
        df = _carregar_estadias(apenas_activas=False)
        _render_lista_estadias(df, apenas_activas=False, key_prefix="enc")

    with tab_calendario:
        st.info("Em desenvolvimento")
