from __future__ import annotations

import json
import re
from pathlib import Path

PROTOCOL = Path("benchmark/open-transfer-v1.json")


def test_open_transfer_protocol_is_exact_and_bounded() -> None:
    payload = json.loads(PROTOCOL.read_text())
    assert payload["schema_version"] == "erasemap-open-transfer-v1"
    assert [item["id"] for item in payload["families"]] == [
        "keycloak-identity",
        "mlflow-lineage",
        "qdrant-biometric",
    ]
    assert payload["seeds"] == [3101, 3109, 3119, 3121, 3137]
    assert payload["fault_states"] == [
        "safe_native",
        "surviving_derivative",
        "recovery_regeneration",
        "coverage_fault",
    ]
    assert 3 * 5 * 4 == payload["gates"]["case_count"] == 60
    assert payload["claim_boundary"]["independent"] is False


def test_open_transfer_protocol_uses_immutable_images_and_three_rotations() -> None:
    payload = json.loads(PROTOCOL.read_text())
    image_pattern = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")
    assert all(image_pattern.fullmatch(item["image"]) for item in payload["families"])
    family_ids = {item["id"] for item in payload["families"]}
    assert {item["held_out_family"] for item in payload["rotations"]} == family_ids
    assert all(len(item["calibration_families"]) == 2 for item in payload["rotations"])


def test_open_transfer_protocol_freezes_public_input_and_conjunctive_gates() -> None:
    payload = json.loads(PROTOCOL.read_text())
    source = payload["public_inputs"][0]
    assert source["id"] == "olivetti-faces"
    assert source["source_sha256"] == (
        "sha256:b612fb967f2dc77c9c62d3e1266e0c73d5fca46a4b8906c18e454d41af987794"
    )
    assert source["vector_dimension"] == 4096
    gates = payload["gates"]
    assert gates == {
        "case_count": 60,
        "family_count": 3,
        "erasemap_false_complete_max": 0,
        "coverage_fault_unverified_count": 15,
        "post_control_recurrence_max": 0,
        "retained_loss_max": 0,
        "native_false_complete_min_per_family": 1,
        "specificity_drop_max": 0.0,
        "oracle_mismatch_max": 0,
        "core_diff_max": 0,
        "rotation_count": 3,
    }
