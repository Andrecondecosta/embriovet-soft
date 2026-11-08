-- 039: apagar um proprietário nunca apaga os lotes dele em cascata (a app
-- já o impede; isto garante-o na própria base). ON DELETE CASCADE → RESTRICT.
DO $$
DECLARE c text;
BEGIN
    FOR c IN
        SELECT con.conname FROM pg_constraint con
        JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = ANY(con.conkey)
        WHERE con.conrelid = 'estoque_dono'::regclass AND con.contype = 'f'
          AND con.confrelid = 'dono'::regclass AND att.attname = 'dono_id' AND con.confdeltype = 'c'
    LOOP
        EXECUTE format('ALTER TABLE estoque_dono DROP CONSTRAINT %I', c);
        ALTER TABLE estoque_dono
            ADD CONSTRAINT estoque_dono_dono_id_fkey FOREIGN KEY (dono_id) REFERENCES dono(id) ON DELETE RESTRICT;
    END LOOP;
END $$;
