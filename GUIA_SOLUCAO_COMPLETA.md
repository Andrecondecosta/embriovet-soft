# 🚨 GUIA DE SOLUÇÃO - Dados Mal Sincronizados

## 🐛 PROBLEMAS IDENTIFICADOS:

### **1. Valores NaN (Not a Number)**
- ❌ Local: NaN
- ❌ Qualidade: nan%
- ❌ Motilidade: nan%  
- ❌ Observações: NaN

### **2. Filtro de Garanhão Mostrando Data**
- ❌ Mostra "2009-01-14" ao invés do nome do cavalo

### **3. Nomes de Cavalos como Proprietários**
- ❌ "Rico", "Aladino" aparecendo como proprietários (são nomes de cavalos!)

---

## ✅ SOLUÇÃO COMPLETA:

### **PASSO 1: Limpar Banco de Dados** (No seu computador)

```bash
# Conectar ao PostgreSQL
psql -U postgres -d embriovet

# Executar script de limpeza
\i /caminho/para/limpar_banco.sql

# OU copiar e colar direto:
DELETE FROM inseminacoes;
DELETE FROM estoque_dono;
DELETE FROM dono;

ALTER SEQUENCE dono_id_seq RESTART WITH 1;
ALTER SEQUENCE estoque_dono_id_seq RESTART WITH 1;
ALTER SEQUENCE inseminacoes_id_seq RESTART WITH 1;

INSERT INTO dono (nome, contato, email) VALUES 
    ('Sem proprietário', '', '');

-- Sair
\q
```

---

### **PASSO 2: Preencher CSV Corretamente**

Baixe o arquivo: `base_stock_com_proprietario.csv`

**Abra no Excel e preencha assim:**

| Garanhão | Proprietário | Data | Origem | Palhetas | Qualidade | Motilidade | Concentração | ... |
|----------|--------------|------|--------|----------|-----------|------------|--------------|-----|
| Niro das figueiras | André Costa | 2024-03-20 | Espanha | 50 | 85.0 | 75.0 | 250.0 | ... |
| Retoque | Filipe Silva | 2024-03-25 | | 60 | 88.0 | 78.0 | 260.0 | ... |
| Aladino | João Santos | 2024-04-01 | | 40 | 80.0 | 70.0 | 240.0 | ... |
| Pacifico | | 2024-04-05 | | 30 | 75.0 | 65.0 | 220.0 | ... |

**IMPORTANTE:**
- ✅ Coluna "Proprietário" = NOMES DE PESSOAS (André Costa, Filipe Silva)
- ✅ Coluna "Garanhão" = NOMES DE CAVALOS (Niro, Retoque, Aladino)
- ✅ Preencha TODOS os campos numéricos (não deixe vazios)
- ✅ Se não souber algum valor, coloque 0 ou um valor padrão

---

### **PASSO 3: Importar Dados Corretamente**

```bash
# Copiar CSV preenchido
cp base_stock_com_proprietario.csv /tmp/

# Executar importação
python importar_dados.py
```

**Output esperado:**
```
📊 RESUMO DA IMPORTAÇÃO:
   ✅ Importados: 1449
   ✨ Novos proprietários criados: 15
   ❌ Erros: 0
   📦 Total: 1449
```

---

### **PASSO 4: Verificar se Está Correto**

```bash
psql -U postgres -d embriovet

-- Ver proprietários (deve ter PESSOAS, não cavalos!)
SELECT * FROM dono;
-- Resultado esperado:
-- 1 | Sem proprietário
-- 2 | André Costa
-- 3 | Filipe Silva
-- 4 | João Santos

-- Ver stock (deve ter CAVALOS com proprietários corretos)
SELECT e.garanhao, d.nome as proprietario, e.existencia_atual
FROM estoque_dono e
JOIN dono d ON e.dono_id = d.id
LIMIT 10;
-- Resultado esperado:
-- Niro das figueiras | André Costa | 50
-- Retoque | Filipe Silva | 60
-- Aladino | João Santos | 40

\q
```

---

## 🎯 ESTRUTURA CORRETA:

### ✅ **TABELA DONO (Proprietários - PESSOAS):**
```
ID | Nome             | Contato    | Email
---|------------------|------------|-------------------
1  | Sem proprietário |            |
2  | André Costa      | 912345678  | andre@embriovet.pt
3  | Filipe Silva     | 913456789  | filipe@embriovet.pt
4  | João Santos      | 914567890  | joao@embriovet.pt
```

### ✅ **TABELA ESTOQUE_DONO (Stock - CAVALOS):**
```
ID | Garanhão           | Proprietário   | Palhetas | Qualidade | Motilidade | ...
---|--------------------|--------------  |----------|-----------|------------|-----
1  | Niro das figueiras | André Costa    | 50       | 85.0      | 75.0       | ...
2  | Retoque            | Filipe Silva   | 60       | 88.0      | 78.0       | ...
3  | Aladino            | João Santos    | 40       | 80.0      | 70.0       | ...
```

---

## 🔍 CHECKLIST DE VERIFICAÇÃO:

### **No CSV:**
- [ ] Coluna "Proprietário" tem NOMES DE PESSOAS
- [ ] Coluna "Garanhão" tem NOMES DE CAVALOS
- [ ] Coluna "Qualidade" tem NÚMEROS (não vazio)
- [ ] Coluna "Motilidade" tem NÚMEROS (não vazio)
- [ ] Coluna "Concentração" tem NÚMEROS (não vazio)
- [ ] Não há células completamente vazias em campos numéricos

### **No Sistema (após importação):**
- [ ] Menu "📦 Ver Estoque" → Filtro mostra NOMES DE CAVALOS
- [ ] Resumo por Proprietário mostra NOMES DE PESSOAS
- [ ] Lotes detalhados mostram valores numéricos (não NaN)
- [ ] Qualidade, Motilidade, Concentração têm valores válidos

---

## 🆘 RESOLVER PROBLEMAS:

### **Se continuar aparecendo NaN:**

**Causa:** Valores vazios ou inválidos no CSV

**Solução:**
1. Abra o CSV no Excel
2. Procure por células vazias nas colunas: Qualidade, Motilidade, Concentração
3. Preencha com valores válidos (números)
4. Salve e reimporte

### **Se filtro mostrar data ao invés de cavalo:**

**Causa:** Campo "data_embriovet" sendo usado no filtro

**Solução:** Já corrigido no código! Apenas reimporte com dados limpos.

### **Se cavalos aparecerem como proprietários:**

**Causa:** CSV com nomes trocados ou banco com dados antigos

**Solução:**
1. Limpe o banco (PASSO 1)
2. Verifique CSV (coluna Proprietário = pessoas)
3. Reimporte

---

## 📊 EXEMPLO DE CSV CORRETO:

```csv
Garanhão,Proprietário,Data de Produção (Embriovet),Origem Externa / Referência,Palhetas Produzidas,Qualidade (%),Motilidade (%),Concentração (milhões/mL),Dose inseminante (DI),Local Armazenagem,Certificado,Existência Atual,Observações
Niro das figueiras,André Costa,2024-03-20,Espanha,50,85.0,75.0,250.0,6,Tanque A,Sim,50,Excelente qualidade
Retoque,Filipe Silva,2024-03-25,,60,88.0,78.0,260.0,6,Tanque B,Sim,60,Alta motilidade
Aladino,João Santos,2024-04-01,,40,80.0,70.0,240.0,6,Tanque C,Sim,40,Boa concentração
Pacifico,,2024-04-05,,30,75.0,65.0,220.0,6,Tanque D,Não,30,
```

**Pontos-chave:**
- ✅ Proprietário: "André Costa" (pessoa)
- ✅ Garanhão: "Niro das figueiras" (cavalo)
- ✅ Qualidade: 85.0 (número válido)
- ✅ Motilidade: 75.0 (número válido)
- ✅ Concentração: 250.0 (número válido)

---

## 🚀 RESUMO DO QUE FAZER:

1. **Limpar banco** (limpar_banco.sql)
2. **Preencher CSV** com dados corretos (pessoas como proprietários)
3. **Importar** (python importar_dados.py)
4. **Verificar** se está tudo OK
5. **Usar sistema** sem erros!

---

**🎯 Após seguir todos os passos, o sistema vai funcionar perfeitamente sem NaN, com cavalos e proprietários nos lugares certos!**
