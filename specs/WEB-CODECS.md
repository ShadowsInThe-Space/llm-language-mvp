# General web codecs — web-codecs-v1

Normative bounded foundation for M3 issues #22/#32. This additive module does
not change `a1-ir-v1`, pkg1, the historical w1/w2 parsers, emitted files or hashes.
Codec checking is a host/value boundary, not a proof of a website or its target.

## Closed types and API

`llmlang.web.general.codecs` exports immutable, frozen descriptors:

| Python descriptor | Portable descriptor | Runtime value | JSON wire value |
| --- | --- | --- | --- |
| `TextType(N)` | `{kind:"text",capacity:N}` | Unicode string | JSON string |
| `IntType()` | `{kind:"int"}` | exact safe integer | canonical decimal string |
| `NatType()` | `{kind:"nat"}` | exact safe nonnegative integer | canonical decimal string |
| `BoolType()` | `{kind:"bool"}` | Python bool / JS boolean | JSON boolean |
| `OptionType(T)` | `{kind:"option",elem:T}` | tagged Option | tagged Option |
| `ListType(T,N)` | `{kind:"list",elem:T,capacity:N}` | `{list:[T],capacity:N}` | array of encoded T |
| `RecordType(ID,fields)` | `{kind:"record",name:ID,fields:[{name,type}]}` | `{record:ID,fields:{...}}` | same nominal envelope with encoded fields |

`ScalarType` is Text/Int/Nat/Bool; `CodecType` is the complete closed union.
`fields` is an immutable tuple of `(name, descriptor)` pairs. Records require
at least one unique field. IDs match `[A-Za-z_][A-Za-z0-9_.:-]{0,127}`;
fields match `[A-Za-z_][A-Za-z0-9_]{0,63}`. Unknown type classes, extra portable
descriptor fields, duplicate fields and malformed nested descriptors fail.
There is no capability, raw code, Unit, Result or general Variant codec in v1.

Every public operation validates the complete descriptor before use:

```python
validate_type(codec) -> None
type_descriptor(codec) -> dict[str, object]
encode_value(codec, native_value) -> object
decode_value(codec, parsed_wire_value) -> object
encode_json(codec, native_value) -> str
decode_json(codec, source: str | bytes) -> object
parse_wire_json(source: str | bytes) -> object
emit_typescript_runtime() -> str
```

`encode_value` validates native data and converts it to wire data; `decode_value`
does the reverse. Neither mutates or returns a mutable container from its input.
`decode_value` cannot detect keys already discarded by an earlier JSON parser:
HTTP callers must use `decode_json` on the bounded raw body instead.

The standalone TypeScript module exports `CodecType`, `CodecError`,
`CODEC_VERSION`, `validateType`, `encodeValue`, `decodeValue`, `encodeJson` and
`decodeJson` and `parseWireJson`. The untyped parser handles the action envelope
before selecting its declared input codec: dispatch must independently enforce
the exact action/input envelope fields and action allowlist, then decodeValue
with the selected trusted type. Parsing alone does not license any value type.
It uses standard web globals only, including TextEncoder and
fatal UTF-8 TextDecoder; no Node imports, globals or polyfills are required.
`decodeJson` accepts a string or Uint8Array. Its structural JSON parser checks
duplicate decoded keys at every nesting level; JSON.parse is used only for an
individual string token, never as the structural object parser.

## Exact primitive semantics

The reference and this JS target codec both accept Int in
`[-9007199254740991,9007199254740991]`; Nat additionally requires nonnegativity.
Python bool and float are not integers here. JS values must satisfy
Number.isSafeInteger; native negative zero is rejected by the JS encoder.
The broader mathematical Int semantics of A1 are not narrowed by this codec;
unsupported target inputs are rejected at this explicitly versioned boundary.

Wire integer grammar is exactly `0` or `-?[1-9][0-9]*`, restricted to the safe
range. Plus signs, leading zeros, negative zero, whitespace, exponents, fractions
and non-ASCII digits are forbidden. Check digit length/range before conversion.
All bare JSON numeric tokens are rejected, including those inside otherwise
invalid objects. This prevents a fractional or excessive numeric token from
rounding into an accepted integer during JSON parsing: for example JS parses
`9007199254740991.1` as the safe Number `9007199254740991`.

Text contains Unicode scalar values, forbids U+0000 and uses UTF-8 byte capacity.
An escaped, properly paired JSON surrogate pair decodes to its Unicode scalar;
unpaired surrogates and invalid UTF-8 bytes fail. There is no normalization,
trim, case conversion or line-ending conversion. Empty text, CR/LF, emoji,
combining characters, Arabic and HTML/SQL-like strings remain data.

Bool does not accept `0`, `1`, strings or truthy objects. D1 conversion is a
separate boundary: its adapter must encode/decode Bool explicitly as exactly
integer 0/1 and validate every native database value. These codecs do not
implement SQL queries or assert D1 INTEGER64/BigInt support.

## Structures and authority

Option has exactly `{tag:"None",value:null}` or
`{tag:"Some",value:encoded_T}`. Missing payloads, implicit null, additional keys
and unknown constructors are invalid. None is distinct from Some(empty text).

Records have exactly `record` and `fields`; ID and the exact declared field set
are checked. Field order is not significant on the wire; decoding restores
descriptor declaration order for the native map. Object keys such as
`__proto__` remain ordinary data: TS parsed/decoded field maps use null prototypes.

Lists are ordered and dense, with at most their declared N elements. Their wire
array never supplies a capacity. Decoding reconstructs native capacity from the
trusted descriptor; encoding rejects a native container with another capacity.
Every element is independently checked, including nominal identity.

Descriptors are compiler/host inputs, not authority supplied by a client. A
record resembling a DB capability or authenticated principal confers no rights.
Capabilities must remain outside the ordinary codec value universe. Server
authorization, origin/media checks, streaming HTTP limits, database validation
and action allowlists still belong at their respective integration boundaries.

## Resource and JSON limits

| Boundary | Maximum |
| --- | --- |
| Text capacity | 32768 UTF-8 bytes |
| List capacity | 4096 |
| Descriptor nesting / visited type nodes | 32 / 4096 |
| Native value nesting / visited value nodes | 32 / 4096 |
| Encoded or received JSON | 32768 UTF-8 bytes |
| JSON nesting / token nodes, including object keys | 32 / 4096 |

All limits apply together: a permitted declared capacity is not a promise that
every value of that size fits the wire/body/node budgets. Capacities must be
actual nonnegative integers, not bools. Large text is rejected before allocating
a full UTF-8 buffer; excessive integer digit strings before integer conversion.
Python preflights raw JSON depth and token budget before json.loads; TS checks
the same budgets in its structural parser. Parsing an untrusted body does not
invoke application or package code.

JSON uses the ordinary JSON whitespace/escape rules; malformed syntax,
duplicate keys after escape decoding, non-JSON constants and unknown value
fields fail. A UTF-8 BOM is preserved by the decoder and is invalid JSON, rather
than silently stripped. Canonical output is ASCII-escaped, keys sorted,
separators `,` and `:`, no insignificant whitespace or trailing newline.
Limits also apply to canonical output, whose Unicode escapes can use more
bytes than an equivalent incoming Unicode JSON string.

Stable error codes: `W_CODEC_TYPE`, `W_CODEC_VALUE`, `W_CODEC_INTEGER`,
`W_CODEC_TEXT`, `W_CODEC_CAPACITY`, `W_CODEC_JSON`, `W_CODEC_LIMIT`.
Python CodecError exposes code/message/path and `to_dict()` in diagnostic-v1.
Messages do not echo supplied values. Multiple simultaneous violations may be
reported in parser traversal order; acceptance always fails closed.

## RED / GREEN evidence and remaining target acceptance

`tests/test_general_web_codecs.py` is independently runnable with stdlib unittest
and is also collected by pytest. Initial RED: import failed because the general
codec module did not exist. After implementation all six test methods passed.
A subsequent differential RED exposed a depth discrepancy for 32 nested arrays
containing Bool: Python returned W_CODEC_VALUE while TS returned W_CODEC_LIMIT.
Counting primitive/key depth in the Python preflight and matching TS key depth
made that test GREEN without increasing the bounds.

The differential suite executes emitted TypeScript in Node and compares native
decoded data, exact canonical output, and rejection codes against Python. Cases
include safe integer edges, rounded bare numeric input, noncanonical integers,
Unicode boundaries, invalid scalars, nested nominal records, duplicate escaped
keys, reconstructed list capacities, prototype-shaped field names and node/depth
exhaustion. This is differential test evidence, not formal target equivalence.
Actual browser, Worker/D1, client-bundle and complete web-app acceptance remain
the separate #32 integration gates.
