DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='transferencias' AND column_name='stock_id'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='transferencias' AND column_name='estoque_id'
  ) THEN
    ALTER TABLE transferencias RENAME COLUMN stock_id TO estoque_id;
  END IF;
END $$;
