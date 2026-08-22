from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED = {
    "case_commitment",
    "case_id",
    "exception",
    "family",
    "method",
    "shortest_path",
    "verdict",
}
VERDICTS = {"COMPLETE", "INCOMPLETE", "UNVERIFIED"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate external EraSeMap records")
    parser.add_argument("records")
    args = parser.parse_args()
    payload = json.loads(Path(args.records).read_text())
    if not isinstance(payload, list) or not payload:
        raise ValueError("records must be a non-empty array")
    keys: set[tuple[str, str]] = set()
    for record in payload:
        if not isinstance(record, dict) or set(record) != REQUIRED:
            raise ValueError("record schema mismatch")
        key = (record["case_id"], record["method"])
        if key in keys or record["verdict"] not in VERDICTS:
            raise ValueError("duplicate record or invalid verdict")
        keys.add(key)
    print(f"validated {len(payload)} unique records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
