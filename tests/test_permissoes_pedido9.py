"""Testes de `verificar_permissao` — sanity antes do Pedido 9 (user_repo).

O user pediu 2-3 testes simples de permissões:
- admin vê Utilizadores
- não-admin não vê Utilizadores
"""
from __future__ import annotations

from unittest.mock import patch

import streamlit as st

from modules.services.auth_service import verificar_permissao


def test_verificar_permissao_admin_ve_utilizadores():
    with patch.dict(st.session_state, {"user": {"nivel": "Administrador"}}):
        assert verificar_permissao("Administrador") is True
        assert verificar_permissao("Gestor") is True
        assert verificar_permissao("Visualizador") is True


def test_verificar_permissao_gestor_nao_ve_utilizadores():
    with patch.dict(st.session_state, {"user": {"nivel": "Gestor"}}):
        assert verificar_permissao("Administrador") is False  # não vê Utilizadores
        assert verificar_permissao("Gestor") is True
        assert verificar_permissao("Visualizador") is True


def test_verificar_permissao_visualizador_so_ve_visualizador():
    with patch.dict(st.session_state, {"user": {"nivel": "Visualizador"}}):
        assert verificar_permissao("Administrador") is False
        assert verificar_permissao("Gestor") is False
        assert verificar_permissao("Visualizador") is True


def test_verificar_permissao_sem_login_retorna_false():
    # Garantir que não há user no session_state
    if "user" in st.session_state:
        del st.session_state["user"]
    assert verificar_permissao("Administrador") is False
    assert verificar_permissao("Visualizador") is False
