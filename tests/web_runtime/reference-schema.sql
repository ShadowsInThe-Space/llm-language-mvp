-- Independent oracle for the frozen w1 schema, not generated migration evidence.
CREATE TABLE w1_values (
  app_id TEXT NOT NULL,
  store_id TEXT NOT NULL,
  value TEXT NOT NULL,
  PRIMARY KEY (app_id, store_id),
  CHECK (typeof(value) = 'text'),
  CHECK (length(CAST(value AS BLOB)) <= 4096),
  CHECK (instr(value, char(0)) = 0)
);
