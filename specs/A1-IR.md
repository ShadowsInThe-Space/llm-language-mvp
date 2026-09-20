# A1-IR — canonical typed execution IR

Status: normative M2 contract for issue #19, amended after independent review.
Only the subset defined here may be called `a1-ir-v1`. P0, w1, w2 and pkg1
remain unchanged.

## Document and canonical binding

An IR document has exactly these top-level keys:

```json
{
  "format": "a1-ir-v1",
  "profile": "a1",
  "checker": "a1-check-v1",
  "types": [],
  "functions": [],
  "specializations": [],
  "entrypoints": [],
  "limits": {
    "max_steps": 10000,
    "max_collection_expansion": 1000,
    "max_call_depth": 64
  }
}
```

Missing and unknown keys fail closed. Limits are explicit positive metadata
integers. JSON is serialized with sorted keys, no insignificant whitespace,
ASCII escapes, no NaN/Infinity, and UTF-8/ASCII bytes. Semantic binding is:

```text
SHA-256(frame(
  "llmlang:a1-ir", format, profile, checker, canonical_json(document)
))
frame(x...) = concat(u64be(byte_length(x)), utf8(x))
```

The hash therefore includes all types, functions, specializations, entrypoints
and limits. Certificates using an unframed payload hash are invalid.

## Types

Primitive type spellings are `Unit`, `Bool`, `Int`, `Nat`, or their lowercase
`{"kind": ...}` object form. `Int` is mathematically exact in the reference
interpreter. A JavaScript target fails closed before emission or execution when
an integer cannot be represented exactly as a safe JavaScript integer.

Bounded and structured types use:

```text
{"kind":"text","capacity":N}
{"kind":"list","elem":T,"capacity":N}
{"kind":"option","elem":T}
{"kind":"result","ok":T,"error":E}
{"kind":"record","id":"Customer"}
{"kind":"variant","id":"Choice"}
```

For convenience, a nominal ID may be used directly where a type is expected.
Record declarations are `{"kind":"record","name":ID,"fields":[...]}`.
Variant declarations are `{"kind":"variant","name":ID,"cases":[...]}`;
each case has a `tag` and optional payload `type`. IDs, fields and tags are
unique. Records are nominal even when field layouts match. Variants are closed.
`Option` and `Result` values obey the same tagged-value rules; they do not add
implicit null.

`Text<N>` contains valid Unicode scalars, no U+0000, and at most N UTF-8 bytes.
There is no implicit normalization or trim. `List<T,N>` is ordered, immutable
and has length at most N.

## Functions and SSA values

A function has exactly one static name, ordered typed parameters, a declared
`result`, an ordered `body`, and a `return` name. Parameters and instruction
destinations share one immutable namespace; every reference is backward-bound
and every destination is unique. Function result and returned value types must
match. Calls and callbacks name static functions. Their graph is acyclic.

Example:

```json
{
  "name":"bytes",
  "params":[{"name":"text","type":{"kind":"text","capacity":32}}],
  "result":"Nat",
  "body":[
    {"op":"text_utf8_bytes","dest":"%0","value":{"ref":"text"},"type":"Nat"}
  ],
  "return":"%0"
}
```

An instruction always has `op` and unique `dest`. Its result type is inferred
by the checker. If `type` is present, it is an explicit assertion and must equal
the inferred type. This deliberately replaces the earlier unimplemented CFG
sketch: `a1-ir-v1` is a linear A-normal IR, not a general block IR.

## Operations

The closed operation set is:

| Operation | Required data | Result rule |
| --- | --- | --- |
| `const` | `type`, `value` | literal must inhabit type |
| `record_make` | record ID, exact fields | nominal record |
| `record_get` | nominal record, field | declared field type |
| `variant_make` | variant, tag, payload if declared | nominal variant |
| `match_value` | variant value, exact arm map | all arms same type |
| `add` | two Int/Nat operands | exact Int, or Nat for Nat+Nat |
| `refine_nat` | Int plus A1-C004 evidence | Nat |
| `call` | callee plus exact arguments | declared callee result |
| `list_empty` | element type/capacity via asserted type | empty list |
| `list_append` | list and element | Result with CapacityError |
| `list_index` | list and Nat | Option element |
| `bounded_map` | list and one-argument callback | bounded list |
| `bounded_fold` | list, initial, two-argument callback | accumulator |
| `text_utf8_bytes` | Text | Nat |
| `text_codepoint_count` | Text | Nat |
| `text_prefix_codepoints` | Text and Nat | same Text capacity |
| `text_concat` | two Text values and capacity | bounded Text |

`refine_nat` evidence is exactly
`{"predicate":">=0","rule":"A1-C004"}` and is reconstructed by the
checker. A negative literal is rejected even if this object is present.

Append at capacity returns `Err(CapacityError)` and does not mutate its input.
Indexing outside the current length returns `None`. Map/fold run left to right
and consume the explicit collection expansion budget. Text prefixes operate on
Unicode scalars, never UTF-16 code units or partial UTF-8 sequences.

## Generics and specializations

Generic declarations and deterministic instance construction are defined in
`A1-GENERICS.md`. `specializations` contains the canonical, used-only instance
inventory. An empty list is valid for a non-generic module. Instance IDs bind
the shared generic declaration, explicit type arguments and non-negative
capacity arguments. Dynamic function values are forbidden.

## Static and runtime validation

Before `proved`, the checker validates:

- the exact document/version schema and canonical encodability;
- unique declarations, fields, cases, functions and SSA destinations;
- every operand binding and instruction result type;
- record fields, variant payloads and exhaustive matches;
- call/callback argument and result types, acyclic graph and Nat evidence;
- collection/text bounds and explicit budgets.

The host boundary independently validates entry arity and every runtime value:
primitive shape, nominal record/variant identity and payload, Nat non-negativity,
valid bounded Text, and list element/capacity invariants. Successful static
checking never licenses an unvalidated external value.

The interpreter applies document limits; an explicit caller limit may only
tighten them. `proved`, `returned`, `input_rejected`, and `resource_exhausted`
are separate statuses.

## Target and assurance boundary

The JavaScript target is a generated executable, not proof evidence. It rejects
unsafe integers rather than rounding them, repeats text scalar/capacity checks,
and uses `Array.from` for scalar prefixes. Differential tests compare canonical
reference and target outputs for two distinct consumers, nominal records and
capacities. These tests detect translation defects but do not formally prove
target equivalence.

P0/w1/w2/pkg1 compatibility tests and installed-wheel CLI tests are mandatory.
No M2 claim includes recursion, mutation, dynamic dispatch, unbounded data,
general CFGs, source-to-IR correctness, or a formally proved Python TCB.
