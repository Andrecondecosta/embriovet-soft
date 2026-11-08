-- 040: fuso horário da clínica (Definições). "Hoje" e as horas gravadas
-- automaticamente seguem este fuso. Só acrescenta a coluna.
ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS fuso_horario TEXT NOT NULL DEFAULT 'Europe/Lisbon';
