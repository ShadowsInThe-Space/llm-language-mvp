# Contributing

Thanks for taking a look at this early compiler project.
Start with the [quickstart](docs/QUICKSTART.md) and the [scope explained in the README](README.md).

## Useful first contributions

- Try the quickstart and report the exact step that fails, your OS and Python version.
- Improve English documentation while preserving the stated proof boundaries.
- Suggest a small `.llapp` example using the existing w1 or w2 language.
- Report a compiler bug with the smallest source program that reproduces it.

For language or architecture changes, open a proposal before implementing them.
Libraries, general data structures and booking workflows are planned, not available.

## Development

Use Python 3.12+ and Node.js 24, then install with `python -m pip install -e '.[dev]'`.

```bash
python -m pytest -q
python -m ruff check src tests scripts
python -m mypy --no-incremental src
```

For a bug fix, begin with a failing regression test, make the smallest fix,
and rerun the relevant checks. Tests should exercise behavior.
Record changes to language rules in the corresponding specification and `Log.md`.
Change the compiler or source program rather than editing generated app files by hand.

A pull request should explain the problem, the change, checks actually run,
and any remaining limitation. Do not describe the generated website as formally proven.
Please avoid including credentials, private user data or production database dumps.
