"""Ambiente da API — tem de ser importado antes de qualquer `modules.*`.

Mesma proteção que `app.py` e `tests/conftest.py`: fora do Render, a API
liga-se SEMPRE à base de TESTE (`TEST_DATABASE_URL`), nunca à produção,
mesmo que haja uma `DATABASE_URL` no `.env` ou exportada na shell.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# `RENDER` é definida pelo próprio Render em todos os serviços.
IS_RENDER = bool(os.getenv("RENDER"))

if not IS_RENDER:
    load_dotenv(ROOT / ".env")
    _test_database_url = (os.getenv("TEST_DATABASE_URL") or "").strip()
    if _test_database_url:
        os.environ["DATABASE_URL"] = _test_database_url
    else:
        os.environ.pop("DATABASE_URL", None)

SESSION_COOKIE = "equicore_session"
SESSION_MAX_AGE = 30 * 24 * 3600  # igual ao `INTERVAL '30 days'` de user_sessions

FRONTEND_DIST = ROOT / "frontend" / "dist"
