from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, cast

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from erasemap.cdc import evaluate_actions
from erasemap.pcug_domain import (
    CDCAction,
    CDCProtocol,
    ChannelDecision,
    ChannelResult,
    EdgeKind,
    EdgeState,
    FeasibilityReport,
    PCUGEdge,
    PCUGGraph,
    PCUGNode,
    PCUGVerdict,
    Transition,
    TransitionTarget,
)

SCHEMA_VERSION = "erasemap-pcug-proof-v1"

_BUNDLE_FIELDS = frozenset(
    {
        "schema_version",
        "key_id",
        "nonce",
        "request_id",
        "pre_graph_root",
        "protocol_hash",
        "pre_graph",
        "protocol",
        "selected_actions",
        "challenge_commitment",
        "challenge_opening",
        "declared_verdict",
        "declared_total_cost",
        "producer_revision",
        "previous_bundle_hash",
        "signature",
    }
)


def canonical_json(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def commitment(payload: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def challenge_commitment(opening: tuple[str, ...]) -> str:
    return commitment({"domain": "erasemap-pcug-challenge-v1", "opening": list(opening)})


def _channel_payload(channel: ChannelResult) -> dict[str, object]:
    return {
        "decision": channel.decision.value,
        "evidence_id": channel.evidence_id,
        "mandatory": channel.mandatory,
        "name": channel.name,
        "stratum": channel.stratum,
        "threshold": channel.threshold,
        "upper_bound": channel.upper_bound,
        "value": channel.value,
    }


def _node_payload(node: PCUGNode) -> dict[str, object]:
    return {
        "active_sink": node.active_sink,
        "display_name": node.display_name,
        "evidence_id": node.evidence_id,
        "id": node.id,
        "kind": node.kind,
        "state": node.state.value,
        "subject_id": node.subject_id,
    }


def _edge_payload(edge: PCUGEdge) -> dict[str, object]:
    return {
        "evidence_id": edge.evidence_id,
        "id": edge.id,
        "kind": edge.kind.value,
        "request_scoped": edge.request_scoped,
        "source_id": edge.source_id,
        "state": edge.state.value,
        "subject_id": edge.subject_id,
        "target_id": edge.target_id,
    }


def graph_payload(graph: PCUGGraph) -> dict[str, object]:
    return {
        "channel_results": [
            _channel_payload(channel)
            for channel in sorted(graph.channel_results, key=lambda item: (item.name, item.stratum))
        ],
        "edges": [_edge_payload(edge) for edge in sorted(graph.edges, key=lambda item: item.id)],
        "nodes": [_node_payload(node) for node in sorted(graph.nodes, key=lambda item: item.id)],
    }


def protocol_payload(protocol: CDCProtocol) -> dict[str, object]:
    return {
        "mandatory_channels": sorted(protocol.mandatory_channels),
        "max_exact_actions": protocol.max_exact_actions,
        "request_id": protocol.request_id,
        "sink_ids": sorted(protocol.sink_ids),
        "source_ids": sorted(protocol.source_ids),
        "subject_id": protocol.subject_id,
    }


def _transition_payload(transition: Transition) -> dict[str, object]:
    return {
        "evidence_id": transition.evidence_id,
        "result_state": transition.result_state.value,
        "target": transition.target.value,
        "target_id": transition.target_id,
        "verified": transition.verified,
    }


def _action_payload(action: CDCAction) -> dict[str, object]:
    return {
        "cost": action.cost,
        "id": action.id,
        "permitted": action.permitted,
        "result_channels": [
            _channel_payload(channel)
            for channel in sorted(
                action.result_channels, key=lambda item: (item.name, item.stratum)
            )
        ],
        "transitions": [
            _transition_payload(transition)
            for transition in sorted(
                action.transitions,
                key=lambda item: (item.target.value, item.target_id),
            )
        ],
    }


@dataclass(frozen=True, slots=True)
class ProofBundle:
    schema_version: str
    key_id: str
    nonce: str
    request_id: str
    pre_graph_root: str
    protocol_hash: str
    pre_graph: PCUGGraph
    protocol: CDCProtocol
    selected_actions: tuple[CDCAction, ...]
    challenge_commitment: str
    challenge_opening: tuple[str, ...]
    declared_verdict: PCUGVerdict
    declared_total_cost: int
    producer_revision: str
    previous_bundle_hash: str
    signature: bytes

    def __post_init__(self) -> None:
        required = (
            self.schema_version,
            self.key_id,
            self.nonce,
            self.request_id,
            self.pre_graph_root,
            self.protocol_hash,
            self.challenge_commitment,
            self.producer_revision,
        )
        if not all(required):
            raise ValueError("proof bundle required field is empty")
        if self.declared_total_cost < 0:
            raise ValueError("declared total cost cannot be negative")
        action_ids = [action.id for action in self.selected_actions]
        if action_ids != sorted(action_ids) or len(action_ids) != len(set(action_ids)):
            raise ValueError("selected actions must be unique and canonical")

    def payload(self) -> dict[str, object]:
        return {
            "challenge_commitment": self.challenge_commitment,
            "challenge_opening": list(self.challenge_opening),
            "declared_total_cost": self.declared_total_cost,
            "declared_verdict": self.declared_verdict.value,
            "key_id": self.key_id,
            "nonce": self.nonce,
            "pre_graph": graph_payload(self.pre_graph),
            "pre_graph_root": self.pre_graph_root,
            "previous_bundle_hash": self.previous_bundle_hash,
            "producer_revision": self.producer_revision,
            "protocol": protocol_payload(self.protocol),
            "protocol_hash": self.protocol_hash,
            "request_id": self.request_id,
            "schema_version": self.schema_version,
            "selected_actions": [_action_payload(action) for action in self.selected_actions],
        }

    def serialized(self) -> dict[str, object]:
        return {**self.payload(), "signature": self.signature.hex()}


@dataclass(frozen=True, slots=True)
class BundleCheck:
    valid: bool
    reason: str
    replayed_report: FeasibilityReport | None


def issue_bundle(
    private_key: Ed25519PrivateKey,
    *,
    key_id: str,
    nonce: str,
    graph: PCUGGraph,
    protocol: CDCProtocol,
    actions: tuple[CDCAction, ...],
    challenge_opening: tuple[str, ...],
    producer_revision: str,
    previous_bundle_hash: str = "",
    declared_verdict: PCUGVerdict | None = None,
    challenge_commitment_override: str | None = None,
) -> ProofBundle:
    ordered_actions = tuple(sorted(actions, key=lambda item: item.id))
    report = evaluate_actions(graph, protocol, ordered_actions)
    bundle = ProofBundle(
        schema_version=SCHEMA_VERSION,
        key_id=key_id,
        nonce=nonce,
        request_id=protocol.request_id,
        pre_graph_root=commitment(graph_payload(graph)),
        protocol_hash=commitment(protocol_payload(protocol)),
        pre_graph=graph,
        protocol=protocol,
        selected_actions=ordered_actions,
        challenge_commitment=challenge_commitment_override
        or challenge_commitment(challenge_opening),
        challenge_opening=challenge_opening,
        declared_verdict=declared_verdict or report.verdict,
        declared_total_cost=sum(action.cost for action in ordered_actions),
        producer_revision=producer_revision,
        previous_bundle_hash=previous_bundle_hash,
        signature=b"",
    )
    return replace(bundle, signature=private_key.sign(canonical_json(bundle.payload())))


def encode_bundle(bundle: ProofBundle) -> str:
    return canonical_json(bundle.serialized()).decode()


def _object(value: object, location: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{location} must be an object with string keys")
    return cast(Mapping[str, Any], value)


def _array(value: object, location: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{location} must be an array")
    return cast(list[object], value)


def _fields(payload: Mapping[str, Any], expected: frozenset[str], location: str) -> None:
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


def _int(payload: Mapping[str, Any], key: str, location: str) -> int:
    value = payload[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{location}.{key} must be an integer")
    return value


def _float(payload: Mapping[str, Any], key: str, location: str) -> float:
    value = payload[key]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{location}.{key} must be a number")
    return float(value)


def _strings(value: object, location: str) -> tuple[str, ...]:
    values = _array(value, location)
    if not all(isinstance(item, str) for item in values):
        raise ValueError(f"{location} must contain strings")
    return tuple(cast(list[str], values))


_CHANNEL_FIELDS = frozenset(
    {
        "decision",
        "evidence_id",
        "mandatory",
        "name",
        "stratum",
        "threshold",
        "upper_bound",
        "value",
    }
)
_NODE_FIELDS = frozenset(
    {"active_sink", "display_name", "evidence_id", "id", "kind", "state", "subject_id"}
)
_EDGE_FIELDS = frozenset(
    {
        "evidence_id",
        "id",
        "kind",
        "request_scoped",
        "source_id",
        "state",
        "subject_id",
        "target_id",
    }
)
_TRANSITION_FIELDS = frozenset({"evidence_id", "result_state", "target", "target_id", "verified"})
_ACTION_FIELDS = frozenset({"cost", "id", "permitted", "result_channels", "transitions"})
_GRAPH_FIELDS = frozenset({"channel_results", "edges", "nodes"})
_PROTOCOL_FIELDS = frozenset(
    {
        "mandatory_channels",
        "max_exact_actions",
        "request_id",
        "sink_ids",
        "source_ids",
        "subject_id",
    }
)


def _channel_from_payload(value: object, location: str) -> ChannelResult:
    item = _object(value, location)
    _fields(item, _CHANNEL_FIELDS, location)
    return ChannelResult(
        name=_string(item, "name", location),
        value=_float(item, "value", location),
        upper_bound=_float(item, "upper_bound", location),
        threshold=_float(item, "threshold", location),
        decision=ChannelDecision(_string(item, "decision", location)),
        mandatory=_bool(item, "mandatory", location),
        evidence_id=_string(item, "evidence_id", location),
        stratum=_string(item, "stratum", location),
    )


def _graph_from_payload(value: object) -> PCUGGraph:
    payload = _object(value, "bundle.pre_graph")
    _fields(payload, _GRAPH_FIELDS, "bundle.pre_graph")
    nodes: list[PCUGNode] = []
    for index, raw in enumerate(_array(payload["nodes"], "bundle.pre_graph.nodes")):
        location = f"bundle.pre_graph.nodes[{index}]"
        item = _object(raw, location)
        _fields(item, _NODE_FIELDS, location)
        nodes.append(
            PCUGNode(
                id=_string(item, "id", location),
                kind=_string(item, "kind", location),
                subject_id=_string(item, "subject_id", location),
                state=EdgeState(_string(item, "state", location)),
                active_sink=_bool(item, "active_sink", location),
                evidence_id=_string(item, "evidence_id", location),
                display_name=_string(item, "display_name", location),
            )
        )
    edges: list[PCUGEdge] = []
    for index, raw in enumerate(_array(payload["edges"], "bundle.pre_graph.edges")):
        location = f"bundle.pre_graph.edges[{index}]"
        item = _object(raw, location)
        _fields(item, _EDGE_FIELDS, location)
        edges.append(
            PCUGEdge(
                source_id=_string(item, "source_id", location),
                target_id=_string(item, "target_id", location),
                kind=EdgeKind(_string(item, "kind", location)),
                state=EdgeState(_string(item, "state", location)),
                request_scoped=_bool(item, "request_scoped", location),
                subject_id=_string(item, "subject_id", location),
                evidence_id=_string(item, "evidence_id", location),
                id=_string(item, "id", location),
            )
        )
    channels = tuple(
        _channel_from_payload(raw, f"bundle.pre_graph.channel_results[{index}]")
        for index, raw in enumerate(
            _array(payload["channel_results"], "bundle.pre_graph.channel_results")
        )
    )
    return PCUGGraph(tuple(nodes), tuple(edges), channels)


def _protocol_from_payload(value: object) -> CDCProtocol:
    payload = _object(value, "bundle.protocol")
    _fields(payload, _PROTOCOL_FIELDS, "bundle.protocol")
    return CDCProtocol(
        request_id=_string(payload, "request_id", "bundle.protocol"),
        subject_id=_string(payload, "subject_id", "bundle.protocol"),
        source_ids=frozenset(_strings(payload["source_ids"], "bundle.protocol.source_ids")),
        sink_ids=frozenset(_strings(payload["sink_ids"], "bundle.protocol.sink_ids")),
        mandatory_channels=frozenset(
            _strings(payload["mandatory_channels"], "bundle.protocol.mandatory_channels")
        ),
        max_exact_actions=_int(payload, "max_exact_actions", "bundle.protocol"),
    )


def _action_from_payload(value: object, location: str) -> CDCAction:
    payload = _object(value, location)
    _fields(payload, _ACTION_FIELDS, location)
    transitions: list[Transition] = []
    for index, raw in enumerate(_array(payload["transitions"], f"{location}.transitions")):
        child = f"{location}.transitions[{index}]"
        item = _object(raw, child)
        _fields(item, _TRANSITION_FIELDS, child)
        transitions.append(
            Transition(
                target_id=_string(item, "target_id", child),
                result_state=EdgeState(_string(item, "result_state", child)),
                evidence_id=_string(item, "evidence_id", child),
                target=TransitionTarget(_string(item, "target", child)),
                verified=_bool(item, "verified", child),
            )
        )
    channels = tuple(
        _channel_from_payload(raw, f"{location}.result_channels[{index}]")
        for index, raw in enumerate(
            _array(payload["result_channels"], f"{location}.result_channels")
        )
    )
    return CDCAction(
        id=_string(payload, "id", location),
        cost=_int(payload, "cost", location),
        transitions=tuple(transitions),
        permitted=_bool(payload, "permitted", location),
        result_channels=channels,
    )


def decode_bundle(raw: str) -> ProofBundle:
    try:
        decoded: object = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON: {error.msg}") from error
    payload = _object(decoded, "bundle")
    _fields(payload, _BUNDLE_FIELDS, "bundle")
    signature_text = _string(payload, "signature", "bundle")
    try:
        signature = bytes.fromhex(signature_text)
    except ValueError as error:
        raise ValueError("bundle.signature must be hexadecimal") from error
    actions = tuple(
        _action_from_payload(raw_action, f"bundle.selected_actions[{index}]")
        for index, raw_action in enumerate(
            _array(payload["selected_actions"], "bundle.selected_actions")
        )
    )
    return ProofBundle(
        schema_version=_string(payload, "schema_version", "bundle"),
        key_id=_string(payload, "key_id", "bundle"),
        nonce=_string(payload, "nonce", "bundle"),
        request_id=_string(payload, "request_id", "bundle"),
        pre_graph_root=_string(payload, "pre_graph_root", "bundle"),
        protocol_hash=_string(payload, "protocol_hash", "bundle"),
        pre_graph=_graph_from_payload(payload["pre_graph"]),
        protocol=_protocol_from_payload(payload["protocol"]),
        selected_actions=actions,
        challenge_commitment=_string(payload, "challenge_commitment", "bundle"),
        challenge_opening=_strings(payload["challenge_opening"], "bundle.challenge_opening"),
        declared_verdict=PCUGVerdict(_string(payload, "declared_verdict", "bundle")),
        declared_total_cost=_int(payload, "declared_total_cost", "bundle"),
        producer_revision=_string(payload, "producer_revision", "bundle"),
        previous_bundle_hash=_string(payload, "previous_bundle_hash", "bundle"),
        signature=signature,
    )


def check_bundle(
    bundle: ProofBundle,
    trust_store: Mapping[str, Ed25519PublicKey],
) -> BundleCheck:
    if bundle.schema_version != SCHEMA_VERSION:
        return BundleCheck(False, "unsupported schema version", None)
    public_key = trust_store.get(bundle.key_id)
    if public_key is None:
        return BundleCheck(False, "untrusted key id", None)
    try:
        public_key.verify(bundle.signature, canonical_json(bundle.payload()))
    except (InvalidSignature, ValueError):
        return BundleCheck(False, "invalid signature", None)
    if challenge_commitment(bundle.challenge_opening) != bundle.challenge_commitment:
        return BundleCheck(False, "challenge commitment mismatch", None)
    if commitment(graph_payload(bundle.pre_graph)) != bundle.pre_graph_root:
        return BundleCheck(False, "pre-graph commitment mismatch", None)
    if commitment(protocol_payload(bundle.protocol)) != bundle.protocol_hash:
        return BundleCheck(False, "protocol commitment mismatch", None)
    if bundle.request_id != bundle.protocol.request_id:
        return BundleCheck(False, "request id mismatch", None)
    replayed = evaluate_actions(bundle.pre_graph, bundle.protocol, bundle.selected_actions)
    if replayed.verdict is not bundle.declared_verdict:
        return BundleCheck(
            False,
            "declared verdict differs from replayed verdict",
            replayed,
        )
    expected_cost = sum(action.cost for action in bundle.selected_actions)
    if expected_cost != bundle.declared_total_cost:
        return BundleCheck(False, "declared cost differs from replayed cost", replayed)
    return BundleCheck(True, "verified", replayed)
