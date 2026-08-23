from __future__ import annotations

import argparse
import json
from pathlib import Path

from erasemap.ghostgraph_conformance import generate_conformance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = generate_conformance()
    if args.output is not None:
        args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    if args.expected is not None:
        expected = json.loads(args.expected.read_text())
        if result != expected:
            raise SystemExit("GhostGraph conformance artifact mismatch")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["mismatches"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
