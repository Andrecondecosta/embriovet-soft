-- Script de correção rápida para o banco de dados do Render
-- Execute este script se o deploy falhou com erro de colunas faltantes

-- Adicionar coluna nome_completo à tabela usuarios
ALTER TABLE usuarios 
ADD COLUMN IF NOT EXISTS nome_completo VARCHAR(255);

-- Adicionar coluna created_by à tabela usuarios
ALTER TABLE usuarios 
ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES usuarios(id) ON DELETE SET NULL;

-- Adicionar coluna created_at à tabela usuarios
ALTER TABLE usuarios 
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Adicionar coluna last_login à tabela usuarios
ALTER TABLE usuarios 
ADD COLUMN IF NOT EXISTS last_login TIMESTAMP;

-- Atualizar usuário admin existente
UPDATE usuarios 
SET nome_completo = 'Administrador',
    created_at = CURRENT_TIMESTAMP
WHERE username = 'admin' AND nome_completo IS NULL;

-- Verificar
SELECT id, username, nome_completo, nivel, ativo, created_at, last_login FROM usuarios;
