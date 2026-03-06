-- Adicionar coluna atualizado para rastreio de edições
ALTER TABLE inseminacoes ADD COLUMN IF NOT EXISTS atualizado BOOLEAN DEFAULT FALSE;
ALTER TABLE transferencias ADD COLUMN IF NOT EXISTS atualizado BOOLEAN DEFAULT FALSE;

DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'transferencias_externas') THEN
        ALTER TABLE transferencias_externas ADD COLUMN IF NOT EXISTS atualizado BOOLEAN DEFAULT FALSE;
    END IF;
END $$;
