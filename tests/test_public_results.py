import json
from pathlib import Path

import pytest

RESULTS = Path("benchmark/results")


def load(name: str) -> dict[str, object]:
    return json.loads((RESULTS / name).read_text())


def test_task_agnostic_public_result_meets_frozen_targets() -> None:
    result = load("task-agnostic-v2-summary.json")
    evaluation = result["evaluation"]
    assert isinstance(evaluation, dict)
    methods = evaluation["methods"]
    assert isinstance(methods, dict)
    lineage = methods["lineage_guided"]
    exact = methods["exact_retrain"]
    assert isinstance(lineage, dict) and isinstance(exact, dict)
    assert lineage["retained_verification_auc"] >= exact["retained_verification_auc"] - 0.01
    assert abs(lineage["membership_attack_auc"] - exact["membership_attack_auc"]) <= 0.05
    assert lineage["speedup_vs_exact"] >= 1.5


def test_task_agnostic_v21_external_result_meets_frozen_targets() -> None:
    result = load("task-agnostic-v21-summary.json")
    external = result["external"]
    assert isinstance(external, dict)
    assert external["success"] is True
    assert external["functional_embedding_mse_ratio_to_stale"] <= 1.01
    assert external["worst_privacy_advantage_gap_to_exact"] <= 0.10
    assert (
        external["influence_selective_retained_auc"]
        >= external["exact_retained_auc"] - 0.01
    )
    assert external["influence_selective_speedup"] >= 1.5


def test_head_only_encoder_metrics_equal_stale() -> None:
    result = load("task-agnostic-v2-summary.json")
    evaluation = result["evaluation"]
    assert isinstance(evaluation, dict)
    methods = evaluation["methods"]
    assert isinstance(methods, dict)
    stale = methods["stale"]
    head = methods["head_only"]
    assert isinstance(stale, dict) and isinstance(head, dict)
    assert head["retained_cka_to_exact"] == pytest.approx(stale["retained_cka_to_exact"])
    assert head["retained_verification_auc"] == pytest.approx(
        stale["retained_verification_auc"]
    )


def test_core_and_simulator_public_results_pass() -> None:
    core = load("core-holdout-v1-summary.json")
    simulator = load("egov-pilot-simulator-v1-summary.json")
    erasemap = core["erasemap"]
    assert isinstance(erasemap, dict)
    assert erasemap["false_complete_rate"] == 0
    assert erasemap["recall"] == 1
    assert core["failures"] == 0
    assert simulator["success"] is True
    assert simulator["retained_intact"] is True
    assert simulator["tampered_receipt_rejected"] is True
