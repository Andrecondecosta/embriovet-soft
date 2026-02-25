#!/usr/bin/env python3
"""
Script para adicionar campos à tabela dono
Execute este script antes de usar a aplicação
"""
import psycopg2
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def executar_migracao():
    """Executa o script SQL de migração"""
    try:
        # Conectar ao banco
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME", "embriovet"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "123"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
        )
        cur = conn.cursor()
        
        print("🔄 Conectado ao banco de dados...")
        print("🔄 Executando migração...")
        
        # Ler e executar o script SQL
        with open('/app/adicionar_campos_proprietarios.sql', 'r') as f:
            sql = f.read()
        
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
        conn.close()
        
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
