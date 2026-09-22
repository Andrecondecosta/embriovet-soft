-- ============================================================
-- Migration 031 — trabalho_diario.concluida_por
-- ============================================================
-- `utilizador` é quem CRIOU a tarefa (agendou/gerou), não quem a
-- concluiu — com vários veterinários, a lista "Feitas hoje" do
-- Trabalho diário estava a mostrar quem agendou, não quem fez o
-- trabalho clínico. Esta coluna guarda separadamente quem concluiu,
-- sem tocar em `utilizador`.
-- ============================================================

BEGIN;

ALTER TABLE trabalho_diario
    ADD COLUMN IF NOT EXISTS concluida_por VARCHAR(50);

COMMIT;
