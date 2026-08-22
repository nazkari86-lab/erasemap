from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from erasemap.external_cases import build_source_cases
from erasemap.holdout_commitment import commitment_payload
from erasemap.source_lock import canonical_json, load_source_manifest


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default="benchmark/external-sources-v1.json")
    parser.add_argument("--protocol", default="benchmark/pcug-source-locked-holdout-v1.json")
    parser.add_argument(
        "--output", default="benchmark/commitments/pcug-source-locked-holdout-v1.json"
    )
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    cases = build_source_cases(load_source_manifest(args.sources))
    payload = commitment_payload(cases, file_hash(Path(args.protocol)))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_json(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
