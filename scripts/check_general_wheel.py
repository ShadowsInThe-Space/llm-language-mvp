"""Exercise both generated applications from an isolated installed wheel."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import llmlang
from llmlang.web.general.build import check_build


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--examples", type=Path, required=True)
    args = parser.parse_args()
    installed = Path(llmlang.__file__).resolve()
    if "site-packages" not in installed.parts:
        raise RuntimeError(f"Expected isolated installed wheel, imported {installed}")
    examples = args.examples.resolve()
    libraries = {"common": (examples / "common.webuilib").read_text(encoding="utf-8")}
    pure = {"helpers": (examples / "helpers.a1src").read_text(encoding="utf-8")}
    with tempfile.TemporaryDirectory(prefix="general-wheel-") as directory:
        for name in ("history", "tasks"):
            output = Path(directory) / name
            subprocess.run([
                sys.executable, "-m", "llmlang", "compile-general-web",
                str(examples / f"{name}.webapp"), "--library",
                f"common={examples / 'common.webuilib'}", "--pure-library",
                f"helpers={examples / 'helpers.a1src'}", "--out", str(output),
            ], cwd=directory, check=True)
            files = {str(path.relative_to(output)): path.read_text(encoding="utf-8")
                     for path in output.rglob("*") if path.is_file()}
            if not check_build((examples / f"{name}.webapp").read_text(encoding="utf-8"),
                               files, library_sources=libraries, pure_sources=pure):
                raise RuntimeError(f"Installed-wheel artifact binding failed: {name}")
            print(f"Installed-wheel general web check passed: {name}")


if __name__ == "__main__":
    main()
