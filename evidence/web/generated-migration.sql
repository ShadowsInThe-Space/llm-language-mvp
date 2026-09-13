CREATE TABLE `w1_values` (
	`app_id` text NOT NULL,
	`store_id` text NOT NULL,
	`value` text NOT NULL,
	PRIMARY KEY(`app_id`, `store_id`),
	CONSTRAINT "w1_value_text" CHECK(typeof("w1_values"."value") = 'text'),
	CONSTRAINT "w1_value_bytes" CHECK(length(CAST("w1_values"."value" AS BLOB)) <= 4096),
	CONSTRAINT "w1_value_no_nul" CHECK(instr("w1_values"."value", char(0)) = 0)
);
