from __future__ import annotations

from collections import Counter
from pathlib import Path

from erasemap.cdc import evaluate_actions
from erasemap.external_cases import build_source_cases
from erasemap.pcug_domain import PCUGVerdict
from erasemap.source_lock import load_source_manifest


def test_cases_are_heterogeneous_independent_units() -> None:
    cases = build_source_cases(load_source_manifest(Path("benchmark/external-sources-v1.json")))
    assert len(cases) == 125
    assert len({case.id for case in cases}) == 125
    assert Counter(case.family for case in cases) == {
        "identity": 25,
        "ml": 25,
        "provenance": 25,
        "recovery": 25,
        "search": 25,
    }
    assert len({tuple(node.kind for node in case.graph.nodes) for case in cases}) == 5


def test_truth_is_constructed_without_calling_auditor() -> None:
    cases = build_source_cases(load_source_manifest(Path("benchmark/external-sources-v1.json")))
    counts = Counter(case.truth_verdict for case in cases)
    assert counts == {
        PCUGVerdict.COMPLETE: 25,
        PCUGVerdict.INCOMPLETE: 75,
        PCUGVerdict.UNVERIFIED: 25,
    }
    for case in cases:
        case.protocol.validate_graph(case.graph)
        assert evaluate_actions(case.graph, case.protocol, ()).verdict is case.truth_verdict


def test_complete_action_catalogue_closes_every_case() -> None:
    cases = build_source_cases(load_source_manifest(Path("benchmark/external-sources-v1.json")))
    for case in cases:
        report = evaluate_actions(case.graph, case.protocol, case.actions)
        assert report.verdict is PCUGVerdict.COMPLETE
