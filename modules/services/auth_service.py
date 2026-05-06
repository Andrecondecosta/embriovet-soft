"""Serviço de autenticação e gestão de utilizadores."""

import json
import logging

import bcrypt
import pandas as pd
import streamlit as st

from modules.db import get_connection
from modules.i18n import t

logger = logging.getLogger(__name__)


# ── Password helpers ──────────────────────────────────────────────────────────
def criar_hash_password(password: str) -> str:
    """Cria hash da password usando bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_password(password: str, password_hash: str) -> bool:
    """Verifica se a password corresponde ao hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


# ── Bootstrap admin ───────────────────────────────────────────────────────────
def ensure_admin_user_exists(username: str, password: str) -> None:
    """Cria utilizador admin inicial se ainda não existir nenhum utilizador."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM usuarios")
            total = cur.fetchone()[0] or 0
            if total > 0:
                cur.close()
                return

            password_hash = criar_hash_password(password)
            cur.execute(
                """
                INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo, must_change_password)
                VALUES (%s, %s, %s, %s, TRUE, TRUE)
                """,
                (username, "Administrador", password_hash, "Administrador"),
            )
            conn.commit()
            cur.close()
            logger.info("Utilizador admin inicial criado")
    except Exception as e:
        logger.error(f"Erro ao criar admin inicial: {e}")


# ── Autenticação ──────────────────────────────────────────────────────────────
def autenticar_usuario(username: str, password: str):
    """Autentica utilizador e retorna seus dados."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, username, nome_completo, password_hash, nivel, ativo, must_change_password
                FROM usuarios
                WHERE username = %s AND ativo = TRUE
                """,
                (username,),
            )
            resultado = cur.fetchone()
            cur.close()

            if not resultado:
                return None

            user_id, username, nome, pwd_hash, nivel, ativo, must_change_password = resultado

            if verificar_password(password, pwd_hash):
                cur = conn.cursor()
                cur.execute(
                    "UPDATE usuarios SET last_login = CURRENT_TIMESTAMP WHERE id = %s",
                    (user_id,),
                )
                conn.commit()
                cur.close()

                return {
                    "id": user_id,
                    "username": username,
                    "nome": nome,
                    "nivel": nivel,
                    "must_change_password": must_change_password,
                }

            return None
    except Exception as e:
        logger.error(f"Erro ao autenticar: {e}")
        return None


# ── Gestão de utilizadores ────────────────────────────────────────────────────
def carregar_usuarios() -> pd.DataFrame:
    """Carrega lista de utilizadores."""
    try:
        with get_connection() as conn:
            df = pd.read_sql_query(
                """
                SELECT id, username, nome_completo, nivel, ativo,
                       created_at, last_login
                FROM usuarios
                ORDER BY nivel, nome_completo
                """,
                conn,
            )
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar utilizadores: {e}")
        return pd.DataFrame()


def adicionar_usuario(username, nome_completo, password, nivel, created_by_id) -> bool:
    """Adiciona novo utilizador."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("SELECT id FROM usuarios WHERE username = %s", (username,))
            if cur.fetchone():
                st.error(t("error.username_exists"))
                return False

            password_hash = criar_hash_password(password)
            cur.execute(
                """
                INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo, created_by)
                VALUES (%s, %s, %s, %s, TRUE, %s)
                """,
                (username, nome_completo, password_hash, nivel, created_by_id),
            )
            conn.commit()
            cur.close()
            logger.info(f"Utilizador criado: {username} ({nivel})")
            return True
    except Exception as e:
        logger.error(f"Erro ao adicionar utilizador: {e}")
        st.error(f"Erro ao adicionar utilizador: {e}")
        return False


def alterar_password(user_id, nova_password) -> bool:
    """Altera password do utilizador."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            password_hash = criar_hash_password(nova_password)
            cur.execute(
                "UPDATE usuarios SET password_hash = %s WHERE id = %s",
                (password_hash, user_id),
            )
            conn.commit()
            cur.close()
            return True
    except Exception as e:
        logger.error(f"Erro ao alterar password: {e}")
        return False


def desativar_usuario(user_id) -> bool:
    """Desativa utilizador."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE usuarios SET ativo = FALSE WHERE id = %s", (user_id,))
            conn.commit()
            cur.close()
            return True
    except Exception as e:
        logger.error(f"Erro ao desativar utilizador: {e}")
        return False


def ativar_usuario(user_id) -> bool:
    """Ativa utilizador."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE usuarios SET ativo = TRUE WHERE id = %s", (user_id,))
            conn.commit()
            cur.close()
            return True
    except Exception as e:
        logger.error(f"Erro ao ativar utilizador: {e}")
        return False


# ── Sessões persistentes (BD) ─────────────────────────────────────────────────
def save_session_db(token: str, user: dict) -> None:
    """Guarda a sessão na BD (persiste após restart do servidor)."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_sessions (token, username, user_data, expires_at)
                    VALUES (%s, %s, %s, NOW() + INTERVAL '30 days')
                    ON CONFLICT (token) DO UPDATE SET expires_at = NOW() + INTERVAL '30 days'
                    """,
                    (token, user.get("username", ""), json.dumps(user)),
                )
                conn.commit()
    except Exception as e:
        logger.warning(f"save_session_db falhou: {e}")


def load_session_db(token: str):
    """Carrega a sessão da BD pelo token."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT user_data FROM user_sessions
                    WHERE token = %s AND expires_at > NOW()
                    """,
                    (token,),
                )
                row = cur.fetchone()
                if row:
                    return json.loads(row[0])
    except Exception as e:
        logger.warning(f"load_session_db falhou: {e}")
    return None


def delete_session_db(token: str) -> None:
    """Remove a sessão da BD (logout)."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM user_sessions WHERE token = %s", (token,))
                conn.commit()
    except Exception as e:
        logger.warning(f"delete_session_db falhou: {e}")


# ── Permissões ────────────────────────────────────────────────────────────────
def verificar_permissao(nivel_minimo: str) -> bool:
    """Verifica se o utilizador atual tem permissão mínima necessária."""
    if "user" not in st.session_state:
        return False

    user_nivel = st.session_state["user"]["nivel"]

    niveis = {
        "Administrador": 3,
        "Gestor": 2,
        "Visualizador": 1,
    }

    return niveis.get(user_nivel, 0) >= niveis.get(nivel_minimo, 0)
