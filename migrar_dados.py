# 🔄 Guia de Migração de Dados - Local → Render

## 📊 Quando Migrar?

**Migrar SE:**
- ✅ Você tem proprietários cadastrados localmente
- ✅ Você tem stock de sêmen cadastrado
- ✅ Você tem histórico de inseminações
- ✅ Você tem transferências registradas
- ✅ Você tem utilizadores criados (além do admin)

**NÃO migrar SE:**
- ❌ Banco local vazio ou apenas com dados de teste
- ❌ Quer começar do zero no Render
- ❌ Dados locais não são importantes

---

## 🎯 Opção 1: Migração Completa (Recomendado)

### Passo 1: Exportar Dados do Banco Local

No seu terminal **LOCAL**:

```bash
# Exportar banco completo
pg_dump -U postgres -d embriovet \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl \
  -f backup_embriovet.sql

# Verificar arquivo criado
ls -lh backup_embriovet.sql
```

### Passo 2: Obter URL Externa do Banco Render

1. Acesse: https://dashboard.render.com
2. Vá em seu banco: `embriovet-db`
3. Na seção "Connections", copie **"External Database URL"**
   - Exemplo: `postgresql://embriovet_db_user:senha@dpg-xxx.oregon-postgres.render.com:5432/embriovet_db`

### Passo 3: Importar Dados para o Render

No seu terminal **LOCAL**:

```bash
# Importar backup para o Render
psql [COLE AQUI a External Database URL] < backup_embriovet.sql

# Verificar importação
psql [COLE AQUI a External Database URL] -c "\dt"
```

**Deve mostrar:**
```
              List of relations
 Schema |         Name          | Type  |  Owner   
--------+-----------------------+-------+----------
 public | dono                  | table | ...
 public | estoque_dono          | table | ...
 public | inseminacoes          | table | ...
 public | transferencias        | table | ...
 public | transferencias_externas | table | ...
 public | usuarios              | table | ...
```

### Passo 4: Verificar Dados

```bash
# Verificar proprietários
psql [External URL] -c "SELECT id, nome FROM dono LIMIT 5;"

# Verificar stock
psql [External URL] -c "SELECT garanhao, COUNT(*) FROM estoque_dono GROUP BY garanhao;"

# Verificar utilizadores
psql [External URL] -c "SELECT username, nivel FROM usuarios;"
```

✅ **Pronto! Dados migrados.**

---

## 🎯 Opção 2: Migração Seletiva (Apenas Dados)

Se quiser migrar apenas os dados (não a estrutura):

### Passo 1: Exportar APENAS Dados

```bash
# Exportar só os dados (sem estrutura)
pg_dump -U postgres -d embriovet \
  --data-only \
  --no-owner \
  --no-acl \
  -f dados_embriovet.sql
```

### Passo 2: Deixar o Render Criar as Tabelas

1. Fazer deploy normal no Render
2. Aguardar `setup_database.py` criar todas as tabelas
3. Verificar nos logs: `✅ Banco de dados configurado com sucesso!`

### Passo 3: Importar Apenas os Dados

```bash
# Importar dados
psql [External Database URL] < dados_embriovet.sql
```

---

## 🎯 Opção 3: Migração Manual (Pequenos Volumes)

Para poucos registros, pode fazer manualmente:

### Via Interface Web

1. Exportar para Excel localmente:
   - Abrir aplicação local
   - Ir em "Relatórios"
   - Exportar cada seção para Excel

2. No Render:
   - Acessar aplicação
   - Adicionar proprietários manualmente
   - Adicionar stock manualmente

---

## 🛠️ Opção 4: Script Python de Migração

Vou criar um script automático:

<function_calls>
<invoke name="mcp_create_file">
<parameter name="file_text">#!/usr/bin/env python3
"""Script de migração de dados - Local para Render"""

import os
import psycopg2
from psycopg2.extras import execute_values
import sys

def conectar_local():
    """Conecta ao banco local"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="embriovet",
            user="postgres",
            password="123"
        )
        print("✅ Conectado ao banco LOCAL")
        return conn
    except Exception as e:
        print(f"❌ Erro ao conectar LOCAL: {e}")
        return None

def conectar_render(database_url):
    """Conecta ao banco do Render"""
    try:
        conn = psycopg2.connect(database_url)
        print("✅ Conectado ao banco RENDER")
        return conn
    except Exception as e:
        print(f"❌ Erro ao conectar RENDER: {e}")
        return None

def migrar_tabela(conn_origem, conn_destino, tabela, truncate=True):
    """Migra uma tabela completa"""
    try:
        # Ler dados da origem
        cur_origem = conn_origem.cursor()
        cur_origem.execute(f"SELECT * FROM {tabela}")
        dados = cur_origem.fetchall()
        
        if not dados:
            print(f"  ⚠️ {tabela}: Nenhum dado para migrar")
            return True
        
        # Obter nomes das colunas
        colunas = [desc[0] for desc in cur_origem.description]
        
        # Limpar tabela destino (opcional)
        cur_destino = conn_destino.cursor()
        if truncate:
            cur_destino.execute(f"TRUNCATE TABLE {tabela} CASCADE")
        
        # Inserir dados no destino
        query = f"INSERT INTO {tabela} ({','.join(colunas)}) VALUES %s"
        execute_values(cur_destino, query, dados)
        
        conn_destino.commit()
        
        print(f"  ✅ {tabela}: {len(dados)} registros migrados")
        
        cur_origem.close()
        cur_destino.close()
        return True
        
    except Exception as e:
        print(f"  ❌ {tabela}: Erro - {e}")
        return False

def migrar_completo(database_url_render):
    """Migração completa de todas as tabelas"""
    
    print("="*60)
    print("🔄 MIGRAÇÃO DE DADOS - LOCAL → RENDER")
    print("="*60)
    print()
    
    # Conectar aos bancos
    conn_local = conectar_local()
    if not conn_local:
        return False
    
    conn_render = conectar_render(database_url_render)
    if not conn_render:
        conn_local.close()
        return False
    
    print()
    print("📦 Migrando tabelas...")
    print()
    
    # Ordem de migração (respeitando foreign keys)
    tabelas = [
        'usuarios',
        'dono',
        'estoque_dono',
        'inseminacoes',
        'transferencias',
        'transferencias_externas'
    ]
    
    sucesso = True
    for tabela in tabelas:
        if not migrar_tabela(conn_local, conn_render, tabela):
            sucesso = False
    
    # Fechar conexões
    conn_local.close()
    conn_render.close()
    
    print()
    if sucesso:
        print("="*60)
        print("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        print("="*60)
        print()
        print("📝 Próximos passos:")
        print("1. Acessar aplicação no Render")
        print("2. Verificar se os dados estão corretos")
        print("3. Fazer login com suas credenciais existentes")
        print()
        return True
    else:
        print("="*60)
        print("⚠️ MIGRAÇÃO CONCLUÍDA COM ALGUNS ERROS")
        print("="*60)
        return False

if __name__ == "__main__":
    print()
    print("⚠️ IMPORTANTE:")
    print("1. Certifique-se que o deploy no Render foi concluído")
    print("2. As tabelas já devem existir no Render")
    print("3. Tenha a External Database URL do Render em mãos")
    print()
    
    # Pedir URL do Render
    database_url = input("Cole aqui a External Database URL do Render:\n> ").strip()
    
    if not database_url or not database_url.startswith("postgresql://"):
        print("❌ URL inválida!")
        sys.exit(1)
    
    print()
    confirmacao = input("⚠️ ATENÇÃO: Isso vai SUBSTITUIR os dados no Render. Confirma? (sim/não): ").strip().lower()
    
    if confirmacao not in ['sim', 's', 'yes', 'y']:
        print("❌ Migração cancelada")
        sys.exit(0)
    
    print()
    sucesso = migrar_completo(database_url)
    sys.exit(0 if sucesso else 1)
