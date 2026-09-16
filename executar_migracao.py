#!/usr/bin/env python3
"""
Script para adicionar campos à tabela dono
Execute este script antes de usar a aplicação
"""
from pathlib import Path

from dotenv import load_dotenv

from modules.db import get_connection

# Carregar variáveis de ambiente
load_dotenv()

SQL_PATH = Path(__file__).resolve().parent / "adicionar_campos_proprietarios.sql"


def executar_migracao():
    """Executa o script SQL de migração"""
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            print("🔄 Conectado ao banco de dados...")
            print("🔄 Executando migração...")

            # Ler e executar o script SQL
            sql = SQL_PATH.read_text()

            cur.execute(sql)
            conn.commit()

            print("✅ Migração executada com sucesso!")
            print("\n📋 Verificando colunas adicionadas...")

            # Verificar colunas
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'dono'
                ORDER BY ordinal_position
            """)

            colunas = cur.fetchall()
            print("\n📌 Colunas da tabela 'dono':")
            for col in colunas:
                print(f"   - {col[0]} ({col[1]})")

            cur.close()

        print("\n✅ Tudo pronto! Pode iniciar a aplicação.")

    except Exception as e:
        print(f"❌ Erro ao executar migração: {e}")
        return False

    return True

if __name__ == "__main__":
    print("=" * 60)
    print("   MIGRAÇÃO: Adicionar campos à tabela dono")
    print("=" * 60)
    print()
    
    executar_migracao()
