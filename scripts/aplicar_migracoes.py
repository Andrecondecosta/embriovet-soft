"""Aplica as migrations (`migrations/*.sql`) antes de arrancar a app nova.

Na app antiga era o `app.py` (Streamlit) que o fazia no arranque; a app
nova (FastAPI) não as corre sozinha, por isso o `start.sh` chama isto
primeiro. Se falhar, sai com erro e o Render mantém a versão anterior.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import config  # noqa: E402,F401 — define a DATABASE_URL certa (teste fora do Render)
from migration_runner import run_migrations  # noqa: E402
from modules.db import get_connection  # noqa: E402

if __name__ == "__main__":
    with get_connection() as conn:
        run_migrations(conn, migrations_dir=str(ROOT / "migrations"))
    print("✅ Migrations aplicadas")
