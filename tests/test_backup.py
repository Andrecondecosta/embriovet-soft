"""Testes da cópia de segurança: ciclo completo gerar → restaurar numa
base nova → comparar.

A base de destino é uma base temporária criada no mesmo servidor local
(esquema copiado da base de teste com `pg_dump --schema-only`) e
apagada no fim — a base de teste nunca é substituída.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import time
import zipfile
from urllib.parse import urlparse, urlunparse

import psycopg2
import pytest

from modules.backup import (
    TABELAS_EXCLUIDAS, TABELAS_NAO_RESTAURAR, gerar_backup_zip, ler_manifest, restaurar_backup_zip,
)

URL_TESTE = os.getenv("DATABASE_URL", "").strip()


def _url_com_base(url: str, base: str) -> str:
    p = urlparse(url)
    return urlunparse(p._replace(path=f"/{base}"))


@pytest.fixture(scope="module")
def backup_zip():
    conn = psycopg2.connect(URL_TESTE)
    try:
        yield gerar_backup_zip(conn, criado_por="pytest")
    finally:
        conn.close()


@pytest.fixture(scope="module")
def base_destino():
    """Base vazia com o mesmo esquema da base de teste."""
    if not shutil.which("pg_dump") or not shutil.which("psql"):
        pytest.skip("pg_dump/psql não disponíveis")
    assert urlparse(URL_TESTE).hostname in ("localhost", "127.0.0.1"), "só corre contra um servidor local"
    nome = f"embriovet_backup_test_{int(time.time())}"
    admin = psycopg2.connect(URL_TESTE)
    admin.autocommit = True
    admin.cursor().execute(f'CREATE DATABASE "{nome}"')
    url_destino = _url_com_base(URL_TESTE, nome)
    try:
        esquema = subprocess.run(
            ["pg_dump", "--schema-only", "--no-owner", "--no-privileges", URL_TESTE],
            check=True, capture_output=True, text=True,
        ).stdout
        # pg_dump mais recente do que o servidor (ex.: 17 vs 15) emite este
        # SET, que o servidor não conhece.
        esquema = "\n".join(l for l in esquema.splitlines() if not l.startswith("SET transaction_timeout"))
        subprocess.run(["psql", "-q", "-v", "ON_ERROR_STOP=1", url_destino],
                       input=esquema, check=True, capture_output=True, text=True)
        yield url_destino
    finally:
        # Apaga sempre a base temporária, mesmo se a preparação falhar.
        admin.cursor().execute(f'DROP DATABASE IF EXISTS "{nome}" WITH (FORCE)')
        admin.close()


def _contagens(url: str) -> dict:
    conn = psycopg2.connect(url)
    try:
        cur = conn.cursor()
        cur.execute("""SELECT table_name FROM information_schema.tables
                       WHERE table_schema='public' AND table_type='BASE TABLE'""")
        out = {}
        for (t,) in cur.fetchall():
            cur.execute(f'SELECT COUNT(*) FROM "{t}"')
            out[t] = cur.fetchone()[0]
        return out
    finally:
        conn.close()


def test_conteudo_do_zip(backup_zip):
    with zipfile.ZipFile(io.BytesIO(backup_zip)) as zf:
        nomes = set(zf.namelist())
    assert {"manifest.json", "LEIA-ME.txt", "tabelas/estoque_dono.csv", "tabelas/dono.csv"} <= nomes
    manifest = ler_manifest(backup_zip)
    assert manifest["criado_por"] == "pytest"
    assert not (set(manifest["tabelas"]) & TABELAS_EXCLUIDAS)
    origem = _contagens(URL_TESTE)
    for t, info in manifest["tabelas"].items():
        assert info["linhas"] == origem[t], t


def test_ligacao_volta_ao_normal_depois_do_backup():
    conn = psycopg2.connect(URL_TESTE)
    try:
        gerar_backup_zip(conn)
        assert conn.readonly is False
        cur = conn.cursor()
        cur.execute("CREATE TEMP TABLE _t_backup (x int)")  # escrita possível
        conn.rollback()
    finally:
        conn.close()


def test_restaurar_numa_base_nova_e_comparar(backup_zip, base_destino):
    conn = psycopg2.connect(base_destino)
    try:
        resultado = restaurar_backup_zip(conn, backup_zip)
    finally:
        conn.close()

    manifest = ler_manifest(backup_zip)
    destino = _contagens(base_destino)
    for t, info in manifest["tabelas"].items():
        if t in TABELAS_NAO_RESTAURAR:
            continue
        assert resultado[t] == info["linhas"], t
        assert destino[t] == info["linhas"], t

    # Conteúdo igual linha a linha (lotes e proprietários).
    for tabela in ("estoque_dono", "dono"):
        linhas = []
        for url in (URL_TESTE, base_destino):
            c = psycopg2.connect(url)
            cur = c.cursor()
            cur.execute(f'SELECT * FROM "{tabela}" ORDER BY id')
            linhas.append(cur.fetchall())
            c.close()
        assert linhas[0] == linhas[1], tabela


def test_restaurar_duas_vezes_e_ids_continuam(backup_zip, base_destino):
    conn = psycopg2.connect(base_destino)
    try:
        restaurar_backup_zip(conn, backup_zip)  # repetir não duplica
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), COALESCE(MAX(id), 0) FROM dono")
        total, maior = cur.fetchone()
        assert total == ler_manifest(backup_zip)["tabelas"]["dono"]["linhas"]
        # A sequência continua depois do maior id restaurado (sem colisões).
        cur.execute("INSERT INTO dono (nome) VALUES ('_TEST_BACKUP_SEQ') RETURNING id")
        assert cur.fetchone()[0] > maior
        conn.rollback()
    finally:
        conn.close()


def test_restaurar_falha_sem_alterar_nada(backup_zip, base_destino):
    """Uma cópia com uma coluna que o destino não tem é recusada antes
    de tocar nos dados."""
    with zipfile.ZipFile(io.BytesIO(backup_zip)) as zf:
        ficheiros = {n: zf.read(n) for n in zf.namelist()}
    csv_dono = ficheiros["tabelas/dono.csv"].decode("utf-8").split("\n", 1)
    ficheiros["tabelas/dono.csv"] = (csv_dono[0] + ",coluna_inexistente\n" + csv_dono[1]).encode("utf-8")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for n, d in ficheiros.items():
            zf.writestr(n, d)

    antes = _contagens(base_destino)
    conn = psycopg2.connect(base_destino)
    try:
        with pytest.raises(ValueError, match="coluna_inexistente"):
            restaurar_backup_zip(conn, buf.getvalue())
        conn.rollback()
    finally:
        conn.close()
    assert _contagens(base_destino) == antes
