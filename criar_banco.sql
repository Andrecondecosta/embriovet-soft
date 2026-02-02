-- ================================================
-- SCRIPT DE CRIAÇÃO DO BANCO EMBRIOVET
-- Execute este script no PostgreSQL
-- ================================================

-- 1. Criar banco de dados (execute fora do psql ou conectado a outro DB)
-- CREATE DATABASE embriovet;

-- 2. Conecte-se ao banco embriovet
-- \c embriovet

-- 3. Criar tabelas

-- Tabela de donos/proprietários
DROP TABLE IF EXISTS inseminacoes CASCADE;
DROP TABLE IF EXISTS estoque_dono CASCADE;
DROP TABLE IF EXISTS dono CASCADE;

CREATE TABLE dono (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE dono IS 'Proprietários do sémen';
COMMENT ON COLUMN dono.nome IS 'Nome do proprietário';

-- Tabela de estoque de sémen
CREATE TABLE estoque_dono (
    id SERIAL PRIMARY KEY,
    garanhao VARCHAR(255) NOT NULL,
    dono_id INTEGER REFERENCES dono(id) ON DELETE SET NULL,
    data_embriovet VARCHAR(100),
    origem_externa VARCHAR(255),
    palhetas_produzidas INTEGER DEFAULT 0,
    qualidade NUMERIC(5,2),
    concentracao NUMERIC(10,2),
    motilidade NUMERIC(5,2),
    local_armazenagem VARCHAR(255),
    certificado VARCHAR(10),
    dose VARCHAR(100),
    observacoes TEXT,
    quantidade_inicial INTEGER DEFAULT 0,
    existencia_atual INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_palhetas_positivas CHECK (palhetas_produzidas >= 0),
    CONSTRAINT check_existencia_positiva CHECK (existencia_atual >= 0),
    CONSTRAINT check_qualidade_valida CHECK (qualidade >= 0 AND qualidade <= 100),
    CONSTRAINT check_motilidade_valida CHECK (motilidade >= 0 AND motilidade <= 100)
);

COMMENT ON TABLE estoque_dono IS 'Estoque de sémen por garanhão e dono';
COMMENT ON COLUMN estoque_dono.garanhao IS 'Nome do garanhão (cavalo reprodutor)';
COMMENT ON COLUMN estoque_dono.dono_id IS 'Proprietário do sémen';
COMMENT ON COLUMN estoque_dono.data_embriovet IS 'Data de produção pela Embriovet';
COMMENT ON COLUMN estoque_dono.origem_externa IS 'Referência externa (se não produzido pela Embriovet)';
COMMENT ON COLUMN estoque_dono.qualidade IS 'Qualidade do sémen em percentual';
COMMENT ON COLUMN estoque_dono.concentracao IS 'Concentração em milhões/mL';
COMMENT ON COLUMN estoque_dono.motilidade IS 'Motilidade em percentual';
COMMENT ON COLUMN estoque_dono.quantidade_inicial IS 'Quantidade inicial de palhetas';
COMMENT ON COLUMN estoque_dono.existencia_atual IS 'Quantidade atual disponível';

-- Tabela de inseminações
CREATE TABLE inseminacoes (
    id SERIAL PRIMARY KEY,
    garanhao VARCHAR(255) NOT NULL,
    dono_id INTEGER REFERENCES dono(id) ON DELETE SET NULL,
    data_inseminacao DATE NOT NULL,
    egua VARCHAR(255) NOT NULL,
    protocolo VARCHAR(255),
    palhetas_gastas INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_palhetas_gastas_positiva CHECK (palhetas_gastas > 0)
);

COMMENT ON TABLE inseminacoes IS 'Registro de inseminações realizadas';
COMMENT ON COLUMN inseminacoes.garanhao IS 'Garanhão usado na inseminação';
COMMENT ON COLUMN inseminacoes.dono_id IS 'Dono do sémen utilizado';
COMMENT ON COLUMN inseminacoes.data_inseminacao IS 'Data do procedimento';
COMMENT ON COLUMN inseminacoes.egua IS 'Égua que recebeu a inseminação';
COMMENT ON COLUMN inseminacoes.protocolo IS 'Protocolo ou referência usada';
COMMENT ON COLUMN inseminacoes.palhetas_gastas IS 'Quantidade de palhetas utilizadas';

-- 4. Criar índices para melhorar performance
CREATE INDEX idx_estoque_garanhao ON estoque_dono(garanhao);
CREATE INDEX idx_estoque_dono ON estoque_dono(dono_id);
CREATE INDEX idx_estoque_existencia ON estoque_dono(existencia_atual) WHERE existencia_atual > 0;
CREATE INDEX idx_inseminacoes_garanhao ON inseminacoes(garanhao);
CREATE INDEX idx_inseminacoes_dono ON inseminacoes(dono_id);
CREATE INDEX idx_inseminacoes_data ON inseminacoes(data_inseminacao);

-- 5. Inserir dados iniciais

-- Inserir donos de exemplo
INSERT INTO dono (nome) VALUES 
    ('Embriovet'),
    ('André'),
    ('Filipe');

-- Stock de exemplo: Retoque com 2 donos
INSERT INTO estoque_dono (
    garanhao, dono_id, data_embriovet, 
    palhetas_produzidas, qualidade, concentracao, motilidade,
    local_armazenagem, certificado, dose, observacoes,
    quantidade_inicial, existencia_atual
) VALUES 
    -- Retoque do André
    ('Retoque', 2, '2025-01-15', 
     50, 85.0, 250.0, 75.0,
     'Tanque A', 'Sim', '1 dose', 'Sémen do André - Alta qualidade',
     50, 50),
    
    -- Retoque do Filipe
    ('Retoque', 3, '2025-01-20', 
     60, 88.0, 260.0, 78.0,
     'Tanque B', 'Sim', '1 dose', 'Sémen do Filipe - Excelente motilidade',
     60, 60);

-- 6. Criar função para atualizar timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 7. Criar trigger para atualizar updated_at automaticamente
CREATE TRIGGER trigger_update_estoque_timestamp
    BEFORE UPDATE ON estoque_dono
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- 8. Verificar criação
SELECT 'Donos cadastrados:' as info;
SELECT id, nome, email FROM dono;

SELECT 'Stock cadastrado:' as info;
SELECT 
    e.garanhao, 
    d.nome as dono, 
    e.existencia_atual as palhetas,
    e.local_armazenagem as local
FROM estoque_dono e
JOIN dono d ON e.dono_id = d.id
ORDER BY e.garanhao, d.nome;

-- 9. Estatísticas
SELECT 
    'Total de donos: ' || COUNT(*) as estatistica
FROM dono;

SELECT 
    'Total de lotes de sémen: ' || COUNT(*) as estatistica
FROM estoque_dono;

SELECT 
    'Total de palhetas: ' || SUM(existencia_atual) as estatistica
FROM estoque_dono;

-- ================================================
-- PRONTO! Banco de dados criado e populado
-- ================================================
