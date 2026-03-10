-- Adicionar operation_id para agrupar múltiplos lotes numa operação
ALTER TABLE inseminacoes ADD COLUMN IF NOT EXISTS operation_id UUID;
ALTER TABLE transferencias ADD COLUMN IF NOT EXISTS operation_id UUID;
ALTER TABLE transferencias_externas ADD COLUMN IF NOT EXISTS operation_id UUID;

CREATE INDEX IF NOT EXISTS idx_inseminacoes_op ON inseminacoes(operation_id);
CREATE INDEX IF NOT EXISTS idx_transferencias_op ON transferencias(operation_id);
CREATE INDEX IF NOT EXISTS idx_transf_ext_op ON transferencias_externas(operation_id);
