"""Acceptance test for the reproducible Issue #16 package demonstration."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)


def test_pkg1_demo_is_reproducible_and_fail_closed() -> None:
    result = subprocess.run(
        [str(PYTHON), "scripts/demo_pkg1.py"],
        cwd=ROOT,
        env=None,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    summary = json.loads(result.stdout)
    assert summary["status"] == "passed"
    assert summary["app"]["result"] == {"type": "Int", "value": "3"}
    assert summary["remaining"]["result"] == {"type": "Int", "value": "0"}
    assert summary["shared_base_hash"]
    assert summary["transitive_dependency"] is True
    assert summary["stale_lock_rejected"] is True
    assert summary["stale_lock_rejected_by_consumer"] == {"app": True, "remaining": True}
    assert summary["stale_proof_rejected"] is True
    assert summary["stale_proof_rejected_by_consumer"] == {"app": True, "remaining": True}
    assert summary["fresh_proof_valid"] is True
    assert summary["fresh_proof_valid_by_consumer"] == {"app": True, "remaining": True}
    assert summary["relocation_deterministic"] is True
