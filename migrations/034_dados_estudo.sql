-- 034: dados para o estudo da época de 2027 (ciclo inseminado).
-- Só acrescenta: nenhuma coluna ou tabela existente muda.

-- Hora da inseminação (as antigas ficam sem hora).
ALTER TABLE inseminacoes ADD COLUMN IF NOT EXISTS hora_inseminacao TIME;

-- Diagnósticos de gestação guardados por etapa, sem se substituírem uns
-- aos outros. `inseminacoes.resultado` continua a ter o estado atual.
CREATE TABLE IF NOT EXISTS diagnosticos_gestacao (
    id SERIAL PRIMARY KEY,
    animal_id INTEGER NOT NULL REFERENCES animais(id) ON DELETE CASCADE,
    operation_id UUID,
    etapa VARCHAR(5) NOT NULL CHECK (etapa IN ('D+14', 'D+28', 'D+45')),
    resultado VARCHAR(15) NOT NULL CHECK (resultado IN ('positivo', 'negativo', 'inconclusivo', 'sem_exame')),
    data_exame TIMESTAMP NOT NULL,
    registo_clinico_id INTEGER REFERENCES registo_clinico(id) ON DELETE SET NULL,
    utilizador VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_diagnosticos_gestacao_animal ON diagnosticos_gestacao (animal_id);
CREATE INDEX IF NOT EXISTS idx_diagnosticos_gestacao_operacao ON diagnosticos_gestacao (operation_id);

-- Anti-duplicados: cada envio de um formulário leva um id; o mesmo id
-- não pode ser gravado duas vezes (duplo clique, rede lenta).
CREATE TABLE IF NOT EXISTS pedidos_unicos (
    id UUID PRIMARY KEY,
    tipo VARCHAR(30) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
