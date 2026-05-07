-- 019_create_trabalho_diario.sql
-- Cria a tabela `trabalho_diario` para gerir tarefas/observações agendadas
-- (urgentes, do dia, do dia seguinte, ou em modo observação) por animal/estadia.

CREATE TABLE IF NOT EXISTS trabalho_diario (
    id SERIAL PRIMARY KEY,
    animal_id  INTEGER NOT NULL REFERENCES animais(id),
    estadia_id INTEGER NOT NULL REFERENCES estadias(id),
    data_tarefa DATE NOT NULL,
    tipo VARCHAR(50) NOT NULL CHECK (tipo IN (
        'observacao_clinica',
        'diagnostico_gestacao',
        'confirmacao_gestacao',
        'segunda_confirmacao',
        'parto_previsto',
        'tratamento',
        'primeira_observacao'
    )),
    motivo TEXT NOT NULL,
    urgencia VARCHAR(20) DEFAULT 'hoje' CHECK (urgencia IN (
        'urgente', 'hoje', 'amanha', 'observacao'
    )),
    concluida BOOLEAN DEFAULT FALSE,
    data_conclusao DATE,
    observacoes_conclusao TEXT,
    criado_automaticamente BOOLEAN DEFAULT TRUE,
    utilizador VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trabalho_diario_animal_id   ON trabalho_diario(animal_id);
CREATE INDEX IF NOT EXISTS idx_trabalho_diario_estadia_id  ON trabalho_diario(estadia_id);
CREATE INDEX IF NOT EXISTS idx_trabalho_diario_data_tarefa ON trabalho_diario(data_tarefa);
CREATE INDEX IF NOT EXISTS idx_trabalho_diario_concluida   ON trabalho_diario(concluida);
