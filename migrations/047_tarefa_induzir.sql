-- 047: tarefa "induzir" — indução marcada para outro dia (ou mais tarde no
-- mesmo dia): aparece no Trabalho diário nesse dia. Só alarga o CHECK do tipo.
BEGIN;
ALTER TABLE trabalho_diario DROP CONSTRAINT IF EXISTS trabalho_diario_tipo_check;
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
        'colheita',
        'inseminar',
        'induzir'
    ));
COMMIT;
