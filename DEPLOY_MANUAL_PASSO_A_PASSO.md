# ⚠️ ATENÇÃO: Usar Deploy Manual

## ❌ Problemas com Blueprint

O Blueprint do Render tem apresentado erros:
1. ❌ Erro de PYTHON_VERSION
2. ❌ Erro de aspas no buildCommand
3. ❌ Problemas intermitentes

## ✅ SOLUÇÃO: Deploy Manual (100% Confiável)

### Por que Deploy Manual?

- ✅ Mais controle sobre cada etapa
- ✅ Mais fácil de debugar erros
- ✅ Funciona sempre
- ✅ Melhor para troubleshooting

---

## 🚀 GUIA COMPLETO: Deploy Manual

### PASSO 1: Criar Banco de Dados PostgreSQL

1. Acesse: https://dashboard.render.com
2. Clique em **"New +"** → **"PostgreSQL"**
3. Configure:
   ```
   Name: embriovet-db
   Database: embriovet
   Region: Frankfurt
   PostgreSQL Version: 16
   Plan: Free
   ```
4. Clique **"Create Database"**
5. Aguarde status = "Available" (2-3 minutos)

6. **COPIAR URL DO BANCO:**
   - Na página do banco, role até "Connections"
   - Copie **"Internal Database URL"**
   - Exemplo: `postgresql://embriovet_db_user:senha@dpg-xxx.frankfurt-postgres.render.com/embriovet_db`
   - ⚠️ **GUARDAR ESSA URL!** Você vai precisar no próximo passo

---

### PASSO 2: Criar Web Service (Aplicação)

1. Volte ao Dashboard
2. Clique **"New +"** → **"Web Service"**
3. **Conectar repositório:**
   - Connect account (GitHub/GitLab)
   - Selecione: `embriovet-soft`
   - Clique **"Connect"**

4. **Configurações Básicas:**
   ```
   Name: embriovet-app
   Region: Frankfurt (mesma do banco!)
   Branch: master
   Root Directory: (deixe vazio)
   Runtime: Python 3
   ```

5. **Build & Start Commands:**
   ```
   Build Command:
   pip install -r requirements_streamlit.txt
   
   Start Command:
   bash start.sh
   ```

6. **Clique em "Advanced"** (botão no topo)

7. **Environment Variables** (clicar em "Add Environment Variable"):
   
   **Variável 1:**
   ```
   Key: PYTHON_VERSION
   Value: 3.11.0
   ```
   
   **Variável 2:**
   ```
   Key: DATABASE_URL
   Value: [COLE AQUI a Internal Database URL que você copiou]
   ```
   
   ⚠️ **IMPORTANTE:** A URL deve começar com `postgresql://`

8. **Plan:** Free

9. Clique **"Create Web Service"**

---

### PASSO 3: Monitorar Deploy

1. Você será redirecionado para a página do serviço
2. Clique em **"Logs"** no menu lateral
3. Acompanhe o deploy (5-10 minutos)

**O que você deve ver nos logs:**

```
==> Cloning from https://github.com/...
==> Installing Python version 3.11.0...
✅ Using Python version 3.11.0
==> Running build command...
✅ Successfully installed streamlit pandas psycopg2-binary...
==> Starting service...
🚀 Iniciando EmbrioVet...
📦 Configurando banco de dados pela primeira vez...
✅ Banco de dados configurado com sucesso!
✅ Usu\u00e1rio admin criado (username: admin, password: admin123)
🎯 Iniciando Streamlit...
✅ You can now view your Streamlit app in your browser
```

4. Aguarde status mudar para **"Live"** (verde)

---

### PASSO 4: Acessar Aplicação

1. Na página do serviço, no topo verá a URL:
   - Exemplo: `https://embriovet-app.onrender.com`

2. Clique na URL ou copie e abra em nova aba

3. **Primeira requisição:** Aguarde 30-60 segundos (normal)

4. **Fazer Login:**
   ```
   Username: admin
   Password: admin123
   ```

5. **⚠️ IMPORTANTE:** Alterar senha imediatamente!
   - Ir em "⚙️ Gestão de Utilizadores"
   - Editar admin → Nova senha forte → Salvar

---

## ✅ Checklist de Verificação

### Durante Setup
- [ ] Banco criado (status = Available)
- [ ] Internal Database URL copiada
- [ ] Web service criado
- [ ] Mesma região para banco e app (Frankfurt)
- [ ] Build command correto: `pip install -r requirements_streamlit.txt`
- [ ] Start command correto: `bash start.sh`
- [ ] PYTHON_VERSION = 3.11.0
- [ ] DATABASE_URL configurada (começa com postgresql://)

### Após Deploy
- [ ] Logs sem erros vermelhos
- [ ] Viu mensagem "Banco de dados configurado com sucesso"
- [ ] Status = "Live" (verde)
- [ ] URL acessível
- [ ] Login funciona (admin/admin123)
- [ ] Senha alterada
- [ ] Teste criar proprietário
- [ ] Teste adicionar stock

---

## 🐛 Resolver Problemas

### Erro: "Application failed to respond"

**Verificar:**
1. Logs → Procure erro em vermelho
2. DATABASE_URL está correta?
3. Banco e app na mesma região?

**Solução:**
```
Dashboard → embriovet-app → Manual Deploy → 
Clear build cache & deploy
```

---

### Erro: "Connection to database failed"

**Causa:** DATABASE_URL incorreta

**Solução:**
1. Vá em: `embriovet-db` (serviço do banco)
2. Copie novamente "Internal Database URL"
3. Vá em: `embriovet-app` (serviço da app)
4. Environment → Editar DATABASE_URL
5. Cole a URL correta
6. Save (reinicia automaticamente)

---

### Erro: "ModuleNotFoundError: No module named 'streamlit'"

**Causa:** Dependências não instaladas

**Solução:**
1. Verificar Build Command:
   ```
   pip install -r requirements_streamlit.txt
   ```
2. Forçar rebuild:
   ```
   Manual Deploy → Clear build cache & deploy
   ```

---

### Site muito lento / não carrega

**Causa:** Sleep mode (plano free)

**Normal:** Primeira requisição após 15min de inatividade demora 30-60s

**Solução:** 
- Aguardar e recarregar
- Ou upgrade para plano pago ($7/mês - sem sleep)

---

## 🔄 Atualizações Futuras

Após deploy inicial funcionando:

```bash
# Local: fazer mudanças
git add .
git commit -m "Descrição"
git push origin master

# Render: deploy automático! 🎉
```

Acompanhe em: Dashboard → embriovet-app → Logs

---

## 💡 Dicas Importantes

### 1. Mesma Região
**Banco e App devem estar na MESMA região!**
- Recomendado: Frankfurt
- Ou: Oregon, Frankfurt, Singapore

### 2. Internal vs External Database URL
- **Internal URL:** Para a aplicação (mais rápida)
- **External URL:** Para acessar via cliente SQL local

**Use Internal URL no DATABASE_URL!**

### 3. Logs em Tempo Real
```
Dashboard → embriovet-app → Logs → 
Botão "Live" (canto superior direito)
```

### 4. Verificar Banco Conectou
No terminal local:
```bash
# Usar External Database URL
psql [cole External URL aqui]

# Ver tabelas
\dt

# Deve mostrar: dono, estoque_dono, inseminacoes, etc.
```

---

## 📊 Limites Plano Free

- ✅ Grátis para sempre
- ✅ 750 horas/mês (suficiente para 1 app)
- ✅ 100 GB bandwidth/mês
- ✅ PostgreSQL 1GB storage
- ⚠️ Sleep após 15 min inatividade
- ⚠️ Sem backups automáticos

### Upgrade ($14/mês total)
- Web Service: $7/mês
- PostgreSQL: $7/mês

**Benefícios:**
- Sem sleep mode (sempre online)
- Backups automáticos diários
- Mais recursos (RAM, storage)

---

## 📞 Suporte

### Problemas Técnicos
1. **Logs primeiro:** Dashboard → Logs
2. **Status Render:** https://status.render.com
3. **Community:** https://community.render.com
4. **Docs:** https://render.com/docs

### Verificar Localmente
Se não funciona no Render, teste local:
```bash
streamlit run app.py
```

Se funciona local mas não no Render:
- Problema é com deploy/configuração
- Revisar Environment Variables
- Verificar DATABASE_URL

---

## ✅ Sucesso!

Se tudo funcionou:
- ✅ URL acessível: `https://embriovet-app.onrender.com`
- ✅ Login OK
- ✅ Senha admin alterada
- ✅ Funcionalidades testadas

**🎉 Parabéns! EmbrioVet está no ar!**

---

## 🔗 Links Úteis

- **Dashboard:** https://dashboard.render.com
- **Seu App:** https://embriovet-app.onrender.com (após deploy)
- **Docs PostgreSQL:** https://render.com/docs/databases
- **Docs Python:** https://render.com/docs/python-version
- **Community:** https://community.render.com

---

**Última atualização:** Guia completo de deploy manual (melhor que Blueprint)
