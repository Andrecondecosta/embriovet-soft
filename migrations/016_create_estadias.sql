-- 016_create_estadias.sql
-- Cria a tabela `estadias` para registo de estadias e visitas dos animais.

CREATE TABLE IF NOT EXISTS estadias (
    id SERIAL PRIMARY KEY,
    tipo_registo VARCHAR(20) NOT NULL CHECK (tipo_registo IN ('estadia', 'visita')),
    animal_id INTEGER NOT NULL REFERENCES animais(id),
    alojamento_id INTEGER REFERENCES alojamentos(id),
    dono_id INTEGER NOT NULL REFERENCES dono(id),
    dono_doadora_id INTEGER REFERENCES dono(id),
    animal_doador_id INTEGER REFERENCES animais(id),
    data_entrada DATE NOT NULL,
    data_saida DATE,
    motivo VARCHAR(50) NOT NULL CHECK (motivo IN ('inseminacao', 'colheita', 'diagnostico', 'tratamento', 'embriao')),
    estado VARCHAR(30) NOT NULL DEFAULT 'internado' CHECK (estado IN ('internado', 'visitante', 'gestante', 'alta', 'sem_resultado')),
    garanhao VARCHAR(100),
    observacoes_entrada TEXT,
    observacoes_saida TEXT,
    criado_por VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_estadias_tipo_registo ON estadias(tipo_registo);
CREATE INDEX IF NOT EXISTS idx_estadias_animal_id ON estadias(animal_id);
CREATE INDEX IF NOT EXISTS idx_estadias_alojamento_id ON estadias(alojamento_id);
CREATE INDEX IF NOT EXISTS idx_estadias_dono_id ON estadias(dono_id);
CREATE INDEX IF NOT EXISTS idx_estadias_estado ON estadias(estado);
CREATE INDEX IF NOT EXISTS idx_estadias_data_entrada ON estadias(data_entrada);
