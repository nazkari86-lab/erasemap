from __future__ import annotations

import json
from pathlib import Path

import pytest

from erasemap.cli import main
from erasemap.showcase import build_showcase, render_showcase_html, write_showcase

ROOT = Path(__file__).parents[1]


def test_showcase_binds_live_and_frozen_evidence() -> None:
    report = build_showcase(ROOT)

    assert report["live_audit"]["status"] == "INCOMPLETE"
    assert report["live_audit"]["shortest_residual_path"] == ["source", "template"]
    assert report["evidence"]["mechanism_stress"]["pcug_false_complete"] == 0
    assert report["evidence"]["measured_multiservice"]["speedup_geometric_mean"] > 17
    assert report["evidence"]["formal_conformance"]["mismatches"] == 0
    assert report["evidence"]["temporal_erasure"]["risk_detections"] == 30
    assert report["evidence"]["temporal_erasure"]["conformance_configurations"] == 16384
    assert report["evidence"]["topology_robust_erasure"]["nominal_recurrences"] == 35
    assert report["evidence"]["topology_robust_erasure"]["robust_recurrences"] == 0
    assert report["evidence"]["topology_robust_erasure"]["conformance_configurations"] == 4096
    assert report["claim_boundary"]["independence_score"] == 7.8
    assert len(report["source_sha256"]) == 8


def test_showcase_html_exposes_scope_and_not_supported_claims() -> None:
    rendered = render_showcase_html(build_showcase(ROOT))

    assert "source → template" in rendered
    assert "PROJECT_AUTHORED_DEVELOPMENT" in rendered
    assert "production-внедрение в FaceID/eGov" in rendered
    assert "7.8/10" in rendered


def test_showcase_fails_closed_on_tampered_result(tmp_path: Path) -> None:
    copied = tmp_path / "repo"
    for source in (
        "examples/five_branch_system.json",
        "benchmark/results/pcug-mechanism-stress-v1.json",
        "benchmark/results/measured-multiservice-v1-summary.json",
        "formal/conformance-v1.json",
        "outputs/regeneration-safe-erasure-v2/result.json",
        "formal/rse-msc-conformance-v1.json",
        "outputs/topology-robust-erasure-v1/result.json",
        "formal/tre-conformance-v1.json",
    ):
        destination = copied / source
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / source).read_bytes())
    path = copied / "benchmark/results/measured-multiservice-v1-summary.json"
    payload = json.loads(path.read_text())
    payload["decision"] = "FAIL"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="measured multi-service decision"):
        build_showcase(copied)


def test_showcase_cli_writes_json_and_html(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "showcase"
    assert main(["showcase", "--repo-root", str(ROOT), "--output", str(output)]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["status"] == "INCOMPLETE"
    assert response["independence_score"] == 7.8
    assert (output / "report.json").is_file()
    assert (output / "index.html").is_file()
    assert write_showcase(ROOT, output)["schema_version"] == "erasemap-jury-showcase-v1"
