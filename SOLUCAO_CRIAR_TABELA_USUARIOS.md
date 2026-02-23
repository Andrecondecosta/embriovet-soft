# 🔧 SOLUÇÃO DEFINITIVA - Criar Tabela Usuarios

## ❌ O ERRO

```
ERROR: relation "usuarios" does not exist
```

**Significa:** A tabela `usuarios` não existe no banco de dados.

---

## ✅ SOLUÇÃO SIMPLES (Copiar e colar no terminal)

### Método 1: Script SQL Direto (RECOMENDADO)

Abra o terminal e execute **este comando completo**:

```bash
psql -U postgres -d embriovet << 'EOF'
-- Criar tabela de utilizadores
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    nome_completo VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nivel VARCHAR(50) NOT NULL CHECK (nivel IN ('Administrador', 'Gestor', 'Visualizador')),
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    created_by INTEGER REFERENCES usuarios(id) ON DELETE SET NULL
);

-- Criar índices
CREATE INDEX IF NOT EXISTS idx_usuarios_username ON usuarios(username);
CREATE INDEX IF NOT EXISTS idx_usuarios_nivel ON usuarios(nivel);
CREATE INDEX IF NOT EXISTS idx_usuarios_ativo ON usuarios(ativo);

-- Inserir admin inicial
INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo)
VALUES (
    'admin',
    'Administrador',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYsP8f3glK.',
    'Administrador',
    TRUE
) ON CONFLICT (username) DO NOTHING;

-- Verificar
SELECT 'Tabela criada com sucesso!' as status;
SELECT * FROM usuarios;
EOF
```

**Digite a password quando pedir:** `123`

---

### Método 2: Se o Método 1 Não Funcionar

Execute **linha por linha**:

```bash
# 1. Conectar ao banco
psql -U postgres -d embriovet
```

Depois, **dentro do psql**, copie e cole isto:

```sql
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    nome_completo VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nivel VARCHAR(50) NOT NULL,
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_usuarios_username ON usuarios(username);

INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo)
VALUES ('admin', 'Administrador', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYsP8f3glK.', 'Administrador', TRUE)
ON CONFLICT (username) DO NOTHING;

SELECT * FROM usuarios;
```

Para sair do psql: `\q`

---

### Método 3: Usando o Arquivo (se os anteriores falharem)

Primeiro, verifique se o arquivo existe:

```bash
ls -la /Users/andrecondecosta/projects/embriovet-soft/criar_tabela_usuarios.sql
```

Se existir, tente:

```bash
cd /Users/andrecondecosta/projects/embriovet-soft
cat criar_tabela_usuarios.sql | psql -U postgres -d embriovet
```

---

## 🔍 VERIFICAR SE FUNCIONOU

Após executar qualquer método acima:

```bash
psql -U postgres -d embriovet -c "SELECT username, nivel FROM usuarios;"
```

**Deve mostrar:**
```
 username |     nivel      
----------+----------------
 admin    | Administrador
```

✅ **Se aparecer isso, funcionou!**

---

## 🔄 DEPOIS DE CRIAR A TABELA

1. **Pare o Streamlit** (Ctrl+C no terminal)
2. **Reinicie:**
   ```bash
   streamlit run app.py
   ```
3. **Abra o navegador:** http://localhost:8501
4. **Faça login:**
   - Username: `admin`
   - Password: `admin123`

**Deve funcionar agora!** 🎉

---

## 🆘 ERROS COMUNS

### "psql: command not found"

Tente adicionar o caminho completo:

```bash
/Library/PostgreSQL/*/bin/psql -U postgres -d embriovet
```

Ou:

```bash
/Applications/Postgres.app/Contents/Versions/*/bin/psql -U postgres -d embriovet
```

### "database 'embriovet' does not exist"

Crie o banco primeiro:

```bash
psql -U postgres -c "CREATE DATABASE embriovet;"
```

### "password authentication failed"

A password pode não ser `postgres`. Tente descobrir:

```bash
psql -U postgres -l
```

Ou tente sem especificar usuário:

```bash
psql embriovet
```

---

## 📊 RESUMO

**Problema:** Tabela usuarios não existe  
**Causa:** Script SQL não foi executado com sucesso  
**Solução:** Executar comandos SQL diretamente  
**Resultado:** Tabela criada + Admin criado  

**Tempo:** 2 minutos ⚡

---

## ✅ PRÓXIMOS PASSOS

Após a tabela ser criada e o login funcionar:

```bash
# 1. Corrigir transferências internas
psql -U postgres -d embriovet << 'EOF'
DROP TABLE IF EXISTS transferencias CASCADE;
CREATE TABLE transferencias (
    id SERIAL PRIMARY KEY,
    estoque_id INTEGER,
    proprietario_origem_id INTEGER,
    proprietario_destino_id INTEGER,
    quantidade INTEGER NOT NULL,
    data_transferencia TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
EOF

# 2. Criar transferências externas
psql -U postgres -d embriovet << 'EOF'
CREATE TABLE IF NOT EXISTS transferencias_externas (
    id SERIAL PRIMARY KEY,
    estoque_id INTEGER,
    proprietario_origem_id INTEGER,
    garanhao VARCHAR(255),
    destinatario_externo VARCHAR(255) NOT NULL,
    quantidade INTEGER NOT NULL,
    tipo VARCHAR(50) DEFAULT 'Venda',
    observacoes TEXT,
    data_transferencia TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
EOF
```

---

**Status:** Solução completa fornecida ✅
