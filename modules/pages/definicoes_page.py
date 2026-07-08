"""Página 'Definições' (Pedido 7) — orquestrador com 5 separadores:

- **Marca** (branding: nome da empresa, logo, cor primária)
- **Alojamentos**
- **Proprietários** (movido do menu top-level)
- **Utilizadores** (movido do menu top-level; apenas Administrador)
- **Idioma**

As permissões são respeitadas pelo próprio orquestrador — utilizadores
não-admin não vêem o separador **Utilizadores**. O conteúdo dos tabs
Proprietários e Utilizadores delega para as funções `_render_owners_view`
e `_render_users_view` definidas em `app.py` (movidas em Pedido 7 sem
alteração de lógica).
"""

from __future__ import annotations

import streamlit as st

from modules.i18n import t
from modules.pages import settings_page as _settings_module
from modules.pages.settings_page import (
    _render_tab_alojamentos,
    _run_settings_geral,
)


def run_definicoes_page(ctx: dict) -> None:
    """Entry-point da nova página Definições (Pedido 7)."""
    # Injectar globals para as funções que dependem de `app_settings`,
    # `update_branding_settings`, etc. (padrão herdado do settings_page).
    globals().update(ctx)
    # Também injectar no namespace do `settings_page` — o padrão
    # `globals().update(ctx)` legado exige que `_run_settings_geral`
    # e `_render_tab_alojamentos` vejam `inject_stock_css`,
    # `app_settings`, `update_branding_settings`, etc. no seu próprio
    # módulo. Sem isto, o tab Marca dá `NameError`.
    _settings_module.__dict__.update(ctx)

    st.header(t("settings.title"))

    # Consumir eventual redirect para separador específico.
    _pending_tab = st.session_state.pop("definicoes_tab", None)

    verificar_permissao = ctx.get("verificar_permissao")
    is_admin = verificar_permissao and verificar_permissao("Administrador")

    labels = ["Marca", "Alojamentos", "Proprietários"]
    if is_admin:
        labels.append("Utilizadores")
    labels.append("Idioma")

    tabs = st.tabs(labels)

    # Marca (a antiga `_run_settings_geral` mistura marca+idioma; aqui só
    # vamos mostrar a componente de marca no separador Marca e o selector
    # de idioma no separador Idioma — reutilizamos a função inteira em
    # ambos porque a lógica de save é comum e o preview lá dentro já
    # cobre as duas facetas. Alternativa mais elegante fica para o
    # redesign das Definições, deferido no backlog.)
    with tabs[0]:
        _run_settings_geral()

    with tabs[1]:
        _render_tab_alojamentos()

    with tabs[2]:
        owners_fn = ctx.get("_render_owners_view")
        if owners_fn is None:
            st.error("Vista de Proprietários indisponível.")
        else:
            owners_fn()

    idx = 3
    if is_admin:
        with tabs[idx]:
            users_fn = ctx.get("_render_users_view")
            if users_fn is None:
                st.error("Vista de Utilizadores indisponível.")
            else:
                users_fn()
        idx += 1

    with tabs[idx]:
        st.info(
            "A configuração de idioma partilha o painel de Marca. "
            "Ajuste o idioma no separador **Marca** — em breve terá "
            "painel dedicado."
        )
