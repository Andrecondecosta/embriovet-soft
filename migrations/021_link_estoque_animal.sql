ALTER TABLE estoque_dono ADD COLUMN IF NOT EXISTS animal_id INTEGER REFERENCES animais(id);
CREATE INDEX IF NOT EXISTS idx_estoque_dono_animal_id ON estoque_dono(animal_id);
UPDATE estoque_dono e SET animal_id = a.id FROM animais a WHERE LOWER(e.garanhao) = LOWER(a.nome) AND a.tipo = 'garanhao' AND e.animal_id IS NULL;
