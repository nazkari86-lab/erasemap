from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from experiments.run_ghostgraph_live_v2 import _validate_inputs, score_records
from experiments.run_ghostgraph_v1 import ROOT


def verify_bundle(protocol_path: Path, reveal_path: Path, output: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        protocol, reveal = _validate_inputs(protocol_path, reveal_path)
        trials = [json.loads(line) for line in (output / "trials.jsonl").read_text().splitlines()]
        result = json.loads((output / "result.json").read_text())
        provenance = json.loads((output / "PROVENANCE.json").read_text())
        expected = score_records(protocol, reveal, trials)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return {"passed": False, "errors": [f"bundle validation failed: {exc}"]}
    if result != expected:
        errors.append("result payload mismatch")
    for name in ("result.json", "trials.jsonl"):
        digest = "sha256:" + hashlib.sha256((output / name).read_bytes()).hexdigest()
        if provenance.get("artifacts", {}).get(name) != digest:
            errors.append(f"artifact hash mismatch: {name}")
    if expected["decision"] != "PASS":
        errors.append("recomputed live decision is not PASS")
    return {"passed": not errors, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol", type=Path, default=ROOT / "benchmark/ghostgraph-live-v2.json"
    )
    parser.add_argument(
        "--reveal", type=Path, default=ROOT / "benchmark/ghostgraph-live-v2-reveal.json"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "outputs/ghostgraph-live-v2"
    )
    args = parser.parse_args()
    report = verify_bundle(args.protocol, args.reveal, args.output)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
