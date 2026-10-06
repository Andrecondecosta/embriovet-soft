"""Ao "Atualizar" no browser, a app fica na página (e no separador do
Stock de sémen) onde se estava, em vez de voltar ao Dashboard.

Uma sessão nova do AppTest com `?pagina=`/`?separador=` no endereço
simula exactamente o "Atualizar" (sessão nova, endereço igual).
"""

from __future__ import annotations

import logging

import pytest
from streamlit.testing.v1 import AppTest

from modules.url_state import slug

USER = {"id": 10, "username": "admin", "nivel": "Administrador",
        "nome_completo": "Admin", "must_change_password": False}


@pytest.fixture(autouse=True)
def _silencio():
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


def _app(**params) -> AppTest:
    at = AppTest.from_file("app.py", default_timeout=120)
    at.session_state["user"] = USER
    for k, v in params.items():
        at.query_params[k] = v
    return at


def _param(at, nome):
    """O AppTest devolve os parâmetros do endereço como lista."""
    v = at.query_params.get(nome)
    return v[0] if isinstance(v, list) and v else v


def test_slug():
    assert slug("Stock de sémen") == "stock-de-semen"
    assert slug("Mapa dos contentores") == "mapa-dos-contentores"
    assert slug("Definições") == "definicoes"


def test_sessao_nova_volta_a_pagina_do_endereco():
    at = _app(pagina="relatorios")
    at.run()
    assert not at.exception
    assert at.session_state["_nav_last_active"] == "Relatórios"


def test_sessao_nova_volta_ao_separador_do_stock():
    at = _app(pagina="stock-de-semen", separador="mapa-dos-contentores")
    at.run()
    assert not at.exception
    assert at.session_state["_nav_last_active"] == "Stock de sémen"
    assert at.session_state["stock_semen_active_tab"] == "Mapa dos contentores"


def test_sem_pagina_no_endereco_abre_o_dashboard():
    at = _app()
    at.run()
    assert at.session_state["_nav_last_active"] == "Dashboard"
    assert _param(at, "pagina") == "dashboard"


def test_mudar_de_pagina_atualiza_o_endereco():
    at = _app(pagina="stock-de-semen", separador="lotes")
    at.run()
    at.session_state["_nav_last_active"] = "Atividade"
    at.run()
    assert _param(at, "pagina") == "atividade"
    assert "separador" not in at.query_params  # só faz sentido no Stock de sémen


def test_valor_invalido_no_endereco_e_ignorado():
    at = _app(pagina="nao-existe", separador="tambem-nao")
    at.run()
    assert not at.exception
    assert at.session_state["_nav_last_active"] == "Dashboard"


def test_css_esconde_a_pagina_anterior_ao_navegar():
    """Ao mudar de página, o CSS emitido logo no início esconde todos os
    containers de página excepto o da página nova (key nova a cada
    navegação) — a página anterior deixa de ficar visível, esbatida,
    enquanto a nova é desenhada."""
    at = _app(pagina="dashboard")
    at.run()
    seq0 = at.session_state["_nav_render_seq"]

    # Navegação real (como o on_click da sidebar).
    at.session_state["_nav_last_active"] = "Atividade"
    at.session_state["_nav_render_seq"] = seq0 + 1
    at.run()
    estilos = [m.value for m in at.markdown if "st-key-page-" in m.value]
    assert estilos, "CSS de esconder a página anterior não foi emitido"
    assert f".st-key-page-atividade-{seq0 + 1})" in estilos[0]
    assert "display:none" in estilos[0]

    # Rerun dentro da mesma página: a key (e o CSS) não muda.
    at.run()
    assert f".st-key-page-atividade-{seq0 + 1})" in [m.value for m in at.markdown if "st-key-page-" in m.value][0]
