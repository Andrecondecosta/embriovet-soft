#!/usr/bin/env python3
"""
Script de Importação de Dados do CSV
Importa base_stock_inicial.csv para o banco de dados PostgreSQL
"""

import pandas as pd
import psycopg2
from dotenv import load_dotenv
import os
from datetime import datetime

# Carregar variáveis de ambiente
load_dotenv('/app/.env')

def get_connection():
    return psycopg2.connect(
        dbname=os.getenv('DB_NAME', 'embriovet'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '123'),
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432')
    )

def criar_proprietario_padrao():
    """Cria o proprietário padrão 'Sem proprietário'"""
    print("📋 Criando proprietário padrão...")
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            INSERT INTO dono (nome, contato, email)
            VALUES ('Sem proprietário', '', '')
            ON CONFLICT DO NOTHING
            RETURNING id;
        """)
        
        result = cur.fetchone()
        if result:
            proprietario_id = result[0]
            print(f"✅ Proprietário padrão criado com ID: {proprietario_id}")
        else:
            # Já existe, buscar ID
            cur.execute("SELECT id FROM dono WHERE nome = 'Sem proprietário'")
            proprietario_id = cur.fetchone()[0]
            print(f"✅ Proprietário padrão já existe com ID: {proprietario_id}")
        
        conn.commit()
        cur.close()
        conn.close()
        return proprietario_id
    except Exception as e:
        print(f"❌ Erro ao criar proprietário: {e}")
        conn.rollback()
        cur.close()
        conn.close()
        return None

def importar_stock(csv_file, proprietario_padrao_id):
    """Importa dados do CSV para o banco"""
    print(f"\n📂 Lendo arquivo: {csv_file}")
    
    # Ler CSV
    df = pd.read_csv(csv_file)
    print(f"✅ {len(df)} registros encontrados no CSV")
    
    # Mostrar colunas
    print(f"📊 Colunas: {list(df.columns)}")
    
    conn = get_connection()
    cur = conn.cursor()
    
    importados = 0
    erros = 0
    
    print("\n🔄 Importando dados...")
    
    for idx, row in df.iterrows():
        try:
            garanhao = row['Garanhão'] if pd.notna(row['Garanhão']) else 'Desconhecido'
            data_embriovet = row['Data de Produção (Embriovet)'] if pd.notna(row['Data de Produção (Embriovet)']) else None
            origem_externa = row['Origem Externa / Referência'] if pd.notna(row['Origem Externa / Referência']) else None
            palhetas_produzidas = int(row['Palhetas Produzidas']) if pd.notna(row['Palhetas Produzidas']) else 0
            qualidade = float(row['Qualidade (%)']) if pd.notna(row['Qualidade (%)']) else None
            motilidade = float(row['Motilidade (%)']) if pd.notna(row['Motilidade (%)']) else None
            concentracao = float(row['Concentração (milhões/mL)']) if pd.notna(row['Concentração (milhões/mL)']) else None
            dose = str(row['Dose inseminante (DI)']) if pd.notna(row['Dose inseminante (DI)']) else None
            local_armazenagem = row['Local Armazenagem'] if pd.notna(row['Local Armazenagem']) else None
            certificado = row['Certificado'] if pd.notna(row['Certificado']) else None
            existencia_atual = int(row['Existência Atual']) if pd.notna(row['Existência Atual']) else 0
            observacoes = row['Observações'] if pd.notna(row['Observações']) else None
            
            # Inserir no banco
            cur.execute("""
                INSERT INTO estoque_dono (
                    garanhao, dono_id, data_embriovet, origem_externa,
                    palhetas_produzidas, qualidade, concentracao, motilidade,
                    local_armazenagem, certificado, dose, observacoes,
                    quantidade_inicial, existencia_atual
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                garanhao, proprietario_padrao_id, data_embriovet, origem_externa,
                palhetas_produzidas, qualidade, concentracao, motilidade,
                local_armazenagem, certificado, dose, observacoes,
                palhetas_produzidas, existencia_atual
            ))
            
            importados += 1
            
            if (idx + 1) % 100 == 0:
                print(f"   ✅ {idx + 1} registros processados...")
                conn.commit()
                
        except Exception as e:
            print(f"   ❌ Erro no registro {idx + 1}: {e}")
            erros += 1
            continue
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"\n📊 RESUMO DA IMPORTAÇÃO:")
    print(f"   ✅ Importados: {importados}")
    print(f"   ❌ Erros: {erros}")
    print(f"   📦 Total: {len(df)}")
    
    return importados, erros

def main():
    print("="*60)
    print("  🐴 IMPORTAÇÃO DE DADOS - EMBRIOVET GESTOR")
    print("="*60)
    
    # 1. Criar proprietário padrão
    proprietario_id = criar_proprietario_padrao()
    
    if not proprietario_id:
        print("❌ Não foi possível criar proprietário padrão. Abortando.")
        return
    
    # 2. Importar stock
    csv_file = '/tmp/base_stock_inicial.csv'
    
    if not os.path.exists(csv_file):
        print(f"❌ Arquivo não encontrado: {csv_file}")
        return
    
    importados, erros = importar_stock(csv_file, proprietario_id)
    
    print("\n" + "="*60)
    print("  🎉 IMPORTAÇÃO CONCLUÍDA!")
    print("="*60)
    print(f"\n✅ {importados} registros importados com sucesso!")
    print(f"⚠️  Todos os registros foram atribuídos a 'Sem proprietário'")
    print(f"📝 Você pode editar os proprietários no sistema depois")
    print("\n🌐 Acesse: http://localhost:8501")
    print("="*60)

if __name__ == "__main__":
    main()
