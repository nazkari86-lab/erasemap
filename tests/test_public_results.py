import gzip
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


def test_task_agnostic_v22_shadow_attack_result_meets_frozen_targets() -> None:
    result = load("task-agnostic-v22-summary.json")
    splits = result["splits"]
    assert isinstance(splits, dict)
    for split in splits.values():
        assert isinstance(split, dict)
        assert split["success"] is True
        assert split["primary_ratio"] <= 1.01
        assert split["worst_privacy_gap"] <= 0.10
        assert split["speedup"] >= 1.5
        assert split["selective_lira_auc"] >= 0.5
        assert split["exact_lira_auc"] >= 0.5


def test_manual_pipeline_public_result_is_not_claimed_independent() -> None:
    result = load("manual-pipelines-v1-summary.json")

    assert result["passed"] is True
    assert result["generator_independent"] is True
    assert result["authorship"] == "project-authored"


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


def test_v3_public_results_preserve_passes_and_preregistered_external_failure() -> None:
    development = load("task-agnostic-v3/development-summary.json")
    evaluation = load("task-agnostic-v3/evaluation-summary.json")
    external = load("task-agnostic-v3/external-summary.json")

    assert development["success"] is True
    assert evaluation["success"] is True
    assert external["success"] is False
    endpoints = external["endpoints"]
    summary = external["summary"]
    assert isinstance(endpoints, dict) and isinstance(summary, dict)
    assert endpoints["forgotten_embedding_mse_ratio_to_stale"] < 1.0
    assert endpoints["max_attack_paired_advantage_upper_ci"] < 0.10
    candidate = summary["deletion_matched_restart"]
    exact = summary["exact_retrain"]
    assert isinstance(candidate, dict) and isinstance(exact, dict)
    assert (
        candidate["retained_verification_auc"]["mean"]
        - exact["retained_verification_auc"]["mean"]
        < -0.01
    )


def test_v31_negative_ablation_and_pixel_backbone_are_public() -> None:
    development = load("task-agnostic-v31/development-summary.json")
    evaluation = load("task-agnostic-v31/evaluation-summary.json")
    external = load("task-agnostic-v31/adaptive-external-summary.json")
    pixel = load("trainable-pixel-backbone-v1/summary.json")

    assert development["success"] is False
    assert evaluation["success"] is True
    assert external["success"] is False
    assert pixel["success"] is True
    assert pixel["full_gradient_coverage"] is True


def test_v3_full_anonymous_trial_rows_are_tracked() -> None:
    paths = (
        RESULTS / "task-agnostic-v3/development-trials.jsonl.gz",
        RESULTS / "task-agnostic-v3/evaluation-trials.jsonl.gz",
        RESULTS / "task-agnostic-v3/external-trials.jsonl.gz",
    )
    for path in paths:
        with gzip.open(path, "rt") as stream:
            rows = [json.loads(line) for line in stream]
        assert len(rows) == 500
        assert all("anonymous_forget_subject" in row for row in rows)
