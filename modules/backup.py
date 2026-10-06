"""Cópia de segurança dos dados (Definições → Cópia de segurança) e
restauro a partir dela (`restaurar_backup.py`, linha de comandos).

Formato: ZIP com um CSV por tabela (`tabelas/<tabela>.csv`, gerado com
`COPY ... TO STDOUT WITH CSV HEADER`, o formato nativo do PostgreSQL) e
um `manifest.json` com a data, as tabelas, as colunas e o nº de linhas.
Não usa `pg_dump` (não existe no servidor do Render) — só o psycopg2.

O restauro assume uma base com o esquema já criado pelas migrações da
app (arrancar a app uma vez cria-o): esvazia as tabelas e volta a
carregá-las pela ordem das chaves estrangeiras.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime

# Fora da cópia: sessões de login (temporárias; restaurá-las não serve
# para nada e seriam tokens válidos dentro de um ficheiro).
TABELAS_EXCLUIDAS = {"user_sessions"}
# Fica na cópia (para referência), mas não se restaura: a base de
# destino já tem as suas próprias migrações aplicadas.
TABELAS_NAO_RESTAURAR = {"schema_migrations"}

VERSAO_FORMATO = 1


def _ident(nome: str) -> str:
    """Identificador SQL entre aspas (nomes vêm do catálogo, mas nunca
    se interpola texto cru numa query)."""
    return '"' + nome.replace('"', '""') + '"'


def listar_tabelas(cur) -> list:
    cur.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )
    return [r[0] for r in cur.fetchall() if r[0] not in TABELAS_EXCLUIDAS]


def _colunas(cur, tabela: str) -> list:
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (tabela,),
    )
    return [r[0] for r in cur.fetchall()]


def ordem_por_dependencias(cur, tabelas) -> list:
    """Ordena as tabelas para que cada uma venha depois das que ela
    referencia (chaves estrangeiras). Auto-referências (ex.:
    `usuarios.created_by`) não contam — um COPY só verifica as FKs no
    fim da instrução."""
    tabelas = list(tabelas)
    cur.execute(
        """
        SELECT conrelid::regclass::text, confrelid::regclass::text
        FROM pg_constraint
        WHERE contype = 'f' AND connamespace = 'public'::regnamespace
        """
    )
    depende = {t: set() for t in tabelas}
    for filha, mae in cur.fetchall():
        filha, mae = filha.strip('"'), mae.strip('"')
        if filha in depende and mae in depende and filha != mae:
            depende[filha].add(mae)

    ordem, feitas = [], set()
    while len(ordem) < len(tabelas):
        prontas = sorted(t for t in tabelas if t not in feitas and depende[t] <= feitas)
        if not prontas:  # ciclo — não devia acontecer; segue por ordem alfabética
            prontas = sorted(t for t in tabelas if t not in feitas)[:1]
        for t in prontas:
            ordem.append(t)
            feitas.add(t)
    return ordem


def contar_linhas(conn) -> dict:
    """{tabela: nº de linhas} — para mostrar o que vai na cópia. Uma só
    query (corre em cada visita às Definições: `st.tabs` renderiza
    todos os separadores)."""
    with conn.cursor() as cur:
        tabelas = listar_tabelas(cur)
        if not tabelas:
            return {}
        cur.execute("SELECT " + ", ".join(f"(SELECT COUNT(*) FROM {_ident(t)})" for t in tabelas))
        return dict(zip(tabelas, (int(n) for n in cur.fetchone())))


def gerar_backup_zip(conn, criado_por: str | None = None) -> bytes:
    """ZIP com todas as tabelas (CSV) + manifest. Lê tudo numa única
    transacção REPEATABLE READ, para a cópia ser coerente mesmo que
    alguém esteja a gravar dados ao mesmo tempo."""
    buffer = io.BytesIO()
    manifest = {
        "formato": VERSAO_FORMATO,
        "app": "embriovet",
        "criado_em": datetime.now().isoformat(timespec="seconds"),
        "criado_por": criado_por,
        "tabelas": {},
    }
    nivel_anterior = conn.isolation_level
    conn.rollback()
    conn.set_session(isolation_level="REPEATABLE READ", readonly=True)
    try:
        with conn.cursor() as cur, zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for t in listar_tabelas(cur):
                dados = io.StringIO()
                cur.copy_expert(f"COPY (SELECT * FROM {_ident(t)}) TO STDOUT WITH CSV HEADER", dados)
                texto = dados.getvalue()
                linhas = max(0, sum(1 for _ in csv.reader(io.StringIO(texto))) - 1)
                zf.writestr(f"tabelas/{t}.csv", texto)
                manifest["tabelas"][t] = {"linhas": linhas, "colunas": _colunas(cur, t)}
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            zf.writestr("LEIA-ME.txt", _LEIA_ME)
        conn.rollback()
    finally:
        conn.set_session(isolation_level=nivel_anterior, readonly=False)
    return buffer.getvalue()


def ler_manifest(zip_bytes: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        return json.loads(zf.read("manifest.json"))


def restaurar_backup_zip(conn, zip_bytes: bytes) -> dict:
    """Substitui os dados da base `conn` pelos da cópia. Tudo numa só
    transacção: ou fica tudo restaurado, ou nada muda.

    Devolve `{tabela: linhas restauradas}`. Lança `ValueError` se a cópia
    tiver colunas que a base de destino não tem (esquema mais antigo —
    arrancar a versão actual da app aplica as migrações em falta)."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        if manifest.get("formato") != VERSAO_FORMATO:
            raise ValueError(f"Formato de cópia desconhecido: {manifest.get('formato')}")
        ficheiros = {t: zf.read(f"tabelas/{t}.csv").decode("utf-8") for t in manifest["tabelas"]}

    resultado = {}
    with conn.cursor() as cur:
        destino = set(listar_tabelas(cur))
        a_restaurar = [t for t in ficheiros if t in destino and t not in TABELAS_NAO_RESTAURAR]
        em_falta = sorted(set(ficheiros) - destino - TABELAS_NAO_RESTAURAR)
        if em_falta:
            raise ValueError(f"A base de destino não tem as tabelas: {', '.join(em_falta)}")

        for t in a_restaurar:
            cabecalho = next(csv.reader(io.StringIO(ficheiros[t])), [])
            extra = sorted(set(cabecalho) - set(_colunas(cur, t)))
            if extra:
                raise ValueError(f"Tabela {t}: colunas da cópia que não existem no destino: {', '.join(extra)}")

        cur.execute("TRUNCATE " + ", ".join(_ident(t) for t in a_restaurar) + " RESTART IDENTITY CASCADE")
        for t in ordem_por_dependencias(cur, a_restaurar):
            cabecalho = next(csv.reader(io.StringIO(ficheiros[t])), [])
            if not cabecalho:
                resultado[t] = 0
                continue
            cols = ", ".join(_ident(c) for c in cabecalho)
            cur.copy_expert(f"COPY {_ident(t)} ({cols}) FROM STDIN WITH CSV HEADER", io.StringIO(ficheiros[t]))
            resultado[t] = cur.rowcount

        # Sequências (ids automáticos) a continuar depois do maior id restaurado.
        cur.execute(
            """
            SELECT table_name, column_name, pg_get_serial_sequence(quote_ident(table_name), column_name)
            FROM information_schema.columns
            WHERE table_schema = 'public' AND pg_get_serial_sequence(quote_ident(table_name), column_name) IS NOT NULL
            """
        )
        for t, col, seq in cur.fetchall():
            if t in a_restaurar:
                cur.execute(
                    f"SELECT setval(%s, COALESCE((SELECT MAX({_ident(col)}) FROM {_ident(t)}), 0) + 1, false)",
                    (seq,),
                )
    conn.commit()
    return resultado


_LEIA_ME = """Cópia de segurança do Embriovet
================================

Este ficheiro contém TODOS os dados da aplicação (um CSV por tabela, em
tabelas/), incluindo os utilizadores (com as palavras-passe encriptadas).
Guarde-o num sítio seguro e não o partilhe.

- manifest.json: data da cópia, tabelas e número de linhas.
- Os CSV abrem no Excel, mas para repor os dados use o script
  restaurar_backup.py do projeto (ver instruções no próprio script).
"""
