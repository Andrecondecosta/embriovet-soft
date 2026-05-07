-- 018_create_diario_clinico.sql
-- Cria a tabela `diario_clinico` para registo de observações clínicas diárias
-- (folículos, edema, fluido uterino, comportamento, tratamentos, etc.)

CREATE TABLE IF NOT EXISTS diario_clinico (
    id SERIAL PRIMARY KEY,
    estadia_id INTEGER NOT NULL REFERENCES estadias(id),
    animal_id  INTEGER NOT NULL REFERENCES animais(id),
    data_registo DATE NOT NULL DEFAULT CURRENT_DATE,
    foliculo_mm INTEGER,
    edema_grau INTEGER CHECK (edema_grau IN (0, 1, 2, 3)),
    fluido_uterino BOOLEAN DEFAULT FALSE,
    comportamento VARCHAR(30) CHECK (comportamento IN ('cio_ativo', 'sem_cio', 'anestro', 'pos_ovulacao')),
    temperatura DECIMAL(4,1),
    tratamentos TEXT,
    proxima_observacao DATE,
    observacoes TEXT,
    utilizador VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_diario_clinico_estadia_id   ON diario_clinico(estadia_id);
CREATE INDEX IF NOT EXISTS idx_diario_clinico_animal_id    ON diario_clinico(animal_id);
CREATE INDEX IF NOT EXISTS idx_diario_clinico_data_registo ON diario_clinico(data_registo);
