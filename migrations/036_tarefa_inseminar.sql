-- 036: tarefa "inseminar" — criada pela indução da ovulação e fechada ao
-- registar a inseminação (passagem de turno). Só alarga o CHECK do tipo.
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
        'inseminar'
    ));
COMMIT;
