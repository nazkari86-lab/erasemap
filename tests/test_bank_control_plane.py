from __future__ import annotations

import pytest

from erasemap.bank_control_plane import RequestStage, SyntheticBankControlPlane


def test_control_plane_has_512_synthetic_customers_and_connector_inventory() -> None:
    plane = SyntheticBankControlPlane(customer_count=512)
    manifest = plane.manifest()

    assert manifest["customer_count"] == 512
    assert manifest["registered_artifact_count"] == 3072
    assert [item["id"] for item in manifest["connectors"]] == [
        "postgres",
        "keycloak",
        "redis",
        "qdrant",
        "minio",
    ]
    assert len(plane.list_customers()) == 80
    assert len(plane.list_customers(query="KZ-DEMO-042")) == 1


def test_control_plane_requires_ordered_replay_lifecycle() -> None:
    plane = SyntheticBankControlPlane()
    customer_id = plane.demo_customer_id

    with pytest.raises(ValueError, match="expected action"):
        plane.execute_action(customer_id, "verify-replay")

    stages = []
    for action in (
        "create-request",
        "delete-visible",
        "simulate-recovery",
        "run-probes",
        "apply-exact-cut",
        "verify-replay",
    ):
        stages.append(plane.execute_action(customer_id, action)["stage"])

    assert stages == [stage.value for stage in (
        RequestStage.REQUESTED,
        RequestStage.VISIBLE_COPIES_ERASED,
        RequestStage.RECURRENCE_OBSERVED,
        RequestStage.RECOVERY_LOCALIZED,
        RequestStage.CUT_APPLIED,
        RequestStage.VERIFIED,
    )]
    snapshot = plane.customer_snapshot(customer_id)
    assert snapshot["verdict"]["status"] == "COMPLETE"
    assert {item["state"] for item in snapshot["artifacts"]} == {"ERASED"}
    assert snapshot["retained_customer_count"] == 511


def test_control_plane_stops_at_synthetic_scope() -> None:
    plane = SyntheticBankControlPlane()
    snapshot = plane.customer_snapshot(plane.demo_customer_id)

    assert snapshot["verdict"]["status"] == "NOT_REQUESTED"
    assert snapshot["dry_run"][0]["connector"] == "postgres"
    with pytest.raises(ValueError, match="unknown synthetic customer"):
        plane.customer_snapshot("real-bank-customer")
