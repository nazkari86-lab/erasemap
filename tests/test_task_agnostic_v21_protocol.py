import json
from pathlib import Path


def test_v21_primary_endpoint_is_an_explicit_success_gate() -> None:
    protocol = json.loads(Path("benchmark/task-agnostic-v21.json").read_text())

    assert protocol["primary_endpoint"] == "functional_embedding_mse_ratio_to_stale"
    assert protocol["success_criteria"]["primary_endpoint_max"] == 1.01
    assert set(protocol["privacy_attacks"]) == {
        "confidence",
        "energy",
        "margin",
        "negative_entropy",
    }


def test_external_dataset_is_revision_pinned_before_content_access() -> None:
    protocol = json.loads(Path("benchmark/mufac-external-v1.json").read_text())

    assert len(protocol["dataset_revision"]) == 40
    assert protocol["selection_count"] == 60
    assert protocol["split_seed"] == 20260822


def test_v22_registers_shadow_lira_and_embedding_attacks() -> None:
    protocol = json.loads(Path("benchmark/task-agnostic-v22.json").read_text())

    assert set(protocol["privacy_attacks"]) == {
        "confidence",
        "embedding_nn",
        "energy",
        "margin",
        "negative_entropy",
        "task_agnostic_lira",
    }
    assert protocol["shadow_models"] == {
        "epochs": 100,
        "inclusions_per_sample": 8,
        "models": 16,
        "statistic": "negative_entropy",
    }


def test_v3_registers_deletion_matched_primary_and_paired_privacy_gate() -> None:
    protocol = json.loads(Path("benchmark/task-agnostic-v3.json").read_text())

    assert protocol["primary_endpoint"] == "forgotten_embedding_mse_ratio_to_stale"
    assert protocol["methods"][3] == "deletion_matched_restart"
    assert protocol["deletion_matched_restart"]["epochs"] < protocol["local_model"]["epochs"]
    assert protocol["success_criteria"]["primary_endpoint_max"] == 1.0
    assert "identity_deletion_lira" in protocol["privacy_attacks"]
    assert "privacy_identity_deletion_lira_in_probability" in protocol[
        "paired_privacy_attacks"
    ]
    assert protocol["success_criteria"]["max_attack_paired_advantage_upper_ci_max"] == 0.10
