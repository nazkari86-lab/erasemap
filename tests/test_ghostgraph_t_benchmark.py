from __future__ import annotations

from collections import Counter

from erasemap.ghostgraph import predict_trace
from erasemap.ghostgraph_action import action_signature, assess_action_identifiability
from erasemap.ghostgraph_t_benchmark import experiments, generate_cases


def test_generator_freezes_300_cases_across_four_disjoint_splits() -> None:
    cases = generate_cases()

    assert len(cases) == 300
    assert Counter(item.split for item in cases) == {
        "instance-held-out": 120,
        "composition-held-out": 80,
        "family-held-out": 50,
        "temporal-shift-held-out": 50,
    }
    assert len({item.case_id for item in cases}) == 300


def test_in_model_truths_match_one_catalogue_action_and_trace_vector() -> None:
    probes = experiments()
    for case in generate_cases():
        truth_vector = tuple(predict_trace(case.truth, item).bits for item in probes)
        matches = tuple(
            hypothesis
            for hypothesis in case.catalogue
            if tuple(predict_trace(hypothesis, item).bits for item in probes) == truth_vector
        )
        if case.expected == "ACTION_IDENTIFIED":
            assert matches
            assert {action_signature(item) for item in matches} == {
                action_signature(case.truth)
            }
        else:
            assert not matches


def test_every_frozen_catalogue_is_action_identifiable() -> None:
    probes = experiments()
    unique_catalogues = {
        tuple(item.graph_id for item in case.catalogue): case.catalogue
        for case in generate_cases()
    }

    assert len(unique_catalogues) == 3
    assert all(
        assess_action_identifiability(catalogue, probes).identifiable
        for catalogue in unique_catalogues.values()
    )
