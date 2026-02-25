# 🚀 Deploy Manual no Render - Guia Atualizado

## ❌ Problema Encontrado

O Blueprint pode ter problemas. Use o **deploy manual** (mais confiável).

## ✅ Solução: Deploy Manual (Passo a Passo)

### 1️⃣ Criar PostgreSQL Database

1. Acesse: https://dashboard.render.com
2. Clique em **"New +"** → **"PostgreSQL"**
3. Configure:
   - **Name:** `embriovet-db`
   - **Database:** `embriovet`
   - **Region:** Frankfurt (ou mais próximo)
   - **PostgreSQL Version:** 16
   - **Plan:** Free
4. Clique em **"Create Database"**
5. Aguarde 2-3 minutos até status = "Available"
6. **COPIE** a **"Internal Database URL"** (começará com `postgresql://`)
   - Exemplo: `postgresql://user:pass@dpg-xxx-a.frankfurt-postgres.render.com/embriovet_xxx`

### 2️⃣ Criar Web Service

1. Clique em **"New +"** → **"Web Service"**
2. Conecte seu repositório GitHub/GitLab
3. Selecione o repositório `embriovet-soft`
4. Configure:

   **Basic Settings:**
   - **Name:** `embriovet-app`
   - **Region:** Frankfurt (mesma do banco!)
   - **Branch:** `master` (ou `main`)
   - **Root Directory:** (deixe vazio)
   - **Runtime:** Python 3
   - **Build Command:** 
     ```
     pip install -r requirements_streamlit.txt
     ```
   - **Start Command:** 
     ```
     bash start.sh
     ```

5. Clique em **"Advanced"** e adicione **Environment Variables:**

   ```
   PYTHON_VERSION
   3.11.0

   DATABASE_URL
   [Cole a Internal Database URL copiada no Passo 1]
   ```

   ⚠️ **IMPORTANTE:** Cole a URL exata do banco de dados!

6. **Plan:** Free

7. Clique em **"Create Web Service"**

### 3️⃣ Acompanhar Deploy

1. Você será redirecionado para a página do serviço
2. Vá em **"Logs"** (menu lateral)
3. Aguarde 5-10 minutos e verifique:
   - ✅ `Installing dependencies...`
   - ✅ `Successfully installed streamlit...`
   - ✅ `🚀 Iniciando EmbrioVet...`
   - ✅ `✅ Banco de dados configurado com sucesso!`
   - ✅ `You can now view your Streamlit app in your browser`

4. Status deve mudar para **"Live"** (verde)

### 4️⃣ Acessar Aplicação

1. Na página do serviço, copie a URL (ex: `https://embriovet-app.onrender.com`)
2. Abra em uma nova aba
3. **Primeira vez:** Aguarde 30-60 segundos (cold start)
4. Login:
   - **Username:** `admin`
   - **Password:** `admin123`

5. **⚠️ ALTERE A SENHA IMEDIATAMENTE:**
   - Vá em "⚙️ Gestão de Utilizadores"
   - Editar admin → Nova senha forte

---

## 🐛 Resolver Problemas Comuns

### Erro: "Application failed to respond"

**Solução 1:** Verificar logs
```
Dashboard → Seu serviço → Logs
```
Procure por erros em vermelho.

**Solução 2:** Verificar DATABASE_URL
```
Dashboard → Seu serviço → Environment → DATABASE_URL
```
Confirme que está correta (mesma do banco).

**Solução 3:** Rebuild
```
Dashboard → Seu serviço → Manual Deploy → Clear build cache & deploy
```

### Erro: "ModuleNotFoundError"

**Causa:** Dependências não instaladas

**Solução:**
```
Dashboard → Seu serviço → Environment
```
Verificar se `PYTHON_VERSION=3.11.0` está definida.

Forçar rebuild:
```
Manual Deploy → Clear build cache & deploy
```

### Erro: "Connection refused" (banco de dados)

**Causa:** DATABASE_URL incorreta

**Solução:**
1. Vá no serviço do banco: `embriovet-db`
2. Copie a **Internal Database URL** novamente
3. Vá no serviço da app: `embriovet-app`
4. Environment → Editar `DATABASE_URL`
5. Cole a URL correta
6. Save Changes (reinicia automaticamente)

### Site lento ou não carrega

**Causa:** Sleep mode (plano free)

**Solução:** 
- Aguarde 30-60 segundos
- Recarregue a página
- É normal na primeira requisição após inatividade

---

## 📝 Checklist Deploy Manual

Antes de começar:
- [ ] Código commitado e pushed no GitHub/GitLab
- [ ] Arquivo `start.sh` tem permissão de execução
- [ ] `requirements_streamlit.txt` tem todas as dependências

Durante deploy:
- [ ] Banco de dados criado e status "Available"
- [ ] Internal Database URL copiada
- [ ] Web service criado
- [ ] Build command: `pip install -r requirements_streamlit.txt`
- [ ] Start command: `bash start.sh`
- [ ] Environment variables configuradas:
  - [ ] PYTHON_VERSION = 3.11.0
  - [ ] DATABASE_URL = (URL do banco)
- [ ] Mesma região para banco e app

Após deploy:
- [ ] Logs sem erros
- [ ] Status = "Live"
- [ ] Aplicação acessível via URL
- [ ] Login funcionando
- [ ] Senha admin alterada

---

## 🔄 Atualizar Aplicação

Depois que o deploy inicial funcionar:

```bash
# 1. Fazer mudanças no código
git add .
git commit -m "Descrição"
git push origin master

# 2. Render faz deploy automático!
```

Acompanhe em: Dashboard → Logs

---

## 💡 Dicas

### Verificar se banco está conectado
No terminal local:
```bash
psql [Cole a External Database URL aqui]
\dt
```
Deve mostrar as tabelas: dono, estoque_dono, etc.

### Logs em tempo real
```
Dashboard → embriovet-app → Logs → "Live" (botão)
```

### Reiniciar serviço
```
Dashboard → embriovet-app → Manual Deploy → Deploy latest commit
```

### Verificar métricas
```
Dashboard → embriovet-app → Metrics
```
CPU, RAM, Requests

---

## 📞 Ainda com problemas?

1. **Logs do serviço:** Copie e leia com atenção
2. **Status page:** https://status.render.com (ver se Render está fora)
3. **Community:** https://community.render.com
4. **Testar localmente:** Confirme que funciona antes de fazer deploy

---

## ✅ Deploy Bem-Sucedido?

Se tudo funcionou:
- [ ] URL acessível
- [ ] Login OK
- [ ] Senha alterada
- [ ] Primeiro proprietário adicionado
- [ ] Primeiro stock criado
- [ ] Teste completo realizado

**🎉 Parabéns! EmbrioVet está no ar!**

---

## 🔗 Links Úteis

- **Dashboard:** https://dashboard.render.com
- **Docs:** https://render.com/docs
- **Python Version:** https://render.com/docs/python-version
- **PostgreSQL:** https://render.com/docs/databases

---

**Última atualização:** Fix para erro PYTHON_VERSION
