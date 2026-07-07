-- Migration 027: adiciona `verificar_ovulacao` aos tipos válidos de
-- `trabalho_diario` (usado pela tarefa D+1 criada pelo
-- `registar_inseminacao_completa` quando `criar_tarefa_d1=True`).
--
-- Idempotente: só recria a constraint se o novo valor ainda não
-- constar da definição actual.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'trabalho_diario_tipo_check'
          AND pg_get_constraintdef(oid) NOT LIKE '%verificar_ovulacao%'
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
                'verificar_ovulacao'
            ));
    END IF;
END$$;
