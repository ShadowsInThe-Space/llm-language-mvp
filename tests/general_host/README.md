# General web host acceptance

This fixture belongs to the v0.7.0 Web Preview source. Once the release is
available in [GitHub Releases](https://github.com/ShadowsInThe-Space/llm-language-mvp/releases),
use `git checkout v0.7.0` before installing and building it. This guide does not
claim that publication has occurred.

This disposable host imports the generated history and tasks applications without
editing their output. The `/history` and `/tasks` pages use their corresponding
`/api/history` and `/api/tasks` POST routes. Routes receive the real local D1
binding and allowed origin from trusted Cloudflare host configuration.

The target retains Node 24.19.0, Vinext 1.0.0-beta.5, Vite 8.0.13 and React
19.2.6. Supporting package versions follow the
[official beta.5 source and lockfile](https://github.com/cloudflare/vinext/tree/vinext%401.0.0-beta.5/examples/app-router-cloudflare).
Its CLI builds with `vinext build`; Wrangler serves the resulting
`dist/server/wrangler.json` using local workerd. The package manifest pins each
direct dependency. Acceptance also requires a committed npm lockfile, captured
on the CI runner when local package network access is unavailable.

Run from the repository root with its Python environment installed:

```sh
PYTHONPATH=src python scripts/prepare_general_host.py
cd tests/general_host
npm ci --ignore-scripts
npm run test:config
npm run build
npx --no-install playwright install --with-deps chromium firefox webkit
cd ../..
python scripts/check_general_client_bundle.py --client-dir tests/general_host/dist/client --program-dir tests/general_host/generated
python scripts/run_general_host_acceptance.py --host-dir tests/general_host
```

Preparation refuses to overwrite existing generated output. The acceptance
runner requires a fresh `.acceptance-state` directory, applies both generated
schemas, runs D1 checks, stops the complete server process group, then restarts
the same built worker with the same state and checks persistence before browser
tests. It does not delete prior state. Use a fresh disposable fixture checkout
for another complete run.

`node check-conditional-insert.mjs` uses the same local Wrangler configuration
and persistence directory to probe a conditional `INSERT … SELECT` in test-only
tables. It checks the individual mutation counts for initial success, full
capacity across actors, blocked policy, and independent replay exclusion. The
replay case uses a separate enabled scope with capacity two and one confirmed
reservation, so one slot remains available when the repeated actor/request is
rejected. This isolates the replay predicate from the capacity and policy gates.
The final read verifies both stored outcomes and the remaining replay capacity. Multiple statements in one CLI invocation do not establish a
batch transaction; this probe does not establish concurrent booking or the
later M4 reservation/idempotence contract.

For manual local inspection after building:

```sh
cd tests/general_host
npm run db:apply
npm run start
```

The default origin is `http://127.0.0.1:8787`. Host-only environment settings
`LLMLANG_GENERAL_BASE_URL` and `LLMLANG_D1_STATE` select a local HTTP origin and
persistence directory. Set the same settings for schema application and serving.
`LLMLANG_GENERAL_EXTERNAL_SERVER=1` tells Playwright to use an already running
server. Browser callers cannot supply those settings. No Cloudflare account,
token, deployed database or external Sites service is required.

Only built client assets are public; `generated/` contains private server IR and
is never configured as an asset directory. The bundle check inspects built
JavaScript and decoded external source maps with a static filename/string-marker
audit, deriving exact SQL and Pure entry markers from generated server artifacts.
Inline maps are rejected. This checks the inspected build, not semantic isolation
against arbitrary encoding or split strings, or host authentication.
Browser reports are written to `evidence/`, traces
and screenshots to `test-results/`, and server output to `host-acceptance.log`.
Successful execution demonstrates the pinned local host and local D1 provider;
it does not demonstrate deployment or a remote Cloudflare database.

The [CI run 37980399274](https://github.com/ShadowsInThe-Space/llm-language-mvp/actions/runs/37980399274)
at `6b8d4a09f03001f09cea9c4bdf3f0de928a849c3` passed all 33
Chromium/Firefox/WebKit tests in 47 seconds, the
26-request local D1 seed/CAS sequence, five read checks after process restart,
and built-client inspection of ten JavaScript files and seven external maps.
The conditional-insert probe also passed mutation counts `1,0,0,0,1,0`, including
replay rejection with spare capacity. The same run passed both Python baselines,
Ruff, strict Mypy, generated TypeScript, six React checks and both installed-wheel
checks. Release publication remains a separate step whose status is recorded in
GitHub Releases.
