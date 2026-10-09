"""Acceptance for auditing built client artifacts, rather than generated TS alone."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.check_general_client_bundle import AuditError, audit_client_bundle


class ClientBundleAuditAcceptance(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.client = self.root / "dist/client"
        self.client.mkdir(parents=True)
        self.programs = self.root / "generated"
        self.sql = 'SELECT "id", "title" FROM "tasks" LIMIT 8 OFFSET 0'
        for name in ("history", "tasks"):
            target = self.programs / name
            target.mkdir(parents=True)
            (target / "program.json").write_text(json.dumps({
                "format": "web-program-v1", "actions": [{"name": "browse"}],
                "pure_library": {"entries": ["title_preview"], "ir": {}},
            }), encoding="utf-8")
            metadata = json.dumps([{"name": "browse", "sql": self.sql}])
            (target / "server.ts").write_text(
                "const ACTIONS: readonly Action[] = " + metadata + ";\n", encoding="utf-8"
            )
        self.javascript = self.client / "assets/app-123.js"
        self.javascript.parent.mkdir()
        self.javascript.write_text(
            'fetch("/api/tasks",{body:JSON.stringify({action:"browse",input:{}})});'
            'const framework={database:"sql",network:"network.call"};', encoding="utf-8"
        )

    def write_map(self, **values: object) -> Path:
        path = self.javascript.with_suffix(".js.map")
        path.write_text(json.dumps({"version": 3, "sources": [], "names": [], **values}),
                        encoding="utf-8")
        return path

    def test_safe_client_action_transport_and_framework_words_are_allowed(self) -> None:
        self.write_map(sources=["../../generated/tasks/App.tsx", "../codecs.ts"],
                       sourcesContent=['fetch("/api/tasks")', "const sql = 'database';"],
                       names=["browse", "fetch", "network.call"])
        result = audit_client_bundle(self.client, self.programs)
        self.assertEqual((result.javascript_files, result.source_maps), (1, 1))

    def test_actual_generated_clients_and_codecs_are_allowed(self) -> None:
        from llmlang.web.general.build import compile_source, write_build

        examples = Path(__file__).resolve().parents[1] / "examples/web/general"
        generated = self.root / "real-generated"
        for name in ("history", "tasks"):
            build = compile_source(
                (examples / f"{name}.webapp").read_text(encoding="utf-8"),
                library_sources={
                    "common": (examples / "common.webuilib").read_text(encoding="utf-8"),
                },
                pure_sources={
                    "helpers": (examples / "helpers.a1src").read_text(encoding="utf-8"),
                },
            )
            write_build(build, generated / name)
            (self.client / f"{name}.js").write_text(
                build.files["App.tsx"] + build.files["codecs.ts"], encoding="utf-8"
            )
        result = audit_client_bundle(self.client, generated)
        self.assertEqual(result.javascript_files, 3)

    def test_actual_generated_sql_in_client_javascript_is_rejected(self) -> None:
        self.javascript.write_text("const stolen=" + json.dumps(self.sql) + ";",
                                   encoding="utf-8")
        with self.assertRaisesRegex(AuditError, "SQL"):
            audit_client_bundle(self.client, self.programs)

    def test_source_map_paths_content_and_names_cannot_hide_server_modules(self) -> None:
        cases = [
            {"sources": ["../../generated/tasks/server.ts"], "sourcesContent": [None]},
            {"sourceRoot": "../../generated/tasks/", "sources": ["a1-pure.ts"]},
            {"sources": ["safe.ts"], "sourcesContent": ["export function invokePure(){}"]},
            {"names": ["title_preview"]},
            {"sources": ["safe.ts"], "sourcesContent": ["const x=" + json.dumps(self.sql)]},
            {"sections": [{"offset": {"line": 0, "column": 0}, "map": {
                "version": 3, "sources": ["libraries/helpers.a1src"], "names": [],
            }}]},
        ]
        for values in cases:
            with self.subTest(values=values):
                self.write_map(**values)
                with self.assertRaises(AuditError):
                    audit_client_bundle(self.client, self.programs)

    def test_server_provenance_assets_and_capability_markers_are_rejected(self) -> None:
        for filename in ("server.ts", "a1-pure.ts", "schema.sql", "program.json",
                         "source.webapp", "helpers.a1src", "common.webuilib"):
            with self.subTest(filename=filename):
                leaked = self.client / filename
                leaked.write_text("public copy", encoding="utf-8")
                with self.assertRaises(AuditError):
                    audit_client_bundle(self.client, self.programs)
                leaked.unlink()
        for marker in ("invokePure", "moduleIR", "db.write", "identity.admin"):
            with self.subTest(marker=marker):
                self.javascript.write_text("const leaked=" + json.dumps(marker),
                                           encoding="utf-8")
                with self.assertRaises(AuditError):
                    audit_client_bundle(self.client, self.programs)

    def test_missing_client_files_and_malformed_maps_fail_closed(self) -> None:
        self.javascript.unlink()
        with self.assertRaises(AuditError):
            audit_client_bundle(self.client, self.programs)
        self.javascript.write_text("console.log('safe');", encoding="utf-8")
        self.write_map(sources="server.ts")
        with self.assertRaises(AuditError):
            audit_client_bundle(self.client, self.programs)
        self.javascript.with_suffix(".js.map").write_text("not JSON", encoding="utf-8")
        with self.assertRaises(AuditError):
            audit_client_bundle(self.client, self.programs)

    def test_uninspected_inline_maps_and_actual_source_syntax_fail_closed(self) -> None:
        for leaked in (
            'console.log("safe");\n//# sourceMappingURL=data:application/json;base64,e30=',
            '(websrc1 "private-provenance")',
        ):
            with self.subTest(leaked=leaked):
                self.javascript.write_text(leaked, encoding="utf-8")
                with self.assertRaises(AuditError):
                    audit_client_bundle(self.client, self.programs)

    def test_cli_audits_both_directories_and_reports_a_nonzero_failure(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts/check_general_client_bundle.py"
        command = [sys.executable, str(script), "--client-dir", str(self.client),
                   "--program-dir", str(self.programs)]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1 JavaScript", result.stdout)
        self.javascript.write_text("invokePure('title_preview',[]);", encoding="utf-8")
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("invokePure", result.stderr)


if __name__ == "__main__":
    unittest.main()
