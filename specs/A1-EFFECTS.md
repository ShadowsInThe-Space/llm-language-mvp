# A1-EFFECTS — additive M3 execution boundary

`a1-effects-v1`, checked by `a1-effects-check-v1`, is an additive structural
contract for issue #21. It does not alter `a1-ir-v1`, `a1-check-v1`, A1 evidence,
P0, w1, w2 or pkg1. A successful result has `status="checked"`; it is not an A1
contract proof and does not prove a host implementation or authentication.

## Graph adapter and immutable API

`llmlang.a1.effects.EffectFunction` is a frozen, slotted record:

| Field | Type | Meaning |
| --- | --- | --- |
| `name` | nonempty `str` | Unique static function/action ID |
| `location` | `shared`, `client`, `server` | Execution location |
| `effects` | `frozenset[str]` | Declared conservative effect contract |
| `capabilities` | `frozenset[str]` | Required host authority |
| `calls` | `tuple[str, ...]` | Actual static callees, including callbacks |
| `host_calls` | `tuple[str, ...]` | Actual operations from the closed registry |

Purity is an empty effect set. `pure` is not an effect symbol. Capability
requirements describe authority needed by a function, never authority granted
by the checker. Requirements are separate from ordinary A1 data types.

```python
check_effect_graph(
    functions,
    *, client_entries=(), server_entries=(), limits=EffectLimits(),
) -> EffectCheckResult
```

The checker snapshots the input sequences and accepts immutable graph fields
only. The result contains an ordered tuple of `EffectSummary` records, frozen
`client_reachable`/`server_reachable` sets and a lowercase SHA-256
`semantic_hash`. Each summary contains `name`, `transitive_effects` and
`transitive_capabilities`. `summary(name)` returns it or raises `KeyError`.
`to_dict()` creates a new deterministic report; modifying that report does not
modify the checked result.

The WebIR adapter must independently derive edges and host operations from
every actual typed body/action/query/callback. User-provided summaries or
manifests cannot substitute for this derivation. RPC transport is a client
`network.call` operation and an independently checked server entry; it is not
an ordinary client-to-server call. All emitted client exports must be included
as client entries. The generator must use the same checked immutable graph and
the corresponding typed IR snapshot for partitioning and emission.

## Closed host registry

`a1-host-effects-v1` defines these exact signatures:

| Operation | Effect | Capability | Locations |
| --- | --- | --- | --- |
| `db.read` | `db.read` | `db.read` | server |
| `db.write` | `db.write` | `db.write` | server |
| `network.call` | `network.call` | `network.call` | client, server |
| `clock.read` | `clock.read` | `clock.read` | client, server |

`identity.authenticated` and `identity.admin` are additional server-only
capability requirements, without automatic implication between them or DB
permissions. No wildcard, custom operation or `filesystem.read` is supported.
Adding a host operation requires a reviewed registry version change and its
implementation/target boundary; a candidate cannot redefine an operation as
pure or override its authority/location.

## Rules and bounded checking

1. Names are unique. Symbol sets, reference shapes, locations and entries are
   validated; unknown, duplicate or malformed values fail closed.
2. A shared function has no effects or capabilities. A client function holds no
   DB, authenticated-identity or admin capabilities, even when unused.
3. Host calls require the registry's execution location, declared effect and
   capability. DB requirements cannot be satisfied on the client.
4. Ordinary calls allow shared-to-shared, client-to-client/shared and
   server-to-server/shared only. All callbacks are ordinary edges.
5. The graph is acyclic. An iterative dependency traversal reconstructs a
   conservative transitive summary: the function's declared requirements union
   every callee's transitive requirements. Every call requires the callee's
   complete transitive effect/capability sets to be subsets of the caller's
   declaration. Merely matching direct effects is insufficient.
6. Entry reachability follows actual ordinary edges only; the client and server
   partitions may both contain pure shared functions.

`EffectLimits` defaults to `max_functions=1000`, `max_edges=10000`, and
`max_call_depth=64`. Counts include unused declarations, duplicate call sites
and host sites. Entry-list length cannot exceed `max_functions`. Call depth
counts functions, including the entry itself. Integer bounds are nonnegative,
with positive depth; booleans are rejected. Excessive counts, cycles and depth
fail deterministically; the checker uses no Python recursion for the graph.

## Stable diagnostics

The checker raises `EffectError`, derived from the existing `A1Error`, using
`diagnostic-v1`, `phase="validate"`, absent span/symbol and these codes:

| Code | Meaning |
| --- | --- |
| `E_A1_EFFECT` | Unknown effect/host operation or unmet effect subset |
| `E_A1_CAPABILITY` | Unknown, client-forbidden or unmet authority requirement |
| `E_A1_LOCATION` | Unknown location, impure shared function or illegal boundary |
| `E_A1_BINDING` | Malformed/duplicate static function, reference or entry |
| `E_A1_CONTROL` | Cyclic call graph |
| `E_A1_LIMIT` | Invalid or exceeded explicit structural budget |

Paths use immutable string segments, matching the existing `A1Error` convention:
`("functions", "save", "host_calls", "0")` or `("client_entries", "0")`.
Declaration and edge order determine first failure; unknown set members are
sorted before reporting. Validation phases are shape/local host checks,
ordinary call location/binding checks, entries, then graph/depth/subset checks.
Host location precedes effect and capability checking at a host site. No random
ID, timestamp, absolute path or Python set order affects diagnostics.

## Canonical binding

The hash binds the exact ordered function graph, sorted effect/capability sets,
ordered client/server entry lists, explicit limits, format, checker and registry
version. Canonical JSON uses sorted object keys, ASCII escapes, no insignificant
whitespace and no NaN/Infinity. The SHA-256 input is:

```text
frame("llmlang:a1-effects", format, checker, registry_version, canonical_json)
frame(x...) = concat(u64be(byte_length(x)), utf8(x))
```

Array order is part of the binding because it controls stable diagnostics.
Set insertion order is not. This hash binds the effect graph only: it must be
combined with the full WebIR/core semantic hash and provenance in the target
manifest. A changed pure body must not reuse a previous generated artifact
merely because its effect graph is unchanged. This checker does not accept
producer-supplied certificates or grant `proved` to host contracts.

## Runtime trust boundary

Capabilities are not ordinary A1 values and must never be constructed from
constants, records, forms, request JSON, identity labels or caller-selected
headers. The trusted server adapter owns an out-of-band host context created
after server-side authentication and authorization. It must enforce the
checked action's requirements before execution and enforce resource/operation
scope at the DB adapter. A capability name in this graph is a requirement;
putting the same name in browser data grants nothing.

No capability values enter input/output wire codecs or client code. The graph
checker does not mint host contexts, validate credentials or prove the runtime
adapter's security. Those obligations belong to the integrated WebIR/server
tests, including forged browser identity/admin data and denied DB actions.
