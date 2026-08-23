from __future__ import annotations

import hashlib
import json
from pathlib import Path

from erasemap.erasure_tomography_lab import default_probe_design

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "benchmark/erasure-tomography-v1.json"
REVEAL = ROOT / "benchmark/erasure-tomography-v1-reveal.json"


def canonical_sha256(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def test_protocol_matches_implemented_frozen_design() -> None:
    protocol = json.loads(PROTOCOL.read_text())
    design = default_probe_design()

    assert protocol["schema_version"] == "erasemap-erasure-tomography-v1"
    assert tuple(protocol["candidate_mechanism_ids"]) == design.mechanism_ids
    assert tuple(tuple(row) for row in protocol["probe_rows"]) == design.rows
    assert protocol["max_failures"] == design.max_failures == 1
    assert protocol["error_budget"] == design.error_budget == 0
    assert protocol["container_digests"] == {}


def test_protocol_locks_adapter_sources() -> None:
    protocol = json.loads(PROTOCOL.read_text())

    for relative_path, expected_digest in protocol["adapter_source_sha256"].items():
        actual = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
        assert actual == expected_digest


def test_reveal_matches_prospective_commitment_and_counts() -> None:
    protocol = json.loads(PROTOCOL.read_text())
    reveal = json.loads(REVEAL.read_text())
    cases = reveal["cases"]
    schedule = protocol["support_schedule"]

    assert canonical_sha256(reveal) == schedule["canonical_sha256"]
    assert len(cases) == schedule["case_count"]
    assert sum(item["kind"] == "valid" for item in cases) == schedule["valid_case_count"]
    assert sum(item["kind"] == "safe" for item in cases) == schedule["safe_case_count"]
    assert sum(
        item["kind"] not in {"valid", "safe"} for item in cases
    ) == schedule["negative_case_count"]
    case_ids = [item["case_id"] for item in cases]
    assert len(case_ids) == len(set(case_ids))


def test_protocol_has_non_compensatory_primary_gates_and_claim_boundary() -> None:
    protocol = json.loads(PROTOCOL.read_text())
    gates = protocol["primary_gates"]

    assert gates["false_localization_count_max"] == 0
    assert gates["oracle_mismatch_count_max"] == 0
    assert gates["post_control_recurrence_count_max"] == 0
    assert gates["retained_subject_loss_count_max"] == 0
    assert gates["tomography_probe_count"] < gates["individual_audit_probe_count"]
    assert "does not establish arbitrary topology discovery" in protocol["claim_boundary"]
