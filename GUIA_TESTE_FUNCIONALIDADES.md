# 🧪 Guia de Teste - Novas Funcionalidades

## 📋 Pré-requisitos

Antes de começar os testes, certifique-se de que:

1. ✅ O banco de dados PostgreSQL está rodando
2. ✅ A tabela `transferencias` foi criada (execute `criar_tabela_transferencias.sql`)
3. ✅ O Streamlit está rodando (acesse http://localhost:8501)
4. ✅ Há pelo menos 2 proprietários cadastrados no sistema
5. ✅ Há pelo menos 1 lote de stock com palhetas disponíveis

---

## 🧪 Teste 1: Editar Stock

### Objetivo
Verificar se é possível editar informações de um lote de stock existente.

### Passos

1. **Navegar para Ver Estoque**
   - No menu lateral, clique em "📦 Ver Estoque"

2. **Selecionar um Garanhão**
   - No dropdown "Filtrar por Garanhão", escolha qualquer garanhão
   - Você verá os lotes agrupados por proprietário

3. **Abrir um Lote**
   - Clique para expandir qualquer lote (expander)
   - Você verá 3 abas: "📋 Detalhes", "✏️ Editar", "🔄 Transferir"

4. **Editar o Lote**
   - Clique na aba "✏️ Editar"
   - Modifique algum campo, por exemplo:
     - Mude a "Qualidade (%)" de 85 para 90
     - Ou altere a "Existência Atual"
   - Clique em "💾 Guardar Alterações"

### ✅ Resultado Esperado
- Mensagem de sucesso: "✅ Stock atualizado com sucesso!"
- A página recarrega automaticamente
- As alterações aparecem nos "Detalhes" do lote

### ❌ Possíveis Problemas
- Se aparecer erro de conexão ao banco, verifique as credenciais em `.env`
- Se não salvar, verifique os logs do Streamlit

---

## 🧪 Teste 2: Adicionar Proprietário "On-the-fly"

### Objetivo
Verificar se é possível adicionar um novo proprietário diretamente da tela "Adicionar Stock".

### Passos

1. **Navegar para Adicionar Stock**
   - No menu lateral, clique em "➕ Adicionar Stock"

2. **Abrir o Expander de Adicionar Proprietário**
   - No topo da página, clique em "➕ Adicionar Novo Proprietário"

3. **Adicionar Novo Proprietário**
   - Digite um nome de teste, por exemplo: "Teste António"
   - Clique em "Adicionar Proprietário"

### ✅ Resultado Esperado
- Mensagem de sucesso: "✅ Proprietário 'Teste António' adicionado com sucesso!"
- A página recarrega
- O novo proprietário aparece no dropdown "Proprietário do Sémen *" abaixo

### ❌ Possíveis Problemas
- Se não aparecer no dropdown, tente recarregar a página manualmente (F5)
- Se der erro, verifique se a tabela `dono` existe no banco

---

## 🧪 Teste 3: Transferência Parcial de Sêmen

### Objetivo
Verificar se é possível transferir uma quantidade parcial de palhetas de um proprietário para outro.

### Passos

1. **Navegar para Ver Estoque**
   - No menu lateral, clique em "📦 Ver Estoque"

2. **Selecionar um Lote com Palhetas Disponíveis**
   - Escolha um garanhão que tenha estoque disponível
   - Expanda um lote que tenha pelo menos 10 palhetas

3. **Abrir a Aba de Transferir**
   - Clique na aba "🔄 Transferir"

4. **Configurar a Transferência**
   - Em "Para qual proprietário?", selecione um proprietário diferente do atual
   - Em "Quantidade de palhetas", digite um número menor que o total
     - Exemplo: se tem 50 palhetas, digite 10
   - Clique em "🔄 Transferir Palhetas"

### ✅ Resultado Esperado
- Mensagem de sucesso: "✅ 10 palhetas transferidas de [Origem] para [Destino]!"
- A página recarrega
- A quantidade do lote origem diminui (de 50 para 40)
- O proprietário destino agora tem um lote com as palhetas transferidas

### ❌ Possíveis Problemas
- Se der erro "Quantidade insuficiente", verifique se o lote tem palhetas disponíveis
- Se a transferência não aparecer no histórico, verifique se a tabela `transferencias` existe

---

## 🧪 Teste 4: Relatório de Transferências

### Objetivo
Verificar se o histórico de transferências está sendo registrado corretamente.

### Passos

1. **Realizar uma Transferência**
   - Siga os passos do **Teste 3** acima para fazer pelo menos 1 transferência

2. **Navegar para Relatórios**
   - No menu lateral, clique em "📈 Relatórios"

3. **Abrir a Aba de Transferências**
   - Clique na sub-aba "🔄 Transferências"

4. **Verificar o Histórico**
   - Você deve ver uma tabela com as transferências realizadas
   - Colunas: Garanhão, De, Para, Palhetas, Data

### ✅ Resultado Esperado
- A tabela mostra todas as transferências realizadas
- As métricas no topo mostram:
  - Total de Transferências
  - Total de Palhetas Transferidas
- Os dados estão corretos (garanhão, origem, destino, quantidade, data)

### ❌ Possíveis Problemas
- Se aparecer "Nenhuma transferência registrada", verifique se:
  1. A tabela `transferencias` existe no banco
  2. Você realmente completou uma transferência (Teste 3)
- Se aparecer erro de SQL, execute o script `criar_tabela_transferencias.sql`

---

## 🧪 Teste 5: Integração Completa (Cenário Real)

### Objetivo
Simular um fluxo completo de uso do sistema com as novas funcionalidades.

### Cenário
Você é o gestor da Embriovet e precisa:
1. Adicionar um novo proprietário
2. Adicionar stock para esse proprietário
3. Transferir parte desse stock para outro proprietário
4. Editar informações do stock
5. Verificar relatórios

### Passos Detalhados

**1. Adicionar Novo Proprietário "Ricardo"**
- Vá para "➕ Adicionar Stock"
- Expanda "➕ Adicionar Novo Proprietário"
- Digite "Ricardo" e adicione

**2. Adicionar Stock para Ricardo**
- No formulário "Inserir novo stock", preencha:
  - Garanhão: "Campeão"
  - Proprietário: "Ricardo"
  - Palhetas Produzidas: 100
  - Qualidade: 85
  - Concentração: 250
  - Motilidade: 75
  - Local: "Tanque C"
  - Certificado: "Sim"
- Clique em "💾 Salvar"

**3. Transferir 30 Palhetas para Outro Proprietário**
- Vá para "📦 Ver Estoque"
- Selecione "Campeão"
- Expanda o lote do Ricardo
- Na aba "🔄 Transferir":
  - Escolha outro proprietário existente
  - Digite quantidade: 30
  - Clique em "🔄 Transferir Palhetas"

**4. Editar o Lote Original**
- No mesmo lote do Ricardo (agora com 70 palhetas)
- Aba "✏️ Editar"
- Mude a Qualidade para 90%
- Salve

**5. Verificar Relatórios**
- Vá para "📈 Relatórios"
- Aba "🔄 Transferências" → Deve mostrar a transferência de 30 palhetas
- Aba "📊 Estatísticas" → Deve incluir "Campeão" nos top garanhões

### ✅ Resultado Esperado
- Todas as operações completam sem erros
- Os dados estão consistentes em todas as telas
- O histórico está completo e correto

---

## 📊 Checklist de Validação

Use este checklist para garantir que todas as funcionalidades estão operacionais:

- [ ] **Editar Stock**
  - [ ] Formulário abre com dados pré-preenchidos
  - [ ] Alterações são salvas no banco
  - [ ] Dados atualizados aparecem nos detalhes
  - [ ] Validações funcionam (quantidades positivas, etc.)

- [ ] **Adicionar Proprietário On-the-fly**
  - [ ] Expander aparece na tela "Adicionar Stock"
  - [ ] Novo proprietário é criado com sucesso
  - [ ] Aparece imediatamente no dropdown
  - [ ] Não precisa navegar para "Gestão de Proprietários"

- [ ] **Transferência Parcial**
  - [ ] Pode escolher quantidade menor que o total
  - [ ] Quantidade é descontada do lote origem
  - [ ] Proprietário destino recebe as palhetas
  - [ ] Se destino já tem lote do mesmo garanhão, soma as quantidades
  - [ ] Validações funcionam (quantidade disponível, etc.)

- [ ] **Relatório de Transferências**
  - [ ] Tabela `transferencias` existe no banco
  - [ ] Transferências são registradas automaticamente
  - [ ] Relatório mostra dados corretos
  - [ ] Métricas são calculadas corretamente

---

## 🐛 Troubleshooting

### Erro: "relation 'transferencias' does not exist"

**Solução:**
```bash
psql -U postgres -d embriovet -f criar_tabela_transferencias.sql
```

### Erro: "can't adapt type 'numpy.int64'"

**Solução:** Este erro já está resolvido com a função `to_py()` no código. Se ainda aparecer, verifique se você está usando a versão mais recente do `app.py`.

### Transferência não aparece no relatório

**Verificações:**
1. Execute no psql:
```sql
SELECT * FROM transferencias ORDER BY data_transferencia DESC LIMIT 5;
```
2. Se a tabela estiver vazia, a transferência não foi registrada
3. Verifique os logs do Streamlit para erros

### Proprietário não aparece no dropdown após adicionar

**Solução:** 
- Recarregue a página manualmente (F5)
- Ou clique em outra aba e volte para "Adicionar Stock"

---

## 📝 Notas Importantes

1. **Backup:** Sempre faça backup do banco antes de testes extensivos
2. **Logs:** Monitore os logs do Streamlit em caso de erros
3. **Performance:** Com muitos registros, as queries podem ficar lentas. Os índices criados ajudam nisso.
4. **Validações:** O sistema tem validações para evitar dados inválidos, mas sempre revise os dados inseridos.

---

## ✅ Conclusão

Se todos os testes passarem, o sistema está pronto para uso com as 4 novas funcionalidades:
- ✏️ Edição de stock
- ➕ Adição rápida de proprietários
- 🔄 Transferências parciais
- 📊 Relatório de transferências

Caso encontre problemas, consulte a seção de Troubleshooting ou verifique os logs do sistema.
