# 📋 COMO USAR O CSV COM COLUNA PROPRIETÁRIO

## ✅ O QUE FOI FEITO:

Criei um novo arquivo CSV com a coluna **"Proprietário"** adicionada:

**Arquivo:** `base_stock_com_proprietario.csv`

---

## 📊 ESTRUTURA DO NOVO CSV:

```
Garanhão | Proprietário | Data de Produção | Origem Externa | Palhetas | Qualidade | ...
---------|--------------|------------------|----------------|----------|-----------|-----
Niro     | (vazio)      | 2024-03-20      | Espanha        | 29       | 60%       | ...
Retoque  | (vazio)      | 2024-03-25      |                | 40       | 85%       | ...
```

**A coluna "Proprietário" está VAZIA** para você preencher!

---

## 🎯 COMO PREENCHER O CSV:

### **OPÇÃO 1: Excel/LibreOffice (Recomendado)**

1. **Baixe o arquivo:** `base_stock_com_proprietario.csv`

2. **Abra no Excel ou LibreOffice Calc**

3. **Preencha a coluna "Proprietário"** (coluna B):
   ```
   Linha 2: André Costa
   Linha 3: Filipe Silva
   Linha 4: João Santos
   Linha 5: (deixar vazio se não tem proprietário)
   ```

4. **Salve como CSV** (manter formato CSV)

5. **Use este arquivo** para importar

### **OPÇÃO 2: Editor de Texto**

Edite diretamente no Notepad/VSCode:

```csv
Garanhão,Proprietário,Data de Produção,...
Niro das figueiras,André Costa,2024-03-20,...
Retoque,Filipe Silva,2024-03-25,...
Pacifico lagesse,João Santos,,...
Obélix,,2024-04-01,...
```

---

## 📥 COMO IMPORTAR:

### **No seu computador (com PostgreSQL configurado):**

```bash
# 1. Baixe o CSV preenchido
# Coloque em: /tmp/base_stock_com_proprietario.csv

# 2. Execute o script
python importar_dados.py
```

### **O que o script faz:**

✅ Lê a coluna "Proprietário"  
✅ **Cria automaticamente** proprietários que não existem  
✅ **Associa cada lote** ao proprietário correto  
✅ Se "Proprietário" estiver vazio → usa "Sem proprietário"  

**Exemplo:**
```
CSV tem: 
- Linha 1: Garanhão "Niro" | Proprietário "André Costa"
- Linha 2: Garanhão "Retoque" | Proprietário "André Costa"  
- Linha 3: Garanhão "Niro" | Proprietário "Filipe Silva"
- Linha 4: Garanhão "Obélix" | Proprietário (vazio)

Sistema cria:
- Proprietário "André Costa" (ID 1)
- Proprietário "Filipe Silva" (ID 2)  
- Proprietário "Sem proprietário" (ID 3)

Stock criado:
- Niro do André Costa (50 palhetas)
- Retoque do André Costa (60 palhetas)
- Niro do Filipe Silva (40 palhetas)  
- Obélix sem proprietário (30 palhetas)
```

---

## 🎨 EXEMPLOS DE PREENCHIMENTO:

### **Exemplo 1: Mesmo garanhão, vários proprietários**

```csv
Garanhão,Proprietário,Palhetas,...
Retoque,André Costa,50,...
Retoque,Filipe Silva,60,...
Retoque,João Santos,40,...
```

**Resultado no sistema:**
- 📦 Retoque → 3 lotes diferentes
  - 👤 André: 50 palhetas
  - 👤 Filipe: 60 palhetas
  - 👤 João: 40 palhetas

### **Exemplo 2: Sem proprietário**

```csv
Garanhão,Proprietário,Palhetas,...
Niro,,50,...
Obélix,,30,...
```

**Resultado:**
- Ambos atribuídos a "Sem proprietário"

---

## 🔄 EDITAR DEPOIS:

Após importar, você pode editar tudo no sistema:

1. **Menu:** "📦 Ver Estoque"
2. **Selecionar garanhão**
3. **Clicar em:** "🔄 Transferir Proprietário"
4. **Escolher:** Novo proprietário

OU use a nova aba:

1. **Menu:** "👥 Gestão de Proprietários"  
2. **Adicionar/Editar/Deletar** proprietários

---

## 📝 DICAS:

### ✅ **FAÇA:**
- Preencha nomes completos: "André Costa" (não só "André")
- Use sempre o mesmo nome para o mesmo proprietário
- Deixe vazio se não souber o proprietário

### ❌ **NÃO FAÇA:**
- Não use "Sem proprietário" no CSV (deixe vazio)
- Não use abreviações diferentes: "André" vs "Andre Costa"
- Não use caracteres especiais estranhos

---

## 🎯 CENÁRIO REAL:

Você tem 1.449 registros de stock.

### **SE você souber os proprietários:**
1. Abra `base_stock_com_proprietario.csv` no Excel
2. Preencha coluna "Proprietário" linha por linha
3. Salve
4. Execute `python importar_dados.py`

### **SE NÃO souber os proprietários:**
1. Execute `python importar_dados.py` (todos ficam "Sem proprietário")
2. No sistema, vá editando aos poucos:
   - "📦 Ver Estoque"
   - Transferir proprietário lote por lote

---

## 📊 ESTATÍSTICAS:

Após importação, o script mostra:

```
📊 RESUMO DA IMPORTAÇÃO:
   ✅ Importados: 1449
   ✨ Novos proprietários criados: 25
   ❌ Erros: 0
   📦 Total: 1449

📋 Proprietários criados automaticamente:
   - André Costa
   - Filipe Silva
   - João Santos
   - Maria Oliveira
   - (... mais 21)
```

---

## 🆘 PROBLEMAS COMUNS:

### **"Erro ao ler CSV"**
- Salve como CSV UTF-8
- Não use Excel com ";" como separador

### **"Proprietário não aparece"**
- Verifique se preencheu a coluna B
- Certifique-se que salvou o arquivo

### **"Proprietários duplicados"**
- Use sempre o mesmo nome exato
- "André Costa" ≠ "Andre Costa" ≠ "ANDRÉ COSTA"

---

## 📥 DOWNLOAD:

**Arquivo pronto para preencher:**  
`/app/base_stock_com_proprietario.csv`

**Linhas:** 1.449  
**Colunas:** 13 (incluindo "Proprietário")  
**Tamanho:** 91 KB

---

**🎉 Pronto! Agora você pode preencher os proprietários no Excel e importar tudo de uma vez!**
