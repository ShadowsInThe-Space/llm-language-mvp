CREATE TABLE w2_entries (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT,
 app_id TEXT NOT NULL,
 store_id TEXT NOT NULL,
 id TEXT NOT NULL,
 value TEXT NOT NULL CHECK(typeof(value)='text')
   CHECK(length(CAST(value AS BLOB))<=4096) CHECK(instr(value,char(0))=0),
 created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX w2_entry_identity ON w2_entries(app_id,store_id,id);
CREATE INDEX w2_entry_page ON w2_entries(app_id,store_id,sequence);
INSERT INTO w2_entries(app_id,store_id,id,value,created_at)
 SELECT app_id,store_id,'legacy',value,strftime('%Y-%m-%dT%H:%M:%fZ','now') FROM w1_values;
