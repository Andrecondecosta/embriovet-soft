#!/usr/bin/env python3
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME", "embriovet"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "123"),
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432")
)

cur = conn.cursor()

# Verificar estrutura das tabelas
tables = ['transferencias', 'transferencias_externas', 'inseminacoes']

for table in tables:
    print(f"\n{'='*60}")
    print(f"Tabela: {table}")
    print('='*60)
    try:
        cur.execute(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = '{table}'
            ORDER BY ordinal_position
        """)
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
conn.close()
