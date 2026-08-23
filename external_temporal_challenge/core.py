from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from erasemap.temporal import (
    RSEProtocol,
    StabilizationControl,
    TemporalTransition,
    TransitionCoverage,
    TransitionObservation,
    evaluate_rse,
    exact_stabilization_cut,
)

SUITE_SCHEMA = "erasemap-external-temporal-suite-v1"
PUBLIC_SCHEMA = "erasemap-external-temporal-public-v1"
ANSWERS_SCHEMA = "erasemap-external-temporal-answers-v1"
PREDICTIONS_SCHEMA = "erasemap-external-temporal-predictions-v1"
MANIFEST_SCHEMA = "erasemap-external-temporal-manifest-v1"
MAX_CASES = 2_000
MAX_FACTS = 256
MAX_TRANSITIONS = 64
MAX_CONTROLS = 16
AUTHOR_FIELDS = {
    "name",
    "organization",
    "public_identifier",
    "independently_authored",
    "external_repository",
    "external_commit",
}


def canonical_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def read_object(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _strings(value: Any, label: str) -> frozenset[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{label} must be an array of non-empty strings")
    return frozenset(value)


def validate_public_case(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("each temporal case must be an object")
    required = {
        "case_id",
        "family",
        "initial_facts",
        "residual_facts",
        "transitions",
        "coverage",
        "controls",
    }
    if set(raw) != required:
        raise ValueError("temporal case fields do not match the public schema")
    if not isinstance(raw["case_id"], str) or not raw["case_id"]:
        raise ValueError("case_id is required")
    if not isinstance(raw["family"], str) or not raw["family"]:
        raise ValueError("case family is required")
    initial = _strings(raw["initial_facts"], "initial_facts")
    residual = _strings(raw["residual_facts"], "residual_facts")
    if not residual:
        raise ValueError("residual_facts cannot be empty")
    if len(initial | residual) > MAX_FACTS:
        raise ValueError("temporal case fact limit exceeded")

    transitions_raw = raw["transitions"]
    if not isinstance(transitions_raw, list) or not 1 <= len(transitions_raw) <= MAX_TRANSITIONS:
        raise ValueError("temporal transition count is outside the allowed range")
    transition_ids: set[str] = set()
    for item in transitions_raw:
        if not isinstance(item, dict) or set(item) != {
            "id",
            "requires",
            "adds",
            "removes",
            "forbids",
        }:
            raise ValueError("invalid temporal transition fields")
        transition = TemporalTransition(
            str(item["id"]),
            _strings(item["requires"], "transition requires"),
            _strings(item["adds"], "transition adds"),
            _strings(item["removes"], "transition removes"),
            _strings(item["forbids"], "transition forbids"),
        )
        if transition.id in transition_ids:
            raise ValueError("duplicate temporal transition id")
        transition_ids.add(transition.id)

    coverage = raw["coverage"]
    if not isinstance(coverage, dict) or set(coverage) != {
        "required_sensor_ids",
        "observations",
    }:
        raise ValueError("invalid transition coverage fields")
    observations = coverage["observations"]
    if not isinstance(observations, list):
        raise ValueError("coverage observations must be an array")
    TransitionCoverage(
        _strings(coverage["required_sensor_ids"], "required sensor ids"),
        tuple(
            TransitionObservation(
                str(item["id"]),
                str(item["sensor_id"]),
                str(item["transition_id"]),
                bool(item["verified"]),
            )
            for item in observations
            if isinstance(item, dict)
            and set(item) == {"id", "sensor_id", "transition_id", "verified"}
        ),
    )
    if len(observations) != sum(
        isinstance(item, dict)
        and set(item) == {"id", "sensor_id", "transition_id", "verified"}
        for item in observations
    ):
        raise ValueError("invalid transition observation fields")

    controls = raw["controls"]
    if not isinstance(controls, list) or len(controls) > MAX_CONTROLS:
        raise ValueError("temporal control limit exceeded")
    control_ids: set[str] = set()
    for item in controls:
        if not isinstance(item, dict) or set(item) != {
            "id",
            "cost",
            "guarded_transition_ids",
            "permitted",
        }:
            raise ValueError("invalid stabilization control fields")
        control = StabilizationControl(
            str(item["id"]),
            int(item["cost"]),
            _strings(item["guarded_transition_ids"], "guarded transition ids"),
            bool(item["permitted"]),
        )
        if control.id in control_ids:
            raise ValueError("duplicate stabilization control id")
        if not control.guarded_transition_ids <= transition_ids:
            raise ValueError("control guards an unknown transition")
        control_ids.add(control.id)
    return raw


def validate_public_suite(payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    if payload.get("schema_version") != PUBLIC_SCHEMA:
        raise ValueError("unsupported public temporal suite schema")
    if set(payload) != {"schema_version", "author", "cases"}:
        raise ValueError("public temporal suite fields do not match schema")
    author = payload["author"]
    if not isinstance(author, dict) or set(author) != AUTHOR_FIELDS:
        raise ValueError("temporal suite author metadata does not match schema")
    for field in AUTHOR_FIELDS - {"independently_authored"}:
        if not isinstance(author[field], str) or not author[field].strip():
            raise ValueError(f"temporal suite author {field} is required")
    if not isinstance(author["independently_authored"], bool):
        raise ValueError("independently_authored must be boolean")
    if re.fullmatch(r"[0-9a-fA-F]{7,64}", author["external_commit"]) is None:
        raise ValueError("external_commit must be a hexadecimal revision")
    cases = payload["cases"]
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise ValueError("temporal suite case count is outside the allowed range")
    validated = tuple(validate_public_case(item) for item in cases)
    ids = [item["case_id"] for item in validated]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate temporal case id")
    return validated


def predict_case(raw: dict[str, Any]) -> dict[str, Any]:
    transitions = tuple(
        TemporalTransition(
            item["id"],
            frozenset(item["requires"]),
            frozenset(item["adds"]),
            frozenset(item["removes"]),
            frozenset(item["forbids"]),
        )
        for item in raw["transitions"]
    )
    coverage = TransitionCoverage(
        frozenset(raw["coverage"]["required_sensor_ids"]),
        tuple(
            TransitionObservation(
                item["id"],
                item["sensor_id"],
                item["transition_id"],
                item["verified"],
            )
            for item in raw["coverage"]["observations"]
        ),
    )
    protocol = RSEProtocol(
        f"external:{raw['case_id']}", frozenset(raw["residual_facts"])
    )
    controls = tuple(
        StabilizationControl(
            item["id"],
            item["cost"],
            frozenset(item["guarded_transition_ids"]),
            item["permitted"],
        )
        for item in raw["controls"]
    )
    initial = frozenset(raw["initial_facts"])
    report = evaluate_rse(initial, transitions, coverage, protocol)
    plan = exact_stabilization_cut(initial, transitions, coverage, protocol, controls)
    return {
        "case_id": raw["case_id"],
        "verdict": report.verdict.value,
        "coverage_complete": report.coverage.complete,
        "shortest_witness": list(report.shortest_witness or ()),
        "control_ids": list(plan.control_ids),
        "minimum_cost": plan.total_cost if plan.complete else None,
    }
