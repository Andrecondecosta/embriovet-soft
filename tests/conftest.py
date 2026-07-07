"""Configuração comum aos testes: carrega o .env e coloca /app no sys.path."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")
os.environ.setdefault("DATABASE_URL", os.getenv("DATABASE_URL", ""))
