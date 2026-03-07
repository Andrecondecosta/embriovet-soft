-- Adicionar referência ao lote específico usado em cada inseminação
ALTER TABLE inseminacoes ADD COLUMN IF NOT EXISTS estoque_id INTEGER;
