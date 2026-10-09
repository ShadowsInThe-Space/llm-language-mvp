# General web server boundary (M3)

Status: generated TypeScript dispatcher with host-injected D1 capability. This
module does not deploy an application, configure credentials, implement identity
or prove Cloudflare D1 execution. Actual SQLite query behavior is verified
separately by `test_general_web_queries.py`.

`emit_server(WebProgram)` always calls `validate_program` before producing a
standalone module. It imports the versioned scalar/nominal codec runtime from
`./codecs`. Action names, SQL, binding descriptors, projected result columns,
cardinality and input/output codec descriptors come only from checked contracts.
User input cannot choose SQL, a database, an origin policy or a capability.

## Trusted host integration

The module exports `createDispatcher(db, hostOptions)`, returning an async
`(Request) => Response` function. The database capability is injected only into
the closure. It requires a D1-shaped `prepare(sql).bind(...values).all()` API
whose result contains `success: true` and a result-row array. The host must
install the generated checked schema and provide the actual binding.

`hostOptions.allowedOrigin` is mandatory: an exact canonical HTTP(S) origin,
without a trailing slash or path. It is captured at dispatcher creation. All
requests require an exactly matching `Origin` header, POST, and
`application/json` (an explicit UTF-8 charset is accepted). Compressed request
bodies are not supported. There is no wildcard origin default.

Public actions need no host identity callback. Authenticated/admin actions
require `hostOptions.authorize(actionName, request, requirement)` to return
exactly `true`; absence, denial and exceptions fail closed with HTTP 403.
The callback is trusted host policy and must obtain identity from trusted
headers/cookies/session infrastructure. The generated dispatcher never derives
identity from request data. The callback receives a request with its body already
consumed; it should use trusted request metadata. Roles and their verification
remain the host's responsibility.

## Request boundary

The only request envelope is `{ "action": "declaredName", "input": ... }`.
Unknown envelope fields and action names fail. Parameterized actions use the
nominal record wire codec named `<action>Input`, with an exact `fields` object.
Actions without parameters accept only `{}` as input.

Body reading uses `ReadableStream.getReader()` and a fixed byte budget before
concatenation or decoding; it never calls unbounded `request.text()` or
`request.json()`. The default maximum is 32768 bytes. Trusted host options may
lower `maxRequestBytes` to 1–32768 and set `bodyTimeoutMs` to 1–30000 (default
5000). Declared Content-Length is checked when present, and actual streamed
bytes are always counted. Read count is also bounded, preventing arbitrarily
many empty chunks. A timeout ends the response without awaiting stream
cancellation. Strict UTF-8/JSON parsing rejects duplicate keys, malformed JSON,
excessive depth/nodes and bare numeric tokens.

Origin, method and content-type/encoding rejection first disposes the body under
the same byte, read-count and time bounds. Small bodies are read to EOF without
JSON decoding, authorization, pure evaluation or database work before the error
response. Overflow, timeout or invalid declared length instead triggers
best-effort cancellation without awaiting its completion. A cancellation that
throws, rejects or never settles cannot delay the rejection. The original
403/405/415 status is preserved even if body disposition fails; ordinary declared
length rejection retains its 400/413 status. This closes the unread-body transport
boundary, but does not by itself prove upstream keepalive behavior in a provider.

After selecting a closed action, codecs validate the entire nominal input.
Int/Nat arrive as canonical decimal strings and decode into exact safe native
integers. Positional binding types are validated again, Bool binds as 0/1, and
an incrementable maximum revision fails before a database call. Authorization
also precedes database access. SQL is static and contains no runtime values.

## Executable pure parameter transforms

Actions may declare checked `ParamTransform(param, function, args)` nodes bound
to exported functions in the canonical A1 pure library. The program checker
validates their scalar signatures, original input names and unique replacement
targets. Static metadata identifies only the checked transforms. A server with
transforms imports `invokePure` from `./a1-pure`; a server without transforms has
no such import, including when an unused provenance-only pure library exists.
The pure IR and runtime are server artifacts and are never emitted to the client.

The dispatcher first decodes the original nominal input and authorizes protected
actions through trusted host policy. It freezes a separate original parameter
snapshot. Every function reads its arguments from that snapshot; transformations
cannot read earlier replacement values. All functions must complete before any
replacements are applied. The resulting parameter map then passes the usual
scalar binding validation, including expected-revision incrementability checks,
before database preparation. This makes replacement semantics simultaneous and
prevents premature rejection of an original value that a valid transform replaces.

A1 runtime failures, budget exhaustion, unsafe arithmetic and invalid transformed
binding values return generic HTTP 422 `InvalidInput` with zero database calls.
Runtime details are never included in the response. Pure evaluation has its own
per-invocation bounded execution/collection/call budgets, and it receives no
request, identity, database or network capability. Authorization failures avoid
pure evaluation as well as database calls.

## Results and errors

Successful HTTP 200 bodies are directly encoded using the checked action's
output codec. Rows are nominal `<action>Row` records; unique selects return
Option, bounded lists return a wire array, and successful conditional updates
return Some(row). Int/Nat fields encode as canonical decimal strings.

Projected database rows require exact own field names. Null, unexpected fields,
wrong scalar storage types, unsafe integers, capacity overflow and Bool values
other than numeric 0/1 fail closed. Result cardinality is checked. Fields are
built with `Object.create(null)`; action dispatch uses a Map, so valid names
such as `__proto__` cannot alter object prototypes.

A conditional update returning zero rows produces HTTP 409 and
`{"error":"ConditionNotMet"}`. A missing key and stale revision deliberately
share that outcome. An absent unique select instead returns None with HTTP 200.
No cross-statement batch or rollback behavior is claimed.

Errors contain only `{"error":"<fixed label>"}`. Transport/input failures use
400/403/405/408/413/415/422; authorization uses 403; provider failures and invalid
rows use 500 `ServiceUnavailable`. SQL, provider exceptions, identity-provider
exceptions and input values are never reflected. Responses include JSON content
type, `no-store`, exact allowed-origin CORS, `Vary: Origin`, and `nosniff`.

## Evidence and limits

`test_general_web_server.py` executes emitted TypeScript through Node's native
`stripTypeScriptTypes`. The harness provides a deliberately minimal D1-shaped
test double. It checks transport and envelope validation before database calls,
stream byte/time bounds, trusted host authorization, nominal wire outputs,
bounded early-rejection body disposal, original rejection status preservation,
small-body EOF and nonawaited throwing/rejecting/nonsettling cancellation,
safe positional bindings, invalid provider rows, generic errors, conflict
outcomes and prototype-sensitive names. Transform tests additionally run the
actual emitted A1 pure runtime, check changed positional SQL bindings and
original-argument replacement semantics, and require zero database calls after
runtime failures. The test double is HTTP/codec boundary
evidence only. It is not a SQL engine, D1 emulator or proof of provider atomicity.

Real provider acceptance, account binding, schema installation, deployment,
host session policy, production resource limits and D1-specific operational
behavior remain explicit integration work. The dispatcher executes one query
per request and never simulates a multi-statement transaction.
