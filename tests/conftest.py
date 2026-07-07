"""Configuração comum aos testes: carrega o .env e coloca /app no sys.path.

Isolamento contra produção:
    Se `TEST_DATABASE_URL` estiver definido no `.env`, força a variável
    `DATABASE_URL` (usada por `modules.db.get_connection`) a apontar para
    a base de teste antes de qualquer import da app. Caso contrário, os
    testes que dependem de BD são saltados com uma mensagem clara.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

_TEST_URL = (os.getenv("TEST_DATABASE_URL") or "").strip()
if _TEST_URL:
    # Sobrescreve `DATABASE_URL` para que o pool de conexões da app aponte
    # para a base de teste (nunca contra produção).
    os.environ["DATABASE_URL"] = _TEST_URL
else:
    # Sem TEST_DATABASE_URL: bloqueia todos os testes de integração para
    # evitar tocar em produção por engano.
    pytest.skip(
        "TEST_DATABASE_URL não configurada — configure em .env para "
        "correr os testes de integração (ver /app/tests/README.md).",
        allow_module_level=True,
    )
