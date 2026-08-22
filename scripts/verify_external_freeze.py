from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, cast


def _git_blob(commit: str, path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        check=False,
        capture_output=True,
    )
    if result.returncode:
        raise ValueError(f"cannot read frozen artifact {path!r} at {commit}")
    return result.stdout


def verify_freeze(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("freeze must be an object")
    freeze = cast(dict[str, Any], value)
    required = {
        "artifacts",
        "claim_boundary",
        "erasemap_commit",
        "repository",
        "schema_version",
        "status",
    }
    if set(freeze) != required:
        raise ValueError("freeze schema mismatch")
    if freeze["schema_version"] != "erasemap-external-evaluator-freeze-v2":
        raise ValueError("unsupported freeze schema")
    if freeze["status"] != "READY_NOT_EXECUTED":
        raise ValueError("freeze must not claim an external result")
    commit = freeze["erasemap_commit"]
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("erasemap_commit must be a full hexadecimal commit")
    artifacts = freeze["artifacts"]
    if not isinstance(artifacts, dict) or not artifacts:
        raise ValueError("freeze artifacts must be a non-empty object")
    checked: list[str] = []
    for artifact, expected in sorted(artifacts.items()):
        if not isinstance(artifact, str) or artifact.startswith(("/", "../")):
            raise ValueError("artifact paths must be repository-relative")
        if not isinstance(expected, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", expected):
            raise ValueError("artifact commitment must be sha256-prefixed")
        actual = "sha256:" + hashlib.sha256(_git_blob(commit, artifact)).hexdigest()
        if actual != expected:
            raise ValueError(f"frozen artifact commitment mismatch: {artifact}")
        checked.append(artifact)
    return {
        "artifacts_checked": checked,
        "erasemap_commit": commit,
        "schema_version": "erasemap-external-evaluator-freeze-verification-v1",
        "status": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify immutable external evaluator handoff")
    parser.add_argument(
        "--freeze",
        type=Path,
        default=Path("external_challenge/evaluator-freeze-v2.json"),
    )
    args = parser.parse_args()
    print(json.dumps(verify_freeze(args.freeze), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
