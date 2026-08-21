import json
from pathlib import Path

import pytest

from erasemap.benchmark import BenchmarkProtocol, load_protocol, run_protocol


def test_protocol_report_is_reproducible(tmp_path: Path) -> None:
    protocol = load_protocol("benchmark/protocol-v1.json")
    left = run_protocol(protocol, output_dir=tmp_path / "left")
    right = run_protocol(protocol, output_dir=tmp_path / "right")
    assert left.canonical_results == right.canonical_results
    assert left.protocol_hash == right.protocol_hash


def test_runner_writes_complete_audit_artifacts(tmp_path: Path) -> None:
    protocol = BenchmarkProtocol(
        schema_version="erasemap-benchmark-v1",
        development_seeds=(1,),
        holdout_seeds=(99,),
        graph_sizes=(10,),
        fault_matrix=((), ("ORPHANED_TEMPLATE",)),
        methods=("erasemap", "receipt-only"),
        bootstrap_seed=7,
        bootstrap_samples=20,
        primary_endpoint="false_complete_rate",
    )

    report = run_protocol(protocol, output_dir=tmp_path)

    assert report.trial_count == 4
    assert {path.name for path in tmp_path.iterdir()} == {
        "failures.jsonl",
        "manifest.json",
        "summary.json",
        "trials.jsonl",
    }
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["protocol_hash"] == report.protocol_hash
    assert (tmp_path / "failures.jsonl").read_text() == ""


def test_unknown_method_is_recorded_as_failure(tmp_path: Path) -> None:
    protocol = BenchmarkProtocol(
        schema_version="erasemap-benchmark-v1",
        development_seeds=(1,),
        holdout_seeds=(99,),
        graph_sizes=(10,),
        fault_matrix=((),),
        methods=("unknown",),
        bootstrap_seed=7,
        bootstrap_samples=20,
        primary_endpoint="false_complete_rate",
    )

    report = run_protocol(protocol, output_dir=tmp_path)

    assert report.trial_count == 0
    assert "unknown benchmark method" in (tmp_path / "failures.jsonl").read_text()


def test_protocol_rejects_unknown_fields(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"schema_version":"erasemap-benchmark-v1","surprise":1}')

    with pytest.raises(ValueError, match="unknown field"):
        load_protocol(path)
