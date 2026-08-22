import json
from pathlib import Path


def test_v32_adaptive_result_passes_unchanged_mufac_gates() -> None:
    result = json.loads(Path("outputs/task-agnostic-v32-adaptive-external/result.json").read_text())
    candidate = result["summary"]["deletion_matched_restart"]
    exact = result["summary"]["exact_retrain"]
    assert result["success"] is True
    assert (
        candidate["retained_verification_auc"]["mean"] - exact["retained_verification_auc"]["mean"]
        >= -0.01
    )
    assert candidate["speedup_vs_exact"]["mean"] >= 1.5
    assert result["endpoints"]["max_attack_paired_advantage_upper_ci"] <= 0.10
