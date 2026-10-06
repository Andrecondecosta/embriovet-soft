"""Repor os dados a partir de uma cópia de segurança (ZIP descarregado em
Definições → Cópia de segurança).

ATENÇÃO: SUBSTITUI todos os dados da base de destino pelos da cópia.

Uso:
    venv/bin/python restaurar_backup.py <copia.zip> --url "<postgresql://...>"

Passos para recuperar os dados numa base nova (ex.: no Render):
  1. Criar a base nova e apontar a app para ela (DATABASE_URL).
  2. Arrancar a app uma vez — as migrações criam as tabelas.
  3. Correr este script com o URL externo dessa base.

O URL tem de ser dado explicitamente (não se lê o .env), e é preciso
escrever o nome do servidor para confirmar — para nunca se restaurar
por engano na base errada.
"""

from __future__ import annotations

import argparse
import sys
from urllib.parse import urlparse

import psycopg2

from modules.backup import ler_manifest, restaurar_backup_zip


def main() -> int:
    parser = argparse.ArgumentParser(description="Repor dados a partir de uma cópia de segurança.")
    parser.add_argument("ficheiro", help="ZIP da cópia de segurança")
    parser.add_argument("--url", required=True, help="URL da base de destino (postgresql://...)")
    args = parser.parse_args()

    with open(args.ficheiro, "rb") as f:
        dados = f.read()
    manifest = ler_manifest(dados)
    servidor = urlparse(args.url).hostname or "?"

    print(f"Cópia de {manifest['criado_em']} (feita por {manifest.get('criado_por') or '—'})")
    for tabela, info in manifest["tabelas"].items():
        print(f"  {tabela:<28} {info['linhas']:>7} linhas")
    print(f"\nBase de destino: {servidor}")
    print("TODOS os dados actuais dessa base vão ser SUBSTITUÍDOS pelos da cópia.")
    if input(f"Para confirmar, escreva o nome do servidor ({servidor}): ").strip() != servidor:
        print("Cancelado — nada foi alterado.")
        return 1

    conn = psycopg2.connect(args.url)
    try:
        resultado = restaurar_backup_zip(conn, dados)
    except Exception as e:
        conn.rollback()
        print(f"Erro — nada foi alterado: {e}")
        return 2
    finally:
        conn.close()

    print("\nRestauro concluído:")
    for tabela, n in resultado.items():
        print(f"  {tabela:<28} {n:>7} linhas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
