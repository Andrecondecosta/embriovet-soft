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

## 🛠️ Opção 4: Script Python de Migração (RECOMENDADO - Mais fácil!)

**Criamos um script automático para você!**

### Passo 1: Preparar

```bash
# Já deve ter instalado, mas confirme:
pip install psycopg2-binary
```

### Passo 2: Executar Script

```bash
# No seu terminal LOCAL
python3 migrar_dados.py
```

### Passo 3: Seguir Instruções

O script vai:
1. ✅ Conectar ao banco local automaticamente
2. ✅ Pedir a External Database URL do Render
3. ✅ Pedir confirmação
4. ✅ Migrar TODAS as tabelas automaticamente
5. ✅ Mostrar progresso em tempo real

**Saída esperada:**
```
============================================================
🔄 MIGRAÇÃO DE DADOS - LOCAL → RENDER
============================================================

✅ Conectado ao banco LOCAL
✅ Conectado ao banco RENDER

📦 Migrando tabelas...

  ✅ usuarios: 3 registros migrados
  ✅ dono: 5 registros migrados
  ✅ estoque_dono: 12 registros migrados
  ✅ inseminacoes: 8 registros migrados
  ✅ transferencias: 2 registros migrados
  ✅ transferencias_externas: 1 registros migrados

============================================================
✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!
============================================================

📝 Próximos passos:
1. Acessar aplicação no Render
2. Verificar se os dados estão corretos
3. Fazer login com suas credenciais existentes
```

---