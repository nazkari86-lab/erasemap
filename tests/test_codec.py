import pytest

from erasemap.codec import graph_from_json, graph_to_json
from tests.factories import simple_graph


def test_graph_json_is_canonical_and_round_trips() -> None:
    graph = simple_graph()
    encoded = graph_to_json(graph)
    assert encoded == graph_to_json(graph_from_json(encoded))
    assert " " not in encoded


def test_decoder_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError, match="unknown field"):
        graph_from_json('{"nodes":[],"edges":[],"surprise":1}')


def test_decoder_rejects_unknown_nested_fields() -> None:
    raw = (
        '{"edges":[],"nodes":[{"active_sink":false,"commitment":"",'
        '"evidence_id":null,"id":"a","purpose":"","state":"ACTIVE",'
        '"subject_id":"s","type":"SOURCE_RECORD","extra":true}]}'
    )
    with pytest.raises(ValueError, match="unknown field"):
        graph_from_json(raw)
