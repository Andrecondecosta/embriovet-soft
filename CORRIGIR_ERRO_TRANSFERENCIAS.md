# 🔧 CORRIGIR ERRO - Tabela Transferências

## ❌ O ERRO

```
column "estoque_id" of relation "transferencias" does not exist
```

**O que significa:** A tabela `transferencias` existe no seu banco, mas está com a estrutura errada (falta a coluna `estoque_id`).

---

## ✅ SOLUÇÃO RÁPIDA

Execute este comando no seu terminal:

```bash
psql -U postgres -d embriovet -f corrigir_tabela_transferencias.sql
```

**OU** copie e cole o conteúdo do arquivo no psql.

---

## 📋 O QUE O SCRIPT FAZ

1. **Remove a tabela antiga** (se existir) que está com estrutura incorreta
2. **Cria a tabela nova** com TODAS as colunas necessárias:
   - `id` (chave primária)
   - `estoque_id` (referência ao lote)
   - `proprietario_origem_id` (quem cedeu)
   - `proprietario_destino_id` (quem recebeu)
   - `quantidade` (número de palhetas)
   - `data_transferencia` (quando aconteceu)
3. **Cria índices** para melhorar performance

---

## ⚠️ IMPORTANTE

**Se você já tiver dados de transferências na tabela antiga, eles serão PERDIDOS.**

Se você tem dados importantes, me avise antes de executar o script e eu crio uma versão que preserva os dados.

---

## 🧪 COMO VERIFICAR SE FUNCIONOU

Após executar o script, tente fazer uma transferência no sistema:

1. Vá para **"📦 Ver Estoque"**
2. Escolha um garanhão
3. Abra um lote
4. Clique na aba **"🔄 Transferir"**
5. Escolha o destinatário e quantidade
6. Clique em **"Transferir Palhetas"**

Se funcionar sem erro, está tudo certo! ✅

---

## 📊 VERIFICAR A ESTRUTURA

Para ver se a tabela está correta, execute no psql:

```sql
\d transferencias
```

Deve mostrar:

```
Column                  | Type      
------------------------+-----------
id                      | integer   
estoque_id              | integer   
proprietario_origem_id  | integer   
proprietario_destino_id | integer   
quantidade              | integer   
data_transferencia      | timestamp 
```

---

## 🆘 SE AINDA DER ERRO

1. **Verifique se executou o script corretamente:**
   ```bash
   psql -U postgres -d embriovet -c "\d transferencias"
   ```

2. **Se a coluna ainda não aparece, execute manualmente:**
   ```sql
   DROP TABLE IF EXISTS transferencias CASCADE;
   
   CREATE TABLE transferencias (
       id SERIAL PRIMARY KEY,
       estoque_id INTEGER REFERENCES estoque_dono(id) ON DELETE SET NULL,
       proprietario_origem_id INTEGER REFERENCES dono(id) ON DELETE SET NULL,
       proprietario_destino_id INTEGER REFERENCES dono(id) ON DELETE SET NULL,
       quantidade INTEGER NOT NULL,
       data_transferencia TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );
   ```

3. **Reinicie o Streamlit:**
   ```bash
   # No seu ambiente local, pare e inicie novamente:
   Ctrl+C
   streamlit run app.py
   ```

---

## ✅ PRONTO!

Após executar o script, a funcionalidade de transferências vai funcionar perfeitamente! 🎉

**Status:** Script criado e pronto para uso
