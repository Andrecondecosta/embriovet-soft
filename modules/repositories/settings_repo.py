"""Repository de app_settings — extração pura de `app.py` (Pedido 9).

8 funções copiadas bit-for-bit. Nenhuma alteração de lógica.
"""

from __future__ import annotations

import logging

from modules.db import get_connection

logger = logging.getLogger(__name__)


def get_app_settings():
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, company_name, logo_base64, primary_color,
                       is_initialized, show_initial_credentials, theme_key, language, welcome_completed
                FROM app_settings
                WHERE id = 1
                ORDER BY id
                LIMIT 1
                """
            )
            row = cur.fetchone()
            cur.close()
        if not row:
            return None
        return {
            "id": row[0],
            "company_name": row[1],
            "logo_base64": row[2],
            "primary_color": row[3],
            "is_initialized": row[4],
            "show_initial_credentials": row[5],
            "theme_key": row[6],
            "language": row[7],
            "welcome_completed": row[8],
        }
    except Exception as e:
        logger.error(f"Erro ao carregar app_settings: {e}")
        return None


def ensure_app_settings():
    settings = get_app_settings()
    if settings:
        return settings
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO app_settings (id, company_name, theme_key, language, welcome_completed)
                SELECT 1, 'Sistema', 'blue', 'pt-PT', FALSE
                WHERE NOT EXISTS (SELECT 1 FROM app_settings);
                """
            )
            conn.commit()
            cur.close()
        return get_app_settings()
    except Exception as e:
        logger.error(f"Erro ao criar app_settings: {e}")
        return None


def save_app_settings(settings_id, company_name, logo_base64, primary_color, theme_key):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE app_settings
            SET company_name = %s,
                logo_base64 = %s,
                primary_color = %s,
                theme_key = %s,
                is_initialized = TRUE,
                updated_at = now()
            WHERE id = %s
            """,
            (company_name, logo_base64, primary_color, theme_key, settings_id),
        )
        conn.commit()
        cur.close()


def finalize_app_settings(settings_id, company_name, logo_base64, primary_color, theme_key):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE app_settings
            SET company_name = %s,
                logo_base64 = %s,
                primary_color = %s,
                theme_key = %s,
                is_initialized = TRUE,
                show_initial_credentials = FALSE,
                updated_at = now()
            WHERE id = %s
            """,
            (company_name, logo_base64, primary_color, theme_key, settings_id),
        )
        conn.commit()
        cur.close()


def update_show_initial_credentials(value: bool):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE app_settings SET show_initial_credentials = %s, updated_at = now()",
            (value,),
        )
        conn.commit()
        cur.close()


def update_language(language: str):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE app_settings SET language = %s, updated_at = now()",
            (language,),
        )
        conn.commit()
        cur.close()


def update_branding_settings(company_name, logo_base64, language, primary_color):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE app_settings
            SET company_name = %s,
                logo_base64 = %s,
                language = %s,
                primary_color = %s,
                updated_at = now()
            WHERE id = 1
            """,
            (company_name, logo_base64, language, primary_color),
        )
        conn.commit()
        cur.close()


def update_welcome_completed(completed=True):
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE app_settings SET welcome_completed = %s WHERE id = 1",
                (completed,),
            )
            conn.commit()
            cur.close()
        return True
    except Exception as e:
        logger.error(f"Erro ao atualizar welcome_completed: {e}")
        return False
