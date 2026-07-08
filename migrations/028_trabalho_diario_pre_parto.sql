-- Migration 028: adiciona `pre_parto` aos tipos válidos de `trabalho_diario`.
--
-- Contexto: quando o resultado D+45 é positivo, `registar_resultado`
-- passa a criar duas tarefas de parto:
--   - `pre_parto` a D-14 do parto previsto ("preparar acompanhamento")
--   - `parto_previsto` na data prevista
--
-- `parto_previsto` já está na lista (desde a migration 019). Só falta
-- `pre_parto`. Constraint é reconstruída apenas se `pre_parto` ainda
-- não constar.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'trabalho_diario_tipo_check'
          AND pg_get_constraintdef(oid) NOT LIKE '%pre_parto%'
    ) THEN
        ALTER TABLE trabalho_diario
            DROP CONSTRAINT trabalho_diario_tipo_check;

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
                'pre_parto'
            ));
    END IF;
END$$;
