-- Adicionar coluna utilizador para rastrear quem criou/editou cada registo
ALTER TABLE inseminacoes       ADD COLUMN IF NOT EXISTS utilizador VARCHAR(255) DEFAULT '—';
ALTER TABLE transferencias     ADD COLUMN IF NOT EXISTS utilizador VARCHAR(255) DEFAULT '—';
ALTER TABLE transferencias_externas ADD COLUMN IF NOT EXISTS utilizador VARCHAR(255) DEFAULT '—';

-- Adicionar coluna observacoes às inseminacoes
ALTER TABLE inseminacoes ADD COLUMN IF NOT EXISTS observacoes TEXT;
