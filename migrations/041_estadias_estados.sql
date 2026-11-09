-- 041: os estados e tipos que a app usa nas estadias passam a vir das
-- migrações. Até aqui eram acrescentados em tempo de execução (ao gravar
-- uma saída ou um registo "externo"), por isso uma base nova ou reposta de
-- uma cópia de segurança não os aceitava. Só alarga as regras: nenhum dado
-- é alterado. NOT VALID: não falha por algum valor antigo.
ALTER TABLE estadias ADD COLUMN IF NOT EXISTS observacoes_saida TEXT;

ALTER TABLE estadias DROP CONSTRAINT IF EXISTS estadias_estado_check;
ALTER TABLE estadias ADD CONSTRAINT estadias_estado_check CHECK (estado IN (
    'internado', 'visitante', 'gestante', 'alta', 'sem_resultado', 'externo', 'transferido'
)) NOT VALID;

ALTER TABLE estadias DROP CONSTRAINT IF EXISTS estadias_tipo_registo_check;
ALTER TABLE estadias ADD CONSTRAINT estadias_tipo_registo_check
    CHECK (tipo_registo IN ('estadia', 'visita', 'externo')) NOT VALID;
