from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from erasemap.pcug_stress import run_stress_benchmark


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="benchmark/results/pcug-mechanism-stress-v1.json")
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    records = run_stress_benchmark()
    noncomplete = [record for record in records if record.truth != "COMPLETE"]
    payload = {
        "claim_boundary": "Project-authored mechanism stress test; not an external holdout.",
        "evidence_scope": "MECHANISM_STRESS_TEST",
        "pcug_false_complete": sum(record.pcug == "COMPLETE" for record in noncomplete),
        "records": [asdict(record) for record in records],
        "schema_version": "erasemap-pcug-mechanism-stress-v1",
        "trials": len(records),
        "truth_noncomplete": len(noncomplete),
        "typed_node_false_complete": sum(
            record.typed_node_audit == "COMPLETE" for record in noncomplete
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({key: value for key, value in payload.items() if key != "records"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
