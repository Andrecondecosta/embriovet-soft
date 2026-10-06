"""Página/separador actual guardados no endereço (`?pagina=…&separador=…`)
para sobreviverem a um "Atualizar" no browser.

Ao actualizar, o Streamlit começa uma sessão nova (o `session_state`
perde-se); o login já sobrevive por estar no endereço (`?session=…`),
e a página onde se estava passa a sobreviver pelo mesmo caminho.
"""

from __future__ import annotations

import re
import unicodedata

import streamlit as st


def slug(texto: str) -> str:
    """"Stock de sémen" → "stock-de-semen" (legível e seguro num URL)."""
    sem_acentos = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sem_acentos.lower()).strip("-")


def opcao_do_endereco(nome: str, opcoes) -> str | None:
    """A opção de `opcoes` cujo slug está em `?<nome>=`, ou None."""
    valor = st.query_params.get(nome)
    if not valor:
        return None
    return next((o for o in opcoes if slug(o) == valor), None)


def guardar_no_endereco(nome: str, opcao: str | None) -> None:
    """Escreve (ou remove, com None) `?<nome>=<slug>` — só se mudou, para
    não reescrever o endereço em cada rerun."""
    valor = slug(opcao) if opcao else None
    if st.query_params.get(nome) == valor:
        return
    if valor is None:
        st.query_params.pop(nome, None)
    else:
        st.query_params[nome] = valor
