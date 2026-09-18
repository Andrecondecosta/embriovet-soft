"""Página de Atividade — histórico único de operações (inseminações +
transferências), navegável por dia.

Parte 2 de 3: editar e anular por linha, reutilizando os modos de
edição já existentes (insemination_page / transfer_page) e
`transfer_repo.reverter_operacao` para anular — nada disto é motor
novo. A Parte 3 (remover o histórico redundante de Transferências →
Histórico, que passa a redirecionar para aqui) ainda não está feita.
"""

from __future__ import annotations

from html import escape

import streamlit as st

from modules.components.day_navigator import render_day_navigator
from modules.i18n import t
from modules.repositories.dashboard_repo import carregar_atividade_do_dia
from modules.repositories.transfer_repo import reverter_operacao
from modules.ui_kit import inject_design_tokens, render_zone_title


def _fmt_hora(ts) -> str:
    if not ts:
        return "—"
    return ts.strftime("%H:%M")


def _op_key(op: dict) -> str:
    return op.get("operation_id") or f"solo-{op['action_id']}"


def _confirm_key(op: dict) -> str:
    return f"ativ-confirm-{op['tipo']}-{_op_key(op)}"


def _anular(op: dict) -> bool:
    """Chama `reverter_operacao` com os parâmetros certos para `op` —
    extraído à parte da UI para poder ser testado sem simular cliques."""
    return reverter_operacao(
        tipo=op["tipo"],
        action_id=op["action_id"],
        operation_id=op.get("operation_id"),
    )


def _iniciar_edicao(op: dict) -> None:
    """Activa o modo de edição já existente para o tipo da operação —
    não constrói edição nova, só liga aos flags que
    insemination_page.py / transfer_page.py já lêem."""
    if op["tipo"] == "insemination":
        st.session_state["edit_insemination_id"] = op["action_id"]
        st.session_state["edit_insemination_op_id"] = op.get("operation_id")
        st.session_state["aba_selecionada"] = t("menu.register_insemination")
    else:  # transfer_internal / transfer_external
        st.session_state["edit_transfer_id"] = op["action_id"]
        st.session_state["edit_transfer_type"] = op["tipo"]
        st.session_state["edit_transfer_op_id"] = op.get("operation_id")
        # Limpa estado de formulário antigo — mesmo cuidado do botão
        # editar já existente em transfer_page.py, para não arrastar
        # valores presos de uma sessão anterior.
        for k in [
            "transfer_tipo", "transfer_linhas", "transfer_garanhao",
            "transfer_proprietario", "transfer_dest_interno",
            "transfer_dest_externo", "transfer_destinatario_externo",
            "transfer_motivo", "transfer_observacoes",
        ]:
            st.session_state.pop(k, None)
        st.session_state["aba_selecionada"] = t("menu.transfers")
    st.rerun()


def _inject_lista_css() -> None:
    """Lista densa no mesmo estilo do Trabalho Diário — zebra
    cinza/branco, sem bordas pesadas, linhas compactas."""
    st.markdown(
        """
        <style>
            div.st-key-ativ-list {
                gap: 0 !important;
            }
            div.st-key-ativ-list > div[data-testid="stLayoutWrapper"]:nth-child(even)
                > div[class*="st-key-ativ-row-"] {
                background: var(--ds-gray-50);
            }
            div[class*="st-key-ativ-row-"] {
                padding: 4px 10px;
            }
            div[class*="st-key-ativ-row-"] button {
                width: 100% !important;
                min-height: 30px !important;
                height: 30px !important;
                font-size: .78rem !important;
                font-weight: 400 !important;
                padding: 0 8px !important;
            }
            .ativ-info {
                display: block;
                font-size: .84rem;
                color: var(--ds-gray-900);
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            .ativ-info .ativ-muted {
                color: var(--ds-gray-500);
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_linha(op: dict, idx: int) -> None:
    hora = _fmt_hora(op["ts"])
    utilizador = escape(str(op["usuario"] or "—"))
    acao = escape(str(op["acao"] or "—"))
    detalhe = escape(str(op["detalhe"]))

    with st.container(key=f"ativ-row-{idx}"):
        col_info, col_editar, col_anular = st.columns(
            [0.72, 0.14, 0.14], gap="small", vertical_alignment="center",
        )
        with col_info:
            st.markdown(
                f"<span class='ativ-info'><b>{hora}</b> · "
                f"<span class='ativ-muted'>{utilizador}</span> · "
                f"{acao} — {detalhe}</span>",
                unsafe_allow_html=True,
            )
        with col_editar:
            if st.button("Editar", key=f"ativ-editar-{idx}", width="stretch"):
                _iniciar_edicao(op)
        with col_anular:
            if st.button("Anular", key=f"ativ-anular-{idx}", width="stretch"):
                st.session_state[_confirm_key(op)] = True
                st.rerun()


def _render_confirmacao(op: dict) -> None:
    multi_lote = op["num_lotes"] > 1
    aviso = (
        f"Anular esta operação? Isto vai devolver **{op['quantidade']} palhetas** "
        f"ao stock e apagar o registo"
    )
    if multi_lote:
        aviso += (
            f" — a operação **inteira**, incluindo todos os "
            f"**{op['num_lotes']} lotes**."
        )
    else:
        aviso += "."
    aviso += " **Esta ação não pode ser desfeita.**"
    st.warning(aviso)

    col_confirmar, col_cancelar = st.columns([1, 1])
    with col_confirmar:
        if st.button(
            "Confirmar anulação", key="ativ-confirmar-anulacao",
            type="primary", width="stretch",
        ):
            sucesso = _anular(op)
            st.session_state.pop(_confirm_key(op), None)
            if sucesso:
                st.toast("Operação anulada.", icon="✅")
                st.rerun()
            else:
                st.error(
                    "Erro ao anular a operação — nada foi alterado. "
                    "Tenta novamente ou contacta o suporte."
                )
    with col_cancelar:
        if st.button("Cancelar", key="ativ-cancelar-anulacao", width="stretch"):
            st.session_state.pop(_confirm_key(op), None)
            st.rerun()


def run_atividade_page(context: dict) -> None:
    """Entry-point da página (chamado pelo router). `context` não é
    usado — mantido só por compatibilidade com a assinatura comum."""
    del context

    inject_design_tokens()

    dia = render_day_navigator("atividade")

    render_zone_title(
        f"Operações de {dia.strftime('%d/%m/%Y')}",
        "ds-zone-title ds-zone-title--first",
    )

    try:
        ops = carregar_atividade_do_dia(dia)
    except Exception as e:
        st.error(f"Erro ao carregar atividade do dia: {e}")
        return

    if not ops:
        st.caption("Sem operações registadas neste dia.")
        return

    # Se houver um pedido de anulação pendente, mostra só a
    # confirmação — a lista volta a aparecer depois de confirmar ou
    # cancelar (mesmo padrão já usado em transfer_page.py).
    pendente = None
    for op in ops:
        if st.session_state.get(_confirm_key(op)):
            pendente = op
            break

    if pendente:
        _render_confirmacao(pendente)
        return

    _inject_lista_css()
    with st.container(key="ativ-list"):
        for idx, op in enumerate(ops):
            _render_linha(op, idx)
