from pathlib import Path

import pytest

from erasemap.pcug_benchmark import (
    encode_records,
    load_pcug_protocol,
    run_pcug_benchmark,
)

PROTOCOL_PATH = Path("benchmark/pcug-protocol-v1.json")


def test_development_benchmark_is_reproducible() -> None:
    protocol = load_pcug_protocol(PROTOCOL_PATH)
    first = run_pcug_benchmark(protocol, split="development")
    second = run_pcug_benchmark(protocol, split="development")
    assert encode_records(first.records) == encode_records(second.records)
    assert first.metrics == second.metrics


def test_benchmark_keeps_unknown_separate_from_complete() -> None:
    run = run_pcug_benchmark(load_pcug_protocol(PROTOCOL_PATH), split="development")
    record = next(
        item
        for item in run.records
        if item.task == "audit" and item.fault == "unknown_model" and item.method == "pcug"
    )
    assert record.verdict == "UNVERIFIED"
    assert not record.false_complete


def test_pcug_has_no_false_complete_in_registered_simulator() -> None:
    run = run_pcug_benchmark(load_pcug_protocol(PROTOCOL_PATH), split="development")
    assert run.metrics["audit:pcug"].false_complete_rate == 0
    assert run.metrics["audit:receipt_only"].false_complete_rate is not None
    assert run.metrics["audit:receipt_only"].false_complete_rate > 0


def test_exact_planner_cost_never_exceeds_delete_all() -> None:
    run = run_pcug_benchmark(load_pcug_protocol(PROTOCOL_PATH), split="development")
    grouped: dict[tuple[int, str], dict[str, int]] = {}
    for record in run.records:
        if record.task != "planning":
            continue
        grouped.setdefault((record.seed, record.adapter), {})[record.method] = record.cost
        assert record.verdict == "COMPLETE"
    for methods in grouped.values():
        assert methods["exact_cdc"] <= methods["delete_all"]


def test_uncommitted_holdout_cannot_run() -> None:
    protocol = load_pcug_protocol(PROTOCOL_PATH)
    with pytest.raises(RuntimeError, match="not committed"):
        run_pcug_benchmark(protocol, split="holdout")
