from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from erasemap.fixture_benchmark import run_fixture_suite


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", default="benchmark/manual-pipelines-v1.json")
    parser.add_argument("--output", default="outputs/manual-pipelines-v1.json")
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    if args.expected_sha256 is not None:
        actual = hashlib.sha256(Path(args.fixtures).read_bytes()).hexdigest()
        if actual != args.expected_sha256.removeprefix("sha256:"):
            raise RuntimeError("fixture commitment does not match the supplied suite")
    result = run_fixture_suite(args.fixtures)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"passed": result["passed"], "total": result["total"]}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
