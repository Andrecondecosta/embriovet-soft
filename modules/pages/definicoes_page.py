"""Página 'Definições' (Pedido 7) — orquestrador com 5 separadores:

- **Marca** (branding: nome da empresa, logo, cor primária)
- **Alojamentos**
- **Proprietários** (movido do menu top-level)
- **Utilizadores** (movido do menu top-level; apenas Administrador)
- **Idioma**

As permissões são respeitadas pelo próprio orquestrador — utilizadores
não-admin não vêem o separador **Utilizadores**. O conteúdo dos tabs
Proprietários e Utilizadores delega para as vistas extraídas
`_render_owners_view` e `_render_users_view` em `modules/pages/`.

Pedido 9 · Fase 2: `ctx` já não é usado. As dependências vêm por import
explícito (`_run_settings_geral`, `_render_tab_alojamentos` e as vistas
importam o que precisam).
"""

from __future__ import annotations

import streamlit as st

from modules.i18n import t
from modules.pages.settings_page import (
    _render_tab_alojamentos,
    _run_settings_geral,
)
from modules.services.auth_service import verificar_permissao


def _render_backup() -> None:
    """Separador "Cópia de segurança" (só Administrador): descarrega um
    ZIP com todos os dados. O ficheiro só é gerado ao clicar (callable
    no `data` do download_button) — `st.tabs` renderiza todos os
    separadores, e isto não pode pesar em cada visita às Definições."""
    from datetime import datetime

    from modules.backup import contar_linhas, gerar_backup_zip
    from modules.db import get_connection

    st.markdown(f"#### {t('backup.title')}")
    st.caption(t("backup.help"))

    try:
        with get_connection() as conn:
            linhas = contar_linhas(conn)
        principais = {
            t("backup.count.lots"): linhas.get("estoque_dono", 0),
            t("backup.count.owners"): linhas.get("dono", 0),
            t("backup.count.animals"): linhas.get("animais", 0),
            t("backup.count.inseminations"): linhas.get("inseminacoes", 0),
            t("backup.count.stays"): linhas.get("estadias", 0),
        }
        st.caption(" · ".join(f"**{n}** {nome}" for nome, n in principais.items())
                   + " · " + t("backup.count.tables", n=len(linhas)))
    except Exception:
        pass

    utilizador = (st.session_state.get("user") or {}).get("username")

    def _gerar() -> bytes:
        with get_connection() as conn:
            return gerar_backup_zip(conn, criado_por=utilizador)

    st.download_button(
        t("backup.download"),
        data=_gerar,
        file_name=f"embriovet_backup_{datetime.now():%Y%m%d_%H%M}.zip",
        mime="application/zip",
        icon=":material/download:",
        type="primary",
        key="definicoes_backup_download",
        on_click="ignore",
    )
    st.info(t("backup.advice"), icon=":material/info:")


def run_definicoes_page(ctx: dict) -> None:
    """Entry-point da nova página Definições (Pedido 7)."""
    # `ctx` mantido na assinatura por compatibilidade com o router,
    # mas nada é injetado — imports explícitos no topo cobrem tudo.
    del ctx

    st.header(t("settings.title"))

    # Consumir eventual redirect para separador específico.
    _pending_tab = st.session_state.pop("definicoes_tab", None)

    is_admin = bool(verificar_permissao("Administrador"))

    labels = ["Marca", "Alojamentos", "Proprietários"]
    if is_admin:
        labels.append("Utilizadores")
        labels.append(t("backup.tab"))
    labels.append("Idioma")

    # Key própria (com nº de sequência de navegação, ver app.py) — ver
    # nota em estadias_page.py sobre o Streamlit reaproveitar `st.tabs`
    # entre páginas por posição, não por conteúdo.
    _seq = st.session_state.get("_nav_render_seq", 0)
    with st.container(key=f"definicoes-tabs-{_seq}"):
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
        from modules.pages.owners_view import _render_owners_view
        _render_owners_view()

    idx = 3
    if is_admin:
        with tabs[idx]:
            from modules.pages.users_view import _render_users_view
            _render_users_view()
        idx += 1
        with tabs[idx]:
            _render_backup()
        idx += 1

    with tabs[idx]:
        st.info(
            "A configuração de idioma partilha o painel de Marca. "
            "Ajuste o idioma no separador **Marca** — em breve terá "
            "painel dedicado."
        )
