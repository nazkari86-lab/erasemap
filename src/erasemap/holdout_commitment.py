from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from erasemap.external_cases import ExternalCase
from erasemap.source_lock import canonical_json

COMMITMENT_SCHEMA = "erasemap-source-locked-holdout-commitment-v1"


def digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class PublicCase:
    id: str
    family: str
    mapping_ids: tuple[str, ...]
    case_commitment: str
    case: ExternalCase


def _graph_payload(case: ExternalCase) -> dict[str, object]:
    return {
        "actions": [action.id for action in case.actions],
        "edges": [
            {
                "id": edge.id,
                "kind": edge.kind.value,
                "source": edge.source_id,
                "state": edge.state.value,
                "target": edge.target_id,
            }
            for edge in case.graph.edges
        ],
        "family": case.family,
        "id": case.id,
        "mapping_ids": list(case.mapping_ids),
        "nodes": [
            {"id": node.id, "kind": node.kind, "state": node.state.value}
            for node in case.graph.nodes
        ],
        "request_id": case.protocol.request_id,
    }


def public_cases(cases: tuple[ExternalCase, ...]) -> tuple[PublicCase, ...]:
    return tuple(
        PublicCase(
            id=case.id,
            family=case.family,
            mapping_ids=case.mapping_ids,
            case_commitment=digest(_graph_payload(case)),
            case=case,
        )
        for case in cases
    )


def answer_payload(case: ExternalCase) -> dict[str, object]:
    return {
        "expected_path": list(case.expected_path) if case.expected_path else None,
        "id": case.id,
        "truth_verdict": case.truth_verdict.value,
    }


def commitment_payload(cases: tuple[ExternalCase, ...], protocol_hash: str) -> dict[str, object]:
    public = public_cases(cases)
    answers = [answer_payload(case) for case in cases]
    return {
        "answer_commitment": digest(answers),
        "case_count": len(cases),
        "cases": [
            {
                "case_commitment": case.case_commitment,
                "family": case.family,
                "id": case.id,
                "mapping_ids": list(case.mapping_ids),
            }
            for case in public
        ],
        "protocol_hash": protocol_hash,
        "schema_version": COMMITMENT_SCHEMA,
    }


def verify_reveal(
    commitment: dict[str, object], cases: tuple[ExternalCase, ...], protocol_hash: str
) -> None:
    expected = commitment_payload(cases, protocol_hash)
    if canonical_json(commitment) != canonical_json(expected):
        raise ValueError("holdout commitment or reveal mismatch")


def create_output_directory(path: str | Path) -> Path:
    output = Path(path)
    output.mkdir(parents=True, exist_ok=False)
    return output


def load_commitment(path: str | Path) -> dict[str, object]:
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict) or value.get("schema_version") != COMMITMENT_SCHEMA:
        raise ValueError("invalid commitment manifest")
    return value
