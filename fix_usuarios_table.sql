-- Script de correção rápida para o banco de dados do Render
-- Execute este script se o deploy falhou com erro "column nome_completo does not exist"

-- Adicionar coluna nome_completo à tabela usuarios
ALTER TABLE usuarios 
ADD COLUMN IF NOT EXISTS nome_completo VARCHAR(255);

-- Adicionar coluna created_by à tabela usuarios
ALTER TABLE usuarios 
ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES usuarios(id) ON DELETE SET NULL;

-- Atualizar usuário admin existente
UPDATE usuarios 
SET nome_completo = 'Administrador' 
WHERE username = 'admin' AND nome_completo IS NULL;

-- Verificar
SELECT id, username, nome_completo, nivel, ativo FROM usuarios;
