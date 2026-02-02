# 🔧 CORREÇÃO RÁPIDA - Erro "column contato does not exist"

## ❌ ERRO:
```
Erro ao criar proprietário: column "contato" of relation "dono" does not exist
```

## 💡 CAUSA:
A tabela `dono` foi criada com um script SQL antigo que não tinha as colunas `contato` e `email`.

## ✅ SOLUÇÃO RÁPIDA (2 opções):

---

### **OPÇÃO 1: Adicionar Colunas (Mantém dados existentes)**

```bash
# Conectar ao banco
psql -U postgres -d embriovet

# Executar script de correção
\i corrigir_tabela_dono.sql

# OU copiar e colar:
ALTER TABLE dono ADD COLUMN IF NOT EXISTS contato VARCHAR(255);
ALTER TABLE dono ADD COLUMN IF NOT EXISTS email VARCHAR(255);

# Verificar
SELECT * FROM dono;

\q
```

---

### **OPÇÃO 2: Recriar Tabela (APAGA dados existentes!)**

```bash
# Conectar ao banco
psql -U postgres -d embriovet

# Executar script completo
\i criar_banco.sql

\q
```

**⚠️ ATENÇÃO:** Opção 2 apaga todos os dados! Use apenas se não tiver dados importantes.

---

## 🧪 TESTAR:

Após executar uma das opções acima:

```bash
# Executar importação novamente
python importar_dados.py
```

**Output esperado:**
```
✅ Pool de conexões PostgreSQL criado com sucesso
📋 Criando proprietário padrão...
✅ Proprietário padrão criado com ID: 1
```

---

## 🔍 VERIFICAR SE ESTÁ CORRETO:

```sql
psql -U postgres -d embriovet

-- Ver estrutura da tabela
\d dono

-- Deve mostrar:
-- id          | integer
-- nome        | character varying(255)
-- contato     | character varying(255)  ← DEVE EXISTIR
-- email       | character varying(255)  ← DEVE EXISTIR
-- created_at  | timestamp

\q
```

---

## 📋 CHECKLIST:

- [ ] Executar script de correção (Opção 1 ou 2)
- [ ] Verificar colunas existem (\d dono)
- [ ] Executar python importar_dados.py
- [ ] Verificar mensagem de sucesso

---

## 🚀 DEPOIS:

Preencha o CSV e importe os dados normalmente!

```bash
python importar_dados.py
```

---

**🎯 Problema resolvido! A tabela agora tem as colunas necessárias!**
