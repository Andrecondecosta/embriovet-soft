# ⚠️ SOLUÇÃO RÁPIDA: Erro "column nome_completo does not exist"

## Erro Encontrado nos Logs

```
ERROR: column "nome_completo" does not exist
LINE 2: SELECT id, username, nome_completo, password...
```

## 🎯 Causa

O script `setup_database.py` inicial não criou a coluna `nome_completo` na tabela `usuarios`.

## ✅ Solução Rápida (2 opções)

### Opção 1: Executar Script SQL no Render (Mais Rápido)

1. **Obter External Database URL:**
   - Dashboard Render → `embriovet-db`
   - Copiar "External Database URL"

2. **No seu terminal LOCAL:**
   ```bash
   # Baixar código atualizado
   git pull
   
   # Executar script de correção
   psql [COLE AQUI External Database URL] < fix_usuarios_table.sql
   ```

3. **Verificar:**
   ```bash
   psql [External Database URL] -c "SELECT username, nome_completo FROM usuarios;"
   ```
   
   Deve mostrar:
   ```
    username |  nome_completo  
   ----------+-----------------
    admin    | Administrador
   ```

4. **Reiniciar serviço no Render:**
   - Dashboard → `embriovet-app`
   - Manual Deploy → "Deploy latest commit"

---

### Opção 2: Rebuild Completo (Mais Demorado)

Se a Opção 1 não funcionar:

1. **Deletar banco e app:**
   - Dashboard → `embriovet-db` → Settings → Delete
   - Dashboard → `embriovet-app` → Settings → Delete

2. **Atualizar código:**
   ```bash
   git pull
   git add .
   git commit -m "Fix: Adicionar coluna nome_completo"
   git push origin master
   ```

3. **Criar tudo novamente:**
   - Seguir `DEPLOY_MANUAL_PASSO_A_PASSO.md`
   - O novo `setup_database.py` já está corrigido

---

## 📝 O que foi Corrigido

**Arquivo: `setup_database.py`**

**ANTES (incorreto):**
```python
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nivel VARCHAR(50) DEFAULT 'Visualizador',
    ativo BOOLEAN DEFAULT TRUE
)
```

**DEPOIS (correto):**
```python
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    nome_completo VARCHAR(255),              ← ADICIONADO
    password_hash VARCHAR(255) NOT NULL,
    nivel VARCHAR(50) DEFAULT 'Visualizador',
    ativo BOOLEAN DEFAULT TRUE,
    created_by INTEGER REFERENCES usuarios(id)  ← ADICIONADO
)
```

---

## ✅ Verificar se Funcionou

1. **Acessar aplicação:**
   - https://embriovet-app.onrender.com

2. **Fazer login:**
   - Username: `admin`
   - Password: `admin123`

3. **Se funcionar:**
   - ✅ Login bem-sucedido
   - ✅ Ver tela principal
   - ✅ Alterar senha

4. **Se ainda der erro:**
   - Verificar logs: Dashboard → embriovet-app → Logs
   - Tentar Opção 2 (rebuild completo)

---

## 🔄 Próximos Passos

Após corrigir:

```bash
# 1. Atualizar código local
git pull

# 2. Verificar correção
cat setup_database.py | grep nome_completo

# 3. Commitar e push
git add .
git commit -m "Fix: Corrigir tabela usuarios"
git push origin master
```

---

## 💡 Dica

Se você já tinha dados no banco local e quer migrar:

1. Primeiro corrija o erro no Render (Opção 1 ou 2)
2. Depois execute: `python3 migrar_dados.py`
3. Seus dados locais serão migrados para o Render

---

**Status:** ✅ CORRIGIDO nos arquivos
**Ação:** Execute Opção 1 (mais rápido) ou Opção 2 (rebuild)
