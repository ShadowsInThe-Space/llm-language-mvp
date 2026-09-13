CREATE TABLE `w2_entries` (
	`sequence` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`app_id` text NOT NULL,
	`store_id` text NOT NULL,
	`id` text NOT NULL,
	`value` text NOT NULL,
	`created_at` text NOT NULL,
	CONSTRAINT "w2_value_text" CHECK(typeof("w2_entries"."value") = 'text'),
	CONSTRAINT "w2_value_bytes" CHECK(length(CAST("w2_entries"."value" AS BLOB)) <= 4096),
	CONSTRAINT "w2_value_no_nul" CHECK(instr("w2_entries"."value", char(0)) = 0)
);
--> statement-breakpoint
CREATE UNIQUE INDEX `w2_entry_identity` ON `w2_entries` (`app_id`,`store_id`,`id`);--> statement-breakpoint
CREATE INDEX `w2_entry_page` ON `w2_entries` (`app_id`,`store_id`,`sequence`);
--> statement-breakpoint
INSERT INTO w2_entries(app_id,store_id,id,value,created_at)
SELECT app_id,store_id,'legacy',value,strftime('%Y-%m-%dT%H:%M:%fZ','now') FROM w1_values
WHERE 1 ON CONFLICT(app_id,store_id,id) DO NOTHING;
