# 🔧 SOLUÇÃO - Password Incorreta

## ❌ O PROBLEMA

O hash da password no banco de dados está incorreto ou incompatível com o bcrypt.

**Erro:** "Utilizador ou password incorretos"  
**Causa:** O hash armazenado não corresponde à password `admin123`

---

## ✅ SOLUÇÃO RÁPIDA

Execute este comando para atualizar a password do admin:

```bash
psql -U postgres -d embriovet << 'EOF'
UPDATE usuarios 
SET password_hash = '$2b$12$rFwmM.nAwyKsbz19PtWgzeJG64NHAn.fSC8OXAaWBHCekU5iYnafW'
WHERE username = 'admin';

SELECT 'Password atualizada!' as status;
SELECT username, nivel FROM usuarios;
EOF
```

**OU execute este comando alternativo (mais simples):**

```bash
psql -U postgres -d embriovet -c "UPDATE usuarios SET password_hash = '\$2b\$12\$rFwmM.nAwyKsbz19PtWgzeJG64NHAn.fSC8OXAaWBHCekU5iYnafW' WHERE username = 'admin';"
```

---

## 🔄 DEPOIS DE EXECUTAR

1. **Recarregue a página do navegador** (F5)
2. **Faça login:**
   - Username: `admin`
   - Password: `admin123`

**Deve funcionar agora!** ✅

---

## 🆘 SE AINDA NÃO FUNCIONAR

### Opção 1: Criar novo utilizador com password correta

```bash
psql -U postgres -d embriovet << 'EOF'
-- Deletar o admin antigo
DELETE FROM usuarios WHERE username = 'admin';

-- Criar novo admin com hash correto
INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo)
VALUES (
    'admin',
    'Administrador',
    '$2b$12$rFwmM.nAwyKsbz19PtWgzeJG64NHAn.fSC8OXAaWBHCekU5iYnafW',
    'Administrador',
    TRUE
);

SELECT * FROM usuarios;
EOF
```

### Opção 2: Criar um novo utilizador de teste

```bash
psql -U postgres -d embriovet << 'EOF'
INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo)
VALUES (
    'teste',
    'Utilizador Teste',
    '$2b$12$rFwmM.nAwyKsbz19PtWgzeJG64NHAn.fSC8OXAaWBHCekU5iYnafW',
    'Administrador',
    TRUE
);
EOF
```

Depois tente login com: `teste` / `admin123`

---

## 🔍 VERIFICAR HASH ATUAL

Para ver o hash que está no banco:

```bash
psql -U postgres -d embriovet -c "SELECT username, password_hash FROM usuarios WHERE username = 'admin';"
```

---

## 📊 RESUMO

**Problema:** Hash da password incompatível  
**Causa:** Versão do bcrypt ou salt diferente  
**Solução:** Atualizar hash com versão correta  
**Hash correto:** `$2b$12$rFwmM.nAwyKsbz19PtWgzeJG64NHAn.fSC8OXAaWBHCekU5iYnafW`  

---

**Status:** Solução fornecida ✅
