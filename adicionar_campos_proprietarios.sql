-- ================================================
-- ADICIONAR NOVOS CAMPOS À TABELA DONO
-- ================================================

-- Adicionar coluna de status ativo/inativo (se não existir)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='dono' AND column_name='ativo') THEN
        ALTER TABLE dono ADD COLUMN ativo BOOLEAN DEFAULT TRUE;
    END IF;
END $$;

-- Adicionar campos de contato (se não existirem)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='dono' AND column_name='email') THEN
        ALTER TABLE dono ADD COLUMN email VARCHAR(255);
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='dono' AND column_name='telemovel') THEN
        ALTER TABLE dono ADD COLUMN telemovel VARCHAR(20);
    END IF;
END $$;

-- Adicionar campos de faturação (se não existirem)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='dono' AND column_name='nome_completo') THEN
        ALTER TABLE dono ADD COLUMN nome_completo VARCHAR(255);
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='dono' AND column_name='nif') THEN
        ALTER TABLE dono ADD COLUMN nif VARCHAR(20);
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='dono' AND column_name='morada') THEN
        ALTER TABLE dono ADD COLUMN morada TEXT;
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='dono' AND column_name='codigo_postal') THEN
        ALTER TABLE dono ADD COLUMN codigo_postal VARCHAR(10);
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='dono' AND column_name='cidade') THEN
        ALTER TABLE dono ADD COLUMN cidade VARCHAR(100);
    END IF;
END $$;

-- Comentários
COMMENT ON COLUMN dono.ativo IS 'Status do proprietário (TRUE=ativo, FALSE=inativo)';
COMMENT ON COLUMN dono.email IS 'Email de contato';
COMMENT ON COLUMN dono.telemovel IS 'Número de telemóvel';
COMMENT ON COLUMN dono.nome_completo IS 'Nome completo ou razão social para faturação';
COMMENT ON COLUMN dono.nif IS 'Número de Identificação Fiscal';
COMMENT ON COLUMN dono.morada IS 'Morada completa';
COMMENT ON COLUMN dono.codigo_postal IS 'Código postal';
COMMENT ON COLUMN dono.cidade IS 'Cidade';

-- Criar índice para performance (se não existir)
CREATE INDEX IF NOT EXISTS idx_dono_ativo ON dono(ativo);

-- Atualizar todos os registros existentes para ativo=TRUE
UPDATE dono SET ativo = TRUE WHERE ativo IS NULL;

SELECT '✅ Campos adicionados com sucesso!' as status;
