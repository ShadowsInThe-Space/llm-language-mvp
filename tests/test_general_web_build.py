"""Two source applications must pass through the same bound compiler pipeline."""

import tempfile
import unittest
from pathlib import Path

from llmlang.web.general.build import check_build, compile_source, write_build

EXAMPLES = Path(__file__).resolve().parents[1] / "examples/web/general"


class GeneralBuildTests(unittest.TestCase):
    def setUp(self):
        self.library = (EXAMPLES / "common.webuilib").read_text()
        self.libraries = {"common": self.library}
        self.pure = {"helpers": (EXAMPLES / "helpers.a1src").read_text()}

    def test_two_apps_share_library_and_produce_reproducible_bound_outputs(self):
        for name in ("history", "tasks"):
            with self.subTest(name=name):
                source = (EXAMPLES / f"{name}.webapp").read_text()
                build = compile_source(source, library_sources=self.libraries,
                                       pure_sources=self.pure)
                self.assertEqual(build.files, compile_source(
                    source, library_sources=self.libraries, pure_sources=self.pure).files)
                self.assertTrue(check_build(source, build.files, library_sources=self.libraries,
                                            pure_sources=self.pure))
                self.assertIn("App.tsx", build.files)
                self.assertIn("server.ts", build.files)
                self.assertIn("schema.sql", build.files)
                self.assertIn("libraries/common.webuilib", build.files)
                self.assertIn("a1-pure.ts", build.files)
                self.assertIn("libraries/helpers.a1src", build.files)
                self.assertNotIn("CREATE TABLE", build.files["App.tsx"])
                self.assertNotIn("db.write", build.files["App.tsx"])
                changed = {**build.files, "App.tsx": build.files["App.tsx"] + "\n// changed"}
                self.assertFalse(check_build(source, changed, library_sources=self.libraries,
                                             pure_sources=self.pure))
                with self.assertRaises(TypeError):
                    build.files["App.tsx"] = "changed"

    def test_shared_library_changes_both_consumers_and_invalidates_old_binding(self):
        changed = {"common": self.library.replace('"Save"', '"Store"')}
        for name in ("history", "tasks"):
            source = (EXAMPLES / f"{name}.webapp").read_text()
            before = compile_source(source, library_sources=self.libraries, pure_sources=self.pure)
            after = compile_source(source, library_sources=changed, pure_sources=self.pure)
            self.assertNotEqual(before.files["App.tsx"], after.files["App.tsx"])
            self.assertNotEqual(before.manifest["program_hash"], after.manifest["program_hash"])
            self.assertFalse(check_build(source, before.files, library_sources=changed,
                                         pure_sources=self.pure))

    def test_executable_library_changes_both_servers_and_invalidates_build_binding(self):
        changed = {"helpers": self.pure["helpers"].replace(
            "(return text)", "(let n Nat (const 80)) "
            "(let short (Text 4096) (text_prefix_codepoints text n)) (return short)")}
        for name in ("history", "tasks"):
            source = (EXAMPLES / f"{name}.webapp").read_text()
            before = compile_source(source, library_sources=self.libraries, pure_sources=self.pure)
            after = compile_source(source, library_sources=self.libraries, pure_sources=changed)
            self.assertNotEqual(before.files["a1-pure.ts"], after.files["a1-pure.ts"])
            self.assertEqual(before.files["App.tsx"], after.files["App.tsx"])
            self.assertNotEqual(before.manifest["program_hash"], after.manifest["program_hash"])
            self.assertFalse(check_build(source, before.files, library_sources=self.libraries,
                                         pure_sources=changed))
            tampered = {**before.files, "a1-pure.ts": before.files["a1-pure.ts"] + "// changed"}
            self.assertFalse(check_build(source, tampered, library_sources=self.libraries,
                                         pure_sources=self.pure))

    def test_write_is_complete_and_refuses_existing_output(self):
        source = (EXAMPLES / "history.webapp").read_text()
        build = compile_source(source, library_sources=self.libraries, pure_sources=self.pure)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "compiled"
            self.assertEqual(write_build(build, output), output.resolve())
            disk = {str(p.relative_to(output)): p.read_text()
                    for p in output.rglob("*") if p.is_file()}
            self.assertEqual(disk, dict(build.files))
            with self.assertRaises(FileExistsError):
                write_build(build, output)
            self.assertEqual((output / "App.tsx").read_text(), build.files["App.tsx"])


if __name__ == "__main__":
    unittest.main()
