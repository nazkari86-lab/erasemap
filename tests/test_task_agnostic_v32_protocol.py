import json
from pathlib import Path


def test_v32_is_explicitly_adaptive_and_keeps_frozen_gates() -> None:
    protocol = json.loads(Path("benchmark/task-agnostic-v32.json").read_text())
    implementation = Path("experiments/task_agnostic_unlearning_v2.py").read_text()
    assert protocol["schema_version"] == "erasemap-task-agnostic-v3.2"
    assert '"erasemap-task-agnostic-v3.2"' in implementation
    assert protocol["deletion_matched_restart"]["epochs"] == 120
    assert "outcomes were already known" in protocol["deletion_matched_restart"]["selection_note"]
    assert protocol["local_model"]["epochs"] == 200
    assert protocol["success_criteria"]["candidate_retained_auc_delta_min"] == -0.01
    assert protocol["success_criteria"]["candidate_speedup_min"] == 1.5
