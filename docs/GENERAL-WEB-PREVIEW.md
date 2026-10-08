# General web compiler — M3 work branch

This is an implementation preview on `milestone/m3`, not a released M3 package.
W1, W2, pkg1 and their historical generated fixtures remain unchanged.

## Compile both applications

After installing the repository development dependencies, run:

```sh
python -m llmlang compile-general-web examples/web/general/history.webapp \
  --library common=examples/web/general/common.webuilib --out build/general-history
python -m llmlang compile-general-web examples/web/general/tasks.webapp \
  --library common=examples/web/general/common.webuilib --out build/general-tasks
```

`python -m llmlang.web.general` exposes the same source/library/output arguments
without importing the P0 solver. Compilation makes no model or network request.
An existing output directory is refused; choose a new destination for each build.

Each build contains a generic React component, the typed server dispatcher,
browser/worker wire codecs, generated SQL, canonical source and explicit library
snapshots, source positions, checked program IR and an integrity manifest.
`check_build` recompiles the supplied source snapshot and compares every artifact;
an offered manifest hash alone does not establish the binding.

The two applications consume the same `common.webuilib` editor/browser components.
History stores text entries. The planner adds completion, priority and a revision
checked atomic update. IDs are explicitly entered in this first UI. Update uses
the revision displayed by the selected record. The forms never automatically
save initial values. Clear removes local displayed results without deleting rows.
Lists deliberately return at most eight rows so even maximally escaped legal
text fits the bounded wire response. This preview does not implement pagination.

## Host contract

Import the generated `App.tsx` into the React/Vinext host and mount its dispatcher
at the configured same-origin endpoint (default `/api/general`). The host supplies
the actual D1 binding and allowed origin to `createDispatcher`; neither is read
from request data. Apply `schema.sql` only to a fresh disposable database during
acceptance. It creates tables; it is not a migration plan for existing data.

Authenticated/admin actions require an actual trusted host authorization adapter.
Both examples are public shared-data demonstrations, not tenant-isolated apps.
The dispatcher validates method, origin, content type, streamed byte/time budgets,
action names, nominal inputs, SQL bindings and every returned database value.
Integers cross the wire as canonical decimal strings. A conditional update with
no matching revision returns `ConditionNotMet`; a zero-row result does not imply
that a multi-statement D1 batch rolled back.

The generated modules are source outputs, not a complete pinned Vinext project.
The historical host starter and deployment are maintained separately. A source
build or strict TypeScript check does not demonstrate browser or D1 behavior.

## What remains before M3 acceptance

- Bind executable pure A1 library calls into the general application path. The
  optional `pure_library` field currently records independently checked provenance;
  it does not execute a pure library from a UI/query action.
- Run a clean build in the pinned Vinext host with generated modules unchanged.
- Run actual D1 conditional-write/concurrency and persistence/restart tests.
- Exercise both applications in the supported browser matrix, including keyboard,
  focus, labels, Unicode, failures, stale selections, reload and clear behavior.
- Inspect built client modules and source maps for server capability separation.
- Complete independent package review, release documentation, installed-wheel
  acceptance and the exact milestone gate before closing #21, #22 or #32.

Current tests include actual SQLite queries and Node execution of generated
TypeScript/controller boundaries with a controlled D1-shaped double. The latter
is explicitly not D1 provider evidence. There is no whole-website formal proof.
