# A1 Generics, Functions and Nat — normative contract

Status: frozen for M2 (`a1-ir-v1`). This document is normative for issue #18.

## Functions and call graph

An A1 function has a stable name, explicit value parameter and result types,
optional explicit type parameters, optional non-negative capacity parameters,
and a body in canonical A1 IR. Overloading, closures, implicit type arguments,
dynamic dispatch and general recursion are forbidden. Every call names its
callee and all generic arguments. The module call graph must be acyclic;
self-edges and cycles are rejected before evaluation or proof generation.

Function references accepted by `bounded_map` and `bounded_fold` are static
callee IDs. Their input and result types must equal the helper's instantiated
callback signature.

## Parameters and Nat

Type parameters range over closed A1 types. Capacity parameters range over
canonical non-negative integers and may occur only in bounded types and loop
bounds. `Nat` is the refinement `{x: Int | x >= 0}`, not an unsigned host
integer. `refine_nat` succeeds only when the checker has reconstructed evidence
for non-negativity; a caller assertion or a successful example execution is not
evidence.

## Deterministic specialization

Only instances reachable from concrete entry functions are materialized. The
worklist starts with sorted entry IDs; each body is scanned in canonical
instruction order; newly discovered instances are keyed by:

`generic-function-id + canonical-type-arguments + decimal-capacity-arguments`.

The key is hashed with the canonical A1 JSON rules. Duplicate keys collapse.
The final instance table is sorted by key, so source declaration order cannot
alter its serialization or hash. Specialization substitutes types and
capacities capture-free and then reruns the ordinary structural checker. No
consumer name or domain type may select a compiler branch.

Expansion fails closed before emitting a partial proof when any configured
limit for instances, substituted nodes, call depth or bounded iterations is
exceeded. Unused generic declarations do not consume the instance budget.

## Required shared map gate

The library declares one generic `map<T,U,N>` implementation. M2 acceptance
must instantiate that same declaration for at least two nominal record types
and two different capacities. The resulting instance IDs must be distinct,
stable and traceable to the shared declaration. Copying the body into either
consumer or adding consumer-specific compiler logic does not pass.

## Verification rules

The checker records rule IDs defined by `A1-VERIFICATION.md` for call-graph
acyclicity, argument substitution, callback compatibility, refinement
introduction, specialization reachability and budget accounting. A certificate
that omits, reorders or alters required evidence is rejected independently.
Preconditions and proven callee summaries are checked at every instantiated
call; an interpreter result never upgrades a call to `proved`.

## Stable diagnostics

| Code | Meaning |
| --- | --- |
| `E_A1_CALL_CYCLE` | recursive or cyclic call graph |
| `E_A1_TYPE_ARGUMENT` | missing, extra or invalid type argument |
| `E_A1_CAPACITY_ARGUMENT` | missing, extra or negative capacity |
| `E_A1_CALLBACK_TYPE` | statically named callback has wrong signature |
| `E_A1_REFINEMENT` | `Nat` introduction lacks reconstructed evidence |
| `E_A1_SPECIALIZATION_LIMIT` | deterministic expansion budget exhausted |
| `E_A1_DYNAMIC_CALL` | dynamic function value or unresolved callee |

Diagnostics use `diagnostic-v1`, identify the phase and canonical source/IR
location, and do not depend on host exception text.

## RED/GREEN acceptance

RED tests precede implementation and cover direct and mutual recursion, wrong
type/capacity arity, negative capacities, wrong map/fold callbacks, unsound Nat
assumptions, deterministic instance ordering, used-only generation, duplicate
collapse and every expansion budget. GREEN additionally executes two domain
consumers through the same generic map at two capacities, checks their distinct
nominal record types, compares reference and target results, mutates instance
and refinement evidence, and verifies P0/w1/w2/pkg1 compatibility.
