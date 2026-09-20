"""No tests contact GitHub or publish releases."""

import hashlib
from pathlib import Path

import pytest

from scripts import publish_release as pub


def artifacts(tmp_path):
    wheel = tmp_path / "llmlang_mvp-0.6.0-py3-none-any.whl"
    wheel.write_bytes(b"tested wheel")
    sums = tmp_path / "SHA256SUMS"
    sums.write_text(f"{hashlib.sha256(wheel.read_bytes()).hexdigest()}  {wheel.name}\n")
    return pub.artifacts(tmp_path, "0.6.0")


def release(files, draft=False, target="a" * 40):
    return {
        "draft": draft,
        "prerelease": True,
        "tag_name": "v0.6.0",
        "target_commitish": target,
        "assets": [
            {"name": p.name, "state": "uploaded", "digest": f"sha256:{digest}"}
            for p, digest in files
        ],
    }


def test_corrupt_checksums_fail_before_upload(tmp_path):
    artifacts(tmp_path)
    (tmp_path / "SHA256SUMS").write_text("bad\n")
    with pytest.raises(pub.PublishError):
        pub.artifacts(tmp_path, "0.6.0")


@pytest.mark.parametrize("change", ["digest", "missing", "prerelease", "tag"])
def test_published_release_must_match_exact_assets_and_identity(tmp_path, change):
    files = artifacts(tmp_path)
    data = release(files)
    if change == "digest":
        data["assets"][0]["digest"] = "sha256:wrong"
    elif change == "missing":
        data["assets"] = []
    elif change == "prerelease":
        data["prerelease"] = False
    else:
        data["tag_name"] = "v0.5.0"
    with pytest.raises(pub.PublishError):
        pub.verify_published(data, "v0.6.0", True, files)


def test_existing_published_release_is_not_overwritten(tmp_path):
    files = artifacts(tmp_path)
    calls = []
    data = release(files)
    pub.publish(
        "o/r",
        "0.6.0",
        True,
        3,
        "a" * 40,
        Path("notes"),
        files,
        api=lambda endpoint: data,
        tag_target=lambda: "a" * 40,
        command=lambda args: calls.append(args),
    )
    assert len(calls) == 1
    assert calls[0][-2:] == ["-f", "state=closed"]


def test_wrong_tag_commit_blocks_all_mutations(tmp_path):
    calls = []
    files = artifacts(tmp_path)
    with pytest.raises(pub.PublishError):
        pub.publish(
            "o/r",
            "0.6.0",
            True,
            3,
            "a" * 40,
            Path("notes"),
            files,
            api=lambda endpoint: release(files),
            tag_target=lambda: "b" * 40,
            command=lambda args: calls.append(args),
        )
    assert not calls


def test_draft_recovery_uploads_then_publishes_then_closes(tmp_path):
    files = artifacts(tmp_path)
    values = iter([release(files, draft=True), release(files, draft=True), release(files)])
    calls = []
    pub.publish(
        "o/r",
        "0.6.0",
        True,
        3,
        "a" * 40,
        Path("notes"),
        files,
        api=lambda endpoint: next(values),
        tag_target=lambda: "a" * 40,
        command=lambda args: calls.append(args),
    )
    assert calls[0][:2] == ["release", "upload"]
    assert "--clobber" in calls[0]
    assert calls[1][:2] == ["release", "edit"]
    assert "--draft=false" in calls[1]
    assert calls[-1][:2] == ["api", "repos/o/r/milestones/3"]


def test_wrong_draft_target_blocks_upload(tmp_path):
    files = artifacts(tmp_path)
    calls = []
    with pytest.raises(pub.PublishError):
        pub.publish(
            "o/r",
            "0.6.0",
            True,
            3,
            "a" * 40,
            Path("notes"),
            files,
            api=lambda endpoint: release(files, draft=True, target="b" * 40),
            tag_target=lambda: None,
            command=lambda args: calls.append(args),
        )
    assert not calls


def test_asset_verification_failure_never_closes_milestone(tmp_path):
    files = artifacts(tmp_path)
    broken = release(files, draft=True)
    broken["assets"] = []
    values = iter([release(files, draft=True), broken])
    calls = []
    with pytest.raises(pub.PublishError):
        pub.publish(
            "o/r",
            "0.6.0",
            True,
            3,
            "a" * 40,
            Path("notes"),
            files,
            api=lambda endpoint: next(values),
            tag_target=lambda: "a" * 40,
            command=lambda args: calls.append(args),
        )
    assert all(args[0] != "api" for args in calls)
    assert all("--draft=false" not in args for args in calls)


def test_by_tag_404_falls_back_to_paginated_authenticated_draft_list(tmp_path):
    import json

    data = release(artifacts(tmp_path), draft=True)
    calls = []

    def command(args):
        calls.append(args)
        return json.dumps([[], [data]])

    assert pub.find_release("o/r", "v0.6.0", lambda endpoint: None, command) == data
    assert "--paginate" in calls[0]


def test_extra_draft_asset_is_never_published(tmp_path):
    files = artifacts(tmp_path)
    broken = release(files, draft=True)
    broken["assets"].append({"name": "unexpected.zip", "state": "uploaded"})
    values = iter([release(files, draft=True), broken])
    calls = []
    with pytest.raises(pub.PublishError):
        pub.publish(
            "o/r",
            "0.6.0",
            True,
            3,
            "a" * 40,
            Path("notes"),
            files,
            api=lambda endpoint: next(values),
            tag_target=lambda: "a" * 40,
            command=lambda args: calls.append(args),
        )
    assert all("--draft=false" not in args for args in calls)


def test_new_release_is_private_until_assets_verify_and_closes_last(tmp_path):
    files = artifacts(tmp_path)
    values = iter([None, release(files, draft=True), release(files)])
    targets = iter([None, None, "a" * 40])
    calls = []

    def command(args):
        calls.append(args)
        return "[]" if "--slurp" in args else ""

    pub.publish(
        "o/r",
        "0.6.0",
        True,
        3,
        "a" * 40,
        Path("notes"),
        files,
        api=lambda endpoint: next(values),
        tag_target=lambda: next(targets),
        command=command,
    )
    create = next(args for args in calls if args[:2] == ["release", "create"])
    assert "--draft" in create
    assert create[create.index("--target") + 1] == "a" * 40
    assert calls[-1][:2] == ["api", "repos/o/r/milestones/3"]


@pytest.mark.parametrize(
    "error", [OSError("network down"), pub.subprocess.TimeoutExpired("gh", 60)]
)
def test_api_network_failure_cannot_become_not_found(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(pub.subprocess, "run", fail)
    with pytest.raises(pub.PublishError):
        pub.api("repos/o/r/releases/tags/v0.6.0")


def test_failed_gate_never_calls_publisher(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pub.release_gate, "main", lambda args: 1)
    calls = []
    monkeypatch.setattr(pub, "publish", lambda *args: calls.append(args))
    assert pub.main(["--repository", "o/r"]) == 1
    assert calls == []
