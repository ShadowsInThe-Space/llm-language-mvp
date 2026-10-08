# WEB-PROGRAM — bounded typed application composition

`web-program-v1` defines an immutable application model and deterministic IR
snapshot for M3. It composes existing exact wire codecs, typed schema/query
nodes, reusable UI components and the independently checked effect graph. It
does not change P0, w1, w2, pkg1 or `a1-ir-v1`. This document describes model
validation; it does not claim implementation or verification of a browser,
HTTP host, D1 adapter or authentication system.

## Declaration API

All model records are frozen and slotted. Every declaration collection is an
exact tuple; scalar types and query/schema nodes use the existing closed
classes from `web.general.codecs` and `web.general.queries`.

```python
WebProgram(
    name, title, schema, actions, views,
    components=(), libraries=(), imports=(), pure_library=None,
)
QueryAction(name, params, query, authorization="public")
```

Program/action/component/view IDs use ASCII identifiers of 1..64 characters.
Display text is nonempty, valid Unicode scalar text without NUL, bounded to
512 UTF-8 bytes. Names and labels are data, never target-code fragments. No raw
SQL, TypeScript, HTML, free-form expressions or caller-provided effect graphs
are accepted.

The program declares a nonempty `Schema`, nonempty unique actions and a
nonempty UI composition. Schema constructors are defensively reconstructed;
frozen dataclasses alone are not treated as validation evidence. Tables,
columns, keys, scalar types, flags, query shapes and parameter uses are checked
again. Duplicate names, mutable nested collections, unknown nodes, missing
projections and invalid cardinalities fail closed.

An action contains exactly one `Insert`, `SelectUnique`, `SelectList` or
`ConditionalUpdate` query. Its ordered `params` tuple contains unique `Param`
declarations. The name/type mapping must exactly equal all parameter uses
reconstructed by `compile_query`; unused advertised parameters, missing
parameters and repeated names with inconsistent types are rejected. Query
constants and parameter uses retain the schema's scalar types. Conditional
updates preserve the declared unique key and non-key Nat revision boundary,
including runtime rejection of a revision increment outside the exact range.

## Action codecs and result contracts

`validate_program(program, *, limits=DEFAULT_LIMITS)` returns a frozen
`CheckedWebProgram` with:

| Attribute | Meaning |
| --- | --- |
| `actions` | Ordered tuple of independently compiled `ActionContract` records |
| `expanded_views` | Ordered concrete Form/List/Detail composition |
| `effects` | Reconstructed structural effect report and partitions |
| `canonical_bytes` | Defensive immutable canonical IR snapshot |
| `semantic_hash` | Framed SHA-256 of the complete snapshot |

`action(name)` looks up a compiled contract or raises `KeyError`. `snapshot()`
decodes a fresh JSON copy; changing that copy cannot alter the checked result.
`validate_program` accepts an exact unchecked `WebProgram` declaration only.
A caller-constructed `CheckedWebProgram` cannot bypass checking. Target emitters
must invoke `validate_program` on every invocation and use the returned
snapshot/contracts, never trust a `checked` marker or external manifest.

An `ActionContract` retains `name`, ordered `params`, closed `query`,
`authorization`, generated `CompiledQuery`, `input_codec` and `output_codec`.
No query SQL is taken from user input; SQL in the compiled contract is derived
by the closed query compiler.

For action `save`, nonempty inputs use nominal `RecordType("saveInput", ...)`;
fields are exactly its parameter declarations. A parameter-free action has
`input_codec=None` and accepts exactly `{}`. `decode_input(wire)` returns
validated native parameter data and rechecks the compiled bindings. Ordinary
input fields cannot create or replace host authority.

Projected rows use nominal `RecordType("saveRow", ...)`, with exact projected
schema fields in declaration order. The output wrapper follows query
cardinality:

| Query cardinality | Output codec |
| --- | --- |
| `one` | Nominal projected row |
| `optional` | `OptionType(row)` |
| `bounded` | `ListType(row, max_rows)` |
| `conditional` | `OptionType(row)` |

`encode_output(native_value)` validates row identity, field set, types and
wrapper/capacity before producing wire data. Integers use canonical decimal
strings on wire and exact safe integers at the TypeScript target. Conditional
failure remains a separate host outcome (`ConditionNotMet`); a host may map it
to a conflict response rather than a successful optional absence. This model
does not prescribe an HTTP status code or execute SQL.

The web transport has a fixed `MAX_WIRE_BYTES=32768` boundary. Program checking
uses `max_wire_bytes(codec)` to bound the canonical ASCII representation of
every value allowed by the inferred codec, including nominal record names,
field names, wrappers and worst-case Unicode/control-character escaping. The
complete closed request `{"action": action_name, "input": value}` must fit;
checking just the inner input value is insufficient. Both this request bound
and the output codec bound must fit before an action is accepted. Failure is
`W_PROGRAM_LIMIT` at `actions.<name>.input` or `actions.<name>.output`.

Query-level capacities such as `MAX_LIST_ROWS=1000` remain available to the
query library. A web action must choose a row limit appropriate for its actual
projected types and transport budget; query legality alone is not transport
feasibility. These byte bounds concern canonical wire data. The checker also
uses `max_wire_nodes(codec)` to bound JSON parsing/allocation nodes, including
record wrapper objects, nominal strings, field keys and values. Outputs must
fit `MAX_NODES=4096`; requests must fit after adding four nodes for the outer
object, its `action` and `input` keys, and action-name string. Exceeding this
bound uses the same deterministic input/output `W_PROGRAM_LIMIT` paths.
Current action shapes are flat scalar-parameter records and flat projected rows
with one Option/List wrapper; even the closed request envelope has depth at
most five, below the codec depth limit. No generic deeply nested action type is
advertised. Runtime decoders continue to enforce raw body size, depth and node
budgets independently for hostile or noncanonical input.

## Typed views and local state

```python
ViewStates(loading, error, empty, success)
InputField(param, label, control="input", choices=())
DisplayColumn(column, label)
FormView(name, action, fields, states, submit_label="Save", clear_label="Clear")
ListView(name, action, columns, states, selection=None)
DetailView(name, action, columns, states)
Selection(detail, param, column)
```

All four states are required and contain bounded display text.

- A form binds every parameter of a parameterized Insert/ConditionalUpdate
  action exactly once. Types come from the action signature, not field claims.
  Bool uses a checkbox. Other scalar types use input or select. A select has
  1..64 distinct typed values with bounded labels; other controls have no
  choices. Submit invokes the declared action. Clear is strictly local UI
  reset; no server clear action or DB effect is represented.
- A list binds a parameter-free, explicitly ordered bounded SelectList. Its
  nonempty display columns are distinct projected fields.
- A detail binds SelectUnique cardinality and explicitly declared projected
  columns. It has the same required loading/error/empty/success states.
- A list selection names one concrete DetailView. The detail's action must
  have exactly one input parameter used as its unique-key query value. The
  selection binds that exact parameter from the same projected unique-key
  column, type and table. The target action follows unambiguously from the
  named detail view; it is never an independently supplied conflicting call.

Expanded view IDs are globally unique. These rules do not contain branches for
history, tasks, CRM or another domain. Different schemas and column sets use
the same composition model.

## Reusable component definitions and imports

```python
ComponentDef(name, children)
ComponentLibrary(name, definitions)
ComponentImport(library, component, alias)
ComponentUse(name)
```

A component is a nonempty tuple of concrete views or static component uses.
Definitions are explicit; libraries have unique names and nonempty definition
sets. A use in the main program/local definitions resolves only to an explicit
local definition or imported alias. A library's nested uses resolve only to
that library's own definitions. Aliases cannot shadow local declarations or
each other. Unresolved references, ambiguous imports, duplicate definitions
and cycles are rejected, including in unused definitions.

Concrete view IDs form one globally unambiguous namespace across the main
composition and all local/library definitions, including unused definitions.
Identical reused declarations coalesce for reference checking; different views
advertising the same ID are rejected. Selection references are checked in this
entire namespace, so a target may live in a sibling component but an unused
component cannot retain a nonexistent target. Final actual expansion must
still contain each concrete view ID exactly once and resolve its selections.

Libraries reuse declarative composition against the application's explicitly
named action contracts. This initial model has no dynamic components,
component parameters or arbitrary code templates. Repeated expansion that
duplicates a concrete view ID is rejected. Imports and original definitions
remain in the semantic snapshot alongside the expanded composition.

## Derived effects and trust boundary

The checker derives each `server:<action>` function directly from its actual
query node: SelectUnique/SelectList require `db.read`, while
Insert/ConditionalUpdate require `db.write`. All actions remain server-side.
Each actual concrete UI view derives a `ui:<view>` function with
`network.call`; a list-to-detail selection also records the static client
detail edge. The HTTP action boundary is transport, never an ordinary
client-to-server function edge. Entry sets are derived from actual declarations
and views. `check_effect_graph` checks the resulting graph and partitions.

`authorization="public"` adds no identity requirement. `"authenticated"`
requires server `identity.authenticated`; `"admin"` requires both
`identity.authenticated` and `identity.admin`. These are requirements, never
grants. A generated host must reject protected actions unless a trusted
server adapter supplies and enforces actual authenticated/authorized context.
Request fields, labels, form inputs or a declaration naming admin cannot
satisfy this requirement.

Client descriptors contain UI bindings, ordinary data codecs and transport
action names only. They contain no schema/query definitions, DB capability
values, authentication context or server policy. The full IR snapshot is a
server/build artifact; copying it wholesale into generated client code would
violate this boundary. This model checks structure and provenance, not the
implementation of a host's authentication or authorization.

## Pure library provenance

`pure_library` is optional exact canonical `a1-ir-v1` bytes, bounded to 131072
bytes and at most 64 function declarations. The existing A1 validator checks
it independently; its `module_hash` and complete IR are bound in the WebIR
snapshot. Noncanonical JSON, duplicate-key encodings, malformed or unsupported
IR are rejected. The role is explicitly `provenance_only`: no pure function
call integration, evaluation, property proof or used-entry proof is advertised
by this model. The binding cannot turn an external manifest into evidence.

## Limits, diagnostics and canonical binding

Default `ProgramLimits` are 64 actions, 64 total component declarations, 256
nodes, component depth 16, canonical snapshot size 262144 bytes and pure
library size 131072 bytes. Query/schema counts use the existing query bounds.
The node budget covers declared nodes and visits during validation/expansion,
including unused definitions. Depth is checked before recursive expansion.
Budgets must be nonnegative exact integers; depth is positive. Structural and
canonical-byte limits fail closed.

`ProgramError` supplies the existing `diagnostic-v1` envelope with stable code
and dotted path. Codes are `W_PROGRAM_BINDING`, `W_PROGRAM_SCHEMA`,
`W_PROGRAM_ACTION`, `W_PROGRAM_VIEW`, `W_PROGRAM_COMPONENT`, `W_PROGRAM_PURE`,
`W_PROGRAM_EFFECT`, `W_PROGRAM_LIMIT`, and `W_PROGRAM_INPUT`. External values
are not interpolated into diagnostics. Declaration order determines failure
order. Codec/query runtime errors retain their own typed-boundary diagnostics.

The canonical snapshot binds every schema/query declaration, literal and
parameter descriptor, original component/library/import, expanded UI binding,
all labels/states, inferred action codecs, authorization requirements, pure
library provenance, effect graph report and explicit limits. Versions include
`web-codecs-v1`, `web-queries-v1`, `a1-effects-check-v1` and
`a1-host-effects-v1`. Canonical JSON has sorted object keys, ASCII escapes, no
insignificant whitespace and no NaN/Infinity. Semantic binding is:

```text
SHA-256(frame("llmlang:web-program", "web-program-v1", canonical_snapshot))
frame(x...) = concat(u64be(byte_length(x)), utf8(x))
```

Ordered declarations, projections, views and choices remain ordered. Changing
the schema, literal, parameter, query, component, import, state, authorization,
codec, effect or bound pure-library IR invalidates the binding. A successful
model result is structurally checked; it is not a formally proved translation
or runtime-security guarantee.
