from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def choose_method(protocol: dict[str, Any], evidence: dict[str, Any]) -> dict[str, object]:
    candidate = cast(str, protocol["candidate"])
    fallback = cast(str, protocol["fallback"])
    criteria = cast(dict[str, float], protocol["selection_rule"])
    summary = cast(dict[str, Any], evidence["summary"])
    candidate_metrics = cast(dict[str, Any], summary[candidate])
    exact_metrics = cast(dict[str, Any], summary[fallback])
    retained_loss_upper = float(exact_metrics["retained_verification_auc"]["ci95"][1]) - float(
        candidate_metrics["retained_verification_auc"]["ci95"][0]
    )
    privacy_upper = float(evidence["endpoints"]["max_attack_paired_advantage_upper_ci"])
    forgotten_ratio = float(evidence["endpoints"]["forgotten_embedding_mse_ratio_to_stale"])
    gates = {
        "forgotten_mse_ratio": forgotten_ratio <= criteria["forgotten_mse_ratio_max"],
        "privacy_advantage_upper": privacy_upper <= criteria["privacy_advantage_upper_max"],
        "retained_auc_loss_upper": retained_loss_upper <= criteria["retained_auc_loss_upper_max"],
    }
    selected = candidate if all(gates.values()) else fallback
    selected_metrics = cast(dict[str, Any], summary[selected])
    return {
        "candidate": candidate,
        "candidate_original_success": bool(evidence["success"]),
        "decision": "SAFE_FALLBACK" if selected == fallback else "CANDIDATE_ACCEPTED",
        "fallback": fallback,
        "gates": gates,
        "observed": {
            "forgotten_mse_ratio": forgotten_ratio,
            "privacy_advantage_upper": privacy_upper,
            "retained_auc_loss_upper": retained_loss_upper,
        },
        "selected_method": selected,
        "selected_retained_auc_mean": selected_metrics["retained_verification_auc"]["mean"],
        "selected_retained_cka_mean": selected_metrics["retained_cka_to_exact"]["mean"],
        "selected_speedup_mean": selected_metrics["speedup_vs_exact"]["mean"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", default="benchmark/mufac-external-v2.json")
    parser.add_argument(
        "--evidence", default="benchmark/results/task-agnostic-v3/external-summary.json"
    )
    parser.add_argument("--output", default="benchmark/results/mufac-safe-policy-v2-summary.json")
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    protocol = json.loads(Path(args.protocol).read_text())
    evidence_path = Path(args.evidence)
    evidence = json.loads(evidence_path.read_text())
    result = choose_method(protocol, evidence)
    result["claim_boundary"] = protocol["claim_boundary"]
    result["input_evidence_hash"] = file_hash(evidence_path)
    result["protocol_hash"] = file_hash(Path(args.protocol))
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
