"""The host consumes complete compiler outputs without editing target code."""

import tempfile
import unittest
from pathlib import Path

from llmlang.web.general.build import compile_source
from scripts.prepare_general_host import prepare_host

EXAMPLES = Path(__file__).resolve().parents[1] / "examples/web/general"


class HostPreparationTests(unittest.TestCase):
    def test_both_host_inputs_are_byte_identical_to_compiler_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            host = Path(directory)
            prepare_host(host, EXAMPLES)
            for name in ("history", "tasks"):
                expected = compile_source(
                    (EXAMPLES / f"{name}.webapp").read_text(encoding="utf-8"),
                    library_sources={"common":
                        (EXAMPLES / "common.webuilib").read_text(encoding="utf-8")},
                    pure_sources={"helpers":
                        (EXAMPLES / "helpers.a1src").read_text(encoding="utf-8")},
                )
                generated = host / "generated" / name
                actual = {str(path.relative_to(generated)): path.read_text(encoding="utf-8")
                          for path in generated.rglob("*") if path.is_file()}
                self.assertEqual(actual, dict(expected.files))

    def test_existing_host_outputs_are_refused_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            host = Path(directory)
            prepare_host(host, EXAMPLES)
            app = host / "generated/history/App.tsx"
            app.write_text("hostile manual patch", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                prepare_host(host, EXAMPLES)
            self.assertEqual(app.read_text(encoding="utf-8"), "hostile manual patch")


if __name__ == "__main__":
    unittest.main()
