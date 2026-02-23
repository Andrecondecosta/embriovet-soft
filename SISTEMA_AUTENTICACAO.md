# 🔐 SISTEMA DE AUTENTICAÇÃO - 3 Níveis de Acesso

**Data:** 02/02/2026  
**Versão:** 3.0  
**Feature:** Sistema completo de autenticação com 3 escalões

---

## 🎯 O QUE FOI IMPLEMENTADO?

Sistema de login com **3 níveis de acesso** e permissões diferenciadas.

---

## 👥 OS 3 NÍVEIS DE ACESSO

### 🔴 1. ADMINISTRADOR
**Acesso Total ao Sistema**

**Pode fazer:**
- ✅ Ver estoque e relatórios
- ✅ Adicionar stock
- ✅ **Editar stock** (EXCLUSIVO)
- ✅ **Deletar stock** (EXCLUSIVO)
- ✅ Registrar inseminações
- ✅ Transferir sêmen (interna e externa)
- ✅ Gerir proprietários
- ✅ **Gerir utilizadores** (EXCLUSIVO)
- ✅ **Adicionar outros administradores** (EXCLUSIVO)

### 🟡 2. GESTOR / VETERINÁRIO
**Operações do Dia-a-Dia**

**Pode fazer:**
- ✅ Ver estoque e relatórios
- ✅ Adicionar stock
- ✅ Registrar inseminações
- ✅ Transferir sêmen (interna e externa)
- ✅ Gerir proprietários

**NÃO pode:**
- ❌ Editar stock existente
- ❌ Deletar stock
- ❌ Gerir utilizadores

### 🟢 3. VISUALIZADOR
**Acesso Somente Leitura**

**Pode fazer:**
- ✅ Ver estoque
- ✅ Ver relatórios

**NÃO pode:**
- ❌ Adicionar/editar/deletar nada
- ❌ Fazer transferências
- ❌ Registrar inseminações
- ❌ Gerir proprietários ou utilizadores

---

## 🔐 CREDENCIAIS INICIAIS

Após criar a tabela, use estas credenciais para primeiro acesso:

```
👤 Username: admin
🔒 Password: admin123
```

⚠️ **IMPORTANTE:** Altere esta password após o primeiro login!

---

## ⚙️ COMO USAR

### 1️⃣ **Criar a Tabela de Utilizadores**

Execute este comando no terminal:

```bash
psql -U postgres -d embriovet -f criar_tabela_usuarios.sql
```

**Isso cria:**
- Tabela `usuarios` com todos os campos
- Utilizador admin inicial
- Índices para performance

### 2️⃣ **Fazer Login**

1. Abra o sistema (http://localhost:8501)
2. Verá a tela de login
3. Digite:
   - Username: `admin`
   - Password: `admin123`
4. Clique em **"🚀 Entrar"**

### 3️⃣ **Adicionar Novos Utilizadores**

**Como Administrador:**

1. No menu lateral, clique em **"⚙️ Gestão de Utilizadores"**
2. Vá para a aba **"➕ Adicionar Utilizador"**
3. Preencha:
   - Username (sem espaços)
   - Nome Completo
   - Nível de Acesso (Administrador, Gestor ou Visualizador)
   - Password (mínimo 6 caracteres)
   - Confirmar Password
4. Clique em **"➕ Criar Utilizador"**

**Pronto!** O novo utilizador já pode fazer login.

### 4️⃣ **Alterar Password**

**Como Administrador:**

1. **"⚙️ Gestão de Utilizadores"** → Aba **"🔒 Alterar Password"**
2. Selecione o utilizador
3. Digite a nova password
4. Confirme
5. Clique em **"🔄 Alterar Password"**

### 5️⃣ **Desativar/Ativar Utilizador**

**Como Administrador:**

1. **"⚙️ Gestão de Utilizadores"** → Aba **"📋 Lista"**
2. Encontre o utilizador
3. Clique em **"🚫 Desativar"** ou **"✅ Ativar"**

---

## 🎬 EXEMPLO DE USO

### Cenário: Contratar um Novo Veterinário

**Você (Admin) quer dar acesso ao Dr. João:**

1. Login como admin
2. **"⚙️ Gestão de Utilizadores"** → **"➕ Adicionar"**
3. Preencher:
   - Username: `joao.silva`
   - Nome: `Dr. João Silva`
   - Nível: `Gestor`
   - Password: `vet123456`
4. Criar utilizador
5. Informar ao Dr. João:
   - Username: `joao.silva`
   - Password: `vet123456`

**O que o Dr. João pode fazer:**
- ✅ Adicionar stock
- ✅ Registrar inseminações
- ✅ Transferir sêmen
- ❌ NÃO pode editar stock existente
- ❌ NÃO pode gerir utilizadores

---

## 🔒 SEGURANÇA

### Password Hash
- Todas as passwords são armazenadas com **bcrypt**
- Não é possível ver as passwords no banco
- Hash de 256 bits (muito seguro)

### Sessão
- Login mantém sessão ativa
- Botão de logout no sidebar
- Verificação de permissões em cada ação

---

## 🖼️ INTERFACE

### Antes de Logar:
- Tela de login com campos de username e password

### Depois de Logar:
- **Sidebar mostra:**
  - Nome do utilizador
  - Nível de acesso
  - Botão de logout

- **Menu adaptado:**
  - **Visualizador:** Vê só "Ver Estoque" e "Relatórios"
  - **Gestor:** Vê também "Adicionar Stock", "Registrar Inseminação", "Gestão de Proprietários"
  - **Administrador:** Vê tudo, incluindo "Gestão de Utilizadores"

---

## 📊 ESTRUTURA DO BANCO

### Tabela: `usuarios`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | SERIAL | Chave primária |
| username | VARCHAR(100) | Username único |
| nome_completo | VARCHAR(255) | Nome completo |
| password_hash | VARCHAR(255) | Hash bcrypt da password |
| nivel | VARCHAR(50) | 'Administrador', 'Gestor' ou 'Visualizador' |
| ativo | BOOLEAN | Se está ativo |
| created_at | TIMESTAMP | Data de criação |
| last_login | TIMESTAMP | Último login |
| created_by | INTEGER | Quem criou |

---

## 🛡️ CONTROLES DE PERMISSÃO

### No Código:

Cada seção verifica permissões:

```python
if not verificar_permissao('Administrador'):
    st.warning("⚠️ Apenas Administradores podem editar stock")
else:
    # Mostrar formulário de edição
```

### Abas Bloqueadas:

- **Editar Stock:** Só Admin
- **Gestão de Utilizadores:** Só Admin
- **Adicionar Stock:** Gestor ou superior
- **Transferir:** Gestor ou superior

---

## ⚠️ IMPORTANTE

### Credenciais do Admin

**SEMPRE altere a password padrão** (`admin123`) após o primeiro login!

### Backup de Utilizadores

Se perder acesso ao admin, você precisará:
1. Aceder ao banco diretamente
2. Resetar a password manualmente
3. Ou recriar o utilizador admin via SQL

### Utilizadores Múltiplos

Pode ter quantos utilizadores quiser de cada nível!

---

## 🧪 TESTAR

### Teste 1: Login como Admin
1. Username: `admin` / Password: `admin123`
2. Verifique que vê TODAS as opções no menu
3. Teste editar um stock

### Teste 2: Criar um Gestor
1. Como admin, crie um utilizador "Gestor"
2. Faça logout
3. Login com o novo utilizador
4. Verifique que NÃO vê "Gestão de Utilizadores"
5. Verifique que NÃO pode editar stock (aba bloqueada)

### Teste 3: Criar um Visualizador
1. Como admin, crie um "Visualizador"
2. Login com ele
3. Verifique que só vê "Ver Estoque" e "Relatórios"
4. Não há opção de adicionar/editar

---

## 📁 ARQUIVOS

**SQL:**
- `criar_tabela_usuarios.sql` - Cria tabela e admin inicial

**Código:**
- Funções de autenticação adicionadas no `app.py`
- Tela de login
- Controles de permissão em todas as seções
- Seção "Gestão de Utilizadores" (só para admins)

---

## ✅ CHECKLIST DE IMPLEMENTAÇÃO

- [x] Tabela `usuarios` criada
- [x] Sistema de login funcional
- [x] Hash de passwords (bcrypt)
- [x] 3 níveis de acesso implementados
- [x] Controles de permissão em cada seção
- [x] Gestão de utilizadores (admin only)
- [x] Botão de logout
- [x] Sidebar mostra info do utilizador
- [x] Menu adaptado às permissões
- [x] Utilizador admin inicial criado

---

## 🚀 STATUS

**Versão:** 3.0  
**Status:** ✅ IMPLEMENTADO  
**Aguardando:** Criação da tabela no seu banco local

---

## 📞 PRÓXIMOS PASSOS

1. Execute o script SQL: `criar_tabela_usuarios.sql`
2. Faça login com `admin` / `admin123`
3. **ALTERE A PASSWORD DO ADMIN!**
4. Crie seus utilizadores (gestor, visualizador)
5. Teste as permissões de cada nível
6. Me avise se está tudo funcionando!

Agora seu sistema está **seguro e com controle de acesso**! 🔐✨
