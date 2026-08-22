from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from external_challenge.submission import verify_submission

ALGORITHM_PATHS = (
    "external_challenge/runner.py",
    "src/erasemap/audit.py",
    "src/erasemap/codec.py",
    "src/erasemap/domain.py",
    "src/erasemap/evidence.py",
)


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", *args),
        check=False,
        capture_output=True,
        text=True,
    )


def verify_registry(root: Path, protocol: Path) -> list[dict[str, object]]:
    submissions = sorted(path.parent for path in root.glob("*/manifest.json"))
    if not submissions:
        raise ValueError("external registry contains no submission directories")
    reports: list[dict[str, object]] = []
    for submission in submissions:
        manifest = json.loads((submission / "manifest.json").read_text())
        commit = str(manifest.get("erasemap_commit", ""))
        exists = _git("cat-file", "-e", f"{commit}^{{commit}}")
        if exists.returncode != 0:
            raise ValueError(f"unknown EraSeMap commit in {submission.name}")
        ancestor = _git("merge-base", "--is-ancestor", commit, "HEAD")
        if ancestor.returncode != 0:
            raise ValueError(f"tested commit is not an ancestor for {submission.name}")
        changed = _git("diff", "--quiet", commit, "HEAD", "--", *ALGORITHM_PATHS)
        if changed.returncode != 0:
            raise ValueError(
                f"audit implementation changed after tested commit for {submission.name}"
            )
        reports.append(verify_submission(submission, protocol, commit))
    return reports


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify registered external evidence packages")
    parser.add_argument("--root", default=Path("external_results"), type=Path)
    parser.add_argument(
        "--protocol", default=Path("external_challenge/protocol-v1.json"), type=Path
    )
    args = parser.parse_args()
    reports = verify_registry(args.root, args.protocol)
    print(json.dumps(reports, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
