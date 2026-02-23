# 📤 NOVA FUNCIONALIDADE - Transferências Externas (Vendas/Envios)

**Data:** 02/02/2026  
**Versão:** 2.3  
**Funcionalidade:** Registrar vendas e envios para fora do sistema

---

## 🎯 O QUE FOI ADICIONADO?

### ✨ Nova Funcionalidade: **Transferência Externa**

Agora você pode registrar quando **vende ou envia sêmen para alguém que NÃO está cadastrado** no sistema!

**O que acontece:**
- ✅ O sêmen **sai do stock** (diminui a quantidade)
- ✅ **Registra para quem foi** (nome do comprador/destinatário)
- ✅ **Fica no histórico** com todos os detalhes
- ✅ Pode adicionar **tipo** (Venda, Doação, Exportação, Outro)
- ✅ Pode adicionar **observações** (valor, contato, etc.)

---

## 📍 ONDE ESTÁ?

### 1. **Na Aba Transferir**
**Localização:** Ver Estoque → Expander do lote → Tab "🔄 Transferir"

Agora ao abrir a aba "Transferir", você verá **2 opções**:

**🔄 Interna (para outro proprietário do sistema)**
- Mesma funcionalidade de antes
- Transfere entre proprietários cadastrados

**📤 Externa (venda/envio para fora)**
- **NOVA!** Registra saída para clientes/pessoas não cadastradas

### 2. **No Relatório**
**Localização:** Relatórios → Tab "📤 Transferências Externas"

Novo relatório separado mostrando:
- Todas as vendas e envios externos
- Filtros por tipo e garanhão
- Resumo por destinatário
- Métricas de total vendido

---

## 🎬 COMO USAR?

### Passo a Passo: Registrar Venda/Envio

1. **Vá para Ver Estoque**
   - Escolha o garanhão
   - Abra o lote que quer vender/enviar

2. **Clique na aba "🔄 Transferir"**

3. **Escolha "📤 Externa (venda/envio para fora)"**

4. **Preencha os dados:**
   - **Nome do Comprador/Destinatário*** (obrigatório)
     - Ex: "João Silva", "Fazenda Santa Maria", "Cliente ABC"
   
   - **Tipo de Saída**
     - Venda
     - Doação
     - Exportação
     - Outro
   
   - **Quantidade de palhetas**
     - Quantidade que vai sair
   
   - **Observações** (opcional)
     - Ex: "Valor: R$ 5.000, Pago em dinheiro"
     - Ex: "Contato: (11) 98888-8888"
     - Ex: "Entrega agendada para 15/02"

5. **Clique em "📤 Enviar para Externo"**

6. **Pronto!** ✅
   - O stock diminui automaticamente
   - Fica registrado no histórico

---

## 📊 RELATÓRIO DE TRANSFERÊNCIAS EXTERNAS

### Como Visualizar:

1. Vá para **"📈 Relatórios"**
2. Clique na aba **"📤 Transferências Externas"**

### O que você vê:

**Métricas no topo:**
- Total de Saídas
- Total de Palhetas Vendidas/Enviadas
- Número de Vendas

**Filtros:**
- Por Tipo (Venda, Doação, etc.)
- Por Garanhão

**Tabela principal:**
- Garanhão
- Proprietário (quem vendeu/enviou)
- Destinatário (comprador)
- Tipo
- Quantidade
- Data
- Observações

**Detalhes expandidos:**
- Resumo por destinatário
- Total de palhetas por cliente

---

## 🆚 DIFERENÇA: Interna vs Externa

| Aspecto | Transferência Interna | Transferência Externa |
|---------|----------------------|----------------------|
| **Para quem** | Proprietários do sistema | Pessoas/clientes fora do sistema |
| **O que acontece** | Muda de proprietário no stock | Sai do stock completamente |
| **Destinatário** | Seleciona da lista | Digita o nome |
| **Observações** | Não tem campo | Pode adicionar detalhes |
| **Tipo** | Não aplica | Venda/Doação/Exportação |
| **Relatório** | "Transferências Internas" | "Transferências Externas" |

---

## 🧪 EXEMPLO DE USO

### Cenário: Vendeu 20 palhetas do Garanhão "Campeão"

1. Ver Estoque → Selecionar "Campeão"
2. Abrir o lote (ex: tem 100 palhetas)
3. Aba "Transferir" → Escolher "📤 Externa"
4. Preencher:
   - Comprador: "Haras do Vale"
   - Tipo: "Venda"
   - Quantidade: 20
   - Observações: "Valor: R$ 10.000, Pago via transferência"
5. Clicar em "📤 Enviar para Externo"

**Resultado:**
- ✅ Lote agora tem 80 palhetas (100 - 20)
- ✅ Fica registrado que "Haras do Vale" comprou 20 palhetas
- ✅ Aparece no relatório "Transferências Externas"

---

## ⚠️ AÇÃO NECESSÁRIA

Para usar esta funcionalidade, você precisa criar a tabela no banco:

```bash
psql -U postgres -d embriovet -f criar_tabela_transferencias_externas.sql
```

**Isso cria:**
- Tabela `transferencias_externas`
- Todos os campos necessários
- Índices para performance

---

## 📁 ARQUIVOS

**Scripts SQL:**
- `criar_tabela_transferencias_externas.sql` - Criar a tabela

**Código:**
- Função `transferir_palhetas_externo()` - Nova função
- Função `carregar_transferencias_externas()` - Nova função
- Interface atualizada na aba "Transferir"
- Novo relatório na aba "Relatórios"

---

## ✅ BENEFÍCIOS

✅ **Controle completo** de saídas do stock  
✅ **Histórico de vendas** detalhado  
✅ **Rastreabilidade** de para quem foi o sêmen  
✅ **Relatórios separados** (internas vs externas)  
✅ **Flexibilidade** para adicionar observações  
✅ **Tipos diferentes** de saída (venda, doação, etc.)  

---

## 🐛 POSSÍVEIS PROBLEMAS

### "Erro: relation 'transferencias_externas' does not exist"

**Solução:** Execute o script SQL:
```bash
psql -U postgres -d embriovet -f criar_tabela_transferencias_externas.sql
```

### "Não vejo a opção 'Externa' na aba Transferir"

**Solução:** 
1. Recarregue a página (F5)
2. Verifique se o Streamlit reiniciou corretamente

---

## 📊 RESUMO

**O que mudou na aba Transferir:**
- ANTES: Só transferia entre proprietários
- AGORA: 2 opções → Interna OU Externa

**O que mudou em Relatórios:**
- ANTES: 3 tabs (Inseminações, Transferências, Estatísticas)
- AGORA: 4 tabs (Inseminações, Transferências Internas, **Transferências Externas**, Estatísticas)

---

**Status:** ✅ IMPLEMENTADO  
**Aguardando:** Criação da tabela no seu banco local
