"""Behavioral acceptance for the deterministic compiler and output boundary."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from llmlang.web.build import compile_source, verify_build, write_build
from llmlang.web.model import WebError

SOURCE = '''(app w1 sample
  (store greeting (Text 128))
  (action save_greeting (write greeting))
  (action load_greeting (read greeting))
  (page "/" (title "Sample")
    (input message "Text" (for greeting) (initial "Hello"))
    (button save_button "Save" (invoke save_greeting (input message)) (into result))
    (button load_button "Load" (invoke load_greeting) (into result))
    (output result "Stored")))'''


def test_equivalent_source_has_identical_build_and_checked_inventory() -> None:
    first = compile_source(SOURCE)
    second = compile_source(SOURCE.replace("\n", " ").replace('"Hello"', '"H\\u0065llo"'))
    assert first.files == second.files
    assert first.manifest == second.manifest
    assert first.manifest["status"] == "compiled"
    assert first.manifest["target"] == "vinext-d1"
    assert "app/page.tsx" in first.files
    assert "app/api/store/[slot]/route.ts" in first.files
    assert "db/schema.ts" in first.files
    inventory = first.manifest["files"]
    for path, metadata in inventory.items():
        data = first.files[path].encode("utf-8")
        assert metadata == {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def test_different_program_changes_ui_and_server_binding() -> None:
    first = compile_source(SOURCE)
    second = compile_source(SOURCE.replace("sample", "another_app").replace("greeting", "notice"))
    assert first.manifest["source_sha256"] != second.manifest["source_sha256"]
    assert first.files["lib/w1-server.ts"] != second.files["lib/w1-server.ts"]
    assert first.files["app/page.tsx"] != second.files["app/page.tsx"]


def test_build_verification_recompiles_and_rejects_target_tampering(tmp_path: Path) -> None:
    destination = tmp_path / "compiled"
    write_build(compile_source(SOURCE), destination)
    assert verify_build(destination)
    page = destination / "app/page.tsx"
    page.write_text(page.read_text() + "\n// tampered\n")
    assert not verify_build(destination)


def test_nonempty_destination_preserves_existing_work(tmp_path: Path) -> None:
    destination = tmp_path / "existing"
    destination.mkdir()
    marker = destination / "user.txt"
    marker.write_text("keep me")
    with pytest.raises(WebError):
        write_build(compile_source(SOURCE), destination)
    assert list(destination.iterdir()) == [marker]
    assert marker.read_text() == "keep me"


def test_unsafe_artifact_path_and_symlink_are_rejected_before_writes(tmp_path: Path) -> None:
    build = compile_source(SOURCE)
    bad = replace(build, files={**build.files, "../escape.txt": "unsafe"})
    with pytest.raises(WebError):
        write_build(bad, tmp_path / "out")
    assert not (tmp_path / "escape.txt").exists()
    assert not (tmp_path / "out").exists()
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    with pytest.raises(WebError):
        write_build(build, alias / "out")
    assert not (real / "out").exists()


def test_cli_compiles_source_to_reviewable_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from llmlang.cli import main

    source = tmp_path / "source.llapp"
    source.write_text(SOURCE)
    destination = tmp_path / "output"
    assert main(["compile-web", str(source), "--out", str(destination)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "compiled"
    assert verify_build(destination)
