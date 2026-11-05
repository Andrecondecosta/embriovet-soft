-- 033: data de produção dos lotes no formato único AAAA-MM-DD.
--
-- A app passa a gravar a data escolhida num calendário (AAAA-MM-DD). Os
-- lotes antigos que tinham um DIA escrito de outra forma ("12-01-2021",
-- "2019.12.03", "12/01/2021") passam para esse formato. Fica tudo o resto
-- como está:
--   - só ano ou mês ("2014", "2026-05", "Agosto 2017");
--   - texto ("Várias");
--   - datas com algo escrito a seguir ("2021.01.31HC", "07.03.2019B"),
--     para não se perder o que está depois da data;
--   - dias que não existem (ex.: 31-02-2021).
-- Só mexe na coluna data_embriovet; não apaga nada.

DO $$
DECLARE
    r RECORD;
    p TEXT[];
    d DATE;
BEGIN
    FOR r IN
        SELECT id, btrim(data_embriovet) AS t
        FROM estoque_dono
        WHERE btrim(data_embriovet) ~ '^[0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}$'
           OR btrim(data_embriovet) ~ '^[0-9]{1,2}[-./][0-9]{1,2}[-./][0-9]{4}$'
    LOOP
        BEGIN
            p := regexp_split_to_array(r.t, '[-./]');
            IF length(p[1]) = 4 THEN
                d := make_date(p[1]::int, p[2]::int, p[3]::int);
            ELSE
                d := make_date(p[3]::int, p[2]::int, p[1]::int);
            END IF;
            IF to_char(d, 'YYYY-MM-DD') <> r.t THEN
                UPDATE estoque_dono SET data_embriovet = to_char(d, 'YYYY-MM-DD') WHERE id = r.id;
            END IF;
        EXCEPTION WHEN others THEN
            NULL;  -- dia que não existe: fica como estava
        END;
    END LOOP;
END $$;
