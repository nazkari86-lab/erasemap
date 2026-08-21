from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, cast

from erasemap.domain import Artifact, ArtifactState, ArtifactType, Edge, EdgeType, ErasureGraph

_TOP_FIELDS = frozenset({"nodes", "edges"})
_NODE_FIELDS = frozenset(
    {
        "id",
        "subject_id",
        "type",
        "state",
        "active_sink",
        "purpose",
        "commitment",
        "evidence_id",
    }
)
_EDGE_FIELDS = frozenset({"source_id", "target_id", "type", "cross_subject"})


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def graph_to_json(graph: ErasureGraph) -> str:
    nodes = [
        {
            "active_sink": node.active_sink,
            "commitment": node.commitment,
            "evidence_id": node.evidence_id,
            "id": node.id,
            "purpose": node.purpose,
            "state": node.state.value,
            "subject_id": node.subject_id,
            "type": node.type.value,
        }
        for node in sorted(graph.nodes.values(), key=lambda item: item.id)
    ]
    edges = [
        {
            "cross_subject": edge.cross_subject,
            "source_id": edge.source_id,
            "target_id": edge.target_id,
            "type": edge.type.value,
        }
        for edge in sorted(
            graph.edges,
            key=lambda item: (item.source_id, item.target_id, item.type.value),
        )
    ]
    return _canonical_json({"edges": edges, "nodes": nodes})


def _object(value: object, location: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be an object")
    if not all(isinstance(key, str) for key in value):
        raise ValueError(f"{location} keys must be strings")
    return cast(Mapping[str, Any], value)


def _array(value: object, location: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{location} must be an array")
    return cast(list[object], value)


def _check_fields(payload: Mapping[str, Any], expected: frozenset[str], location: str) -> None:
    extras = sorted(set(payload) - expected)
    if extras:
        raise ValueError(f"unknown field at {location}: {extras[0]}")
    missing = sorted(expected - set(payload))
    if missing:
        raise ValueError(f"missing field at {location}: {missing[0]}")


def _string(payload: Mapping[str, Any], key: str, location: str) -> str:
    value = payload[key]
    if not isinstance(value, str):
        raise ValueError(f"{location}.{key} must be a string")
    return value


def _bool(payload: Mapping[str, Any], key: str, location: str) -> bool:
    value = payload[key]
    if not isinstance(value, bool):
        raise ValueError(f"{location}.{key} must be a boolean")
    return value


def graph_from_json(raw: str) -> ErasureGraph:
    try:
        decoded: object = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON: {error.msg}") from error

    payload = _object(decoded, "graph")
    _check_fields(payload, _TOP_FIELDS, "graph")
    nodes: dict[str, Artifact] = {}
    for index, value in enumerate(_array(payload["nodes"], "graph.nodes")):
        location = f"graph.nodes[{index}]"
        item = _object(value, location)
        _check_fields(item, _NODE_FIELDS, location)
        evidence_value = item["evidence_id"]
        if evidence_value is not None and not isinstance(evidence_value, str):
            raise ValueError(f"{location}.evidence_id must be a string or null")
        node = Artifact(
            id=_string(item, "id", location),
            subject_id=_string(item, "subject_id", location),
            type=ArtifactType(_string(item, "type", location)),
            state=ArtifactState(_string(item, "state", location)),
            active_sink=_bool(item, "active_sink", location),
            purpose=_string(item, "purpose", location),
            commitment=_string(item, "commitment", location),
            evidence_id=evidence_value,
        )
        if node.id in nodes:
            raise ValueError(f"duplicate node id: {node.id}")
        nodes[node.id] = node

    edges: list[Edge] = []
    for index, value in enumerate(_array(payload["edges"], "graph.edges")):
        location = f"graph.edges[{index}]"
        item = _object(value, location)
        _check_fields(item, _EDGE_FIELDS, location)
        edges.append(
            Edge(
                source_id=_string(item, "source_id", location),
                target_id=_string(item, "target_id", location),
                type=EdgeType(_string(item, "type", location)),
                cross_subject=_bool(item, "cross_subject", location),
            )
        )
    return ErasureGraph(nodes=nodes, edges=tuple(edges))
