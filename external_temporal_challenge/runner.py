from __future__ import annotations

import argparse
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from external_temporal_challenge.core import (
    PREDICTIONS_SCHEMA,
    canonical_bytes,
    digest_bytes,
    predict_case,
    read_object,
    validate_public_suite,
)


def current_erasemap_commit() -> str:
    root = Path(__file__).resolve().parents[1]
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        raise RuntimeError("EraSeMap worktree must be clean before a frozen challenge run")
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    commit = result.stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValueError("unable to resolve a full EraSeMap git commit")
    return commit


def run(public_path: Path, output: Path) -> dict[str, Any]:
    public_bytes = public_path.read_bytes()
    public = read_object(public_path)
    cases = validate_public_suite(public)
    result: dict[str, Any] = {
        "schema_version": PREDICTIONS_SCHEMA,
        "public_cases_sha256": digest_bytes(public_bytes),
        "tested_erasemap_commit": current_erasemap_commit(),
        "prediction_created_at_utc": datetime.now(UTC).isoformat(),
        "predictions": [predict_case(item) for item in cases],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(result))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("public_cases", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.public_cases, args.output)
    print(canonical_bytes({"prediction_count": len(result["predictions"])}).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
