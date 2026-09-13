# Try LLM-Language

[Back to the overview](../README.md)

You can try the compiler and proof demo without an AI account or API key.
The examples are included; no new model request is made.

## 1. Install

Requirements: Git and Python 3.12 or newer. Installation downloads Python packages.
Run these commands in a terminal on Linux or macOS:

```bash
git clone https://github.com/ShadowsInThe-Space/llm-language-mvp.git
cd llm-language-mvp
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
The repository does not yet include a standalone one-command web host.
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

## For contributors

Install development tools with `python -m pip install -e '.[dev]'`.
The full test suite also needs Node.js 24 for its SQLite runtime tests.
Then run `python -m pytest -q` and `python -m ruff check src tests scripts`.
See [CONTRIBUTING.md](../CONTRIBUTING.md) for how to help.

## Verification of these instructions

On September 13, 2026, the compile, integrity-check and proof-demo commands were
run on Linux using the existing Python 3.12 environment. A fresh internet-based
package installation and the Windows instructions were not tested.
