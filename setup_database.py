#!/usr/bin/env python3
"""Script para configurar o banco de dados na primeira execução"""

import os
import psycopg2
from psycopg2 import sql
import sys

def criar_tabelas():
    """Cria todas as tabelas necessárias"""
    
    # Pegar credenciais do ambiente
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        print("❌ DATABASE_URL não configurada")
        return False
    
    try:
        # Conectar ao banco
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        print("✅ Conectado ao banco de dados")
        
        # Criar tabela de proprietários
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dono (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(255) UNIQUE NOT NULL,
                ativo BOOLEAN DEFAULT TRUE,
                email VARCHAR(255),
                telemovel VARCHAR(50),
                nome_completo VARCHAR(255),
                nif VARCHAR(50),
                morada TEXT,
                codigo_postal VARCHAR(20),
                cidade VARCHAR(100)
            )
        """)
        print("✅ Tabela 'dono' criada/verificada")
        
        # Criar tabela de estoque
        cur.execute("""
            CREATE TABLE IF NOT EXISTS estoque_dono (
                id SERIAL PRIMARY KEY,
                garanhao VARCHAR(255) NOT NULL,
                dono_id INTEGER REFERENCES dono(id) ON DELETE CASCADE,
                data_embriovet VARCHAR(100),
                origem_externa VARCHAR(255),
                palhetas_produzidas INTEGER DEFAULT 0,
                qualidade INTEGER DEFAULT 0,
                concentracao INTEGER DEFAULT 0,
                motilidade INTEGER DEFAULT 0,
                local_armazenagem VARCHAR(255),
                certificado VARCHAR(10),
                dose VARCHAR(100),
                observacoes TEXT,
                quantidade_inicial INTEGER DEFAULT 0,
                existencia_atual INTEGER DEFAULT 0,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                criado_por VARCHAR(100)
            )
        """)
        print("✅ Tabela 'estoque_dono' criada/verificada")
        
        # Adicionar colunas de auditoria se não existirem
        try:
            cur.execute("""
                ALTER TABLE estoque_dono 
                ADD COLUMN IF NOT EXISTS data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """)
            cur.execute("""
                ALTER TABLE estoque_dono 
                ADD COLUMN IF NOT EXISTS criado_por VARCHAR(100)
            """)
            conn.commit()
            print("✅ Colunas de auditoria verificadas/adicionadas")
        except Exception as e:
            print(f"⚠️ Aviso ao verificar colunas de auditoria: {e}")
            conn.rollback()
        
        # Criar tabela de contentores
        cur.execute("""
            CREATE TABLE IF NOT EXISTS contentores (
                id SERIAL PRIMARY KEY,
                codigo VARCHAR(50) UNIQUE NOT NULL,
                descricao TEXT,
                x INTEGER DEFAULT 100,
                y INTEGER DEFAULT 100,
                w INTEGER DEFAULT 150,
                h INTEGER DEFAULT 150,
                ativo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Tabela 'contentores' criada/verificada")
        
        # Criar contentor temporário padrão
        try:
            cur.execute("""
                INSERT INTO contentores (codigo, descricao, x, y, w, h, ativo)
                VALUES ('CT-TEMP', 'Contentor Temporário (migração)', 100, 100, 150, 150, TRUE)
                ON CONFLICT (codigo) DO NOTHING
            """)
            conn.commit()
            print("✅ Contentor temporário criado/verificado")
        except Exception as e:
            print(f"⚠️ Aviso ao criar contentor temporário: {e}")
            conn.rollback()
        
        # Adicionar colunas de localização estruturada ao estoque
        try:
            cur.execute("""
                ALTER TABLE estoque_dono 
                ADD COLUMN IF NOT EXISTS contentor_id INTEGER REFERENCES contentores(id) ON DELETE RESTRICT
            """)
            cur.execute("""
                ALTER TABLE estoque_dono 
                ADD COLUMN IF NOT EXISTS canister INTEGER CHECK (canister >= 1 AND canister <= 10)
            """)
            cur.execute("""
                ALTER TABLE estoque_dono 
                ADD COLUMN IF NOT EXISTS andar INTEGER CHECK (andar IN (1, 2))
            """)
            conn.commit()
            print("✅ Colunas de localização estruturada adicionadas")
        except Exception as e:
            print(f"⚠️ Aviso ao adicionar colunas de localização: {e}")
            conn.rollback()
        
        # Criar tabela de inseminações
        cur.execute("""
            CREATE TABLE IF NOT EXISTS inseminacoes (
                id SERIAL PRIMARY KEY,
                garanhao VARCHAR(255) NOT NULL,
                dono_id INTEGER REFERENCES dono(id) ON DELETE SET NULL,
                data_inseminacao DATE NOT NULL,
                egua VARCHAR(255) NOT NULL,
                protocolo VARCHAR(255),
                palhetas_gastas INTEGER DEFAULT 1
            )
        """)
        print("✅ Tabela 'inseminacoes' criada/verificada")
        
        # Criar tabela de transferências internas
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transferencias (
                id SERIAL PRIMARY KEY,
                stock_id INTEGER REFERENCES estoque_dono(id) ON DELETE SET NULL,
                proprietario_origem_id INTEGER REFERENCES dono(id) ON DELETE SET NULL,
                proprietario_destino_id INTEGER REFERENCES dono(id) ON DELETE SET NULL,
                quantidade INTEGER NOT NULL,
                data_transferencia TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Tabela 'transferencias' criada/verificada")
        
        # Criar tabela de transferências externas
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transferencias_externas (
                id SERIAL PRIMARY KEY,
                estoque_id INTEGER REFERENCES estoque_dono(id) ON DELETE SET NULL,
                proprietario_origem_id INTEGER REFERENCES dono(id) ON DELETE SET NULL,
                garanhao VARCHAR(255),
                destinatario_externo VARCHAR(255) NOT NULL,
                quantidade INTEGER NOT NULL,
                tipo VARCHAR(50),
                observacoes TEXT,
                data_transferencia TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Tabela 'transferencias_externas' criada/verificada")
        
        # Criar tabela de usuários
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                nome_completo VARCHAR(255),
                password_hash VARCHAR(255) NOT NULL,
                nivel VARCHAR(50) DEFAULT 'Visualizador',
                ativo BOOLEAN DEFAULT TRUE,
                created_by INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        """)
        print("✅ Tabela 'usuarios' criada/verificada")
        
        # Adicionar colunas se não existirem (para bancos já existentes)
        try:
            cur.execute("""
                ALTER TABLE usuarios 
                ADD COLUMN IF NOT EXISTS nome_completo VARCHAR(255)
            """)
            cur.execute("""
                ALTER TABLE usuarios 
                ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES usuarios(id) ON DELETE SET NULL
            """)
            cur.execute("""
                ALTER TABLE usuarios 
                ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """)
            cur.execute("""
                ALTER TABLE usuarios 
                ADD COLUMN IF NOT EXISTS last_login TIMESTAMP
            """)
            conn.commit()
            print("✅ Colunas adicionais verificadas/adicionadas")
        except Exception as e:
            print(f"⚠️ Aviso ao verificar colunas: {e}")
            conn.rollback()
        
        # Criar usuário admin padrão (senha: admin123)
        import bcrypt
        senha_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        cur.execute("""
            INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo)
            VALUES ('admin', 'Administrador', %s, 'Administrador', TRUE)
            ON CONFLICT (username) DO NOTHING
        """, (senha_hash,))
        print("✅ Usuário admin criado (username: admin, password: admin123)")
        
        conn.commit()
        cur.close()
        conn.close()
        
        print("\n🎉 Banco de dados configurado com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao configurar banco: {e}")
        return False

if __name__ == "__main__":
    sucesso = criar_tabelas()
    sys.exit(0 if sucesso else 1)