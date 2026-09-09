# P0 Golden Programs

This corpus freezes ten small behavioral contracts independently of candidate generation.
Each task has three neighboring files in `examples/golden/`:

- `.llspec`: authoritative public function signatures, input requirements and exact result contracts.
- `.ll`: a candidate implementation, which verification must check against that specification.
- `.json`: entry index, a concrete valid-input witness and exact-value execution examples.

The ten contracts determine the result for every admissible input. They are call-free;
candidate implementations may use backward calls. Integer arithmetic denotes mathematical integers,
subject to explicit operational resource limits; it has no signed machine overflow.

| Task | Input order | Required input | Exact result | Candidate features |
| --- | --- | --- | --- | --- |
| `identity` | `x` | Any Int | `x` | Variable |
| `minimum` | `a, b` | Any Ints | `min(a, b)` | Comparison, conditional |
| `maximum` | `a, b` | Any Ints | `max(a, b)` | Strict comparison with reversed operand order |
| `abs` | `x` | Any Int | Absolute value of `x` | Constant multiplication, conditional |
| `clamp` | `value, lower, upper` | `lower <= upper` | `min(max(value, lower), upper)` | Nested conditionals, equality boundaries |
| `nonnegative_difference` | `a, b` | Any Ints | `max(0, a - b)` | `let`, subtraction |
| `overlap_length` | `a, b, c, d` | `a <= b` and `c <= d` | `max(0, min(b, d) - max(a, c))` | Three nested `let` bindings |
| `grant` | `requested, available` | Both nonnegative | `min(requested, available)` | Entry fn 1 calls fn 0 and must satisfy its precondition |
| `tiered_fee` | `quantity` | Nonnegative | First ten units cost 2 each, remaining units cost 1 each | `let`, constant multiplication, piecewise arithmetic |
| `access_rule` | `age, active` | Nonnegative age, Bool flag | `age >= 18 and active` | Strict Boolean conjunction, negation |

`overlap_length` measures interval length, so touching endpoints and degenerate intervals have
zero length. This is not an inclusive integer-element count. `tiered_fee` uses abstract integer
units and is a language fixture, not a commercial tariff or currency calculation.

The `grant` specification contains two public functions with the same exact result contract.
Function 0 is the helper; function 1 is the default entry. Both contracts must be proved.
The source language's variables use de Bruijn indices: the last parameter has index zero,
and each `let` pushes a new value at index zero.

## Exact transport

JSON metadata uses a numeric entry index, but language values are always tagged:

```json
{
  "inputs": [
    {"type": "Int", "value": "9007199254740993"},
    {"type": "Bool", "value": true}
  ],
  "expected": {"type": "Bool", "value": true}
}
```

An Int payload is a decimal string, never a JSON number. Bool payloads are JSON booleans.
The corpus deliberately includes values above binary64's exact-integer range and outside
signed 64-bit range, plus negative inputs, equality boundaries and every access-rule outcome.
There are 58 concrete execution samples.

## Verification gates

`tests/test_golden.py` requires each candidate to:

1. Parse and type-check under its frozen specification.
2. Return `proved` with a non-null certificate.
3. Pass independent certificate checking against that exact specification and candidate.
4. Report `domain_nonempty` for every public function, with a separately validated fixture witness.
5. Execute all examples with exact output type and value.

Four rejection cases replace the final body of identity, minimum, grant or access_rule with an
incorrect constant while preserving the specification. Each must return `counterexample`,
without an acceptance certificate. The test replays the reported input through the interpreter,
checks the precondition and independently observes a false postcondition.

These examples exercise the implementation; they do not establish universal correctness by
sampling. Universal acceptance for this fragment depends on the separate certificate checker.

## Recorded development evidence

- TDD RED: before fixture creation, the actual command
  `.venv/bin/python -m pytest tests/test_golden.py -q` exited 2 because `llmlang.core`
  did not yet exist. The acceptance and rejection tests were already written.
- Intermediate check: after the parser and interpreter became available, all ten specifications
  and candidates parsed and validated, and all 58 samples executed with the expected exact values.
- TDD GREEN: once the proof implementation became available, the actual command
  `.venv/bin/python -m pytest tests/test_golden.py -q` returned **15 passed in 0.60s**.
  This run includes ten independently checked certificates, all 58 sample executions, all four
  counterexample replays and the corpus inventory check. It is a component result; broader release
  verification is recorded separately in the final integration evidence.
