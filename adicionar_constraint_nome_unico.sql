-- ================================================
-- ADICIONAR CONSTRAINT UNIQUE AO NOME DO PROPRIETÁRIO
-- ================================================

-- Verificar se já existe a constraint
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'dono_nome_unique'
    ) THEN
        -- Adicionar constraint para nomes únicos
        ALTER TABLE dono ADD CONSTRAINT dono_nome_unique UNIQUE (nome);
        RAISE NOTICE 'Constraint dono_nome_unique adicionada com sucesso!';
    ELSE
        RAISE NOTICE 'Constraint dono_nome_unique já existe.';
    END IF;
END $$;

SELECT '✅ Nome dos proprietários agora é único!' as status;
