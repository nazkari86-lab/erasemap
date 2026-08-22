from erasemap.pcug_stress import run_stress_benchmark


def test_pcug_catches_edge_and_channel_failures_missed_by_typed_nodes() -> None:
    records = run_stress_benchmark()
    noncomplete = [record for record in records if record.truth != "COMPLETE"]
    assert len(records) == 100
    assert len(noncomplete) == 75
    assert sum(record.pcug == "COMPLETE" for record in noncomplete) == 0
    assert sum(record.typed_node_audit == "COMPLETE" for record in noncomplete) == 75
    assert all(record.pcug == record.truth for record in records)
