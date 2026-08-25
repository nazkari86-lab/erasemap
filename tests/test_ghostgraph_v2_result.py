from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.run_ghostgraph_v2 import run_experiment
from scripts.verify_ghostgraph_v2 import verify_bundle
from tests.test_ghostgraph_v2_protocols import test_future_reveal_commitments_are_canonical


def _reveal() -> dict[str, object]:
    # Keep the development fixture byte-equivalent to the preregistered commitment test.
    test_future_reveal_commitments_are_canonical()
    return {
        "schema_version": "erasemap-ghostgraph-reveal-v2",
        "protocol_schema_version": "erasemap-ghostgraph-v2",
        "cases": [
            {"case_id": "alt", "truth_graph_id": "g-alt"},
            {"case_id": "combo", "truth_graph_id": "g-combo"},
            {
                "case_id": "cross-contamination",
                "evidence_overrides": {"subjects_isolated": False},
                "truth_graph_id": "g-direct",
            },
            {"case_id": "direct", "truth_graph_id": "g-direct"},
            {"case_id": "multi-log", "truth_graph_id": "g-multi-log"},
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


def test_v2_runs_all_baselines_and_full_certificates(tmp_path: Path) -> None:
    reveal = tmp_path / "reveal.json"
    reveal.write_text(json.dumps(_reveal(), sort_keys=True, indent=2) + "\n")
    output = tmp_path / "result"

    result = run_experiment(Path("benchmark/ghostgraph-v2.json"), reveal, output)

    assert result["decision"] == "PASS"
    metrics = {item["strategy_id"]: item for item in result["strategy_metrics"]}
    assert set(metrics) == {
        "active-minimax", "flat-erasure-tomography", "frozen-random-feasible",
        "greedy-separated-pairs", "nonadaptive-exhaustive", "passive-declared-lineage",
    }
    assert (
        metrics["active-minimax"]["probe_count"]
        < metrics["nonadaptive-exhaustive"]["probe_count"]
    )
    trials = [json.loads(line) for line in (output / "trials.jsonl").read_text().splitlines()]
    active = [item for item in trials if item["strategy_id"] == "active-minimax"]
    assert any(item["certificates"] and item["certificates"][0]["candidates"] for item in active)
    assert verify_bundle(Path("benchmark/ghostgraph-v2.json"), reveal, output)["passed"] is True


def test_v2_output_is_append_only(tmp_path: Path) -> None:
    reveal = tmp_path / "reveal.json"
    reveal.write_text(json.dumps(_reveal()))
    output = tmp_path / "result"
    run_experiment(Path("benchmark/ghostgraph-v2.json"), reveal, output)

    with pytest.raises(FileExistsError):
        run_experiment(Path("benchmark/ghostgraph-v2.json"), reveal, output)
