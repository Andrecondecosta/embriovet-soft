-- ================================================
-- SCRIPT DE CORREÇÃO - Adicionar coluna 'contato'
-- Execute este script para corrigir a tabela dono
-- ================================================

-- Verificar e adicionar coluna 'contato' se não existir
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'dono' AND column_name = 'contato'
    ) THEN
        ALTER TABLE dono ADD COLUMN contato VARCHAR(255);
        RAISE NOTICE 'Coluna contato adicionada com sucesso!';
    ELSE
        RAISE NOTICE 'Coluna contato já existe!';
    END IF;
END $$;

-- Verificar e adicionar coluna 'email' se não existir
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'dono' AND column_name = 'email'
    ) THEN
        ALTER TABLE dono ADD COLUMN email VARCHAR(255);
        RAISE NOTICE 'Coluna email adicionada com sucesso!';
    ELSE
        RAISE NOTICE 'Coluna email já existe!';
    END IF;
END $$;

-- Verificar estrutura da tabela
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'dono'
ORDER BY ordinal_position;
