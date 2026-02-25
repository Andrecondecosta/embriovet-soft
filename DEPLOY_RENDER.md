# 🚀 Deploy EmbrioVet no Render

## Pré-requisitos

1. Conta no [Render](https://render.com) (gratuita)
2. Repositório Git com o código (GitHub, GitLab ou Bitbucket)

## Opção 1: Deploy Automático (Recomendado)

### Passo 1: Preparar o Repositório

```bash
# No seu ambiente local, commitar todos os arquivos
git add .
git commit -m "Preparar para deploy no Render"
git push origin main
```

### Passo 2: Conectar no Render

1. Acesse [https://dashboard.render.com](https://dashboard.render.com)
2. Clique em **"New +"** → **"Blueprint"**
3. Conecte seu repositório Git
4. O Render vai detectar o arquivo `render.yaml` automaticamente
5. Clique em **"Apply"**
6. Aguarde o deploy (5-10 minutos)

### Passo 3: Acessar a Aplicação

- A aplicação estará disponível em: `https://embriovet-app.onrender.com`
- **Username:** `admin`
- **Password:** `admin123`

⚠️ **IMPORTANTE:** Altere a senha do admin após o primeiro login!

---

## Opção 2: Deploy Manual

### Passo 1: Criar PostgreSQL Database

1. No dashboard do Render, clique em **"New +"** → **"PostgreSQL"**
2. Configurações:
   - **Name:** `embriovet-db`
   - **Database:** `embriovet`
   - **User:** (gerado automaticamente)
   - **Region:** Frankfurt (ou mais próximo)
   - **Plan:** Free
3. Clique em **"Create Database"**
4. Aguarde a criação (2-3 minutos)
5. **Copie** a "Internal Database URL" (começará com `postgresql://`)

### Passo 2: Criar Web Service

1. Clique em **"New +"** → **"Web Service"**
2. Conecte seu repositório Git
3. Configurações:
   - **Name:** `embriovet-app`
   - **Region:** Frankfurt (mesma do banco)
   - **Branch:** `main`
   - **Root Directory:** (deixe vazio)
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements_streamlit.txt`
   - **Start Command:** `bash start.sh`
   - **Plan:** Free

4. **Environment Variables** (clique em "Advanced"):
   ```
   DATABASE_URL = <cole a Internal Database URL do Passo 1>
   PYTHON_VERSION = 3.11
   ```

5. Clique em **"Create Web Service"**
6. Aguarde o build e deploy (5-10 minutos)

### Passo 3: Verificar Logs

No dashboard do serviço, vá em **"Logs"** e verifique:
- ✅ "Banco de dados configurado com sucesso!"
- ✅ "Iniciando Streamlit..."
- ✅ "You can now view your Streamlit app in your browser"

---

## 🔧 Configurações Adicionais

### Alterar Senha do Admin

1. Faça login com `admin` / `admin123`
2. Vá em **"⚙️ Gestão de Utilizadores"**
3. Clique em **"Editar"** no usuário admin
4. Altere a senha
5. Salve

### Conectar ao Banco de Dados (Opcional)

Para conectar via cliente PostgreSQL (DBeaver, pgAdmin, etc.):

1. No dashboard do Render, vá no serviço `embriovet-db`
2. Copie a **External Database URL**
3. Use no seu cliente SQL

⚠️ **Atenção:** O banco free dorme após 90 dias de inatividade

### Backup do Banco de Dados

O Render **não faz backup automático** no plano free. Recomendações:

1. **Exportar dados regularmente:**
   ```bash
   # Instalar pg_dump localmente
   pg_dump -h <host> -U <user> -d <database> -F c -f backup.dump
   ```

2. **Upgrade para plano pago** ($7/mês) com backups automáticos

---

## 🐛 Resolução de Problemas

### Erro: "Application failed to respond"

1. Verifique os logs do serviço
2. Confirme que `DATABASE_URL` está configurada
3. Reinicie o serviço: **"Manual Deploy"** → **"Clear build cache & deploy"**

### Erro: "Database connection failed"

1. Verifique se o banco está rodando (não em sleep mode)
2. Confirme que a `DATABASE_URL` está correta
3. Verifique se ambos os serviços estão na mesma região

### Aplicação lenta na primeira requisição

O plano free do Render coloca serviços inativos para "dormir" após 15 minutos sem uso. A primeira requisição após o sleep pode demorar 30-60 segundos.

**Solução:** Upgrade para plano pago ($7/mês) remove o sleep.

### Erro: "This site can't be reached"

1. Aguarde 5-10 minutos após o deploy
2. Verifique se o serviço está "Live" (verde) no dashboard
3. Teste em modo anônimo (sem cache)

---

## 📊 Monitoramento

### Métricas Disponíveis

- **CPU Usage**
- **Memory Usage**
- **Bandwidth**
- **Request Count**

Acesse em: Dashboard → Seu Serviço → **"Metrics"**

### Limites do Plano Free

- ✅ 750 horas/mês de runtime
- ✅ 100 GB de bandwidth/mês
- ✅ 512 MB RAM
- ✅ PostgreSQL com 1 GB de armazenamento
- ❌ Sleep após 15 min de inatividade
- ❌ Sem backups automáticos

---

## 🔐 Segurança em Produção

### Checklist de Segurança:

- [ ] Alterar senha do admin padrão
- [ ] Criar usuários com permissões limitadas
- [ ] Ativar HTTPS (automático no Render)
- [ ] Revisar permissões de acesso ao banco
- [ ] Configurar backups regulares
- [ ] Monitorar logs de acesso

### Recomendações:

1. **Não compartilhe** as credenciais do banco publicamente
2. **Use variáveis de ambiente** para senhas (nunca no código)
3. **Revise usuários** regularmente
4. **Faça backups** antes de updates importantes

---

## 💰 Upgrade para Plano Pago (Opcional)

### Benefícios:

- ✅ Sem sleep mode (sempre online)
- ✅ Backups automáticos diários
- ✅ Mais recursos (RAM, CPU)
- ✅ Suporte prioritário

### Preços:

- **Web Service:** $7/mês (Starter)
- **PostgreSQL:** $7/mês (com backups)
- **Total:** ~$14/mês

---

## 📞 Suporte

- **Documentação Render:** [https://render.com/docs](https://render.com/docs)
- **Community Forum:** [https://community.render.com](https://community.render.com)
- **Status Page:** [https://status.render.com](https://status.render.com)

---

## ✅ Checklist Final

- [ ] Banco de dados criado e rodando
- [ ] Variável `DATABASE_URL` configurada
- [ ] Web service deployado com sucesso
- [ ] Aplicação acessível via URL
- [ ] Login funcionando (admin/admin123)
- [ ] Senha do admin alterada
- [ ] Primeiro proprietário cadastrado
- [ ] Primeiro stock adicionado
- [ ] Teste completo de todas as funcionalidades

---

**🎉 Parabéns! Sua aplicação EmbrioVet está em produção!**