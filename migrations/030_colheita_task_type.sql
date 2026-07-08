-- ============================================================
-- Migration 030 — Colheitas agendadas do garanhão (Pedido 8)
-- ============================================================
-- 1) Adiciona o tipo `colheita` ao CHECK do `trabalho_diario_tipo_check`
--    (mesmo padrão de `verificar_ovulacao` e `pre_parto`).
--
-- 2) Torna `estadia_id` NULLABLE.
--    Motivo: as colheitas do garanhão vivem em `trabalho_diario` mas
--    não têm estadia (o garanhão não está internado). A coluna
--    `animal_id` já é FK para `animais` e é usada para identificar o
--    garanhão da colheita.
--    Impacto: os SELECTs existentes (`_carregar_tarefas_semana`,
--    `dashboard_repo.carregar_tarefas_hoje`, `insemination_repo`)
--    já toleram NULL — nenhum faz JOIN OBRIGATÓRIO com `estadias`.
--    Todos os INSERTs actuais fornecem `estadia_id` — só as
--    colheitas passam NULL. Alteração mínima documentada em vez de
--    criar uma "estadia técnica" fictícia.
-- ============================================================

BEGIN;

-- 1) Alargar o CHECK constraint
ALTER TABLE trabalho_diario
    DROP CONSTRAINT IF EXISTS trabalho_diario_tipo_check;

ALTER TABLE trabalho_diario
    ADD CONSTRAINT trabalho_diario_tipo_check
    CHECK (tipo IN (
        'observacao_clinica',
        'diagnostico_gestacao',
        'confirmacao_gestacao',
        'segunda_confirmacao',
        'parto_previsto',
        'tratamento',
        'primeira_observacao',
        'verificar_ovulacao',
        'pre_parto',
        'colheita'
    ));

-- 2) Tornar estadia_id opcional (colheitas não têm estadia)
ALTER TABLE trabalho_diario
    ALTER COLUMN estadia_id DROP NOT NULL;

COMMIT;
