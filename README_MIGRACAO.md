# 🚨 AÇÃO NECESSÁRIA - Executar Migração do Banco de Dados

## ❌ Problema Atual
A aplicação está apresentando o erro: `column "ativo" does not exist`

## ✅ Solução
Execute o script SQL `adicionar_campos_proprietarios.sql` no seu banco de dados local.

---

## 📝 Passo a Passo

### 1️⃣ Abra o Terminal/CMD no seu computador

### 2️⃣ Navegue até a pasta do projeto
```bash
cd /caminho/para/embriovet-soft
```

### 3️⃣ Execute o script SQL
```bash
psql -U postgres -d embriovet -f adicionar_campos_proprietarios.sql
```
**Senha padrão:** 123

### 4️⃣ Instale o reportlab (necessário para PDF)
```bash
pip install reportlab
```

### 5️⃣ Reinicie o Streamlit
```bash
# Pare a aplicação com Ctrl+C
# Depois execute:
streamlit run app.py
```

---

## 🔍 Verificar se funcionou

Execute este comando para ver as novas colunas:
```bash
psql -U postgres -d embriovet -c "\d dono"
```

Você deve ver estas colunas novas:
- ✅ ativo
- ✅ email
- ✅ telemovel
- ✅ nome_completo
- ✅ nif
- ✅ morada
- ✅ codigo_postal
- ✅ cidade

---

## 🎯 O que você vai ganhar

### 1. Sistema de Status Ativo/Inativo
- Proprietários com stock = 0 ficam automaticamente inativos
- Proprietários inativos não aparecem em pesquisas e relatórios
- Você pode ativar/desativar manualmente

### 2. Perfil Completo de Proprietários
- Email e telemóvel para contato
- Dados de faturação (NIF, morada, código postal, cidade)

### 3. Edição de Perfis
- Botão de editar em cada proprietário
- Formulário completo com todos os campos

### 4. Filtros Inteligentes
- Ver todos, apenas ativos ou apenas inativos
- Relatórios mostram apenas proprietários ativos

### 5. Exportação em PDF
- Relatórios completos dos garanhões em PDF profissional
- Inclui observações das transferências externas

---

## 🆘 Precisa de Ajuda?

Se encontrar algum problema, verifique:

1. PostgreSQL está rodando?
2. As credenciais estão corretas? (user: postgres, password: 123)
3. O banco 'embriovet' existe?

**Comando para verificar conexão:**
```bash
psql -U postgres -l
```

---

## 📚 Arquivos Importantes

- `adicionar_campos_proprietarios.sql` - Script de migração
- `app.py` - Aplicação principal (já atualizada)
- `INSTRUÇÕES_PROPRIETARIOS.txt` - Instruções detalhadas

---

✨ Após executar estes passos, sua aplicação estará totalmente funcional com todas as novas funcionalidades!
