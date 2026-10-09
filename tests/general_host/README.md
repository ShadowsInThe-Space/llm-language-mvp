# General web host acceptance

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
JavaScript and source maps. Browser reports are written to `evidence/`, traces
and screenshots to `test-results/`, and server output to `host-acceptance.log`.
Successful execution demonstrates the pinned local host and local D1 provider;
it does not demonstrate deployment or a remote Cloudflare database.
