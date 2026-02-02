-- ================================================
-- SCRIPT DE LIMPEZA E REINICIALIZAÇÃO
-- Execute este script para limpar todos os dados de teste
-- e recomeçar com a estrutura correta
-- ================================================

-- PASSO 1: Deletar todos os dados de teste
DELETE FROM inseminacoes;
DELETE FROM estoque_dono;
DELETE FROM dono;

-- PASSO 2: Reset das sequences (IDs)
ALTER SEQUENCE dono_id_seq RESTART WITH 1;
ALTER SEQUENCE estoque_dono_id_seq RESTART WITH 1;
ALTER SEQUENCE inseminacoes_id_seq RESTART WITH 1;

-- PASSO 3: Criar proprietário padrão "Sem proprietário"
INSERT INTO dono (nome) VALUES 
    ('Sem proprietário');

-- PASSO 4: (Opcional) Criar alguns proprietários exemplo
-- Descomente as linhas abaixo se quiser alguns proprietários de exemplo

-- INSERT INTO dono (nome) VALUES 
--     ('André Costa'),
--     ('Filipe Silva'),
--     ('João Santos');

-- ================================================
-- VERIFICAÇÃO
-- ================================================

-- Ver proprietários (deve ter apenas "Sem proprietário")
SELECT 'PROPRIETÁRIOS NA BASE DE DADOS:' as info;
SELECT * FROM dono;

-- Ver stock (deve estar vazio)
SELECT 'STOCK NA BASE DE DADOS:' as info;
SELECT COUNT(*) as total_lotes FROM estoque_dono;

-- Ver inseminações (deve estar vazio)
SELECT 'INSEMINAÇÕES NA BASE DE DADOS:' as info;
SELECT COUNT(*) as total_inseminacoes FROM inseminacoes;

-- ================================================
-- PRONTO!
-- ================================================
-- Banco limpo e pronto para importar dados do CSV
-- Execute: python importar_dados.py
-- ================================================
