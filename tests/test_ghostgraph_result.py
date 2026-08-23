from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.run_ghostgraph_v1 import run_experiment
from scripts.verify_ghostgraph_v1 import verify_bundle


def _reveal_payload() -> dict[str, object]:
    return {
        "schema_version": "erasemap-ghostgraph-reveal-v1",
        "protocol_schema_version": "erasemap-ghostgraph-v1",
        "cases": [
            {"case_id": "alt", "truth_graph_id": "g-alt"},
            {"case_id": "combo", "truth_graph_id": "g-combo"},
            {
                "case_id": "cross-contamination",
                "evidence_overrides": {"subjects_isolated": False},
                "truth_graph_id": "g-direct",
            },
            {"case_id": "direct", "truth_graph_id": "g-direct"},
            {"case_id": "multihop", "truth_graph_id": "g-multi"},
            {
                "case_id": "outside",
                "truth_graph": {
                    "edges": [
                        {
                            "edge_id": "unknown-restore",
                            "operation_id": "restore",
                            "source_id": "backup",
                            "target_id": "worker",
                        },
                        {
                            "edge_id": "unknown-index",
                            "operation_id": "index",
                            "source_id": "worker",
                            "target_id": "vector",
                        },
                    ],
                    "graph_id": "truth-outside",
                    "initial_node_ids": ["backup"],
                    "residual_node_ids": ["vector"],
                },
            },
            {"case_id": "safe", "truth_graph_id": "g-safe"},
        ],
    }


def _write_reveal(path: Path) -> None:
    path.write_text(json.dumps(_reveal_payload(), sort_keys=True, indent=2) + "\n")


def test_development_bundle_is_deterministic_and_verifiable(tmp_path: Path) -> None:
    reveal = tmp_path / "reveal.json"
    output = tmp_path / "result"
    _write_reveal(reveal)

    result = run_experiment(Path("benchmark/ghostgraph-v1.json"), reveal, output)

    assert result["summary"]["decision"] == "PASS"
    assert result["summary"]["false_confident_count"] == 0
    assert result["summary"]["planner_oracle_mismatch_count"] == 0
    assert result["summary"]["post_control_recurrence_count"] == 0
    assert result["summary"]["retained_subject_loss_count"] == 0
    assert result["summary"]["adaptive_probe_count"] < result["summary"][
        "exhaustive_probe_count"
    ]
    assert verify_bundle(Path("benchmark/ghostgraph-v1.json"), reveal, output)["passed"] is True


def test_runner_is_append_only(tmp_path: Path) -> None:
    reveal = tmp_path / "reveal.json"
    output = tmp_path / "result"
    _write_reveal(reveal)
    run_experiment(Path("benchmark/ghostgraph-v1.json"), reveal, output)

    with pytest.raises(FileExistsError, match="already exists"):
        run_experiment(Path("benchmark/ghostgraph-v1.json"), reveal, output)


def test_reveal_commitment_drift_is_rejected(tmp_path: Path) -> None:
    reveal = tmp_path / "reveal.json"
    payload = _reveal_payload()
    payload["cases"] = []
    reveal.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="reveal commitment"):
        run_experiment(Path("benchmark/ghostgraph-v1.json"), reveal, tmp_path / "output")


def test_core_hash_drift_is_rejected(tmp_path: Path) -> None:
    protocol = json.loads(Path("benchmark/ghostgraph-v1.json").read_text())
    protocol["core_sha256"] = "sha256:" + "0" * 64
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol))
    reveal = tmp_path / "reveal.json"
    _write_reveal(reveal)

    with pytest.raises(ValueError, match="core hash drift"):
        run_experiment(protocol_path, reveal, tmp_path / "output")


def test_verifier_recomputes_instead_of_trusting_passed_field(tmp_path: Path) -> None:
    reveal = tmp_path / "reveal.json"
    output = tmp_path / "result"
    _write_reveal(reveal)
    run_experiment(Path("benchmark/ghostgraph-v1.json"), reveal, output)
    result_path = output / "result.json"
    result = json.loads(result_path.read_text())
    result["summary"]["decision"] = "PASS"
    result["summary"]["false_confident_count"] = 99
    result_path.write_text(json.dumps(result, sort_keys=True) + "\n")

    verification = verify_bundle(Path("benchmark/ghostgraph-v1.json"), reveal, output)

    assert verification["passed"] is False
    assert "result payload mismatch" in verification["errors"]


def test_trial_file_contains_every_frozen_case_once(tmp_path: Path) -> None:
    reveal = tmp_path / "reveal.json"
    output = tmp_path / "result"
    _write_reveal(reveal)
    run_experiment(Path("benchmark/ghostgraph-v1.json"), reveal, output)

    trials = [json.loads(line) for line in (output / "trials.jsonl").read_text().splitlines()]

    assert [trial["case_id"] for trial in trials] == [
        "alt",
        "combo",
        "cross-contamination",
        "direct",
        "multihop",
        "outside",
        "safe",
    ]
    assert len({trial["case_id"] for trial in trials}) == 7
