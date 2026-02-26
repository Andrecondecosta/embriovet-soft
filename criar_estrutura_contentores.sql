-- Script de criação da estrutura de contentores
-- Executar ANTES de fazer alterações no código

-- 1. Criar tabela de contentores
CREATE TABLE IF NOT EXISTS contentores (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,
    descricao TEXT,
    x INTEGER DEFAULT 100,
    y INTEGER DEFAULT 100,
    w INTEGER DEFAULT 150,
    h INTEGER DEFAULT 150,
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Criar contentor temporário padrão para migração
INSERT INTO contentores (codigo, descricao, x, y, w, h, ativo)
VALUES ('CT-TEMP', 'Contentor Temporário (migração de dados antigos)', 100, 100, 150, 150, TRUE)
ON CONFLICT (codigo) DO NOTHING;

-- 3. Adicionar colunas de localização estruturada à tabela estoque_dono
ALTER TABLE estoque_dono 
ADD COLUMN IF NOT EXISTS contentor_id INTEGER REFERENCES contentores(id) ON DELETE RESTRICT;

ALTER TABLE estoque_dono 
ADD COLUMN IF NOT EXISTS canister INTEGER CHECK (canister >= 1 AND canister <= 10);

ALTER TABLE estoque_dono 
ADD COLUMN IF NOT EXISTS andar INTEGER CHECK (andar IN (1, 2));

-- 4. Migrar dados existentes para o contentor temporário
-- Pegar ID do contentor CT-TEMP
DO $$
DECLARE
    temp_contentor_id INTEGER;
BEGIN
    SELECT id INTO temp_contentor_id FROM contentores WHERE codigo = 'CT-TEMP';
    
    -- Migrar todos os stocks sem contentor para CT-TEMP
    -- Distribuir aleatoriamente em canisters e andares
    UPDATE estoque_dono 
    SET 
        contentor_id = temp_contentor_id,
        canister = 1 + (id % 10),  -- Distribui entre 1-10
        andar = 1 + (id % 2)       -- Alterna entre 1 e 2
    WHERE contentor_id IS NULL;
END $$;

-- 5. Comentários nas colunas
COMMENT ON COLUMN estoque_dono.contentor_id IS 'FK para contentores - localização do sémen';
COMMENT ON COLUMN estoque_dono.canister IS 'Número do canister (1-10) dentro do contentor';
COMMENT ON COLUMN estoque_dono.andar IS 'Nível/andar (1 ou 2) dentro do canister';

-- 6. Verificação
SELECT 
    c.codigo,
    COUNT(e.id) as total_lotes,
    SUM(e.existencia_atual) as total_palhetas
FROM contentores c
LEFT JOIN estoque_dono e ON c.id = e.contentor_id
GROUP BY c.id, c.codigo
ORDER BY c.codigo;
