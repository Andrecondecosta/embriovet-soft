-- Adicionar timestamp de criação às inseminações para ordenação correcta no log
ALTER TABLE inseminacoes ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Preencher registos existentes com data_inseminacao + meio-dia (aproximação razoável)
UPDATE inseminacoes SET created_at = data_inseminacao::timestamp + interval '12 hours'
WHERE created_at IS NULL OR created_at = '1970-01-01 00:00:00';
