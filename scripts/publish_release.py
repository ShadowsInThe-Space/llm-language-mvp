"""Publish one already-validated milestone; never commit or push source changes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

from scripts import release_gate


class PublishError(Exception):
    pass


def command(args: list[str]) -> str:
    try:
        return subprocess.run(
            ["gh", *args], capture_output=True, text=True, check=True, timeout=120
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise PublishError("GitHub operation failed; no success assumed") from exc


def api(endpoint: str):
    try:
        result = subprocess.run(
            ["gh", "api", endpoint], capture_output=True, text=True, check=True, timeout=60
        )
        value = json.loads(result.stdout)
        if type(value) is not dict:
            raise PublishError("Unexpected GitHub response")
        return value
    except subprocess.CalledProcessError as exc:
        if re.search(r"\(HTTP 404\)", exc.stderr or ""):
            return None
        raise PublishError("GitHub read failed") from exc
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise PublishError("GitHub read failed") from exc


def tag_target(repository: str, tag: str):
    value = api(f"repos/{repository}/git/ref/tags/{tag}")
    if value is None:
        return None
    for _ in range(5):
        obj = value.get("object", {})
        sha = obj.get("sha", "")
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise PublishError("Malformed tag reference")
        if obj.get("type") == "commit":
            return sha
        if obj.get("type") != "tag":
            break
        value = api(f"repos/{repository}/git/tags/{sha}")
        if value is None:
            break
    raise PublishError("Tag is not a supported commit reference")


def artifacts(directory: Path, version: str):
    wheel = directory / f"llmlang_mvp-{version}-py3-none-any.whl"
    sums = directory / "SHA256SUMS"
    files = [(p, hashlib.sha256(p.read_bytes()).hexdigest()) for p in (wheel, sums)]
    if sums.read_text(encoding="utf-8") != f"{files[0][1]}  {wheel.name}\n":
        raise PublishError("Wheel checksum file does not match")
    return files


def find_release(repository, tag, api=api, command=command):
    data = api(f"repos/{repository}/releases/tags/{tag}")
    if data is not None:
        return data
    # The by-tag endpoint does not find unpublished drafts. Authenticated listing does.
    pages = json.loads(
        command(
            [
                "api",
                f"repos/{repository}/releases?per_page=100",
                "--paginate",
                "--slurp",
            ]
        )
    )
    if type(pages) is not list or any(type(page) is not list for page in pages):
        raise PublishError("Malformed release listing")
    entries = [item for page in pages for item in page]
    if any(type(item) is not dict for item in entries):
        raise PublishError("Malformed release listing")
    matches = [item for item in entries if item.get("tag_name") == tag]
    if len(matches) > 1:
        raise PublishError("Ambiguous release tag")
    return matches[0] if matches else None


def verify_published(data, tag: str, prerelease: bool, files, *, draft=False) -> None:
    if (
        type(data) is not dict
        or data.get("draft") is not draft
        or data.get("tag_name") != tag
        or data.get("prerelease") is not prerelease
    ):
        raise PublishError("Published release identity mismatch")
    assets = data.get("assets")
    if type(assets) is not list or any(type(a) is not dict for a in assets):
        raise PublishError("Malformed asset metadata")
    if sorted(a.get("name", "") for a in assets) != sorted(p.name for p, _ in files):
        raise PublishError("Published release asset set mismatch")
    for path, digest in files:
        asset = next(a for a in assets if a.get("name") == path.name)
        if asset.get("state") != "uploaded" or asset.get("digest") != f"sha256:{digest}":
            raise PublishError(
                "Published asset digest missing or mismatched; manual audit required"
            )


def publish(
    repository,
    version,
    prerelease,
    milestone,
    head,
    notes,
    files,
    *,
    api=api,
    tag_target=None,
    command=command,
):
    tag = f"v{version}"
    target = tag_target or (lambda: globals()["tag_target"](repository, tag))
    existing_target = target()
    if existing_target is not None and existing_target != head:
        raise PublishError("Existing tag points to another commit")
    data = find_release(repository, tag, api, command)
    if data is not None:
        if data.get("tag_name") != tag or type(data.get("draft")) is not bool:
            raise PublishError("Existing release metadata is invalid")
        if data["draft"] and data.get("target_commitish") != head:
            raise PublishError("Existing draft targets another commit")
        if not data["draft"]:
            if existing_target != head:
                raise PublishError("Published release tag is missing")
            verify_published(data, tag, prerelease, files)
    if data is None or data["draft"]:
        # A release whose tag exists without metadata is ambiguous, not a retryable draft.
        if data is None:
            if existing_target is not None:
                raise PublishError("Tag exists without a release; inspect before proceeding")
            command(
                [
                    "release",
                    "create",
                    tag,
                    "--repo",
                    repository,
                    "--target",
                    head,
                    "--draft",
                    "--title",
                    f"{tag} — milestone {milestone}",
                    "--notes-file",
                    str(notes),
                    f"--prerelease={str(prerelease).lower()}",
                ]
            )
        command(
            [
                "release",
                "upload",
                tag,
                *(str(p) for p, _ in files),
                "--repo",
                repository,
                "--clobber",
            ]
        )
        # Validate ALL uploaded bytes while still private. Extra or partial assets
        # must never become publicly released just because the upload command exited 0.
        draft = find_release(repository, tag, api, command)
        verify_published(draft, tag, prerelease, files, draft=True)
        if draft.get("target_commitish") != head:
            raise PublishError("Draft target changed before publication")
        current_target = target()
        if current_target is not None and current_target != head:
            raise PublishError("Tag changed before publication")
        command(
            [
                "release",
                "edit",
                tag,
                "--repo",
                repository,
                "--draft=false",
                f"--prerelease={str(prerelease).lower()}",
                "--notes-file",
                str(notes),
            ]
        )
        data = find_release(repository, tag, api, command)
        if target() != head:
            raise PublishError("Published tag target mismatch")
        verify_published(data, tag, prerelease, files)
    # Only a verified, public release closes the milestone. No source push is performed.
    command(
        [
            "api",
            f"repos/{repository}/milestones/{milestone}",
            "--method",
            "PATCH",
            "-f",
            "state=closed",
        ]
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    args = parser.parse_args(argv)
    try:
        with tempfile.TemporaryDirectory(prefix="milestone-release-") as temporary:
            notes = Path(temporary) / "notes.md"
            if (
                release_gate.main(
                    [
                        "--repository",
                        args.repository,
                        "--mode",
                        "release",
                        "--notes-output",
                        str(notes),
                    ]
                )
                != 0
            ):
                raise PublishError("Final milestone gate rejected publication")
            plan = release_gate.load_plan(Path("release-plan.json"))
            head = release_gate._git(["rev-parse", "HEAD"])
            publish(
                args.repository,
                plan.version,
                plan.prerelease,
                plan.milestone_number,
                head,
                notes,
                artifacts(Path("dist"), plan.version),
            )
        print(json.dumps({"status": "published", "tag": f"v{plan.version}"}))
        return 0
    except (PublishError, release_gate.GateError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
