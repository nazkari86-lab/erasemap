from __future__ import annotations

import argparse
import json
from pathlib import Path

from erasemap.fixture_benchmark import run_fixture_suite


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", default="benchmark/manual-pipelines-v1.json")
    parser.add_argument("--output", default="outputs/manual-pipelines-v1.json")
    args = parser.parse_args()
    result = run_fixture_suite(args.fixtures)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"passed": result["passed"], "total": result["total"]}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
