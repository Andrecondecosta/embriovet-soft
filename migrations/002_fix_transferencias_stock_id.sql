ALTER TABLE transferencias
ADD COLUMN IF NOT EXISTS stock_id integer;

UPDATE transferencias
SET stock_id = estoque_id
WHERE stock_id IS NULL
  AND estoque_id IS NOT NULL;