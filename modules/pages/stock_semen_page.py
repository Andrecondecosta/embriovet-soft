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


_TABS = ["Lotes", "Garanhões", "Mapa dos contentores", "Transferências"]


def run_stock_semen_page(ctx: dict) -> None:
    """Entry-point da nova página 'Stock de sémen'."""
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
    st.header("Stock de sémen")
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

def _render_tabs(ctx: dict) -> None:
    # Consumir eventual redirect que aponte para uma tab específica.
    default_idx = 0
    if st.session_state.get("stock_semen_tab") in _TABS:
        default_idx = _TABS.index(st.session_state["stock_semen_tab"])
        # Streamlit `st.tabs` não aceita `default_index` — deixamos o
        # valor consumido em `session_state` para próxima navegação;
        # a UX degrada elegantemente (o utilizador clica a tab).
        st.session_state.pop("stock_semen_tab", None)

    tab_lotes, tab_gar, tab_mapa, tab_trans = st.tabs(_TABS)

    with tab_lotes:
        run_stock_page(ctx)

    with tab_gar:
        _render_tab_garanhoes(ctx)

    with tab_mapa:
        run_map_page(ctx)

    with tab_trans:
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
    st.markdown(
        "<div style='font-size:.8rem;color:#64748b;margin-bottom:8px;'>"
        "Garanhões com stock disponível. Clique para abrir a ficha.</div>",
        unsafe_allow_html=True,
    )

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
        head_cols[i].markdown(
            f"<div style='font-size:.7rem;color:#94a3b8;text-transform:uppercase;"
            f"letter-spacing:.5px;font-weight:700;'>{h}</div>",
            unsafe_allow_html=True,
        )
    st.markdown(
        "<hr style='border:none;border-top:1px solid #e2e8f0;margin:4px 0 8px;'>",
        unsafe_allow_html=True,
    )

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
    """Invoca o form existente em `app.py::_render_add_stock_view`.

    Resolvemos o símbolo via `sys.modules['__main__']` — nunca fazer
    `from app import ...` no runtime porque o `app.py` é o entry-point
    do Streamlit e um import forçaria uma segunda execução top-down
    do ficheiro (com colisão de keys em `st.text_input`, `st.button`,
    etc.). Ao passar por `sys.modules['__main__']` reutilizamos o
    módulo já carregado — que a esta altura da execução já processou
    os `def` necessários (foram movidos para antes do router em
    Pedido 8/hotfix).
    """
    import sys
    main = sys.modules.get('__main__')
    fn = getattr(main, '_render_add_stock_view', None)
    if fn is None:
        # Fallback: talvez `main` seja outra coisa (testes). Tenta ctx.
        fn = (ctx or {}).get('_render_add_stock_view')
    if fn is None:
        st.error("Form 'Adicionar lote' indisponível. Reload da página.")
        return
    fn()
