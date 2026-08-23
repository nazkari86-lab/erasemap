from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _core_hash(paths: list[str]) -> str:
    digest = hashlib.sha256()
    for raw_path in paths:
        path = Path(raw_path)
        digest.update(str(path).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def test_protocol_freezes_domain_order_and_caps() -> None:
    protocol = json.loads(Path("benchmark/ghostgraph-v1.json").read_text())

    assert protocol["schema_version"] == "erasemap-ghostgraph-v1"
    assert protocol["domain_caps"] == {
        "max_nodes": 8,
        "max_optional_edges": 12,
        "max_hypotheses": 4096,
        "max_experiments": 32,
        "max_checkpoints": 5,
        "max_time_buckets": 3,
        "trace_error_budget": 0,
    }
    assert protocol["node_ids"] == sorted(protocol["node_ids"])
    assert [item["edge_id"] for item in protocol["edge_catalogue"]] == sorted(
        item["edge_id"] for item in protocol["edge_catalogue"]
    )
    assert [item["graph_id"] for item in protocol["hypotheses"]] == sorted(
        item["graph_id"] for item in protocol["hypotheses"]
    )
    assert [item["experiment_id"] for item in protocol["experiments"]] == sorted(
        item["experiment_id"] for item in protocol["experiments"]
    )
    assert all(item["edge_ids"] == sorted(item["edge_ids"]) for item in protocol["hypotheses"])


def test_protocol_hashes_sources_catalogue_and_future_reveal() -> None:
    protocol = json.loads(Path("benchmark/ghostgraph-v1.json").read_text())

    assert protocol["core_sha256"] == _core_hash(protocol["core_files"])
    catalogue_hash = "sha256:" + hashlib.sha256(_canonical(protocol["hypotheses"])).hexdigest()
    assert protocol["hypothesis_catalogue_sha256"] == catalogue_hash
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", protocol["reveal_sha256"])


def test_protocol_freezes_cases_metrics_gates_and_claim_boundary() -> None:
    protocol = json.loads(Path("benchmark/ghostgraph-v1.json").read_text())

    assert protocol["case_ids"] == sorted(protocol["case_ids"])
    assert len(protocol["case_ids"]) == 7
    assert protocol["development_seeds"] == [101, 103]
    assert protocol["confirmatory_seed"] == 23082026
    assert "negative trace alone is not terminal" in protocol["stopping_rule"]
    assert len(protocol["baselines"]) == 5
    assert "false_confident_count" in protocol["primary_metrics"]
    assert protocol["gates"]["false_confident_count_max"] == 0
    assert protocol["gates"]["adaptive_probe_count_must_be_less_than_exhaustive"] is True
    assert len(protocol["invalid_run_rules"]) == 7
    assert "Project-authored" in protocol["claim_boundary"]
    assert "not independent" in protocol["claim_boundary"]


def test_preregistration_contains_no_achieved_result_claim() -> None:
    text = Path("docs/GHOSTGRAPH_V1_PREREGISTRATION.md").read_text()

    assert "passing result would support" in text
    assert "This is a project-authored bounded prospective experiment" in text
    assert "result passed" not in text.lower()
