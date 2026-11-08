-- 038: a existência de um lote nunca fica negativa (dois pedidos ao mesmo
-- tempo). NOT VALID: vale para todas as escritas a partir de agora, sem
-- falhar se já houver algum valor antigo negativo.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'estoque_dono_existencia_nao_negativa') THEN
        ALTER TABLE estoque_dono
            ADD CONSTRAINT estoque_dono_existencia_nao_negativa CHECK (existencia_atual >= 0) NOT VALID;
    END IF;
END $$;
