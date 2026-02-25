-- ================================================
-- ADICIONAR NOVOS CAMPOS À TABELA DONO
-- ================================================

-- Adicionar coluna de status ativo/inativo
ALTER TABLE dono ADD COLUMN IF NOT EXISTS ativo BOOLEAN DEFAULT TRUE;

-- Adicionar campos de contato
ALTER TABLE dono ADD COLUMN IF NOT EXISTS email VARCHAR(255);
ALTER TABLE dono ADD COLUMN IF NOT EXISTS telemovel VARCHAR(20);

-- Adicionar campos de faturação
ALTER TABLE dono ADD COLUMN IF NOT EXISTS nome_completo VARCHAR(255);
ALTER TABLE dono ADD COLUMN IF NOT EXISTS nif VARCHAR(20);
ALTER TABLE dono ADD COLUMN IF NOT EXISTS morada TEXT;
ALTER TABLE dono ADD COLUMN IF NOT EXISTS codigo_postal VARCHAR(10);
ALTER TABLE dono ADD COLUMN IF NOT EXISTS cidade VARCHAR(100);

-- Comentários
COMMENT ON COLUMN dono.ativo IS 'Status do proprietário (TRUE=ativo, FALSE=inativo)';
COMMENT ON COLUMN dono.email IS 'Email de contato';
COMMENT ON COLUMN dono.telemovel IS 'Número de telemóvel';
COMMENT ON COLUMN dono.nome_completo IS 'Nome completo ou razão social para faturação';
COMMENT ON COLUMN dono.nif IS 'Número de Identificação Fiscal';
COMMENT ON COLUMN dono.morada IS 'Morada completa';
COMMENT ON COLUMN dono.codigo_postal IS 'Código postal';
COMMENT ON COLUMN dono.cidade IS 'Cidade';

-- Criar índice para performance
CREATE INDEX IF NOT EXISTS idx_dono_ativo ON dono(ativo);

-- Verificar
\d dono

SELECT '✅ Campos adicionados com sucesso!' as status;
