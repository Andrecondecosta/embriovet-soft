-- Migration 024: re-sync de garanhões (idempotente).
-- Repete o mesmo trabalho da 023 para apanhar novos lotes/inserções feitas
-- entre migrations e sem `animal_id`. Seguro para executar múltiplas vezes.

INSERT INTO animais (nome, tipo, ativo, created_at)
SELECT DISTINCT e.garanhao, 'garanhao', TRUE, NOW()
FROM estoque_dono e
WHERE NOT EXISTS (
    SELECT 1 FROM animais a WHERE LOWER(a.nome) = LOWER(e.garanhao) AND a.tipo = 'garanhao'
) AND e.garanhao IS NOT NULL AND e.garanhao != '';

UPDATE estoque_dono e SET animal_id = a.id FROM animais a WHERE LOWER(e.garanhao) = LOWER(a.nome) AND a.tipo = 'garanhao' AND e.animal_id IS NULL;

UPDATE inseminacoes i SET animal_id_garanhao = a.id FROM animais a WHERE LOWER(i.garanhao) = LOWER(a.nome) AND a.tipo = 'garanhao' AND i.animal_id_garanhao IS NULL;
