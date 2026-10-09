"""Strictly typecheck both generated example targets against pinned TS/React types.

This is compile-time evidence only; it does not run Vinext, a browser or D1.
"""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from llmlang.web.general.build import compile_source, write_build


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--toolchain", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    examples = root / "examples/web/general"
    libraries = {"common": (examples / "common.webuilib").read_text(encoding="utf-8")}
    pure = {"helpers": (examples / "helpers.a1src").read_text(encoding="utf-8")}
    toolchain = args.toolchain.resolve()
    tsc = toolchain / "node_modules/.bin/tsc"
    with tempfile.TemporaryDirectory(prefix="generated-", dir=toolchain) as directory:
        for name in ("history", "tasks"):
            source = (examples / f"{name}.webapp").read_text(encoding="utf-8")
            output = write_build(compile_source(source, library_sources=libraries,
                                                pure_sources=pure),
                                 Path(directory) / name)
            subprocess.run([
                str(tsc), "--noEmit", "--strict", "--target", "ES2022",
                "--module", "ESNext", "--moduleResolution", "bundler",
                "--jsx", "react-jsx", "--lib", "DOM,ES2022", "--types", "react",
                "App.tsx", "server.ts", "codecs.ts",
            ], cwd=output, check=True)
            print(f"Strict generated-target TypeScript check passed: {name}")


if __name__ == "__main__":
    main()
