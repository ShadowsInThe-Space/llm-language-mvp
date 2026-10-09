"""The additive compiler command handles explicit local library snapshots."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples/web/general"


class GeneralCliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "llmlang.web.general", *map(str, args)],
            cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            capture_output=True, text=True, check=False,
        )

    def test_compile_command_writes_complete_app_and_never_clobbers(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "app"
            args = (EXAMPLES / "history.webapp", "--library",
                    f"common={EXAMPLES / 'common.webuilib'}", "--pure-library",
                    f"helpers={EXAMPLES / 'helpers.a1src'}", "--out", output)
            result = self.run_cli(*args)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(json.loads(result.stdout)["status"], "compiled")
            self.assertTrue((output / "App.tsx").is_file())
            original = (output / "manifest.json").read_bytes()
            self.assertEqual(self.run_cli(*args).returncode, 1)
            self.assertEqual((output / "manifest.json").read_bytes(), original)

    def test_missing_or_duplicate_library_fails_without_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "app"
            result = self.run_cli(EXAMPLES / "history.webapp", "--out", output)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)["status"], "invalid")
            self.assertFalse(output.exists())
            library = f"common={EXAMPLES / 'common.webuilib'}"
            result = self.run_cli(EXAMPLES / "history.webapp", "--out", output,
                                  "--library", library, "--library", library)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
