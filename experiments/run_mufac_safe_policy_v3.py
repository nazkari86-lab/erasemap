from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", default="benchmark/mufac-safe-policy-v3.json")
    parser.add_argument("--output", default="benchmark/results/mufac-safe-policy-v3-summary.json")
    args = parser.parse_args()
    protocol_path = Path(args.protocol)
    protocol = json.loads(protocol_path.read_text())
    result_path = Path(protocol["candidate_result"])
    result = json.loads(result_path.read_text())
    candidate = result["summary"]["deletion_matched_restart"]
    exact = result["summary"]["exact_retrain"]
    speedup = candidate["speedup_vs_exact"]["mean"]
    auc_delta = (
        candidate["retained_verification_auc"]["mean"] - exact["retained_verification_auc"]["mean"]
    )
    privacy_upper = result["endpoints"]["max_attack_paired_advantage_upper_ci"]
    gates = {
        "candidate_success": bool(result["success"]),
        "candidate_speedup": speedup >= protocol["required_gates"]["candidate_speedup_min"],
        "privacy_advantage_upper": privacy_upper
        <= protocol["required_gates"]["privacy_advantage_upper_max"],
        "retained_auc_delta": auc_delta >= protocol["required_gates"]["retained_auc_delta_min"],
    }
    accepted = all(gates.values())
    payload = {
        "claim_boundary": protocol["claim_boundary"],
        "decision": "CANDIDATE_ACCEPTED" if accepted else "SAFE_FALLBACK",
        "gates": gates,
        "input_result_hash": file_hash(result_path),
        "observed": {
            "privacy_advantage_upper": privacy_upper,
            "retained_auc_delta": auc_delta,
            "speedup": speedup,
        },
        "protocol_hash": file_hash(protocol_path),
        "selected_method": protocol["candidate"] if accepted else protocol["fallback"],
    }
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
