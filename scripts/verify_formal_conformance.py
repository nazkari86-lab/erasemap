from __future__ import annotations

import argparse
import json
from pathlib import Path

from erasemap.formal_conformance import run_formal_conformance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    actual = run_formal_conformance()
    expected = json.loads(args.expected.read_text())
    if actual != expected:
        print(json.dumps({"expected": expected, "actual": actual}, indent=2, sort_keys=True))
        return 1
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(actual, indent=2, sort_keys=True) + "\n")
    print(json.dumps(actual, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
