# General web compiler — v0.7.0 Web Preview

This guide describes the v0.7.0 Web Preview source. Publication is a separate
release step; [GitHub Releases](https://github.com/ShadowsInThe-Space/llm-language-mvp/releases)
is authoritative for availability. Once that release is published, use
`git checkout v0.7.0` and install its source before following these commands.
W1, W2, pkg1 and their historical generated fixtures remain unchanged.
See the [release notes](releases/v0.7.0.md) for evidence and publication status.

The historical [assurance document](ASSURANCE.md) is frozen with the P0
compatibility baseline. Its mathematical statement and unsupported-language
list describe P0, not the later A1 or general web profiles. A1 has its own
[acceptance boundary](../specs/A1-ACCEPTANCE.md), including bounded text and lists.
M3 checks types, effects, capabilities and bounded runtime values; these checks
and host tests do not prove the complete website or host correct.

## Compile both applications

After installing the repository development dependencies, run:

```sh
python -m llmlang compile-general-web examples/web/general/history.webapp \
  --library common=examples/web/general/common.webuilib \
  --pure-library helpers=examples/web/general/helpers.a1src --out build/general-history
python -m llmlang compile-general-web examples/web/general/tasks.webapp \
  --library common=examples/web/general/common.webuilib \
  --pure-library helpers=examples/web/general/helpers.a1src --out build/general-tasks
```

`python -m llmlang.web.general` exposes the same source/library/output arguments
without importing the P0 solver. Compilation makes no model or network request.
An existing output directory is refused; choose a new destination for each build.

Each build contains a generic React component, the typed server dispatcher,
browser/worker wire codecs, generated SQL, canonical source and explicit library
snapshots, source positions, checked program IR and an integrity manifest.
`check_build` recompiles the supplied source snapshot and compares every artifact;
an offered manifest hash alone does not establish the binding.

The two applications consume the same `common.webuilib` editor component
and execute `helpers.a1src` on the server before binding write queries. The shared
`preserve_text` entry preserves every admitted text value exactly, including
multiline Unicode and empty text, up to 4096 UTF-8 bytes. The planner uses it for
both create and update. This deliberately neutral helper demonstrates checked
library invocation without changing stored user data; nontrivial transformations
are separately exercised by the runtime and server regression suites.
Transform arguments refer to the original decoded inputs, with replacements
applied together. Parameter and result types must match exactly. Pure execution
has checked input/output values and bounded budgets; failure prevents the query.
The generated `a1-pure.ts` and its library snapshot are bound by the manifest and
are not imported by the generated client component.

History stores text entries. The planner adds completion, priority and a revision
checked atomic update. IDs are explicitly entered in this first UI. Update uses
the revision displayed by the selected record. The forms never automatically
save initial values. Clear removes local displayed results without deleting rows.
Lists deliberately return one row per page so even maximally escaped 4096-byte
text fits the bounded wire response. Generic keyset pagination makes older records
reachable, with stable ordering and a primary-key tie breaker. A successful load
increments a visible local confirmation counter. Clear resets display and paging
state without sending a request or deleting records.
Previous-page navigation retains at most 32 cursors and 262144 serialized
UTF-8 bytes per list. Next continues beyond that window; Previous stops at its
oldest retained cursor. Clear resets navigation to the first page. Load refreshes
the current confirmed page. Page changes leave confirmed detail selection visible
until another selection or explicit detail Clear.

## Host contract

Import the generated `App.tsx` into the React/Vinext host and mount its dispatcher
at the configured same-origin endpoint (default `/api/general`). The host supplies
the actual D1 binding and allowed origin to `createDispatcher`; neither is read
from request data. Apply `schema.sql` only to a fresh disposable database during
acceptance. It creates tables; it is not a migration plan for existing data.
Keep the compiler output directory as server/build input. It includes SQL and the
full checked program/library snapshots; publish only the host's built client
assets, never expose the whole compiler output as a static public directory.

Authenticated/admin actions require an actual trusted host authorization adapter.
Both examples are public shared-data demonstrations, not tenant-isolated apps.
The dispatcher validates method, origin, content type, streamed byte/time budgets,
action names, nominal inputs, SQL bindings and every returned database value.
Integers cross the wire as canonical decimal strings. A conditional update with
no matching revision returns `ConditionNotMet`; a zero-row result does not imply
that a multi-statement D1 batch rolled back.

The generated modules are source outputs. `tests/general_host` provides a pinned
Vinext/Cloudflare acceptance host that imports them unchanged. It runs the built
worker against Cloudflare's local D1 implementation; the historical Sites host and
deployment remain separate. A source build or strict TypeScript check alone does
not demonstrate browser or D1 behavior.

## Acceptance evidence and release status

The [CI run 37980399274](https://github.com/ShadowsInThe-Space/llm-language-mvp/actions/runs/37980399274)
at `6b8d4a09f03001f09cea9c4bdf3f0de928a849c3` passed the pinned Vinext build and
all 33 Playwright tests across Chromium, Firefox and WebKit in 47 seconds.
It also passed the actual local
D1 seed/CAS sequence of 26 requests, five read checks after a complete process
restart, and the separate conditional-insert probe. The probe returned mutation
counts `1,0,0,0,1,0`, including replay rejection with a spare slot. Built-client
inspection covered ten JavaScript files and seven external source maps.

The same run passed 706 tests plus 260 subtests on each of Python 3.12 and 3.13,
Ruff, strict Mypy over 51 files, generated TypeScript, six React checks, and
isolated installed-wheel checks for both applications. These are results for
that exact commit. Release review, completed issue evidence, the exact milestone
gate, the final merge and publication remain separate requirements. Passing CI
does not claim publication or a cloud deployment.

Current tests include actual SQLite queries and Node execution of generated
TypeScript/controller boundaries with a controlled D1-shaped double. The latter
is explicitly not D1 provider evidence; the pinned host exercises the actual
local D1 provider separately. Built-client inspection is a static filename and
string-marker audit of the inspected artifacts and decoded external source maps.
It derives exact SQL and Pure entry markers from generated server artifacts;
inline maps are rejected. It does not prove semantic isolation against arbitrary
encoding or split strings, host authentication, or a whole website's correctness.
