# 🚀 Guia Rápido - Deploy no Render

## ✅ Pré-requisitos Verificados

Execute antes de fazer deploy:
```bash
python3 verificar_deploy.py
```

## 📝 Passos para Deploy

### 1️⃣ Preparar Repositório Git

```bash
# Adicionar todos os arquivos
git add .

# Fazer commit
git commit -m "Preparar aplicação para produção no Render"

# Fazer push para o GitHub/GitLab
git push origin main
```

### 2️⃣ Criar Conta no Render

1. Acesse: https://render.com
2. Clique em **"Get Started for Free"**
3. Faça sign up com GitHub/GitLab/Email

### 3️⃣ Fazer Deploy Automático

1. No dashboard do Render, clique em **"New +"** → **"Blueprint"**
2. Conecte seu repositório Git
3. O Render detectará automaticamente o `render.yaml`
4. Clique em **"Apply"**
5. Aguarde 5-10 minutos

### 4️⃣ Acessar a Aplicação

Após o deploy:
- URL: `https://embriovet-app.onrender.com`
- **Username:** `admin`
- **Password:** `admin123`

⚠️ **ALTERE A SENHA IMEDIATAMENTE!**

---

## 🔧 Configuração Manual (Alternativa)

Se preferir configurar manualmente:

### Criar Banco de Dados
1. **New +** → **PostgreSQL**
2. Nome: `embriovet-db`
3. Plano: **Free**
4. Copie a **Internal Database URL**

### Criar Web Service
1. **New +** → **Web Service**
2. Conecte o repositório
3. Configurações:
   - Runtime: **Python 3**
   - Build: `pip install -r requirements_streamlit.txt`
   - Start: `bash start.sh`
4. Environment Variables:
   ```
   DATABASE_URL = <cole a URL do banco>
   PYTHON_VERSION = 3.11
   ```
5. **Create Web Service**

---

## 📊 Monitoramento

### Verificar Status
- Dashboard → Seu serviço → **"Logs"**
- Procure por: `✅ Banco de dados configurado`

### Métricas
- Dashboard → Seu serviço → **"Metrics"**
- CPU, RAM, Bandwidth

---

## ⚠️ Limitações Plano Free

- ✅ Grátis para sempre
- ✅ 750 horas/mês
- ✅ 100 GB bandwidth
- ❌ Dorme após 15 min inatividade
- ❌ Sem backups automáticos

**Primeira requisição após sleep:** 30-60 segundos

---

## 🆙 Atualizar Aplicação

```bash
# Fazer mudanças no código
git add .
git commit -m "Descrição das mudanças"
git push origin main
```

O Render fará **deploy automático**! 🎉

---

## 🔒 Segurança

### Após primeiro acesso:

1. **Alterar senha admin:**
   - Login → ⚙️ Gestão de Utilizadores
   - Editar admin → Nova senha

2. **Criar utilizadores:**
   - Adicionar Gestor/Visualizador
   - Definir permissões

3. **Backup regular:**
   ```bash
   # Conectar ao banco via External URL
   pg_dump -h <host> -U <user> -d <db> -F c -f backup.dump
   ```

---

## 🐛 Problemas Comuns

### Aplicação não inicia
- Verificar logs: Dashboard → Logs
- Confirmar DATABASE_URL está configurada

### Erro de conexão ao banco
- Verificar se banco está "Available"
- Confirmar URL está correta

### Site lento na primeira vez
- Normal no plano free (sleep mode)
- Aguardar 30-60 segundos

---

## 💰 Upgrade (Opcional)

Para **remover sleep mode** e ter **backups**:

- Web Service: $7/mês
- PostgreSQL: $7/mês
- **Total: $14/mês**

---

## 📞 Ajuda

- 📖 Guia completo: `DEPLOY_RENDER.md`
- 🌐 Docs Render: https://render.com/docs
- 💬 Community: https://community.render.com

---

**✅ Projeto preparado e pronto para produção!** 🎉
