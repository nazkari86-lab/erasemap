from pathlib import Path


def test_ghostgraph_formal_contract_has_no_unchecked_escape() -> None:
    source = Path("EraseMapFormal/GhostGraph.lean").read_text()

    for theorem in (
        "true_graph_survives",
        "singleton_discovery_sound",
        "inseparable_class_fail_closed",
        "selected_query_minimax",
    ):
        assert f"theorem {theorem}" in source
    lowered = source.lower()
    assert "sorry" not in lowered
    assert "admit" not in lowered
    assert "axiom " not in lowered
