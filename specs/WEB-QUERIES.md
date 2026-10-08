# General web typed queries (M3)

Status: bounded Python query foundation. This is separate from frozen W1/W2,
`pkg1`, and `a1-ir-v1`; it neither changes those profiles nor promises arbitrary
SQL support. The executor's evidence is actual SQLite only. Cloudflare D1
execution, deployment and transaction semantics require separate verification.

## Closed immutable schema

`Schema(tables)` contains 1–16 `Table(name, columns)` declarations. Each table
contains 1–32 `Column(name, type, primary_key=False, unique=False)` declarations
and exactly one primary key. Collections are tuples. Identifiers contain only
ASCII letters, digits and underscores, start with a letter or underscore, and
have at most 64 characters. Table/column names cannot collide ignoring ASCII
case. SQLite-reserved table names beginning `sqlite_` are forbidden.

Types come from `general.codecs`: `TextType(capacity)`, `IntType()`, `NatType()`
and `BoolType()`. Columns are non-null. Nullable columns, composite keys,
foreign keys, joins, expression projections and arbitrary predicates are outside
this bounded foundation. `schema_sql(schema)` emits deterministic DDL in
schema declaration order with explicit `NOT NULL`, unique constraints and
storage-class `CHECK` constraints:

| Type | Runtime native value | SQLite representation | Constraint |
| --- | --- | --- | --- |
| Text | Unicode string | TEXT | UTF-8 bytes ≤ declared capacity; no NUL |
| Int | Exact integer | INTEGER | −9007199254740991 through 9007199254740991 |
| Nat | Exact integer | INTEGER | 0 through 9007199254740991 |
| Bool | Boolean | INTEGER | 0 or 1 |

Codec validation rejects booleans masquerading as integers, malformed Unicode,
incorrect scalar types, overflow and null. SQLite affinity may coerce direct
external writes before CHECK evaluation; CHECK constrains the stored value.
The executor validates stored values again before returning native values.

## Query forms

All forms name one declared table and have a nonempty, explicit projection of
unique declared columns; `SELECT *` is never emitted. All values use positional
`?` bindings, including list bounds. No public form takes SQL text, operator
strings, expression fragments or user-selected undeclared identifiers.

* `Insert(table, values, projection)` supplies exactly every column once.
* `SelectUnique(table, key, value, projection)` requires a declared primary or
  unique key, returning zero or one row.
* `SelectList(table, projection, order, limit, offset=0, where=())` uses one or
  more `Order(column, "asc" | "desc")` declarations, a limit of 1–1000, and an
  offset of 0–10000. The primary key is appended ascending when absent from the
  order, making ties deterministic. Optional predicates are equality bindings
  joined with AND. Listing has no snapshot guarantee across separate calls.
* `ConditionalUpdate(table, key, key_value, revision, expected_revision, values,
  projection)` requires a unique key and a non-key Nat revision. Changes cannot
  include the primary key, lookup key or revision; revision increments by one.
  The single statement is `UPDATE ... SET ..., revision = revision + 1 WHERE
  key = ? AND revision = ? RETURNING ...`. A maximum revision is rejected before
  execution because it cannot increment inside the supported range.

Field bindings are tuples of `(column_name, value)` pairs. Compilation orders
bindings by schema column declaration, independently of supplied field order.
Duplicate fields, duplicate order columns, unknown columns and illegal bounds
fail with `QueryError`.

## Prepared descriptors and execution boundary

`compile_query(schema, query)` returns immutable `CompiledQuery(sql, bindings,
result)`. Each `Binding` carries the scalar type and either a validated native
literal or a typed `Param(name, type)`. The result descriptor carries ordered
columns, cardinality and maximum rows. Parameter descriptors make SQL generation
independent of runtime user values. Parameter type must exactly equal the column
type, including Text capacity. Repeated parameter names must have identical
types.

`compiled.bind(params)` requires the exact declared parameter-name set, validates
values through runtime codecs, converts Bool to 0/1, and returns positional
bindings. Int/Nat SQLite bindings are native safe integers; this is distinct
from the JSON wire codec's canonical decimal strings.

`execute_sqlite(connection, schema, query, params=None)` compiles and binds the
query, executes one statement, and returns immutable `Rows(columns, rows)`.
A conditional update matching zero rows returns `ConditionNotMet()` (absent key
and stale revision deliberately share that outcome). Result decoding checks
storage type, range and capacity. An unexpectedly non-unique result fails closed
rather than silently picking a row. Constraint/SQLite errors propagate from the
SQLite driver. The caller owns connection lifetime and commit/rollback.

A conditional conflict is not a batch exception, rollback signal or simulated
transaction guarantee. No prior read is used to decide whether a write is safe.
Tests race independent real SQLite connections with the same expected revision
and require exactly one winner. SQLite writer serialization plus the predicate
provide the single-statement atomic behavior demonstrated here.

## Verification

`tests/test_general_web_queries.py` uses the standard-library unittest runner
and actual SQLite. It checks SQL/value injection separation, deterministic
bindings, explicit projections, schema closure, parameter type/set validation,
UTF-8 capacities, integer bounds, Bool representation, null rejection, bounded
total ordering, stale revision behavior, result decoding and concurrent CAS.
These checks establish bounded local behavior, not a formal database proof or
D1-host acceptance.
