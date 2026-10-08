# General web client target (M3 preview)

`llmlang.web.general.client.emit_client(WebProgram) -> str` emits a React TSX
module. Every call validates the complete immutable source program first; a
previous checked snapshot or arbitrary descriptor is not an accepted input.
The caller supplies the shared generated `codecs.ts` alongside this module.

Emission is deterministic. Client metadata contains the program name/title,
expanded checked views, and only input/output codec descriptors for actions used
by those views. It does not include SQL, query ASTs, schema definitions, unused
actions, authorization requirements, capabilities, server bindings, or a pure
library's executable code. Values deliberately declared as labels, input choices,
or projected public fields remain public. The UI renderer has no application
name, table name, history, or tasks branches.

## Components and controls

The default export `GeneralApp` accepts an optional `endpoint` prop, defaulting
to `/api/general`. The endpoint is a same-origin absolute path; cross-origin
URLs, protocol-relative paths, backslashes, whitespace, and fragments are
rejected. It is host configuration, not a user-entered RPC action. Actions and
view references come from the checked static descriptor map.

Form views bind all declared inputs. Labels use `htmlFor` with stable IDs derived
from program, view, and parameter names. Text uses a controlled text input,
Nat/Int use text inputs with numeric input mode, Bool uses a checkbox, and a
select uses its explicit checked choices. Integer inputs stay as strings until
strict scalar decoding; `01`, `+1`, `-0`, decimal fractions, negative Nat values,
and values outside the exact target range are rejected before fetch. Integer
wire values are canonical decimal strings, never JSON numbers. Confirmed form
values are displayed using field labels rather than codec record metadata.

List views expose a Load button and projected columns. Selecting a row binds the
checked key column to the selected detail view's single checked parameter.
Details display only their declared columns. Each view uses its declared loading,
error, empty, and success text with status/alert roles and loading busy state.
A zero-row list and a `None` detail result are empty outcomes.

Clear removes only that view's local confirmed display and status. It sends no
request and performs no database operation. Form draft inputs remain available.
The client does not implicitly refresh a list after a form submit; Load is an
explicit user action.

## Transport and state

The exported `createClientController(endpoint?, fetcher?)` owns the same state
machine used by React. It exposes `getState`, `subscribe`, `submitForm`,
`loadList`, `selectRow`, `clear`, and `dispose`. State snapshots are defensive
clones. The plain TypeScript runtime is delimited by `BEGIN GENERAL CLIENT
RUNTIME` / `END GENERAL CLIENT RUNTIME` comments for focused executable tests;
this is the actual controller, not a second simulated implementation.

Requests are POST JSON `{action, input}`. Nonempty inputs use their nominal
checked record; zero-parameter list input is exactly `{}`. Encoding validates
closed fields, record identity, text capacities, scalar types, and integer
range. The controller uses same-origin credentials, rejects redirects, requests
no cache, and does not add capability tokens or authorization fields to bodies.
Server identity/authentication remains the host's responsibility.

A successful HTTP response is the direct checked wire codec value. Failed HTTP
responses have exactly `{error: string}`. The UI reports its local declared
error text and does not display remote error bodies. Successful and failed JSON
responses are parsed by the bounded shared codec parser, including duplicate-key
rejection and rejection of numeric wire literals. Requests and streamed responses
are capped at 32768 bytes; response reads and fetch have a ten-second abort bound.
Successful response content type must be JSON. Only decoded successful values
replace confirmed data. Input, HTTP, transport, content-type, response-size, or
codec failures preserve the previous confirmed value and report error state.

Every request gets a per-view revision and abort controller. A newer selection,
Clear, or disposal invalidates older work. A stale response cannot change status
or confirmed data even when a transport ignores abort. Disposal invalidates
pending revisions; subscribing again activates the controller, allowing React's
development effect setup/cleanup cycle without reviving stale work.

## Verification and limits

`tests/test_general_web_client.py` checks deterministic emission, two unrelated
table/field models, revalidation, and isolation of schema/query-only secrets.
It extracts the actual TypeScript controller, supplies the actual shared codec
runtime, and executes it with Node's TypeScript support. Assertions cover save,
list load, row selection, canonical integers, loading/error/empty/success,
confirmed value preservation, malformed/duplicate/numeric/oversized responses,
clear without a request, abort, and ignored stale selection responses.

This evidence is controller execution with standard web `Response` and a test
fetcher. It is not React DOM interaction, browser accessibility verification,
a pinned Vinext production build, or a Cloudflare D1 deployment. Those are
separate integration gates; no local mock is presented as their equivalent.
