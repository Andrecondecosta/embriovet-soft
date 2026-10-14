"""Endpoints que o ecrã de login precisa antes de haver sessão:
marca da empresa e traduções."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.i18n_web import WEB_TRANSLATIONS
from modules.i18n import TRANSLATIONS
from modules.repositories.settings_repo import get_app_settings
from modules.ui_kit import DEFAULT_PRIMARY_COLOR

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/settings/public")
def public_settings():
    s = get_app_settings() or {}
    return {
        "company_name": s.get("company_name") or "Sistema",
        "logo_base64": s.get("logo_base64"),
        "primary_color": s.get("primary_color") or DEFAULT_PRIMARY_COLOR,
        "language": s.get("language") or "pt-PT",
    }


@router.get("/i18n/{lang}")
def translations(lang: str):
    if lang not in TRANSLATIONS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_language")
    # pt-PT por baixo, como o `t()` da app atual faz para chaves em falta.
    return {
        **TRANSLATIONS["pt-PT"],
        **WEB_TRANSLATIONS["pt-PT"],
        **TRANSLATIONS[lang],
        **WEB_TRANSLATIONS.get(lang, {}),
    }
