"""Motor da simulação: base própria, relógio simulado, utilizadores, API e registos.

O "hoje" da app é sempre o dia real. Para simular dias a passar, no fim de
cada dia simulado TODAS as datas da base recuam um dia (`avancar_dia`).
Assim CURRENT_DATE / date.today() continuam certos para a app, e o mundo
comporta-se como se o tempo tivesse avançado.

Datas simuladas: o dia simulado `d` (0..N) corresponde a `INICIO + d`.
Na base, durante o dia `d`, "hoje" (real) = INICIO + d (simulado).
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # raiz do repositório
AQUI = Path(__file__).resolve().parent

# A base da simulação (local). backend.config força TEST_DATABASE_URL fora do Render.
_url_teste = next(l.split("=", 1)[1].strip() for l in (REPO / ".env").read_text().splitlines() if l.startswith("TEST_DATABASE_URL="))
SIM_URL = _url_teste.replace("/embriovet_test?", "/" + os.environ.get("SIM_DB", "embriovet_sim") + "?")
assert "localhost" in SIM_URL and "/embriovet_sim" in SIM_URL
SAIDA = AQUI / "saida" / os.environ.get("SIM_DB", "embriovet_sim")
SAIDA.mkdir(parents=True, exist_ok=True)
os.environ["TEST_DATABASE_URL"] = SIM_URL
os.environ["DATABASE_URL"] = SIM_URL
os.environ.pop("RENDER", None)
sys.path.insert(0, str(REPO))

import logging  # noqa: E402
import warnings  # noqa: E402

logging.disable(logging.WARNING)
warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from modules.db import get_connection  # noqa: E402
from modules.services.auth_service import criar_hash_password  # noqa: E402

INICIO = date(2027, 2, 1)  # 1.º dia simulado
HOJE_REAL = date.today()

# Tabelas com dados de referência que se mantêm entre simulações.
REFERENCIA = {"app_settings", "contentores", "schema_migrations", "alojamentos"}  # 40 boxes + 6 paddocks (8 lugares)


def sql(query, params=(), fetch=False):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            out = cur.fetchall() if fetch else None
        conn.commit()
    return out


def limpar_base():
    """Apaga os dados (menos as tabelas de referência)."""
    tabelas = [t for (t,) in sql("SELECT tablename FROM pg_tables WHERE schemaname = 'public'", fetch=True) if t not in REFERENCIA]
    sql("TRUNCATE " + ", ".join(tabelas) + " RESTART IDENTITY CASCADE")


_COLUNAS_DATA = None


def avancar_dia():
    """Fim do dia simulado: todas as datas recuam 1 dia (o mundo envelhece)."""
    global _COLUNAS_DATA
    if _COLUNAS_DATA is None:
        _COLUNAS_DATA = {}
        for t, c, tipo in sql(
            """SELECT table_name, column_name, data_type FROM information_schema.columns
               WHERE table_schema = 'public'
                 AND data_type IN ('date', 'timestamp without time zone', 'timestamp with time zone')
                 AND table_name NOT IN ('user_sessions', 'schema_migrations')""",
            fetch=True,
        ):
            _COLUNAS_DATA.setdefault(t, []).append(c)
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Restrições (ex.: saída >= entrada) continuam válidas: tudo recua junto.
            for t, cols in _COLUNAS_DATA.items():
                sets = ", ".join(f'"{c}" = "{c}" - INTERVAL \'1 day\'' for c in cols)
                cur.execute(f'UPDATE "{t}" SET {sets}')
            # Datas dentro do JSON do registo clínico (indução, tratamento marcado).
            cur.execute(
                """UPDATE registo_clinico SET dados = jsonb_set(dados, '{TX,inducao,data}',
                       to_jsonb(to_char((dados #>> '{TX,inducao,data}')::timestamp - INTERVAL '1 day', 'YYYY-MM-DD"T"HH24:MI:SS')))
                   WHERE dados #>> '{TX,inducao,data}' IS NOT NULL"""
            )
            cur.execute(
                """UPDATE registo_clinico SET dados = jsonb_set(dados, '{TX,marcar,data}',
                       to_jsonb(to_char((dados #>> '{TX,marcar,data}')::date - 1, 'YYYY-MM-DD')))
                   WHERE dados #>> '{TX,marcar,data}' IS NOT NULL"""
            )
        conn.commit()
    try:
        import streamlit as st

        st.cache_data.clear()
    except Exception:
        pass


class Relogio:
    def __init__(self):
        self.d = 0

    @property
    def hoje(self) -> date:
        """Data simulada de hoje."""
        return INICIO + timedelta(days=self.d)

    def real(self, dia_simulado: date) -> date:
        """Data a usar na app (real) para um dia simulado."""
        return HOJE_REAL + (dia_simulado - self.hoje)

    def simulado(self, dia_real: date) -> date:
        return self.hoje + (dia_real - HOJE_REAL)


RELOGIO = Relogio()


class Log:
    """Registos em JSONL: ações de cada pessoa, erros da API, verdade do mundo."""

    def __init__(self):
        self.f = {n: open(SAIDA / f"{n}.jsonl", "a") for n in ("acoes", "erros", "verdade", "notas")}

    def __call__(self, _ficheiro, **dados):
        dados = {"dia": RELOGIO.d, "data": RELOGIO.hoje.isoformat(), **dados}
        self.f[_ficheiro].write(json.dumps(dados, default=str, ensure_ascii=False) + "\n")
        self.f[_ficheiro].flush()


LOG = Log()


class Pessoa:
    """Uma pessoa da clínica: utilizador próprio na app e um cliente da API.

    `self.api(metodo, caminho, json=...)` devolve (status, corpo) e regista
    erros (status >= 400) em saida/erros.jsonl com o nome da pessoa.
    `self.nota(texto)` regista uma observação da pessoa (o que achou da app).
    `self.memoria` é a memória privada da pessoa (não partilhada).
    """

    nome = "pessoa"
    nivel = "Gestor"

    def __init__(self, mundo):
        self.mundo = mundo
        self.memoria: dict = {}
        self.username = f"sim_{self.nome}"
        sql(
            """INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo, must_change_password)
               VALUES (%s, %s, %s, %s, TRUE, FALSE) ON CONFLICT (username) DO NOTHING""",
            (self.username, self.nome, criar_hash_password("segredo123"), self.nivel),
        )
        self.c = TestClient(app)
        assert self.c.post("/api/auth/login", json={"username": self.username, "password": "segredo123"}).status_code == 200

    def api(self, metodo, caminho, json=None, params=None):
        t0 = time.time()
        r = self.c.request(metodo, "/api" + caminho, json=json, params=params)
        try:
            corpo = r.json()
        except Exception:
            corpo = r.content[:200] if r.headers.get("content-type", "").startswith("text") else None
        if r.status_code == 401:  # sessão expirada → entra outra vez
            self.c.post("/api/auth/login", json={"username": self.username, "password": "segredo123"})
            return self.api(metodo, caminho, json=json, params=params)
        if r.status_code >= 400:
            LOG("erros", pessoa=self.nome, metodo=metodo, caminho=caminho, status=r.status_code, corpo=corpo, pedido=json)
        LOG("acoes", pessoa=self.nome, metodo=metodo, caminho=caminho.split("?")[0], status=r.status_code, ms=int((time.time() - t0) * 1000))
        return r.status_code, corpo

    def nota(self, texto, **extra):
        LOG("notas", pessoa=self.nome, texto=texto, **extra)

    def dia(self, relogio: Relogio):
        """Chamado uma vez por dia simulado. A implementar por cada pessoa."""
        raise NotImplementedError
