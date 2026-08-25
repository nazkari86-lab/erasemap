from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


def _canonical_sha(payload: object) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(data).hexdigest()


def test_internal_v2_freezes_real_baselines_and_certificates() -> None:
    protocol = json.loads(Path("benchmark/ghostgraph-v2.json").read_text())

    assert protocol["schema_version"] == "erasemap-ghostgraph-v2"
    assert len(protocol["strategies"]) == 6
    assert {item["strategy_id"] for item in protocol["strategies"]} == {
        "active-minimax",
        "flat-erasure-tomography",
        "frozen-random-feasible",
        "greedy-separated-pairs",
        "nonadaptive-exhaustive",
        "passive-declared-lineage",
    }
    assert all(protocol["certificate_contract"].values())
    assert protocol["case_ids"] == sorted(protocol["case_ids"])
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", protocol["reveal_sha256"])
    for path, expected in protocol["core_file_sha256"].items():
        assert expected == "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()
    base = Path(protocol["base_protocol"])
    assert protocol["base_protocol_sha256"] == "sha256:" + hashlib.sha256(
        base.read_bytes()
    ).hexdigest()


def test_live_v2_freezes_graphs_experiments_images_and_claim_boundary() -> None:
    protocol = json.loads(Path("benchmark/ghostgraph-live-v2.json").read_text())

    assert protocol["schema_version"] == "erasemap-ghostgraph-live-v2"
    assert set(protocol["images"]) == {"identity", "lineage", "source", "vector"}
    assert all(
        re.fullmatch(r"[^@\s]+@sha256:[0-9a-f]{64}", item)
        for item in protocol["images"].values()
    )
    assert [item["graph_id"] for item in protocol["hypotheses"]] == sorted(
        item["graph_id"] for item in protocol["hypotheses"]
    )
    assert [item["experiment_id"] for item in protocol["experiments"]] == sorted(
        item["experiment_id"] for item in protocol["experiments"]
    )
    assert len(protocol["evidence_contract"]) == 6
    assert "not independent" in protocol["claim_boundary"]


def test_future_reveal_commitments_are_canonical() -> None:
    internal = {
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
    assert _canonical_sha(internal) == json.loads(
        Path("benchmark/ghostgraph-v2.json").read_text()
    )["reveal_sha256"]
