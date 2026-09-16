#!/usr/bin/env python3
from dotenv import load_dotenv

from modules.db import get_connection

load_dotenv()

# Verificar estrutura das tabelas
tables = ['transferencias', 'transferencias_externas', 'inseminacoes']

with get_connection() as conn:
    cur = conn.cursor()
    for table in tables:
        print(f"\n{'='*60}")
        print(f"Tabela: {table}")
        print('='*60)
        try:
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table,))
            columns = cur.fetchall()
            for col in columns:
                print(f"  {col[0]:<30} {col[1]}")

            # Contar registros
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"\nTotal de registros: {count}")

        except Exception as e:
            print(f"Erro: {e}")
    cur.close()
