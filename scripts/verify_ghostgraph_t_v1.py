from __future__ import annotations

import argparse
import json
from pathlib import Path


def verify(result_path: Path) -> dict[str, object]:
    payload = json.loads(result_path.read_text())
    if payload.get("schema_version") != "erasemap-ghostgraph-t-result-v1":
        raise ValueError("unsupported GhostGraph-T result")
    gates = payload.get("gates")
    if not isinstance(gates, dict) or not gates or not all(gates.values()):
        raise ValueError("GhostGraph-T result has a failed gate")
    if payload.get("success") is not True:
        raise ValueError("GhostGraph-T result is not successful")
    if payload.get("case_count") != 300:
        raise ValueError("GhostGraph-T result must contain exactly 300 cases")
    return {
        "valid": True,
        "case_count": payload["case_count"],
        "trial_count": payload["trial_count"],
        "gates": gates,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--result",
        type=Path,
        default=Path("outputs/ghostgraph-t-v1/result.json"),
    )
    args = parser.parse_args()
    print(json.dumps(verify(args.result), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
