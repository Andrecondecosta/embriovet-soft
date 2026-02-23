# 🚀 GUIA DE INÍCIO RÁPIDO - Sistema Completo v3.0

## ⚡ CONFIGURAÇÃO INICIAL (Execute estes 3 comandos)

### 1. Criar Tabela de Transferências (Correção)
```bash
psql -U postgres -d embriovet -f corrigir_tabela_transferencias.sql
```

### 2. Criar Tabela de Transferências Externas (Vendas)
```bash
psql -U postgres -d embriovet -f criar_tabela_transferencias_externas.sql
```

### 3. Criar Tabela de Utilizadores (Autenticação)
```bash
psql -U postgres -d embriovet -f criar_tabela_usuarios.sql
```

---

## 🔐 PRIMEIRO ACESSO

**Credenciais iniciais:**
- 👤 Username: `admin`
- 🔒 Password: `admin123`

⚠️ **IMPORTANTE:** Altere esta password após o primeiro login!

---

## ✅ TUDO PRONTO!

Após executar os 3 comandos acima, seu sistema está **100% funcional** com:

### 🎯 Funcionalidades Completas:
- ✅ **Autenticação** com 3 níveis de acesso
- ✅ **Editar Stock** (só admin)
- ✅ **Adicionar Proprietário** com modal "+" (3 locais)
- ✅ **Transferência Parcial** entre proprietários
- ✅ **Transferência Externa** (vendas/envios)
- ✅ **Relatórios:** Inseminações, Transferências Internas, Transferências Externas, Estatísticas

### 👥 3 Níveis de Acesso:
- 🔴 **Administrador** - Acesso total (incluindo editar e gerir utilizadores)
- 🟡 **Gestor/Veterinário** - Operações do dia-a-dia (adicionar, transferir)
- 🟢 **Visualizador** - Somente leitura (ver estoque e relatórios)

---

## 📚 DOCUMENTAÇÃO DISPONÍVEL

Consulte estes arquivos para detalhes:

1. **`SISTEMA_AUTENTICACAO.md`** - Sistema de login e permissões
2. **`NOVA_FUNCIONALIDADE_TRANSFERENCIAS_EXTERNAS.md`** - Vendas/envios externos
3. **`ATUALIZACAO_INTERFACE.md`** - Botão "+" para adicionar proprietários
4. **`GUIA_TESTE_FUNCIONALIDADES.md`** - Como testar tudo

---

## 🎬 WORKFLOW TÍPICO

### Como Administrador:
1. Login → Criar utilizadores (gestor, visualizador)
2. Gerir stock (adicionar, editar, transferir)
3. Ver relatórios
4. Gerir proprietários

### Como Gestor:
1. Login → Adicionar stock
2. Registrar inseminações
3. Transferir sêmen (interna ou externa)
4. Ver relatórios

### Como Visualizador:
1. Login → Ver estoque
2. Ver relatórios
3. (Sem permissões de edição)

---

## 🔥 DESTAQUES DA VERSÃO 3.0

### 🔐 Autenticação Segura
- Hash bcrypt para passwords
- Sessão segura
- Controle de permissões em todas as ações

### 📤 Transferências Externas (Novo!)
- Registrar vendas para fora do sistema
- Tipos: Venda, Doação, Exportação
- Observações (valor, contato, etc.)
- Relatório separado com filtros

### ➕ Adicionar Proprietário Rápido
- Botão "+" em 3 locais diferentes
- Modal popup intuitivo
- Seleção automática após criar

### ✏️ Edição Protegida
- Somente administradores podem editar
- Gestor pode adicionar mas não editar
- Controle fino de permissões

---

## ✅ CHECKLIST FINAL

Antes de começar a usar, verifique:

- [ ] Executou os 3 scripts SQL
- [ ] Consegue fazer login com `admin` / `admin123`
- [ ] Alterou a password do admin
- [ ] Criou pelo menos 1 utilizador de cada nível
- [ ] Testou as permissões (gestor não pode editar)
- [ ] Fez uma transferência interna
- [ ] Fez uma transferência externa (venda)
- [ ] Verificou os relatórios

---

## 🆘 PROBLEMAS COMUNS

### "Erro: relation 'transferencias' does not exist"
**Solução:** Execute `corrigir_tabela_transferencias.sql`

### "Erro: relation 'transferencias_externas' does not exist"
**Solução:** Execute `criar_tabela_transferencias_externas.sql`

### "Não aparece tela de login"
**Solução:** Execute `criar_tabela_usuarios.sql`

### "Utilizador ou password incorretos"
**Solução:** Use `admin` / `admin123` (credenciais iniciais)

---

## 📊 RESUMO DO SISTEMA

**Versão:** 3.0  
**Tabelas no Banco:** 7
- `dono` (proprietários)
- `estoque_dono` (stock)
- `inseminacoes` (registros)
- `transferencias` (internas)
- `transferencias_externas` (vendas)
- `usuarios` (autenticação)

**Níveis de Acesso:** 3
- Administrador
- Gestor
- Visualizador

**Relatórios:** 4
- Inseminações
- Transferências Internas
- Transferências Externas
- Estatísticas

---

## 🎉 ESTÁ PRONTO!

Seu sistema **Embriovet Gestor v3.0** está completo e pronto para uso profissional!

**Funcionalidades implementadas:**
✅ Gestão de stock multi-proprietário  
✅ Edição de stock (admin only)  
✅ Transferências parciais entre proprietários  
✅ Vendas/envios para clientes externos  
✅ Registro de inseminações  
✅ Relatórios completos  
✅ Autenticação com 3 níveis  
✅ Gestão de utilizadores  

**Próximos Passos:**
1. Execute os 3 comandos SQL
2. Faça login
3. Configure seus utilizadores
4. Comece a usar!

Qualquer dúvida, consulte a documentação! 📚✨
