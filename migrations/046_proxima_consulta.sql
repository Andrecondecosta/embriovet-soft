-- 046: Próxima consulta obrigatória. Depois de cada consulta marca-se a
-- seguinte (tarefa 'observacao_clinica' no Trabalho diário) ou terminam-se
-- as consultas da égua. `falta_proxima_consulta` fica TRUE ao gravar a
-- consulta até se marcar a próxima ou terminar. Só acrescenta.
ALTER TABLE animais ADD COLUMN IF NOT EXISTS falta_proxima_consulta BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE animais ADD COLUMN IF NOT EXISTS consultas_terminadas_em TIMESTAMP;
ALTER TABLE animais ADD COLUMN IF NOT EXISTS consultas_terminadas_por VARCHAR(50);
