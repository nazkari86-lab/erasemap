from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from erasemap.erasure_tomography_conformance import (
    run_erasure_tomography_conformance,
)


def verify(expected_path: Path | None, output_path: Path) -> dict[str, Any]:
    actual = run_erasure_tomography_conformance()
    if actual["mismatches"] != 0:
        raise ValueError("erasure tomography production/oracle mismatch")
    if expected_path is not None:
        expected = json.loads(expected_path.read_text())
        if actual != expected:
            raise ValueError("erasure tomography conformance record mismatch")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(actual, sort_keys=True, separators=(",", ":")) + "\n"
    )
    return actual


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.expected, args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
