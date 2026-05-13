"""Modal de criação rápida de um proprietário (dono).

Uso típico:
    if st.button("+ Novo proprietário"):
        render_modal_proprietario("modal_dono", on_success=lambda did, dnome: ...)
"""

from __future__ import annotations

from typing import Callable, Optional

import streamlit as st

from modules.db import get_connection


def _existe_dono_com_nome(nome: str) -> bool:
    sql = "SELECT 1 FROM dono WHERE LOWER(nome) = LOWER(%s) LIMIT 1"
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, (nome,))
        existe = cur.fetchone() is not None
        cur.close()
        return existe


def _inserir_dono(payload: dict) -> int:
    sql = """
        INSERT INTO dono (
            nome, nome_completo, nif, email, telemovel,
            morada, codigo_postal, cidade, ativo
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
        RETURNING id
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            sql,
            (
                payload["nome"],
                payload.get("nome_completo") or None,
                payload.get("nif") or None,
                payload.get("email") or None,
                payload.get("telemovel") or None,
                payload.get("morada") or None,
                payload.get("codigo_postal") or None,
                payload.get("cidade") or None,
            ),
        )
        new_id = int(cur.fetchone()[0])
        conn.commit()
        cur.close()
        return new_id


def render_modal_proprietario(
    key: str,
    on_success: Optional[Callable[[int, str], None]] = None,
) -> None:
    """Abre um modal para criar um novo proprietário (dono).

    Parâmetros
    ----------
    key : str
        Prefixo único para os widgets do formulário (evita colisões em
        `st.session_state`).
    on_success : Optional[Callable[[int, str], None]]
        Callback opcional invocado após criação com `(dono_id, dono_nome)`.
    """

    @st.dialog("Novo proprietário")
    def _modal() -> None:
        st.markdown(
            "<div style='color:#64748b;font-size:.85rem;margin-bottom:8px;'>"
            "Preencha os dados do novo proprietário. O nome é obrigatório e "
            "deve ser único.</div>",
            unsafe_allow_html=True,
        )

        with st.form(key=f"{key}_form_dono", clear_on_submit=False):
            c1, c2 = st.columns(2)
            with c1:
                nome = st.text_input(
                    "Nome curto *", key=f"{key}_dono_nome",
                    placeholder="Ex.: Tavares de Almeida",
                )
                nif = st.text_input("NIF", key=f"{key}_dono_nif")
                email = st.text_input("Email", key=f"{key}_dono_email")
                telemovel = st.text_input("Telemóvel", key=f"{key}_dono_tel")
            with c2:
                nome_completo = st.text_input(
                    "Nome completo", key=f"{key}_dono_nome_completo",
                )
                morada = st.text_input("Morada", key=f"{key}_dono_morada")
                codigo_postal = st.text_input(
                    "Código postal", key=f"{key}_dono_cp",
                )
                cidade = st.text_input("Cidade", key=f"{key}_dono_cidade")

            cb1, cb2 = st.columns([1, 1])
            with cb1:
                cancelar = st.form_submit_button("Cancelar", width="stretch")
            with cb2:
                guardar = st.form_submit_button(
                    "Guardar proprietário", type="primary", width="stretch",
                )

        if cancelar:
            st.rerun()

        if guardar:
            nome_clean = (nome or "").strip()
            if not nome_clean:
                st.error("O nome do proprietário é obrigatório.")
                return
            if _existe_dono_com_nome(nome_clean):
                st.error(
                    f"Já existe um proprietário com o nome '{nome_clean}'. "
                    "Escolha outro nome.",
                )
                return

            try:
                new_id = _inserir_dono({
                    "nome": nome_clean,
                    "nome_completo": (nome_completo or "").strip(),
                    "nif": (nif or "").strip(),
                    "email": (email or "").strip(),
                    "telemovel": (telemovel or "").strip(),
                    "morada": (morada or "").strip(),
                    "codigo_postal": (codigo_postal or "").strip(),
                    "cidade": (cidade or "").strip(),
                })
            except Exception as exc:  # pragma: no cover - safety net
                st.error(f"Erro ao guardar proprietário: {exc}")
                return

            if on_success is not None:
                try:
                    on_success(new_id, nome_clean)
                except Exception as exc:  # pragma: no cover
                    st.warning(f"Proprietário criado, mas callback falhou: {exc}")

            st.success(f"Proprietário '{nome_clean}' criado com sucesso.")
            st.rerun()

    _modal()
