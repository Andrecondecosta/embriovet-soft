# 🔴 SOLUÇÃO - "Utilizador ou password incorretos"

## ❌ O PROBLEMA

Você vê o erro: **"Utilizador ou password incorretos"**

**Causa:** A tabela `usuarios` ainda **NÃO FOI CRIADA** no seu banco de dados local.

---

## ✅ SOLUÇÃO (Execute AGORA)

### Passo 1: Abrir o Terminal

### Passo 2: Executar o Script SQL

Copie e cole este comando:

```bash
psql -U postgres -d embriovet -f /Users/andrecondecosta/projects/embriovet-soft/criar_tabela_usuarios.sql
```

**Digite a password do PostgreSQL quando pedir:** `123`

---

## 🔍 VERIFICAR SE FUNCIONOU

Após executar o comando acima, verifique se a tabela foi criada:

```bash
psql -U postgres -d embriovet -c "SELECT * FROM usuarios;"
```

**Deve mostrar:**
```
 id | username | nome_completo | password_hash | nivel | ativo 
----+----------+---------------+---------------+-------+-------
  1 | admin    | Administrador | $2b$12$...   | Admin | t
```

Se aparecer isso, **funcionou!** ✅

---

## 🔐 DEPOIS DE CRIAR A TABELA

1. **Recarregue a página de login** (F5)
2. **Digite:**
   - Username: `admin`
   - Password: `admin123`
3. **Clique em "Entrar"**

**Deve funcionar agora!** 🎉

---

## 🆘 SE DER ERRO NO COMANDO SQL

### Erro 1: "psql: command not found"

**Solução:** Encontre onde o PostgreSQL está instalado:

```bash
/Applications/Postgres.app/Contents/Versions/*/bin/psql -U postgres -d embriovet -f criar_tabela_usuarios.sql
```

### Erro 2: "database 'embriovet' does not exist"

**Solução:** Crie o banco primeiro:

```bash
psql -U postgres -c "CREATE DATABASE embriovet;"
```

Depois execute o script novamente.

### Erro 3: "password authentication failed"

**Solução:** A password do postgres não é `123`. Tente sem `-U postgres`:

```bash
psql embriovet -f criar_tabela_usuarios.sql
```

---

## 📊 TODOS OS SCRIPTS QUE VOCÊ PRECISA EXECUTAR

Após resolver este erro, execute TODOS estes scripts na ordem:

```bash
# 1. Utilizadores (o que você está fazendo agora)
psql -U postgres -d embriovet -f criar_tabela_usuarios.sql

# 2. Transferências internas (corrigir)
psql -U postgres -d embriovet -f corrigir_tabela_transferencias.sql

# 3. Transferências externas (vendas)
psql -U postgres -d embriovet -f criar_tabela_transferencias_externas.sql
```

---

## 🎯 RESUMO

**Problema:** Tabela `usuarios` não existe no banco  
**Solução:** Executar o script SQL  
**Comando:** `psql -U postgres -d embriovet -f criar_tabela_usuarios.sql`  
**Depois:** Login funciona com admin/admin123  

---

## ✅ CHECKLIST

- [ ] Abrir terminal
- [ ] Executar script SQL da tabela usuarios
- [ ] Verificar que tabela foi criada
- [ ] Recarregar página de login (F5)
- [ ] Fazer login com admin/admin123
- [ ] Funciona! ✅

---

**Status:** Solução clara fornecida  
**Tempo:** 2 minutos para resolver
