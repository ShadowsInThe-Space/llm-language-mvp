"""Prepare unchanged compiler outputs for the disposable general-web test host."""

from __future__ import annotations

import argparse
from pathlib import Path

from llmlang.web.general.build import compile_source, write_build


def prepare_host(host: Path, examples: Path) -> None:
    generated = host / "generated"
    if generated.exists() or generated.is_symlink():
        raise FileExistsError(generated)
    libraries = {"common": (examples / "common.webuilib").read_text(encoding="utf-8")}
    pure = {"helpers": (examples / "helpers.a1src").read_text(encoding="utf-8")}
    builds = {name: compile_source(
        (examples / f"{name}.webapp").read_text(encoding="utf-8"),
        library_sources=libraries, pure_sources=pure,
    ) for name in ("history", "tasks")}
    for name, build in builds.items():
        write_build(build, generated / name)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--host-dir", type=Path, default=root / "tests/general_host")
    parser.add_argument("--examples", type=Path, default=root / "examples/web/general")
    args = parser.parse_args()
    prepare_host(args.host_dir.resolve(), args.examples.resolve())
    print("Prepared unchanged generated history and tasks applications")


if __name__ == "__main__":
    main()
