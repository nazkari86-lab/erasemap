import json
import re
from pathlib import Path


def test_live_protocol_freezes_safe_digest_pinned_execution() -> None:
    protocol = json.loads(Path("benchmark/ghostgraph-live-v1.json").read_text())

    assert protocol["schema_version"] == "erasemap-ghostgraph-live-v1"
    assert set(protocol["images"]) == {"keycloak", "mlflow", "qdrant", "redis"}
    assert all(
        re.fullmatch(r"[^@\s]+@sha256:[0-9a-f]{64}", image)
        for image in protocol["images"].values()
    )
    assert protocol["network_binding"] == "127.0.0.1 only"
    assert protocol["container_prefix"] == "erasemap-ghostgraph-"
    assert protocol["synthetic_subjects_only"] is True
    assert [case["case_id"] for case in protocol["cases"]] == [
        "live-multihop",
        "live-path-equivalent",
        "live-outside",
        "live-safe",
    ]
    assert "not an independent evaluator" in protocol["claim_boundary"]


def test_live_preregistration_precedes_result() -> None:
    text = Path("docs/GHOSTGRAPH_LIVE_V1_PREREGISTRATION.md").read_text()

    assert "future passing run" in text
    assert "observed result are intentionally absent" in text
