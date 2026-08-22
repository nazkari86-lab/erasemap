from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs="?", default="outputs/source-locked-holdout-v1")
    args = parser.parse_args()
    directory = Path(args.directory)
    manifest = json.loads((directory / "MANIFEST.sha256.json").read_text())
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError("invalid or empty evidence manifest")
    for name, expected in manifest.items():
        path = directory / name
        if not path.is_file() or file_hash(path) != expected:
            raise ValueError(f"evidence hash mismatch: {name}")
    summary = json.loads((directory / "summary.json").read_text())
    pcug = summary["metrics"]["pcug"]
    if summary["decision"] != "PASS" or pcug["false_complete"] != 0:
        raise ValueError("committed primary endpoint is not PASS")
    print(f"verified {len(manifest)} files; decision=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
