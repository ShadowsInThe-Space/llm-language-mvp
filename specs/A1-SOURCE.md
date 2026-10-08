# A1 source — bounded pure frontend

Status: additive M3 source contract for issues #21/#22. Version `a1src1`
lowers into existing `a1-ir-v1`; it does not extend that IR's execution semantics,
certificate format or hash framing. P0, w1, w2 and pkg1 are unchanged.

The source is an actual S-expression language with typed declarations and SSA
instructions. No form accepts opaque JSON, an offered IR, a source hash or proof
as authority. Source-to-IR correctness is checked by independent recomputation,
not established by a formal proof of this Python frontend.

```text
(a1src1
  (limits 10000 1000 64)
  (record Task (title (Text 32)) (done Bool))
  (fn title ((task Task)) (Text 32)
    (let text (Text 32) (record_get Task task title))
    (return text))
  (fn main () Nat
    (let title (Text 32) (const "Grüße"))
    (let done Bool (const false))
    (let task Task (record_make Task (title title) (done done)))
    (let text (Text 32) (call title task))
    (let size Nat (text_utf8_bytes text))
    (return size))
  (entry main))
```

## Closed syntax

Exactly one parenthesized module is required. The first module form must be
`(limits STEPS EXPANSION CALL_DEPTH)` with positive decimal integers; these are
execution budgets. Subsequent forms may be record/variant declarations,
functions, or single-name entry declarations. Their order is preserved within
IR declaration arrays. Duplicate names, fields, cases, binders and entries fail
closed. Built-in type names cannot be redeclared as nominal types.

```text
record       = (record NAME (FIELD TYPE)...)
variant      = (variant NAME (TAG [TYPE])...)
function     = (fn NAME ((PARAM TYPE)...) TYPE LET... (return BINDER))
LET          = (let BINDER TYPE OPERATION)
entry        = (entry NAME)
TYPE         = Unit | Bool | Int | Nat | NOMINAL
             | (Text CAPACITY) | (List TYPE CAPACITY)
             | (Option TYPE) | (Result TYPE TYPE)
```

Records and variants require at least one member, matching the existing IR.
Types are explicit at parameters, function results and every instruction result.
Instructions lower to their declared SSA destination without renaming; references
must be backward-bound, and static calls/callbacks must have an acyclic graph.
Types and operation result assertions are checked by the existing A1 checker.
Nominal type shorthand is resolved by that checker, including forward nominal
references. Function names can be forward referenced by static calls.

Identifiers match `[A-Za-z_%][A-Za-z0-9_.:%-]*`. `true`, `false` and `unit` are
reserved literal atoms. An operand is a bare binder name (an IR reference), or a
primitive literal. Structured values used as operands require a typed `const`
and a binder reference. A string is a double-quoted JSON string: JSON escapes are supported;
invalid escapes, raw string controls, NUL and non-scalar Unicode fail closed.
Integers use `-?(0|[1-9][0-9]*)`, with no leading zeroes or floats. Whitespace is
ASCII space/tab/CR/LF; comments and extra module forms are not supported.

The following are the complete operation forms. `V` denotes an operand, `T` a
static type ID, `F` a static function ID, and `N` a non-negative capacity.

| Source operation | Lowered IR operation |
| --- | --- |
| `(const LITERAL)` | `const` |
| `(record_make T (FIELD V)...)` | `record_make` |
| `(record_get T V FIELD)` | `record_get` |
| `(variant_make T TAG [V])` | `variant_make` |
| `(match_value T V (TAG V)...)` | `match_value` |
| `(add V V)` | `add` |
| `(refine_nat V (evidence >=0 A1-C004))` | `refine_nat`, exact existing evidence |
| `(call F V...)` | `call` |
| `(list_empty)` | `list_empty`, capacity from explicit List result type |
| `(list_append V V)` | `list_append` |
| `(list_index V V)` | `list_index` |
| `(bounded_map V F)` | `bounded_map` |
| `(bounded_fold V V F)` | `bounded_fold` |
| `(text_utf8_bytes V)` | `text_utf8_bytes` |
| `(text_codepoint_count V)` | `text_codepoint_count` |
| `(text_prefix_codepoints V V)` | `text_prefix_codepoints` |
| `(text_concat V V N)` | `text_concat`, explicit capacity |

Structured literals are `(list N LITERAL...)`,
`(record T (FIELD LITERAL)...)`, `(variant T TAG [LITERAL])`, `(none)`,
`(some LITERAL)`, `(ok LITERAL)` and `(err LITERAL)`. They produce the existing
IR tagged host-value representations. A literal never contains binder references.
Every constant and inline literal with an expected type is additionally checked
by A1's full host-value validator: nested
nominal identities, tags, payloads, list lengths/elements and text capacities must
inhabit the asserted constant type. This strengthens frontend validation without
changing historical IR behavior.

All supplied record fields and match arms must be exact. Records are nominal;
structural similarity does not establish type compatibility. `list_append` uses
the existing `CapacityError` result type; this source version does not invent a
new collection-error representation.

## Bounds, diagnostics and canonical binding

`SourceLimits` is separate from the explicit execution budgets. Defaults are
262144 UTF-8 source bytes, nesting depth 64, 50000 syntax nodes and 1024 decimal
digits per integer. Hard configurable ceilings are 1048576 bytes, depth 128,
200000 nodes and 1024 digits. Limits must be positive exact integers. The tokenizer
counts list openings and atoms as nodes and constructs parentheses iteratively.
Canonical output must also fit the configured byte budget, ensuring it can be
reparsed with the same limits. An exhausted parser/checker budget fails with
`E_A1_SOURCE_LIMIT`.

All source rejection uses `A1SourceError` with `E_A1_SOURCE_*` codes and stable
message/location data. Syntax nodes carry zero-based character offsets and
one-based line/column positions. `ParsedSource.source_map` maps IR paths such as
`functions[1].body[2]` to original source positions. Existing IR type diagnostics
are wrapped as `E_A1_SOURCE_TYPE`, preserving their message and IR location.
Source positions are producer metadata; they are not added to `a1-ir-v1` or its
semantic hash. Missing/unknown syntax, types and operations fail closed.

Canonical source uses one space between form elements, canonical decimal
integers, JSON string escaping with raw valid Unicode, and no trailing newline.
It preserves identifiers, declaration/member/instruction order, types and values.
No Unicode normalization occurs. Canonical source roundtrips through the parser;
whitespace or equivalent JSON string escape spellings do not change its result.
Canonicalization is lexical, not alpha-renaming or declaration sorting.

Python API in `llmlang.a1.source`:

- `parse_source(text, limits=...)` returns `ParsedSource` containing freshly
  lowered and checked `module`, `canonical_source`, `semantic_hash`, `source_map`.
  The result retains immutable canonical IR bytes; each `module` access returns
  a defensive copy. The source map is an immutable snapshot of immutable spans.
- `lower_source(text, limits=...)` returns the checked IR dictionary.
- `canonicalize_source(text, limits=...)` returns canonical source text.
- `check_source_binding(text, offered_ir, limits=...)` reparses source, independently
  reconstructs/checks its IR and compares complete canonical IR bytes. It returns
  false for malformed source, unencodable offers or any semantic mismatch; no
  offered source hash, IR hash or certificate is trusted.

`semantic_hash` is exactly existing `a1.ir.module_hash(lowered_ir)`. It includes
all declarations, types, binder names, instructions, entries, the empty
specialization inventory and execution budgets. It is not a hash of source spans
or source whitespace. Adding a field to offered IR cannot preserve binding by
supplying a matching-looking hash.

This is a pure, monomorphic source frontend. Generic declarations,
specialization syntax, effects, mutation, recursion, dynamic callbacks, control
flow blocks, host IO, HTTP/SQL syntax and general web handlers are outside this
version. Such features require their own versioned contracts rather than new
unrecognized forms being accepted by `a1src1`.
