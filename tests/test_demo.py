import shutil
import subprocess
import sys
from pathlib import Path


def test_demo_gates_survive_python_optimization(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    for name in ("scripts", "examples", "evidence"):
        shutil.copytree(root / name, tmp_path / name)
    (tmp_path / "examples/golden/identity.ll").write_text("(candidate p0 (body 0))")
    outcome = subprocess.run(
        [sys.executable, "-O", str(tmp_path / "scripts/demo.py")],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert outcome.returncode != 0
    assert "Definition of Done passed" not in outcome.stdout
