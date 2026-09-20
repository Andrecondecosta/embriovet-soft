"""Página de Estadias e Visitas — gestão de internamentos e visitas dos animais.

Separadores (redesenho): "Internadas agora" (lista densa das estadias
em aberto), "Movimentos da semana" (quem entra/sai nos próximos 7
dias — substitui o antigo calendário de grelha) e "Histórico" (todas
as passagens de um mês seleccionável, incluindo as já encerradas).

Os dois diálogos ("Nova estadia / visita" e "Registar saída") e a
lógica de dados (carregar/gravar estadias) mantêm-se inalterados —
só a apresentação e a organização dos separadores mudou.
"""

import calendar as _calendar
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from modules.components.modal_animal import render_modal_animal
from modules.components.modal_proprietario import render_modal_proprietario
from modules.components.search_animal import render_search_animal
from modules.db import get_connection
from modules.ui_kit import inject_design_tokens, render_kpi_row, render_zone_title


# ────────────────────────────────────────────────────────────────────────────
# Constantes
# ────────────────────────────────────────────────────────────────────────────
TIPOS_REGISTO = ["estadia", "visita", "externo"]
MOTIVOS = ["inseminacao", "colheita", "diagnostico", "tratamento", "embriao"]

MOTIVO_LABELS = {
    "inseminacao": "Inseminação",
    "colheita": "Colheita",
    "diagnostico": "Diagnóstico",
    "tratamento": "Tratamento",
    "embriao": "Embrião",
}
TIPO_REGISTO_LABELS = {
    "estadia": "Estadia",
    "visita": "Visita",
    "externo": "Externo",
}
ESTADO_LABELS = {
    "internado": "Internado",
    "visitante": "Visitante",
    "gestante": "Gestante",
    "alta": "Alta",
    "sem_resultado": "Outro",
    "transferido": "Transferido",
    "externo": "Externo",
}
MESES_PT = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

# Estados finais permitidos ao registar a saída de uma estadia.
ESTADOS_SAIDA = ["gestante", "alta", "sem_resultado", "transferido"]

# Janela de "esta semana" usada no separador Movimentos — 7 dias,
# hoje incluído.
_JANELA_MOVIMENTOS_DIAS = 6


def _label_motivo(m: str | None) -> str:
    return MOTIVO_LABELS.get(m or "", (m or "—").capitalize())


def _label_tipo_registo(t: str | None) -> str:
    return TIPO_REGISTO_LABELS.get(t or "", (t or "—").capitalize())


def _label_estado(e: str | None) -> str:
    return ESTADO_LABELS.get(e or "", (e or "—").capitalize())


def _ensure_saida_constraints() -> None:
    """Garante que `estadias.estado` aceita os estados de saída (incl. 'transferido').

    Idempotente. Mantemos os estados existentes (`internado`, `visitante`,
    `gestante`, `alta`, `sem_resultado`, `externo`) e acrescentamos
    `transferido`.
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "ALTER TABLE estadias DROP CONSTRAINT IF EXISTS estadias_estado_check"
            )
            cur.execute("""
                ALTER TABLE estadias
                ADD CONSTRAINT estadias_estado_check
                CHECK (estado IN (
                    'internado', 'visitante', 'gestante',
                    'alta', 'sem_resultado', 'externo', 'transferido'
                ))
            """)
            cur.execute("""
                ALTER TABLE estadias
                ADD COLUMN IF NOT EXISTS observacoes_saida TEXT
            """)
            conn.commit()
            cur.close()
    except Exception:
        pass


def _registar_saida_estadia(
    estadia_id: int, data_saida, estado_final: str, observacoes: str | None,
) -> None:
    sql = """
        UPDATE estadias
           SET data_saida = %s,
               estado = %s,
               observacoes_saida = %s
         WHERE id = %s
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            sql,
            (data_saida, estado_final, (observacoes or None), int(estadia_id)),
        )
        conn.commit()
        cur.close()


# ────────────────────────────────────────────────────────────────────────────
# Helpers de acesso à BD
# ────────────────────────────────────────────────────────────────────────────
def _carregar_estadias(where_sql: str, params: tuple = ()) -> pd.DataFrame:
    """Carrega estadias/visitas conforme a cláusula WHERE dada.

    Uma só query, partilhada pelos 4 recortes que a página mostra
    (internadas agora, entram esta semana, saem esta semana, histórico
    do mês) — todos usam os mesmos JOINs e o mesmo cálculo de
    `dias_internado`; só a condição de filtro muda.
    """
    sql = f"""
        SELECT
            e.id,
            e.animal_id,
            a.nome                                        AS animal,
            e.tipo_registo                                AS tipo,
            a.tipo                                         AS animal_tipo,
            d.nome                                         AS proprietario,
            e.motivo,
            e.estado,
            e.data_entrada,
            e.data_saida,
            al.nome                                        AS alojamento_nome,
            EXTRACT(DAY FROM (NOW() - e.data_entrada))::int AS dias_internado
        FROM estadias e
        JOIN animais a           ON a.id = e.animal_id
        JOIN dono    d           ON d.id = e.dono_id
        LEFT JOIN alojamentos al ON al.id = e.alojamento_id
        WHERE {where_sql}
        ORDER BY e.data_entrada DESC, e.id DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def _carregar_animal_detalhe(animal_id: int) -> dict:
    sql = """
        SELECT a.id, a.nome, a.tipo, a.dono_id, d.nome AS proprietario
        FROM animais a
        LEFT JOIN dono d ON d.id = a.dono_id
        WHERE a.id = %s
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (animal_id,))
        row = cur.fetchone()
        cur.close()
    if not row:
        return {}
    return {
        "id": int(row[0]),
        "nome": row[1],
        "tipo": row[2],
        "dono_id": row[3],
        "proprietario": row[4],
    }


def _carregar_donos() -> pd.DataFrame:
    sql = "SELECT id, nome FROM dono WHERE ativo = TRUE ORDER BY LOWER(nome)"
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn)


def _carregar_alojamentos() -> pd.DataFrame:
    sql = (
        "SELECT id, nome, tipo, capacidade FROM alojamentos "
        "WHERE ativo = TRUE ORDER BY tipo, LOWER(nome)"
    )
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn)


def _has_animais_resultados(termo: str) -> bool:
    """Devolve True se houver pelo menos um animal cujo nome contém `termo`.

    Mantido como utilitário interno; pode ser usado por validações futuras.
    """
    sql = (
        "SELECT 1 FROM animais "
        "WHERE ativo = TRUE AND LOWER(nome) LIKE LOWER(%s) LIMIT 1"
    )
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (f"%{termo.strip()}%",))
        existe = cur.fetchone() is not None
        cur.close()
    return existe


def _ensure_externo_constraints() -> None:
    """Garante que `estadias.estado` e `estadias.tipo_registo` aceitam 'externo'."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "ALTER TABLE estadias DROP CONSTRAINT IF EXISTS estadias_estado_check"
            )
            cur.execute("""
                ALTER TABLE estadias
                ADD CONSTRAINT estadias_estado_check
                CHECK (estado IN (
                    'internado', 'visitante', 'gestante',
                    'alta', 'sem_resultado', 'externo'
                ))
            """)
            cur.execute(
                "ALTER TABLE estadias DROP CONSTRAINT IF EXISTS estadias_tipo_registo_check"
            )
            cur.execute("""
                ALTER TABLE estadias
                ADD CONSTRAINT estadias_tipo_registo_check
                CHECK (tipo_registo IN ('estadia', 'visita', 'externo'))
            """)
            conn.commit()
            cur.close()
    except Exception:
        pass


def _criar_estadia_apenas(payload: dict) -> int:
    """Insere uma nova linha em `estadias` (sem criar animal). Devolve o id.

    Valida primeiro que **não existe já uma estadia aberta** para o
    mesmo animal — a UNIQUE INDEX PARCIAL da migration 029 impede a
    nível de BD, mas validamos aqui em Python para poder mostrar uma
    mensagem amigável (`ValueError`) antes de a exceção de BD ser
    disparada.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        if payload.get("data_saida") is None:
            cur.execute(
                "SELECT id FROM estadias WHERE animal_id = %s "
                "AND data_saida IS NULL LIMIT 1",
                (int(payload["animal_id"]),),
            )
            row = cur.fetchone()
            if row:
                cur.close()
                raise ValueError(
                    "Este animal já tem uma estadia em aberto "
                    f"(id={row[0]}). Feche a existente antes de criar uma nova."
                )
        cur.execute(
            """
        INSERT INTO estadias (
            tipo_registo, animal_id, alojamento_id, dono_id,
            data_entrada, data_saida, motivo, estado,
            observacoes_entrada
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) RETURNING id
        """,
            (
                payload["tipo_registo"],
                int(payload["animal_id"]),
                payload.get("alojamento_id"),
                int(payload["dono_id"]),
                payload["data_entrada"],
                payload.get("data_saida"),
                payload["motivo"],
                payload["estado"],
                payload.get("observacoes_entrada"),
            ),
        )
        new_id = int(cur.fetchone()[0])
        conn.commit()
        cur.close()
    return new_id


# ────────────────────────────────────────────────────────────────────────────
# Helpers do diálogo
# ────────────────────────────────────────────────────────────────────────────
def _on_animal_for_estadia(animal_id: int, animal_nome: str, estadia_id: int) -> None:
    """Callback usado por `render_modal_animal` quando aberto a partir do
    fluxo "+ Nova estadia / visita" → "+ Criar novo animal"."""
    st.session_state.update({
        "animal_criado_para_estadia": {
            "id": int(animal_id),
            "nome": animal_nome,
            "estadia_id": int(estadia_id),
        },
        "reabrir_modal_nova_estadia": True,
    })
    st.rerun()


def _limpar_estado_modal_nova_estadia() -> None:
    """Limpa todo o session_state usado pelo diálogo, para começar limpo na
    próxima abertura."""
    for k in (
        "estadia_animal_search_termo",
        "estadia_animal_search_selected",
        "estadia_animal_search_select",
        "estadia_animal_search_last_pick",
        "estadia_animal_search_last_auto",
        "estadia_animal_search_open_modal",
        "ne_tipo_reg",
        "ne_motivo",
        "ne_dono",
        "ne_dt_ent",
        "ne_aloj",
        "ne_aloj_v",
        "ne_obs",
        "animal_criado_para_estadia",
    ):
        st.session_state.pop(k, None)


# ────────────────────────────────────────────────────────────────────────────
# Diálogo "Nova estadia / visita"
# ────────────────────────────────────────────────────────────────────────────
def _render_modal_nova_estadia() -> None:
    @st.dialog("Nova estadia / visita", width="large")
    def _modal() -> None:
        # Pré-preencher animal se acabámos de regressar do fluxo "+ Criar novo animal"
        recem = st.session_state.pop("animal_criado_para_estadia", None)
        if recem:
            det = _carregar_animal_detalhe(int(recem["id"]))
            st.session_state["estadia_animal_search_selected"] = {
                "id": int(recem["id"]),
                "nome": recem["nome"],
                "proprietario": det.get("proprietario"),
            }
            st.session_state["estadia_animal_search_termo"] = recem["nome"]

        # Antes de renderizar a pesquisa, descarta qualquer selecção stale
        # (ex.: utilizador escreveu novo termo que não devolve o animal já
        # seleccionado) — assim o "+ Criar novo animal" só aparece quando faz
        # mesmo sentido.
        termo_atual = (st.session_state.get("estadia_animal_search_termo") or "").strip()
        sel_atual = st.session_state.get("estadia_animal_search_selected") or {}
        nome_sel = (sel_atual.get("nome") or "").lower()
        if (
            len(termo_atual) >= 2
            and termo_atual.lower() not in nome_sel
        ):
            st.session_state.pop("estadia_animal_search_selected", None)
            st.session_state.pop("estadia_animal_search_last_pick", None)
            st.session_state.pop("estadia_animal_search_last_auto", None)

        # Pesquisa de animal + botão "+" condicional
        col_search, col_plus = st.columns([6, 1])
        with col_search:
            animal = render_search_animal(
                key="estadia_animal_search",
                label="Animal *",
            )

        with col_plus:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            if st.button(
                "➕ Criar",
                key="ne_btn_criar_animal",
                help="Criar novo animal",
                width="stretch",
            ):
                st.session_state["abrir_modal_animal_para_estadia"] = True
                st.rerun()

        if not animal:
            st.caption("Pesquise um animal pelo nome ou crie um novo.")
            return

        det = _carregar_animal_detalhe(int(animal["id"]))

        st.markdown("---")

        # Inicializar defaults dos widgets antes de renderizar (evita avisos)
        if "ne_dt_ent" not in st.session_state:
            st.session_state["ne_dt_ent"] = date.today()

        c1, c2 = st.columns(2)
        with c1:
            tipo_registo = st.selectbox(
                "Tipo de registo",
                TIPOS_REGISTO,
                key="ne_tipo_reg",
                format_func=lambda x: {
                    "estadia": "Estadia — fica internada no centro",
                    "visita": "Visita — vem no dia e vai embora",
                    "externo": "Externo — não vem ao centro / sémen enviado",
                }.get(x, x.capitalize()),
            )
            motivo_label = (
                "Motivo (opcional)"
                if tipo_registo == "externo"
                else "Motivo"
            )
            motivo = st.selectbox(
                motivo_label,
                MOTIVOS,
                key="ne_motivo",
                format_func=lambda x: {
                    "inseminacao": "Inseminação",
                    "colheita": "Colheita",
                    "diagnostico": "Diagnóstico",
                    "tratamento": "Tratamento",
                    "embriao": "Embrião",
                }.get(x, x.capitalize()),
            )

        with c2:
            donos_df = _carregar_donos()
            default_dono_id = det.get("dono_id")
            dono_options = [None] + donos_df["id"].tolist()
            if (
                "ne_dono" not in st.session_state
                and default_dono_id in dono_options
            ):
                st.session_state["ne_dono"] = default_dono_id

            def _fmt_dono(did):
                if did is None:
                    return "— Selecionar proprietário —"
                row = donos_df.loc[donos_df["id"] == did]
                return str(row.iloc[0]["nome"]) if not row.empty else f"#{did}"

            dono_id = st.selectbox(
                "Proprietário *",
                dono_options,
                format_func=_fmt_dono,
                key="ne_dono",
            )

            dt_label = (
                "Data do serviço / envio"
                if tipo_registo == "externo"
                else "Data de entrada"
            )
            data_entrada = st.date_input(
                dt_label, key="ne_dt_ent", format="DD/MM/YYYY",
            )

        # Alojamento — só aparece para estadia (obrigatório) e visita (opcional)
        alojamento_id = None
        if tipo_registo in ("estadia", "visita"):
            alojamentos_df = _carregar_alojamentos()
            if alojamentos_df.empty:
                if tipo_registo == "estadia":
                    st.warning(
                        "Não existem alojamentos activos. Crie um em "
                        "Definições → Alojamentos.",
                    )
            else:
                aloj_options = [None] + alojamentos_df["id"].tolist()

                def _fmt_aloj(aid):
                    if aid is None:
                        return "— Selecionar alojamento —"
                    row = alojamentos_df.loc[alojamentos_df["id"] == aid]
                    if row.empty:
                        return f"#{aid}"
                    r = row.iloc[0]
                    return f"{r['nome']} ({r['tipo']})"

                alojamento_id = st.selectbox(
                    (
                        "Alojamento *"
                        if tipo_registo == "estadia"
                        else "Alojamento (opcional)"
                    ),
                    aloj_options,
                    format_func=_fmt_aloj,
                    key="ne_aloj",
                )

        # Data de saída é registada mais tarde via "Registar saída" — não
        # pertence ao formulário de criação.
        data_saida = None

        observacoes = st.text_area(
            "Observações", key="ne_obs", height=80,
        )

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        b1, b2 = st.columns(2)
        with b1:
            cancelar = st.button(
                "Cancelar", key="ne_btn_cancelar", width="stretch",
            )
        with b2:
            guardar = st.button(
                "Guardar", type="primary", key="ne_btn_guardar", width="stretch",
            )

        if cancelar:
            _limpar_estado_modal_nova_estadia()
            st.rerun()

        if not guardar:
            return

        # Validações
        if not dono_id:
            st.error("Selecione o proprietário.")
            return
        if tipo_registo == "estadia" and not alojamento_id:
            st.error("O alojamento é obrigatório quando o tipo é 'estadia'.")
            return

        if tipo_registo == "externo":
            _ensure_externo_constraints()
            estado = "externo"
        elif tipo_registo == "estadia":
            estado = "internado"
        else:
            estado = "visitante"

        payload = {
            "tipo_registo": tipo_registo,
            "animal_id": int(animal["id"]),
            "alojamento_id": alojamento_id,
            "dono_id": int(dono_id),
            "data_entrada": data_entrada,
            "data_saida": data_saida,
            "motivo": motivo,
            "estado": estado,
            "observacoes_entrada": (observacoes or "").strip() or None,
        }

        try:
            estadia_id = _criar_estadia_apenas(payload)
        except Exception as exc:
            st.error(f"Erro ao guardar: {exc}")
            return

        st.session_state["ultima_estadia_criada"] = estadia_id
        st.session_state["ultimo_animal_criado"] = int(animal["id"])
        _limpar_estado_modal_nova_estadia()
        st.success("Estadia/visita registada.")
        st.rerun()

    _modal()


# ────────────────────────────────────────────────────────────────────────────
# Navegação por mês (Histórico) — mesmo mecanismo que o antigo calendário
# ────────────────────────────────────────────────────────────────────────────
def _target_year_month(offset: int) -> tuple[int, int]:
    today = date.today()
    y, m = today.year, today.month + offset
    while m <= 0:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    return y, m


# ────────────────────────────────────────────────────────────────────────────
# Lista densa — CSS e helpers partilhados pelos 3 separadores
# ────────────────────────────────────────────────────────────────────────────
def _inject_lista_css() -> None:
    """CSS da lista densa — mesma direcção do Trabalho diário (zebra
    subtil, sem cartões, container com scroll interno para aguentar
    centenas de linhas sem esticar a página)."""
    st.markdown(
        """
        <style>
            .ds-list-header {
                font-size: var(--ds-text-xs);
                color: var(--ds-gray-400);
                text-transform: uppercase;
                letter-spacing: .05em;
                font-weight: 700;
            }
            div.st-key-est-list-internadas,
            div.st-key-est-list-historico {
                max-height: calc(100vh - 430px);
                overflow-y: auto;
                padding-right: 4px;
            }
            /* Movimentos — duas listas na mesma vista, por isso mais
               baixas cada (curtas no caso comum; limitadas em altura
               para não estourar a página em bases com muito volume). */
            div.st-key-est-list-entram,
            div.st-key-est-list-saem {
                max-height: 340px;
                overflow-y: auto;
                padding-right: 4px;
            }
            div.st-key-est-list-internadas > div[data-testid="stLayoutWrapper"]:nth-child(even)
                > div[class*="st-key-estrow-"],
            div.st-key-est-list-historico > div[data-testid="stLayoutWrapper"]:nth-child(even)
                > div[class*="st-key-estrow-"],
            div.st-key-est-list-entram > div[data-testid="stLayoutWrapper"]:nth-child(even)
                > div[class*="st-key-estrow-"],
            div.st-key-est-list-saem > div[data-testid="stLayoutWrapper"]:nth-child(even)
                > div[class*="st-key-estrow-"] {
                background: var(--ds-gray-50);
            }
            div[class*="st-key-estrow-"] {
                padding: 4px 6px;
                border-radius: 4px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header_row(col_w: list[float], headers: list[str]) -> None:
    head_cols = st.columns(col_w)
    for i, h in enumerate(headers):
        head_cols[i].markdown(f"<div class='ds-list-header'>{h}</div>", unsafe_allow_html=True)
    st.markdown(
        "<hr style='border:none;border-top:1px solid var(--ds-gray-200);margin:4px 0 8px;'>",
        unsafe_allow_html=True,
    )


def _ir_para_ficha(animal_id: int) -> None:
    st.session_state["ver_animal_id"] = int(animal_id)
    st.session_state["ver_animal_tab"] = 0
    st.rerun()


# ────────────────────────────────────────────────────────────────────────────
# Separador "Internadas agora"
# ────────────────────────────────────────────────────────────────────────────
_ORDEM_INTERNADAS = {
    "Há mais dias": ("dias_internado", False),
    "Nome (A-Z)": ("animal", True),
    "Box": ("alojamento_nome", True),
}


def _render_linha_internada(row: pd.Series, col_w: list[float]) -> None:
    estadia_id = int(row["id"])
    with st.container(key=f"estrow-int-{estadia_id}"):
        cols = st.columns(col_w)
        cols[0].write(row["animal"] or "—")
        cols[1].write(row["proprietario"] or "—")
        cols[2].write(row["alojamento_nome"] or "—")
        cols[3].write(_label_motivo(row["motivo"]))
        dias = row.get("dias_internado")
        cols[4].write(str(max(int(dias), 0)) if pd.notna(dias) else "—")
        with cols[5]:
            # Navegação, não uma ação — discreto (type="tertiary"), para
            # não competir com "Registar saída" (a ação desta linha).
            if st.button(
                "Ver ficha", key=f"int_ver_{estadia_id}",
                type="tertiary", width="stretch",
            ):
                _ir_para_ficha(row["animal_id"])
        with cols[6]:
            # Só "Registar saída" — "Registar inseminação" foi removido
            # daqui de propósito: regista-se na ficha da égua via
            # Trabalho diário, para não duplicar o fluxo.
            if st.button(
                "Registar saída", key=f"int_saida_{estadia_id}",
                type="primary", width="stretch",
            ):
                st.session_state["abrir_modal_saida_id"] = estadia_id
                st.session_state["abrir_modal_saida_animal"] = row["animal"]
                st.rerun()


def _render_tab_internadas() -> None:
    df = _carregar_estadias("e.data_saida IS NULL")

    render_kpi_row([("Internadas", len(df))])
    render_zone_title("Éguas internadas agora", "ds-zone-title ds-zone-title--first")

    if df.empty:
        st.caption("Sem estadias ou visitas activas.")
        return

    ordem_sel = st.selectbox(
        "Ordenar por", list(_ORDEM_INTERNADAS.keys()),
        key="internadas_ordem", label_visibility="collapsed",
    )
    campo, ascendente = _ORDEM_INTERNADAS[ordem_sel]
    df_ordenado = df.sort_values(campo, ascending=ascendente, na_position="last")

    col_w = [2.1, 1.5, 1.3, 1.2, 0.9, 1.1, 1.3]
    _render_header_row(col_w, ["Égua", "Dono", "Box", "Motivo", "Há dias", "", ""])

    with st.container(key="est-list-internadas"):
        for _, row in df_ordenado.iterrows():
            _render_linha_internada(row, col_w)


# ────────────────────────────────────────────────────────────────────────────
# Separador "Movimentos da semana"
# ────────────────────────────────────────────────────────────────────────────
def _render_linha_movimento(
    row: pd.Series, col_w: list[float], campo_data: str, key_prefix: str,
) -> None:
    estadia_id = int(row["id"])
    with st.container(key=f"estrow-{key_prefix}-{estadia_id}"):
        cols = st.columns(col_w)
        cols[0].write(row["animal"] or "—")
        cols[1].write(row["proprietario"] or "—")
        cols[2].write(row["alojamento_nome"] or "—")
        cols[3].write(_label_motivo(row["motivo"]))
        val = row.get(campo_data)
        cols[4].write(val.strftime("%d/%m/%Y") if pd.notna(val) else "—")
        with cols[5]:
            if st.button(
                "Ver ficha", key=f"{key_prefix}_ver_{estadia_id}",
                type="tertiary", width="stretch",
            ):
                _ir_para_ficha(row["animal_id"])


def _render_tab_movimentos() -> None:
    hoje = date.today()
    fim_semana = hoje + timedelta(days=_JANELA_MOVIMENTOS_DIAS)

    df_entram = _carregar_estadias(
        "e.data_entrada BETWEEN %s AND %s", (hoje, fim_semana),
    ).sort_values("data_entrada")
    df_saem = _carregar_estadias(
        "e.data_saida IS NOT NULL AND e.data_saida BETWEEN %s AND %s",
        (hoje, fim_semana),
    ).sort_values("data_saida")

    render_kpi_row([
        ("Entram", len(df_entram)),
        ("Saem", len(df_saem)),
    ])

    col_w = [2.1, 1.5, 1.3, 1.2, 1.1, 1.1]

    render_zone_title("Entram esta semana", "ds-zone-title ds-zone-title--first")
    if df_entram.empty:
        st.caption("Sem entradas nos próximos 7 dias.")
    else:
        _render_header_row(col_w, ["Égua", "Dono", "Box", "Motivo", "Entrada", ""])
        with st.container(key="est-list-entram"):
            for _, row in df_entram.iterrows():
                _render_linha_movimento(row, col_w, "data_entrada", "mov_ent")

    render_zone_title("Saem esta semana", "ds-zone-title")
    if df_saem.empty:
        # Ver nota em run_estadias_page / resumo ao utilizador: a app só
        # regista a data de saída no momento em que "Registar saída" é
        # usado — não existe um campo de "saída prevista" separado para
        # estadias ainda abertas, por isso esta lista só mostra saídas
        # já efectivamente registadas dentro da janela dos 7 dias.
        st.caption(
            "Sem saídas registadas nos próximos 7 dias — a app regista a "
            "data de saída só quando 'Registar saída' é usado; não há "
            "ainda um campo de saída prevista para quem está internada."
        )
    else:
        _render_header_row(col_w, ["Égua", "Dono", "Box", "Motivo", "Saída", ""])
        with st.container(key="est-list-saem"):
            for _, row in df_saem.iterrows():
                _render_linha_movimento(row, col_w, "data_saida", "mov_sai")


# ────────────────────────────────────────────────────────────────────────────
# Separador "Histórico"
# ────────────────────────────────────────────────────────────────────────────
def _render_linha_historico(row: pd.Series, col_w: list[float]) -> None:
    estadia_id = int(row["id"])
    with st.container(key=f"estrow-hist-{estadia_id}"):
        cols = st.columns(col_w)
        cols[0].write(row["animal"] or "—")
        cols[1].write(_label_tipo_registo(row["tipo"]))
        cols[2].write(row["proprietario"] or "—")
        cols[3].write(row["alojamento_nome"] or "—")
        cols[4].write(_label_motivo(row["motivo"]))
        cols[5].write(_label_estado(row["estado"]))
        data_entrada = row.get("data_entrada")
        cols[6].write(
            data_entrada.strftime("%d/%m/%Y") if pd.notna(data_entrada) else "—"
        )
        data_saida = row.get("data_saida")
        cols[7].write(
            data_saida.strftime("%d/%m/%Y") if pd.notna(data_saida) else "Em curso"
        )
        with cols[8]:
            if st.button(
                "Ver ficha", key=f"hist_ver_{estadia_id}",
                type="tertiary", width="stretch",
            ):
                _ir_para_ficha(row["animal_id"])


def _render_tab_historico() -> None:
    if "historico_offset" not in st.session_state:
        st.session_state["historico_offset"] = 0
    offset = int(st.session_state["historico_offset"])
    target_y, target_m = _target_year_month(offset)
    primeiro = date(target_y, target_m, 1)
    _, last_d = _calendar.monthrange(target_y, target_m)
    ultimo = date(target_y, target_m, last_d)

    # Navegação de mês — mesmo padrão de setas do navegador de dia
    # (`day_navigator.py`), aqui a granularidade de mês.
    c_prev, c_title, c_next = st.columns([1, 2, 1])
    with c_prev:
        if st.button("◀ Mês anterior", key="hist_btn_prev", type="tertiary", width="stretch"):
            st.session_state["historico_offset"] = offset - 1
            st.rerun()
    with c_title:
        st.markdown(
            f"<div style='text-align:center;font-weight:700;"
            f"color:var(--ds-gray-900);font-size:1.05rem;padding-top:6px;'>"
            f"{MESES_PT[target_m - 1]} {target_y}</div>",
            unsafe_allow_html=True,
        )
    with c_next:
        if st.button("Mês seguinte ▶", key="hist_btn_next", type="tertiary", width="stretch"):
            st.session_state["historico_offset"] = offset + 1
            st.rerun()

    df = _carregar_estadias(
        "e.data_entrada <= %s AND (e.data_saida IS NULL OR e.data_saida >= %s)",
        (ultimo, primeiro),
    )

    render_kpi_row([("Passagens no mês", len(df))])
    render_zone_title(
        f"Estadias e visitas em {MESES_PT[target_m - 1]} {target_y}", "ds-zone-title",
    )

    if df.empty:
        st.caption("Sem estadias ou visitas neste mês.")
        return

    col_w = [1.9, 0.9, 1.4, 1.2, 1.1, 1.0, 1.0, 1.0, 1.0]
    _render_header_row(col_w, [
        "Égua", "Tipo", "Dono", "Box", "Motivo", "Estado",
        "Entrada", "Saída", "",
    ])
    with st.container(key="est-list-historico"):
        for _, row in df.sort_values("data_entrada", ascending=False).iterrows():
            _render_linha_historico(row, col_w)


# ────────────────────────────────────────────────────────────────────────────
# Diálogo "Registar saída"
# ────────────────────────────────────────────────────────────────────────────
def _render_modal_saida(estadia_id: int, animal_label: str | None) -> None:
    @st.dialog("Registar saída")
    def _modal() -> None:
        nome_display = (animal_label or "—").strip()
        if nome_display and nome_display != "—":
            nome_display = nome_display[0].upper() + nome_display[1:]
        st.markdown(
            f"<div style='color:#475569;font-size:.85rem;margin-bottom:8px;'>"
            f"Encerrar estadia de <b>{nome_display}</b></div>",
            unsafe_allow_html=True,
        )

        if "ms_data_saida" not in st.session_state:
            st.session_state["ms_data_saida"] = date.today()

        c1, c2 = st.columns(2)
        with c1:
            data_saida = st.date_input(
                "Data de saída",
                key="ms_data_saida",
                format="DD/MM/YYYY",
            )
        with c2:
            estado_final = st.selectbox(
                "Estado final",
                ESTADOS_SAIDA,
                key="ms_estado",
                format_func=lambda x: {
                    "gestante": "Gestante",
                    "alta": "Alta",
                    "sem_resultado": "Outro",
                    "transferido": "Transferido",
                }.get(x, x.capitalize()),
            )

        observacoes = st.text_area(
            "Observações de saída"
            + (" *" if estado_final == "sem_resultado" else ""),
            key="ms_obs",
            height=80,
            help=(
                "Obrigatório quando o estado final é 'Outro'."
                if estado_final == "sem_resultado" else None
            ),
        )

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        b1, b2 = st.columns(2)
        with b1:
            cancelar = st.button(
                "Cancelar", key="ms_btn_cancel", width="stretch",
            )
        with b2:
            guardar = st.button(
                "Guardar saída", type="primary",
                key="ms_btn_save", width="stretch",
            )

        if cancelar:
            for k in ("ms_data_saida", "ms_estado", "ms_obs"):
                st.session_state.pop(k, None)
            st.rerun()

        if not guardar:
            return

        # Quando o estado final é 'Outro' (sem_resultado), as observações
        # passam a ser obrigatórias.
        if (
            estado_final == "sem_resultado"
            and not (observacoes or "").strip()
        ):
            st.warning("Por favor descreva o motivo nas observações")
            return

        _ensure_saida_constraints()
        try:
            _registar_saida_estadia(
                estadia_id, data_saida, estado_final,
                (observacoes or "").strip(),
            )
        except Exception as exc:
            st.error(f"Erro ao registar saída: {exc}")
            return

        for k in ("ms_data_saida", "ms_estado", "ms_obs"):
            st.session_state.pop(k, None)
        st.success("Saída registada com sucesso.")
        st.rerun()

    _modal()


# ────────────────────────────────────────────────────────────────────────────
# Página principal
# ────────────────────────────────────────────────────────────────────────────
def run_estadias_page(context: dict):
    """Página de Estadias e Visitas."""

    # ── Orquestração de modais (Streamlit não permite diálogos aninhados) ───
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

    if st.session_state.get("abrir_modal_animal_para_estadia"):
        del st.session_state["abrir_modal_animal_para_estadia"]
        render_modal_animal(
            key="modal_animal_from_estadia",
            tipo_default="egua",
            on_success=_on_animal_for_estadia,
        )

    if st.session_state.get("reabrir_modal_animal"):
        del st.session_state["reabrir_modal_animal"]
        render_modal_animal(
            key="modal_animal_from_estadia",
            tipo_default="egua",
            on_success=_on_animal_for_estadia,
        )

    if (
        st.session_state.get("abrir_modal_nova_estadia")
        or st.session_state.get("reabrir_modal_nova_estadia")
    ):
        st.session_state.pop("abrir_modal_nova_estadia", None)
        st.session_state.pop("reabrir_modal_nova_estadia", None)
        _render_modal_nova_estadia()

    if st.session_state.get("abrir_modal_saida_id"):
        eid = int(st.session_state.pop("abrir_modal_saida_id"))
        animal_label = st.session_state.pop("abrir_modal_saida_animal", None)
        _render_modal_saida(eid, animal_label)

    # ── Drill-down para ficha do animal ─────────────────────────────────────
    if st.session_state.get("ver_animal_id") is not None:
        # Link de retrocesso — discreto (type="tertiary"), largura ao
        # conteúdo (nunca teve width="stretch"; mantém-se assim).
        if st.button("← Voltar às estadias", key="btn_voltar_estadias", type="tertiary"):
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

    inject_design_tokens()
    _inject_lista_css()

    # Botão de ação — sem título de página aqui (nome+data já vivem na topbar).
    col_spacer, col_btn = st.columns([4, 1])
    with col_btn:
        if st.button(
            "+ Nova estadia / visita", type="primary", width="stretch",
        ):
            _limpar_estado_modal_nova_estadia()
            st.session_state["abrir_modal_nova_estadia"] = True
            st.rerun()

    # Tabs (redesenho): Internadas agora → Movimentos da semana → Histórico.
    # Key própria (com nº de sequência de navegação, ver app.py) — evita
    # que o Streamlit reaproveite este `st.tabs` (que identifica widgets
    # pela posição no script, não pelo conteúdo) ao trocar para outra
    # página que também tenha tabs na mesma posição.
    _seq = st.session_state.get("_nav_render_seq", 0)
    with st.container(key=f"estadias-tabs-{_seq}"):
        tab_internadas, tab_movimentos, tab_historico = st.tabs(
            ["Internadas agora", "Movimentos da semana", "Histórico"]
        )

    with tab_internadas:
        _render_tab_internadas()

    with tab_movimentos:
        _render_tab_movimentos()

    with tab_historico:
        _render_tab_historico()
