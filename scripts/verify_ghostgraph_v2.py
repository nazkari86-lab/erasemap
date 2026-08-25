from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from experiments.run_ghostgraph_v1 import ROOT, canonical_bytes
from experiments.run_ghostgraph_v2 import compute_result


def verify_bundle(protocol: Path, reveal: Path, output: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        expected_result, expected_trials = compute_result(protocol, reveal)
        result = json.loads((output / "result.json").read_text())
        trials = [json.loads(line) for line in (output / "trials.jsonl").read_text().splitlines()]
        provenance = json.loads((output / "PROVENANCE.json").read_text())
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return {"passed": False, "errors": [f"bundle validation failed: {exc}"]}
    if result != json.loads(canonical_bytes(expected_result)):
        errors.append("result payload mismatch")
    if trials != json.loads(canonical_bytes(expected_trials)):
        errors.append("trial payload mismatch")
    for name in ("result.json", "trials.jsonl"):
        digest = "sha256:" + hashlib.sha256((output / name).read_bytes()).hexdigest()
        if provenance.get("artifacts", {}).get(name) != digest:
            errors.append(f"artifact hash mismatch: {name}")
    if expected_result["decision"] != "PASS":
        errors.append("recomputed decision is not PASS")
    return {"passed": not errors, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=ROOT / "benchmark/ghostgraph-v2.json")
    parser.add_argument("--reveal", type=Path, default=ROOT / "benchmark/ghostgraph-v2-reveal.json")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/ghostgraph-v2")
    args = parser.parse_args()
    report = verify_bundle(args.protocol, args.reveal, args.output)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
