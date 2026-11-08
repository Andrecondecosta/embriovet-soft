-- 035: tarefas canceladas à mão ou na saída da estadia ficam registadas
-- (concluida = TRUE e cancelada = TRUE) em vez de serem apagadas.
-- Só acrescenta: nenhuma coluna existente muda.
ALTER TABLE trabalho_diario ADD COLUMN IF NOT EXISTS cancelada BOOLEAN NOT NULL DEFAULT FALSE;
