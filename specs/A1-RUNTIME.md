# Portable pure A1 runtime

`llmlang.a1.runtime.emit_typescript_runtime(module, entries)` emits a standalone
TypeScript module exporting `invokePure(name, args)` and `RUNTIME_VERSION`.
The version is `a1-pure-runtime-v1` and participates in the general web program's
build binding. The historical A1 Node target and frozen P0/W1/W2 targets are
unchanged.

`validate_runtime_module(module, entries=())` applies the same admission checks
without emitting code. The application compiler uses it for executable libraries.
Admission checks the complete module, including unused functions and constants;
the explicit, unique entry tuple must be a subset of its checked entrypoints.
An unlisted name cannot be invoked, even if it is an internal callee. Function,
parameter, field, and nominal type names remain data held in Maps or own fields.

The runtime supports all existing A1 operations: constants, record construction
and projection, variant construction and matching, list construction, append and
index, bounded map and fold, UTF-8 byte length, Unicode scalar count and prefix,
text concatenation, Nat refinement, addition, and calls. Its value monitor checks
Unit, Bool, Int, Nat, capacity-bounded Text and List, nominal records and variants,
Option, and Result. Argument arity and every argument, instruction result, and
function result are checked. Composite values are cloned; extra fields, incorrect
nominal identities, wrong list capacities, and invalid nested payloads fail closed.

This portable subprofile admits only exact JavaScript safe integers, including
capacities and integer literals throughout the module. Arithmetic rejects unsafe
results before they escape. Text uses Unicode scalar values, excludes NUL, and
measures capacity in UTF-8 bytes with `TextEncoder`. Lone surrogates fail instead
of being replaced during encoding. Typed literals receive recursive validation
before emission; a constant cannot masquerade as an SSA reference. Record and
variant operands are also checked before projection or matching.

## Resource contract

Each invocation receives fresh, shared budgets across all internal calls and
callbacks. Producer limits remain effective and cannot exceed these host ceilings:

| Resource | Ceiling |
| --- | ---: |
| Instructions (`max_steps`) | 100,000 |
| Map/fold input elements (`max_collection_expansion`) | 10,000 |
| Call depth (`max_call_depth`, root depth zero) | 64 |
| Recursive value depth | 64 |
| Aggregate value-monitor visits | 100,000 |
| One text value, UTF-8 bytes | 1,048,576 |
| Aggregate text validation work, UTF-8 bytes | 4,194,304 |
| Canonical source module bytes | 131,072 |
| Module functions | 64 |
| Source structure nodes / depth | 20,000 / 128 |

Text work counts each validation, including repeated argument/result monitoring
and text operation inputs. Budget accounting reserves UTF-16 work before encoding
and charges the remaining UTF-8 bytes afterward. This prevents a small repeated
text operation from consuming unbounded work despite a finite instruction limit.
The source structure guard checks available queue space before adding children.
These runtime ceilings can reject a valid abstract A1 program; they are target
admission and execution restrictions, not changes to the A1 core semantics.

The legacy list append error is `{tag:"Err",value:{tag:"CapacityError"}}`.
The monitor accepts that compact inner value only when the expected nominal type
is `CapacityError` and its declaration has exactly one payload-free
`CapacityError` case. Other variants require their nominal identity. This narrow
compatibility exception preserves measured interpreter append results; it does
not claim full equivalence of arbitrary external legacy argument validation.

The emitted module uses web primitives, contains no Node imports, Buffer, process
access, or dynamic evaluation, and performs no I/O. Tests execute the actual
emitted module in Node's TypeScript stripping mode and compare supported normal
values with the interpreter. They also cover hostile names, malformed values,
unsafe arithmetic, static literal rejection, collection/call/step/text limits,
fresh invocation budgets, and capacity failures. These are measured tests, not a
formal proof of equivalence or host isolation.
