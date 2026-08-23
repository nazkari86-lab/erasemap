from __future__ import annotations

import json
from pathlib import Path


def test_public_report_quotes_committed_ghostgraph_result_and_boundaries() -> None:
    result = json.loads(Path("outputs/ghostgraph-v1/result.json").read_text())
    summary = result["summary"]
    report = Path("docs/GHOSTGRAPH_V1_REPORT.md").read_text()

    assert summary["decision"] == "PASS"
    exact_row = (
        f"| Exact unique graph recoveries | "
        f"{summary['exact_unique_graph_recovery_count']} |"
    )
    assert exact_row in report
    assert f"| Correct path-class recoveries | {summary['path_class_recovery_count']} |" in report
    assert f"| False confident outputs | {summary['false_confident_count']} |" in report
    assert f"| Adaptive probes | {summary['adaptive_probe_count']} |" in report
    assert f"| Frozen exhaustive probes | {summary['exhaustive_probe_count']} |" in report
    for boundary in ("project-authored", "production FaceID/eGov", "NOT_COLLECTED"):
        assert boundary in report


def test_readme_keeps_bounded_and_external_status_visible() -> None:
    readme = Path("README.md").read_text()

    assert "GhostGraph" in readme
    assert "project-authored bounded result" in readme
    assert "External GhostGraph challenge" in readme
    assert "NOT_COLLECTED" in readme
