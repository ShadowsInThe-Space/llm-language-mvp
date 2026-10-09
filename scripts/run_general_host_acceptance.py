"""Run the built host, real local D1 restart checks, and real browser tests."""

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import IO


def start(host: Path, environment: dict[str, str], log: IO[bytes]) -> subprocess.Popen[bytes]:
    process = subprocess.Popen(["npm", "run", "start"], cwd=host, env=environment,
                               stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    deadline = time.monotonic() + 90
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Host exited before readiness: {process.returncode}")
            try:
                with urllib.request.urlopen("http://127.0.0.1:8787/history", timeout=2) as response:
                    if response.status == 200:
                        return process
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(0.25)
        raise TimeoutError("Built host did not become ready within 90 seconds")
    except BaseException:
        stop(process)
        raise


def stop(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
    # npm may exit before its workerd descendants. Require an actual interval
    # without a listening host, so the restart check cannot hit the old process.
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with socket.socket() as connection:
            connection.settimeout(0.25)
            if connection.connect_ex(("127.0.0.1", 8787)) != 0:
                return
        time.sleep(0.1)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    raise RuntimeError("Old host still listens after shutdown; restart evidence is invalid")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host-dir", type=Path, required=True)
    args = parser.parse_args()
    host = args.host_dir.resolve()
    environment = {**os.environ, "LLMLANG_D1_STATE": str(host / ".acceptance-state"),
                   "LLMLANG_GENERAL_EXTERNAL_SERVER": "1",
                   "LLMLANG_GENERAL_BASE_URL": "http://127.0.0.1:8787"}
    state = Path(environment["LLMLANG_D1_STATE"])
    if state.exists():
        raise FileExistsError("Acceptance requires a fresh disposable D1 state directory")
    subprocess.run(["npm", "run", "db:apply"], cwd=host, env=environment, check=True, timeout=90)
    subprocess.run(["npm", "run", "test:conditional-insert"], cwd=host, env=environment,
                   check=True, timeout=90)
    with (host / "host-acceptance.log").open("wb") as log:
        first = start(host, environment, log)
        try:
            subprocess.run(["node", "check-d1.mjs", "seed"], cwd=host, env=environment,
                           check=True, timeout=90)
        finally:
            stop(first)
        second = start(host, environment, log)
        try:
            subprocess.run(["node", "check-d1.mjs", "check-restart"], cwd=host,
                           env=environment, check=True, timeout=90)
            subprocess.run(["npm", "run", "test:e2e"], cwd=host, env=environment,
                           check=True, timeout=600)
        finally:
            stop(second)


if __name__ == "__main__":
    main()
