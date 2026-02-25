# 🐴 EmbrioVet - Sistema de Gestão de Sémen

Sistema completo para gestão de sémen equino, desenvolvido em Streamlit com PostgreSQL.

## 📋 Funcionalidades

### 👥 Gestão de Proprietários
- Cadastro completo com dados pessoais e fiscais
- Sistema de ativo/inativo automático baseado em stock
- Validação de nomes duplicados
- Dados de faturação

### 📦 Gestão de Stock
- Controle detalhado de lotes por garanhão e proprietário
- Informações técnicas: qualidade, motilidade, concentração
- Rastreabilidade completa (data de criação, quem criou)
- Filtros e busca avançada
- Lotes com 0 palhetas são automaticamente ocultados

### 📝 Inseminações
- Registro de uso de sémen
- Controle de palhetas gastas
- Histórico completo por égua e garanhão
- Atualização automática de stock

### 🔄 Transferências
- **Internas:** Entre proprietários do sistema
- **Externas:** Vendas, doações, exportações
- Rastreamento completo com data e observações
- Histórico detalhado

### 📊 Relatórios
- Relatórios por garanhão e proprietário
- Histórico completo de movimentações
- Exportação para Excel e PDF
- Visualizações e métricas

### 👤 Gestão de Utilizadores
- 3 níveis de acesso: Administrador, Gestor, Visualizador
- Autenticação segura com bcrypt
- Controle de permissões por funcionalidade

## 🚀 Deploy em Produção

### Render (Recomendado)

Siga o guia completo em [DEPLOY_RENDER.md](DEPLOY_RENDER.md)

**Quick Start:**
```bash
# 1. Fazer push para o Git
git add .
git commit -m "Deploy para produção"
git push origin main

# 2. No Render:
# - New → Blueprint
# - Conectar repositório
# - Aplicar render.yaml
```

## 💻 Desenvolvimento Local

### Pré-requisitos
- Python 3.11+
- PostgreSQL 12+

### Instalação

```bash
# 1. Clonar repositório
git clone <seu-repo>
cd embriovet-soft

# 2. Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# 3. Instalar dependências
pip install -r requirements_streamlit.txt

# 4. Configurar banco de dados
createdb embriovet
psql -U postgres -d embriovet -f adicionar_campos_proprietarios.sql
psql -U postgres -d embriovet -f adicionar_constraint_nome_unico.sql
psql -U postgres -d embriovet -f adicionar_auditoria_stock.sql

# 5. Configurar variáveis de ambiente
# Criar arquivo .env com:
DB_NAME=embriovet
DB_USER=postgres
DB_PASSWORD=sua_senha
DB_HOST=localhost
DB_PORT=5432

# 6. Iniciar aplicação
streamlit run app.py
```

A aplicação estará disponível em `http://localhost:8501`

**Credenciais padrão:**
- Username: `admin`
- Password: `admin123`

⚠️ **Altere a senha após o primeiro login!**

## 📁 Estrutura do Projeto

```
embriovet-soft/
├── app.py                              # Aplicação principal
├── requirements_streamlit.txt          # Dependências Python
├── .streamlit/
│   └── config.toml                     # Configurações Streamlit
├── adicionar_campos_proprietarios.sql  # Script SQL
├── adicionar_constraint_nome_unico.sql # Script SQL
├── adicionar_auditoria_stock.sql       # Script SQL
├── setup_database.py                   # Setup automático do banco
├── start.sh                            # Script de inicialização
├── render.yaml                         # Configuração Render
├── DEPLOY_RENDER.md                    # Guia de deploy
└── README.md                           # Este arquivo
```

## 🔒 Segurança

- ✅ Senhas hasheadas com bcrypt
- ✅ HTTPS automático em produção (Render)
- ✅ Validação de entrada em todos os formulários
- ✅ Proteção contra SQL injection (prepared statements)
- ✅ Controle de acesso baseado em roles

## 🛠️ Tecnologias

- **Frontend:** Streamlit 1.40+
- **Backend:** Python 3.11+
- **Database:** PostgreSQL 12+
- **Auth:** bcrypt
- **Reports:** ReportLab (PDF), Pandas (Excel)
- **Deploy:** Render

## 📊 Modelos de Dados

### Principais Tabelas

- `dono` - Proprietários
- `estoque_dono` - Stock de sémen
- `inseminacoes` - Registros de inseminação
- `transferencias` - Transferências internas
- `transferencias_externas` - Vendas/doações
- `usuarios` - Utilizadores do sistema

Ver scripts SQL para estrutura completa.

## 🐛 Resolução de Problemas

### Erro de conexão ao banco
```bash
# Verificar se PostgreSQL está rodando
sudo systemctl status postgresql

# Verificar credenciais no .env
cat .env
```

### Erro ao importar dependências
```bash
# Reinstalar dependências
pip install -r requirements_streamlit.txt --force-reinstall
```

### Streamlit não inicia
```bash
# Verificar portas em uso
lsof -i :8501

# Matar processo se necessário
kill -9 <PID>
```

## 📈 Atualizações

Para atualizar a aplicação em produção:

```bash
git add .
git commit -m "Descrição das mudanças"
git push origin main
```

O Render fará deploy automático.

## 📝 Licença

Uso privado - EmbrioVet © 2025

## 👨‍💻 Suporte

Para questões ou suporte:
- Abrir issue no repositório
- Contatar o desenvolvedor

---

**Desenvolvido com ❤️ para gestão veterinária profissional**
