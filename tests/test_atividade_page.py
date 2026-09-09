"""Testes da página de Atividade — Parte 2 (editar/anular por linha).

Cobre:
(a) `_anular` chama `reverter_operacao` com `tipo`/`action_id`/
    `operation_id` certos, para operação simples e multi-lote.
(b) `_iniciar_edicao` activa os flags de edição já existentes em
    insemination_page.py / transfer_page.py — não constrói edição
    nova, só liga aos flags.

Estratégia: mock de `reverter_operacao` (sem tocar na BD) — o
comportamento do próprio `reverter_operacao` já está coberto por
outros testes (ex.: test_dashboard_pedido6.py). Aqui testamos só a
wiring da página: que é chamado com os parâmetros certos a partir de
um dict de operação.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from modules.pages import atividade_page


@pytest.fixture(autouse=True)
def _clean_session_state():
    """`st.session_state` fora de um script Streamlit real é um dict
    simples fornecido pelo próprio Streamlit em modo de teste — limpa
    antes/depois para não vazar entre testes."""
    import streamlit as st
    st.session_state.clear()
    yield
    st.session_state.clear()


def _op_insemination(op_id="op-uuid-1", action_id=101, num_lotes=1, quantidade=5):
    return {
        "ts": None, "usuario": "test", "acao": "Inseminação",
        "tipo": "insemination", "action_id": action_id,
        "operation_id": op_id, "quantidade": quantidade,
        "num_lotes": num_lotes, "detalhe": "Égua X · Garanhão Y",
    }


def _op_transfer_interna(op_id=None, action_id=202, num_lotes=2, quantidade=12):
    return {
        "ts": None, "usuario": "test", "acao": "Transferência interna",
        "tipo": "transfer_internal", "action_id": action_id,
        "operation_id": op_id, "quantidade": quantidade,
        "num_lotes": num_lotes, "detalhe": "Dono A → Dono B",
    }


# ────────────────────────────────────────────────────────────────────
# (a) _anular chama reverter_operacao com os parâmetros certos
# ────────────────────────────────────────────────────────────────────

def test_anular_inseminacao_multi_lote_chama_reverter_operacao_certo(monkeypatch):
    mock_reverter = MagicMock(return_value=True)
    monkeypatch.setattr(atividade_page, "reverter_operacao", mock_reverter)

    op = _op_insemination(op_id="op-uuid-multi", action_id=101, num_lotes=3, quantidade=15)
    resultado = atividade_page._anular(op)

    assert resultado is True
    mock_reverter.assert_called_once_with(
        tipo="insemination", action_id=101, operation_id="op-uuid-multi",
    )


def test_anular_transferencia_sem_operation_id_usa_action_id(monkeypatch):
    """Operação solo (sem operation_id, ex.: registo legado) — reverter_operacao
    recebe operation_id=None e usa o action_id para identificar a linha."""
    mock_reverter = MagicMock(return_value=True)
    monkeypatch.setattr(atividade_page, "reverter_operacao", mock_reverter)

    op = _op_transfer_interna(op_id=None, action_id=555, num_lotes=1, quantidade=8)
    atividade_page._anular(op)

    mock_reverter.assert_called_once_with(
        tipo="transfer_internal", action_id=555, operation_id=None,
    )


def test_anular_propaga_falha_de_reverter_operacao(monkeypatch):
    """Se reverter_operacao falhar (devolve False), _anular não deve
    fingir sucesso — devolve False tal e qual."""
    monkeypatch.setattr(
        atividade_page, "reverter_operacao", MagicMock(return_value=False),
    )
    op = _op_insemination()
    assert atividade_page._anular(op) is False


# ────────────────────────────────────────────────────────────────────
# (b) _iniciar_edicao liga aos flags de edição já existentes
# ────────────────────────────────────────────────────────────────────

def test_iniciar_edicao_inseminacao_seta_flags_certos():
    import streamlit as st
    from modules.i18n import t

    op = _op_insemination(op_id="op-uuid-2", action_id=42)
    # st.rerun() é um no-op fora de uma app Streamlit real ("bare
    # mode") — só nos interessa aqui que os flags ficam bem definidos.
    atividade_page._iniciar_edicao(op)

    assert st.session_state["edit_insemination_id"] == 42
    assert st.session_state["edit_insemination_op_id"] == "op-uuid-2"
    assert st.session_state["aba_selecionada"] == t("menu.register_insemination")


def test_iniciar_edicao_transferencia_seta_flags_e_limpa_form_antigo():
    import streamlit as st
    from modules.i18n import t

    st.session_state["transfer_motivo"] = "valor antigo preso"
    op = _op_transfer_interna(op_id="op-uuid-3", action_id=99)
    atividade_page._iniciar_edicao(op)

    assert st.session_state["edit_transfer_id"] == 99
    assert st.session_state["edit_transfer_type"] == "transfer_internal"
    assert st.session_state["edit_transfer_op_id"] == "op-uuid-3"
    assert "transfer_motivo" not in st.session_state
    assert st.session_state["aba_selecionada"] == t("menu.transfers")
