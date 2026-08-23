from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from experiments.run_ghostgraph_v1 import ROOT, canonical_bytes, compute_result


def verify_bundle(protocol: Path, reveal: Path, output: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        expected_result, expected_trials = compute_result(protocol, reveal)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"passed": False, "errors": [f"input validation failed: {exc}"]}

    try:
        actual_result = json.loads((output / "result.json").read_text())
        actual_trials = [
            json.loads(line)
            for line in (output / "trials.jsonl").read_text().splitlines()
            if line
        ]
        provenance = json.loads((output / "PROVENANCE.json").read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return {"passed": False, "errors": [f"bundle read failed: {exc}"]}

    normalized_result = json.loads(canonical_bytes(expected_result))
    normalized_trials = json.loads(canonical_bytes(expected_trials))
    if actual_result != normalized_result:
        errors.append("result payload mismatch")
    if actual_trials != normalized_trials:
        errors.append("trial payload mismatch")
    for name in ("result.json", "trials.jsonl"):
        actual_hash = "sha256:" + hashlib.sha256((output / name).read_bytes()).hexdigest()
        if provenance.get("artifacts", {}).get(name) != actual_hash:
            errors.append(f"artifact hash mismatch: {name}")
    expected_decision = expected_result["summary"]["decision"]  # type: ignore[index]
    if expected_decision != "PASS":
        errors.append("recomputed decision is not PASS")
    return {
        "passed": not errors,
        "errors": errors,
        "result_sha256": "sha256:" + hashlib.sha256(canonical_bytes(actual_result)).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=ROOT / "benchmark/ghostgraph-v1.json")
    parser.add_argument("--reveal", type=Path, default=ROOT / "benchmark/ghostgraph-v1-reveal.json")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/ghostgraph-v1")
    args = parser.parse_args()
    report = verify_bundle(args.protocol, args.reveal, args.output)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
