-- ================================================
-- SCRIPT PARA REMOVER COLUNAS CONTATO E EMAIL
-- Execute este script para remover as colunas desnecessárias
-- ================================================

-- Remover coluna 'contato' se existir
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'dono' AND column_name = 'contato'
    ) THEN
        ALTER TABLE dono DROP COLUMN contato;
        RAISE NOTICE 'Coluna contato removida com sucesso!';
    ELSE
        RAISE NOTICE 'Coluna contato não existe.';
    END IF;
END $$;

-- Remover coluna 'email' se existir
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'dono' AND column_name = 'email'
    ) THEN
        ALTER TABLE dono DROP COLUMN email;
        RAISE NOTICE 'Coluna email removida com sucesso!';
    ELSE
        RAISE NOTICE 'Coluna email não existe.';
    END IF;
END $$;

-- Verificar estrutura final da tabela
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'dono'
ORDER BY ordinal_position;

-- Deve mostrar apenas:
-- id          | integer
-- nome        | character varying
-- created_at  | timestamp
