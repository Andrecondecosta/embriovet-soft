# 🔧 SOLUÇÃO: Limpar Dados de Teste

## 🐛 PROBLEMA:
Os nomes dos garanhões estão aparecendo como nomes de proprietários.

## 💡 CAUSA:
Nos testes iniciais, criamos registros de teste onde os nomes ficaram trocados.

## ✅ SOLUÇÃO:

Execute estes comandos SQL para limpar e recomeçar:

```sql
-- Conectar ao banco
psql -U postgres -d embriovet

-- Ver o que está na tabela dono
SELECT * FROM dono;

-- Se estiver tudo errado, limpar tudo e recomeçar:

-- 1. Deletar inseminações
DELETE FROM inseminacoes;

-- 2. Deletar stock
DELETE FROM estoque_dono;

-- 3. Deletar proprietários
DELETE FROM dono;

-- 4. Criar proprietário padrão
INSERT INTO dono (nome, contato, email) VALUES 
    ('Sem proprietário', '', '');

-- 5. Sair
\q
```

## 🔄 DEPOIS:

### **Opção A: Importar do CSV**
```bash
# Preencha o CSV com proprietários corretos
# Depois execute:
python importar_dados.py
```

### **Opção B: Adicionar via Sistema**
1. Acesse: http://localhost:8501
2. Menu: "👥 Gestão de Proprietários"
3. Adicione os proprietários reais:
   - André Costa
   - Filipe Silva
   - João Santos
   - etc.
4. Menu: "➕ Adicionar Stock"
5. Adicione os lotes escolhendo o proprietário correto

## 🎯 VERIFICAR SE ESTÁ CORRETO:

```sql
-- Ver proprietários (deve ter nomes de PESSOAS, não de cavalos)
SELECT * FROM dono;

-- Resultado esperado:
-- id | nome              | contato     | email
-- ---+-------------------+-------------+------------------
-- 1  | Sem proprietário  |             |
-- 2  | André Costa       | 912345678   | andre@example.com
-- 3  | Filipe Silva      | 913456789   | filipe@example.com
```

**NÃO deveria ter:**
- ❌ Retoque
- ❌ Niro das figueiras
- ❌ Aladino
- ❌ Qualquer nome de cavalo

---

## 🚨 ATENÇÃO:

Se executar `DELETE FROM dono`, você perde TODOS os dados de stock e inseminações também (por causa das foreign keys).

**Por isso, antes de deletar:**
1. Faça backup se tiver dados importantes
2. Ou apenas adicione novos proprietários corretos e transfira os stocks depois

---

## 📝 ALTERNATIVA SEM DELETAR:

Se não quiser deletar tudo:

```sql
-- 1. Adicionar proprietários corretos
INSERT INTO dono (nome, contato, email) VALUES 
    ('André Costa', '912345678', 'andre@example.com'),
    ('Filipe Silva', '913456789', 'filipe@example.com'),
    ('João Santos', '914567890', 'joao@example.com');

-- 2. No sistema, transferir os stocks para os proprietários corretos
-- Menu: "📦 Ver Estoque" → "🔄 Transferir Proprietário"
```

---

**🎯 Resumindo:** Os nomes dos cavalos estão na tabela `dono` onde deveria ter nomes de pessoas. Precisa limpar ou adicionar proprietários corretos!
