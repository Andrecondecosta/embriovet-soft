"""Página 'Stock de sémen' (Pedido 7) — orquestrador que funde as 4
antigas entradas de menu numa página só:

- Separadores: Lotes · Garanhões · Mapa dos contentores · Transferências
- Botões no topo: Adicionar lote · Importar

O tab **Garanhões** é o único novo — resolve a falta de ponto de
entrada para as fichas dos garanhões (lista todos os que têm stock
com atalho para `run_animal_page(animal_id)`).

Este ficheiro **não contém lógica de negócio**. Delega toda a
renderização aos módulos existentes (`stock_page`, `map_page`,
`transfer_page`) e ao form 'Adicionar lote' em `app.py`
(`_render_add_stock_view`) e ao `import_page`. É uma questão de
localização/invocação, não de reescrita.
"""

from __future__ import annotations

import streamlit as st

from modules.db import get_connection
from modules.i18n import t
from modules.pages.map_page import run_map_page
from modules.pages.stock_page import run_stock_page
from modules.pages.transfer_page import run_transfer_page
from modules.ui_kit import inject_reports_css, inject_stock_css, render_zone_title


_TABS = ["Lotes", "Garanhões", "Mapa dos contentores", "Transferências"]


def run_stock_semen_page(ctx: dict) -> None:
    """Entry-point da nova página 'Stock de sémen'."""
    # CSS partilhado do design system — injetado aqui (nível da página),
    # tal como `run_reports_page`/`run_stock_page` fazem, em vez de
    # depender do separador "Lotes" o injetar de forma indireta.
    inject_stock_css()
    inject_reports_css()

    # Sub-views (add_stock / import) — activadas pelos botões topo ou
    # por redirects legacy (t("menu.add_stock") / t("menu.import")).
    sub_view = st.session_state.pop("stock_semen_view", None)

    if sub_view == "add_stock":
        _render_add_stock_topbar()
        _delegate_add_stock(ctx)
        return

    if sub_view == "import":
        _render_import_topbar()
        from modules.pages.import_page import run_import_page
        run_import_page(ctx)
        return

    # Vista padrão: tabs.
    _render_topbar()
    _render_tabs(ctx)


# ─── Topbar (título + botões de ação) ────────────────────────────────

def _render_topbar() -> None:
    # Sem título de página aqui — nome+data já vivem na topbar da app.
    col_l, col_add, col_imp = st.columns([6, 1.4, 1.2])
    with col_add:
        if st.button("Adicionar lote", key="stock-semen-btn-add",
                     type="primary", width="stretch"):
            st.session_state["stock_semen_view"] = "add_stock"
            st.rerun()
    with col_imp:
        if st.button("Importar", key="stock-semen-btn-import",
                     width="stretch"):
            st.session_state["stock_semen_view"] = "import"
            st.rerun()


def _render_add_stock_topbar() -> None:
    if st.button("← Voltar ao Stock de sémen",
                 key="stock-semen-back-from-add"):
        st.rerun()


def _render_import_topbar() -> None:
    if st.button("← Voltar ao Stock de sémen",
                 key="stock-semen-back-from-import"):
        st.rerun()


# ─── Tabs ────────────────────────────────────────────────────────────
# `st.tabs` nativo não deixa escolher o separador activo por código
# (sem `default_index`) — por isso qualquer redirect para um separador
# específico (ex.: "Editar" numa transferência a partir da Atividade,
# ou "Nova Transferência" no Dashboard) ficava sempre a aterrar em
# "Lotes". Substituído por um `st.radio` controlado por nós — o valor
# vive em `session_state` e respeita `stock_semen_tab` de entrada.
# Reestilizado como separadores (esconde o círculo do rádio, sublinha
# a opção activa); scoped ao container "stock-semen-tabs" para não
# afectar os outros `st.radio` desta página (stock_page.py/
# transfer_page.py usam-nos para outras coisas, ex.: tipo de
# transferência).

_TAB_STATE_KEY = "stock_semen_active_tab"


def _inject_tabs_css() -> None:
    st.markdown(
        """
        <style>
            div[class*="st-key-stock-semen-tabs"] [role="radiogroup"] {
                display: flex;
                flex-wrap: wrap;
                gap: 4px;
                border-bottom: 1px solid #e2e8f0;
                margin-bottom: 12px;
            }
            div[class*="st-key-stock-semen-tabs"] [role="radiogroup"] > label {
                margin: 0 !important;
                padding: 8px 14px !important;
                border-bottom: 2px solid transparent;
                cursor: pointer;
            }
            /* 1º filho do <label> é o círculo visual do rádio (o
               <input type="radio"> em si fica no DOM, só o círculo
               desenhado é escondido — clicar no texto continua a
               accionar o input nativo, sem tocar em acessibilidade). */
            div[class*="st-key-stock-semen-tabs"] [role="radiogroup"] > label > div:first-child {
                display: none !important;
            }
            div[class*="st-key-stock-semen-tabs"] [role="radiogroup"] > label p {
                font-size: .92rem !important;
                color: #64748b !important;
                margin: 0 !important;
            }
            div[class*="st-key-stock-semen-tabs"] [role="radiogroup"] > label:has(input:checked) {
                border-bottom-color: #E85D4A;
            }
            div[class*="st-key-stock-semen-tabs"] [role="radiogroup"] > label:has(input:checked) p {
                color: #0f172a !important;
                font-weight: 600 !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_tabs(ctx: dict) -> None:
    # Consumir eventual redirect que aponte para um separador
    # específico — ao contrário do antigo st.tabs, este valor é
    # respeitado de facto.
    incoming = st.session_state.pop("stock_semen_tab", None)
    if incoming in _TABS:
        st.session_state[_TAB_STATE_KEY] = incoming
    elif _TAB_STATE_KEY not in st.session_state:
        st.session_state[_TAB_STATE_KEY] = _TABS[0]

    _inject_tabs_css()
    with st.container(key="stock-semen-tabs"):
        aba_ativa = st.radio(
            "Separador", _TABS, key=_TAB_STATE_KEY,
            horizontal=True, label_visibility="collapsed",
        )

    # Só o separador activo é renderizado (ao contrário do st.tabs
    # nativo, que corria o corpo dos 4 sempre) — é o que nos permite
    # abrir directamente no separador certo sem depender de os outros
    # 3 já terem corrido "em fundo".
    if aba_ativa == "Lotes":
        run_stock_page(ctx)
    elif aba_ativa == "Garanhões":
        _render_tab_garanhoes(ctx)
    elif aba_ativa == "Mapa dos contentores":
        run_map_page(ctx)
    elif aba_ativa == "Transferências":
        run_transfer_page(ctx)


# ─── Tab novo: Garanhões ─────────────────────────────────────────────

def _carregar_garanhoes_com_stock():
    """Lista de garanhões (`animais.tipo='garanhao'`) com pelo menos um
    lote em stock. Devolve id, nome, palhetas_totais, lotes.
    """
    sql = """
        SELECT a.id                                 AS animal_id,
               COALESCE(a.nome, e.garanhao)         AS garanhao,
               SUM(e.existencia_atual)::int         AS palhetas,
               COUNT(DISTINCT e.id)::int            AS lotes,
               COUNT(DISTINCT e.dono_id)::int       AS donos
        FROM estoque_dono e
        LEFT JOIN animais a ON a.id = e.animal_id
        WHERE e.existencia_atual > 0
        GROUP BY 1, 2
        ORDER BY LOWER(COALESCE(a.nome, e.garanhao)) ASC
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cur.close()
    return rows


def _render_tab_garanhoes(ctx: dict) -> None:
    st.caption("Garanhões com stock disponível. Clique para abrir a ficha.")

    try:
        rows = _carregar_garanhoes_com_stock()
    except Exception as e:
        st.error(f"Erro ao carregar garanhões: {e}")
        return

    if not rows:
        st.info("Sem garanhões com stock disponível.")
        return

    # Filtro por nome
    query = st.text_input(
        "Pesquisar garanhão", key="stock-semen-gar-search",
        placeholder="Nome do garanhão...",
    )
    if query:
        q = query.lower()
        rows = [r for r in rows if q in (r[1] or "").lower()]
        if not rows:
            st.info("Sem resultados para o filtro aplicado.")
            return

    # Cabeçalho
    head_cols = st.columns([3, 1.2, 1.2, 1.2, 1.4])
    for i, h in enumerate(["Garanhão", "Palhetas", "Lotes", "Donos", ""]):
        with head_cols[i]:
            render_zone_title(h, "stock-zone-title")
    st.divider()

    for row in rows:
        animal_id, nome, palhetas, lotes, donos = row
        cols = st.columns([3, 1.2, 1.2, 1.2, 1.4])
        cols[0].write(nome or "—")
        cols[1].write(int(palhetas or 0))
        cols[2].write(int(lotes or 0))
        cols[3].write(int(donos or 0))
        with cols[4]:
            # Só é possível abrir a ficha para garanhões que já foram
            # sincronizados com `animais` (têm `animal_id`). Lotes legados
            # sem FK ainda não têm ponto de entrada — clara chamada à
            # limpeza de schema.
            if animal_id is not None:
                if st.button(
                    "Ver ficha",
                    key=f"stock-semen-gar-ficha-{animal_id}",
                    width="stretch",
                ):
                    st.session_state["ver_animal_id"] = int(animal_id)
                    st.session_state["ver_animal_tab"] = 0
                    st.rerun()
            else:
                st.caption("sem ficha")


# ─── Delegação para o form 'Adicionar lote' (em app.py) ──────────────

def _delegate_add_stock(ctx: dict) -> None:
    """Invoca o form 'Adicionar lote' extraído para
    `modules.pages.add_stock_view` (Pedido 9 · Fase 1).

    Import direto no topo do módulo — o `sys.modules['__main__']`
    do último ciclo foi eliminado.
    """
    from modules.pages.add_stock_view import _render_add_stock_view
    _render_add_stock_view()
