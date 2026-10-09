# General web source and component libraries

Status: additive M3 `websrc1` / `webuilib1` frontend for issue #22. These source
versions lower to the generic `WebProgram` model and its `web-program-v1` bound
snapshot. Historical w1/w2 parsers, ASTs, generated outputs and fixtures remain
unchanged. Sources contain actual declarations, static query nodes and generic
views; no source form accepts embedded JSON IR, Python, JavaScript, TypeScript or
SQL as authority.

## Application and query grammar

```text
(websrc1 APP "Application title"
  (schema
    (table entries
      (id (Text 64) primary)
      (title (Text 32))
      (revision Nat)))
  (action save ((id (Text 64)) (title (Text 32))) public
    (insert entries
      (values (id id) (title title) (revision 0))
      (project id title)))
  (action browse () public
    (select_list entries (project id title)
      (order (title asc)) (limit 20) (offset 0) (where)))
  (action fetch ((selected_id (Text 64))) public
    (select_unique entries id selected_id (project id title revision)))
  (library common)
  (import common editor editor)
  (import common browser browser)
  (use editor)
  (use browser))
```

There is exactly one schema. Tables declare ordered non-null scalar columns.
Types are `Int`, `Nat`, `Bool` and `(Text CAPACITY)`, using the exact target-safe
integer and bounded Unicode-scalar codec contract. Optional column markers are
`primary` and `unique`; duplicate/unknown markers fail closed. Every table has
exactly one primary key. The existing query checker enforces identifiers, table
and column uniqueness, codec capacities and query bounds.

Each action declares all parameters explicitly as ordered `(NAME TYPE)` pairs,
a static authorization policy (`public`, `authenticated` or `admin`), and exactly
one query, followed optionally by explicit pure parameter transforms. Query input operands are parameter names or scalar literals: integers,
`true`/`false`, or double-quoted text. Parameter types are derived from the explicit
action declaration, and every query use must match its actual schema column.
Unused, missing, duplicated or inconsistently typed action parameters fail closed.

The closed query forms are:

```text
(insert TABLE (values (COLUMN INPUT)...) (project COLUMN...))
(select_unique TABLE UNIQUE_COLUMN INPUT (project COLUMN...))
(select_list TABLE (project COLUMN...) (order (COLUMN asc|desc)...)
  (limit N) (offset N) (where (COLUMN INPUT)...)
  [(cursor (COLUMN INPUT)...)])
(conditional_update TABLE UNIQUE_COLUMN KEY_INPUT REVISION_COLUMN EXPECTED_INPUT
  (values (COLUMN INPUT)...) (project COLUMN...))
```

Projection, values, order, where, limit and offset forms are explicit; empty
`(where)` is allowed. List order is deterministic and the query compiler appends
a primary-key tie breaker where needed. Unique selects require a declared unique
key. Conditional updates bind the key and expected Nat revision atomically;
updates cannot rewrite their key/revision, and successful updates increment the
revision. Source never supplies raw SQL or interpolated SQL fragments.

The optional `cursor` is a typed keyset boundary, not an arbitrary predicate.
It lists every effective ordering column exactly once in effective order:
explicit order columns followed by the primary key ascending if not already
present. For history ordered by `id desc`, the cursor is `(cursor (id cursor_id))`.
For tasks ordered by `priority desc` with the implicit `id asc` tie breaker, it is
`(cursor (priority cursor_priority) (id cursor_id))`. Cursor inputs must exactly
match column types. Partial, duplicated, reordered, unknown or mistyped cursor
columns fail closed, as does a nonempty cursor with a nonzero offset. The query
compiler builds the bounded prepared lexicographic comparison; source cannot
choose SQL operators or supply an SQL fragment.


## Explicit pure action transforms

An action can append zero or more transform forms after its one query:

```text
(action save ((id (Text 64)) (title (Text 32))) public
  (insert entries (values (id id) (title title) (revision 0)) (project id title))
  (transform title preview (title)))
(pure_library helpers)
```

The grammar is `(transform TARGET_PARAM EXPORTED_FUNCTION (ARG_PARAM...))`.
Targets and arguments are static names of declared action parameters, and the
function must be an exported entrypoint in the explicitly resolved A1 library.
The checker requires exact scalar argument/result types, including Text capacity;
missing library/function/target/arguments, wrong arity/types and duplicate targets
fail closed. Strings, literals, host calls or expression bodies cannot appear as
transform argument names. Zero arguments are syntactically valid when an exported
function's checked signature actually takes none.

Arguments always read the original decoded action inputs. Transforms cannot chain
through another transform's result, and cannot create extra input fields. Each
result replaces only its declared target parameter before the prepared query
binds. Declaration order is preserved in source and checked metadata. Original
inputs and transformed outputs remain subject to their exact scalar codecs and
the library's declared execution budgets. The library and selected function IDs
are part of full semantic binding; renaming a function or changing its source
cannot be authorized by an old offered hash. Sources without transforms retain
their original action syntax and behavior.

## Generic views and shared libraries

Views appear directly at application scope, or inside reusable components:

```text
(form VIEW ACTION
  (fields (PARAM "Label" input|textarea|checkbox)
          (PARAM "Label" select (choice "Label" SCALAR)...))
  (states "Loading" "Error" "Empty" "Success")
  (buttons "Submit" "Clear"))
(list VIEW ACTION (columns (COLUMN "Label")...)
  (states "Loading" "Error" "Empty" "Success")
  [(select DETAIL_VIEW PARAM COLUMN)]
  [(paginate NEXT_ACTION (NEXT_PARAM CONFIRMED_COLUMN)...)])
(detail VIEW ACTION (columns (COLUMN "Label")...)
  (states "Loading" "Error" "Empty" "Success"))
(component NAME VIEW_OR_USE...)
(use COMPONENT_OR_ALIAS)
```

Fields bind every form action parameter exactly once. Bool uses checkbox;
`textarea` is supported only for Text and preserves multiline scalar text;
select choices are typed scalars. List views use parameter-free bounded list
queries, details use unique selects, and displayed columns must be projected.
List selection binds an explicit unique row field into the target detail action
parameter. Clear is local form state, as defined by the generic model; source
does not add a destructive database clear action. Labels, state messages and
buttons are explicit bounded display text.

A list can declare `select` and `paginate` independently, each at most once, in
either order after its states. Pagination names an explicit next-page query
action and maps its cursor parameters to projected fields from the confirmed
row. The next action must preserve the initial list's schema/query shape,
projection, effective ordering, bounds and authorization while adding its exact
typed cursor parameters. Unknown next actions, incorrect field/parameter
mappings and duplicate mappings fail closed. Next-page transforms are forbidden;
a cursor must retain the actual confirmed database ordering values. Component
libraries can declare these mappings explicitly and bind them into both consumers.

Page bounds apply to every response. Large Text capacities therefore require
appropriately small pages within the separate codec body budget; the full-text
examples use `(Text 4096)` with one-row pages and keyset navigation. This syntax
retains the complete bounded text, including line breaks, rather than assuming
that a presentation preview is the stored value.

External UI libraries are separate canonical source snapshots. For example, both
a history application and a task application can use this same source library
when their public UI action/field contracts use `save`, `browse`, `fetch`, `id`
and `title`; table names and additional database columns can differ:

```text
(webuilib1 common
  (component editor
    (form edit save (fields (id "ID" input) (title "Text" input))
      (states "Loading" "Failed" "Empty" "Saved") (buttons "Save" "Clear")))
  (component browser
    (list listing browse (columns (title "Text"))
      (states "Loading" "Failed" "Empty" "Ready")
      (select detail selected_id id))
    (detail detail fetch (columns (title "Text"))
      (states "Loading" "Failed" "Empty" "Ready"))))
```

`(library NAME)` declares an external library. `(import LIBRARY COMPONENT ALIAS)`
imports one named component explicitly, and `(use ALIAS)` expands it. Component
children in a library resolve `use` names lexically within that same library;
they cannot acquire undeclared app components or aliases. Library IDs must match
the source snapshot IDs. Supplied library source names must exactly match declared
libraries: missing or unused snapshots fail closed. Cyclic/unknown component
references are rejected, including unused definitions. Final application checking
resolves library view/action types and bounds all component expansion.

Libraries contain explicit generic views with static contract names. This source
version does not claim parameterized templates, renaming substitution, dynamic
components or an arbitrary UI language. Shared applications must actually satisfy
the shared library's declared action/field contracts.

Optionally, `(pure_library NAME)` resolves one separate `a1src1` source snapshot
supplied through `pure_sources`. The public A1 frontend independently lowers and
checks it, then canonical IR bytes bind it into WebProgram. Without an action
transform its role is `provenance_only`; with checked transforms it is `executable`
for those explicit scalar calls. This binding does not claim a formal proof of
cross-language target equivalence. No embedded IR JSON is accepted by this form.

## Reader bounds and canonical binding

Sources are Unicode text with exactly one parenthesized module. Identifiers match
`[A-Za-z_][A-Za-z0-9_]{0,63}`. Strings use JSON quoting/escapes; NUL, unpaired
surrogates, raw string controls and invalid escapes fail closed. Integers use
`-?(0|[1-9][0-9]*)`; there are no floats. Whitespace is ASCII space/tab/CR/LF;
comments and extra top-level payloads are unsupported.

Default `WebSourceLimits` are 262144 combined UTF-8 source bytes, nesting depth
32, 8192 combined syntax nodes, and 16 digits per integer. Hard configurable
ceilings are 1048576 bytes, depth 64, 65536 nodes and 16 digits. Root and UI
library source nodes/bytes share a reader budget. A declared pure source is
checked against the remaining node budget and the same depth/digit ceilings.
Combined canonical source bytes must also fit, preserving canonical roundtrip.
`ProgramLimits` independently bounds declarations, expanded components and bound
snapshot bytes; these checked budgets are included in semantic binding.

All source rejections use `WebSourceError`, with `W_SOURCE_*` codes, message and
location, and source line/column where available. Source spans use zero-based
character offsets and one-based lines/columns. Immutable source maps retain paths
such as `actions[0]`, `schema.tables[0].columns[0]` and
`libraries.common.definitions[0]`; named checker view/action paths also map back
to their original declaration positions. Span metadata does not alter WebProgram
semantics or the bound snapshot.

Canonical source uses one space between elements, canonical decimal integers,
JSON string escaping with raw valid Unicode, no normalization and no trailing
newline. Declaration order and all explicit values are preserved. Whitespace or
equivalent string escape spellings do not change canonical source/source binding.

Python API in `llmlang.web.general.source`:

- `parse_component_library(text, limits=...)` returns immutable library
  declarations, canonical source, framed source hash and immutable source map.
- `parse_web_source(text, library_sources=..., pure_sources=..., limits=...,
  program_limits=...)` returns `ParsedWebSource` with immutable `program`,
  independently `checked` bound model, canonical root source, `source_hash`,
  `semantic_hash`, and immutable source map.
- `lower_web_source(...)` returns freshly reconstructed WebProgram declarations.
- `canonicalize_web_source(...)` returns canonical root source text.
- `check_web_source_binding(text, offered, ...)` independently reparses every
  declared source snapshot and reconstructs the checked program. `offered` may
  be unchecked WebProgram declarations or a snapshot dictionary. Complete
  canonical bound bytes must match; forged source/program hashes cannot authorize
  mismatched schema, queries, views, libraries, effects or budgets.

`source_hash` is SHA-256 over length-framed UTF-8 parts: domain
`llmlang:web-source`, canonical root source, then each declared UI library's
`ui`, name and canonical source in declaration order, followed by the optional
pure library's `pure`, name and canonical source. UI standalone source uses domain
`llmlang:web-ui-source` followed by its canonical source. Frames prefix each part
with its 64-bit big-endian byte length. `semantic_hash` is exactly the model's
independent `web-program-v1` semantic hash and includes resolved library content,
codecs, query IR, views, effects and checked program budgets. An edited external
snapshot changes both the source binding and its affected semantic binding.
