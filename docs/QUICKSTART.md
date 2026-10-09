# Try LLM-Language

[Back to the overview](../README.md)

You can try the compiler and proof demo without an AI account or API key.
The examples are included; no new model request is made.
These instructions target v0.7.0 Web Preview, including the compatible historical
W2 and P0 examples. [GitHub Releases](https://github.com/ShadowsInThe-Space/llm-language-mvp/releases)
is authoritative for publication: use the tag below once the release exists.
Until then, substitute the published `v0.6.0` tag and use steps 1–5; general web
applications require the v0.7.0 source.

## 1. Install

Requirements: Git and Python 3.12 or newer. Installation downloads Python packages.
Run these commands in a terminal on Linux or macOS:

```bash
git clone https://github.com/ShadowsInThe-Space/llm-language-mvp.git
cd llm-language-mvp
git checkout v0.7.0
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

On Windows, use `py -3.12 -m venv .venv` and activate it in PowerShell with
`.venv\Scripts\Activate.ps1`, then run the same `python -m pip install -e .` command.
The Windows steps have not been tested in this session.

## 2. Turn a blueprint into website source code

Open [the 16-line example](../examples/web/hello-history.llapp). It describes
text storage, save/load buttons, a display, and a button that clears only the display.

From the repository root:

```bash
python -m llmlang compile-web examples/web/hello-history.llapp --out build/my-first-webapp
```

Expected result: a JSON report containing `"status": "compiled"` and `"profile": "w2"`.
Inspect the generated files:

| File | What it does |
| --- | --- |
| `app/page.tsx` | The page and its buttons |
| `lib/w1-server.ts` | Server operations, including the w2 history behavior |
| `db/schema.ts` | The database table definitions |
| `llmlang/source.llapp` | A normalized copy of your blueprint |
| `llmlang/manifest.json` | File hashes and compiler information |

**This command generates source files. It does not start a website or create a database.**
The generated app needs the Vinext/React/D1 host integration described in the
[deployment guide (German)](W1-GUIDE.md#zielbuild-und-datenbank).
This historical W2 walkthrough does not start a host. The v0.7.0 source includes
a pinned local acceptance host with separate generation, build and database
setup steps; it does not replace the historical W2 deployment.
You can view the previously deployed [example website](https://hello-ai-world.adaptiveaisolutions.chatgpt.site);
its access settings may require the owner's permission.

To run compilation again, choose a different empty output directory.
The compiler deliberately refuses to overwrite a directory containing files.

## 3. Check the generated files

```bash
python -c "from llmlang.web.build import verify_build; import sys; ok = verify_build('build/my-first-webapp'); print('Generated files match the compiler:', ok); sys.exit(0 if ok else 1)"
```

Expected: `Generated files match the compiler: True`.
This checks that every generated file matches a fresh compilation. It is an
integrity check, not a mathematical proof of the website.

## 4. Try the separate proof-and-repair demo

```bash
python scripts/demo.py
```

Expected output includes:

```text
Hello World
Definition of Done passed: 10 golden programs, agent Hello World, agent repair.
```

This checks ten small calculation examples and replays saved agent responses:
an incorrect program is rejected, then a repaired program is accepted.
Proof evidence is written to `build/demo/`. This is a reproducible replay,
not a live AI conversation. See [proof boundaries (German)](ASSURANCE.md).

## 5. Try local shared libraries (Linux)

```bash
python scripts/demo_pkg1.py
```

This verifies two distinct programs sharing one transitive dependency, runs
them, and checks that a library change invalidates both old locks and proofs.
It uses temporary copies and leaves the example sources unchanged.
See [the pkg1 guide](PKG1-GUIDE.md) for individual commands and limitations.
Package commands are currently validated on Linux only.

## 6. Compile the general web applications

On the v0.7.0 checkout installed in step 1:

```bash
python -m llmlang compile-general-web examples/web/general/history.webapp \
  --library common=examples/web/general/common.webuilib \
  --pure-library helpers=examples/web/general/helpers.a1src --out build/general-history
python -m llmlang compile-general-web examples/web/general/tasks.webapp \
  --library common=examples/web/general/common.webuilib \
  --pure-library helpers=examples/web/general/helpers.a1src --out build/general-tasks
```

Choose fresh output directories. These commands generate checked React, server,
codec, schema and library artifacts; they do not start a website. Both examples
share a UI library and a server-side A1 helper. Textareas preserve admitted
multiline Unicode text up to 4096 UTF-8 bytes, and typed keyset pages reach older
records. See the [general web guide](GENERAL-WEB-PREVIEW.md) for contracts and
the [pinned host instructions](../tests/general_host/README.md) for building and
running both examples with local D1. Publish only built client assets, never the
whole compiler output directory.

The pinned local host has passed all 33 browser tests and actual D1/restart
checks, and complete package CI passed against the commit listed below.
Publication is a separate release step. Check the
[release notes](releases/v0.7.0.md) for evidence and publication status;
successful compilation alone does not establish browser or D1 behavior.

## For contributors

Install development tools with `python -m pip install -e '.[dev]'`.
The full test suite also needs Node.js 24 for its SQLite runtime tests. The M3
host pins Node 24.19.0 and its JavaScript dependencies separately.
Then run `python -m pytest -q` and `python -m ruff check src tests scripts`.
See [CONTRIBUTING.md](../CONTRIBUTING.md) for how to help.

## Verification of these instructions

The historical W2 compile, integrity-check and proof-demo walkthrough was run
on September 13, 2026, on Linux using the existing Python 3.12 environment.
That dated walkthrough is not M3 host acceptance. The
[CI run 37980399274](https://github.com/ShadowsInThe-Space/llm-language-mvp/actions/runs/37980399274)
at `6b8d4a09f03001f09cea9c4bdf3f0de928a849c3` passed 706 tests plus 260 subtests
on each supported Python version, code/type checks, generated TypeScript,
React and installed-wheel checks, and all 33 browser tests in Chromium,
Firefox and WebKit with local D1 and process-restart checks. This documentation
update does not claim a fresh internet-based installation or Windows verification.
