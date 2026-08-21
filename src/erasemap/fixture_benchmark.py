from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from erasemap.audit import audit_subject
from erasemap.codec import graph_from_json
from erasemap.domain import AuditStatus, Evidence, EvidenceKind

FIXTURE_SCHEMA = "erasemap-manual-pipeline-fixtures-v1"


def _evidence(payload: dict[str, Any]) -> Evidence:
    return Evidence(
        id=str(payload["id"]),
        artifact_id=str(payload["artifact_id"]),
        kind=EvidenceKind(str(payload["kind"])),
        valid_signature=bool(payload.get("valid_signature", False)),
        commitment=str(payload.get("commitment", "")),
        observed_absent=bool(payload.get("observed_absent", False)),
        issued_epoch=int(payload.get("issued_epoch", 0)),
        expires_epoch=(
            int(payload["expires_epoch"])
            if payload.get("expires_epoch") is not None
            else None
        ),
        metadata=tuple(
            (str(key), str(value)) for key, value in payload.get("metadata", [])
        ),
    )


def run_fixture_suite(path: str | Path) -> dict[str, Any]:
    raw = Path(path).read_bytes()
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("manual fixture suite must be an object")
    if payload.get("schema_version") != FIXTURE_SCHEMA:
        raise ValueError("unsupported manual fixture schema")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("manual fixture suite requires at least one case")
    results: list[dict[str, Any]] = []
    seen_case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("every manual fixture case must be an object")
        case_id = str(case["id"])
        if case_id in seen_case_ids:
            raise ValueError(f"duplicate manual fixture case id: {case_id}")
        seen_case_ids.add(case_id)
        graph = graph_from_json(json.dumps(case["graph"]))
        evidence: dict[str, Evidence] = {}
        for item_payload in case["evidence"]:
            if not isinstance(item_payload, dict):
                raise ValueError("every evidence entry must be an object")
            item = _evidence(item_payload)
            if item.artifact_id in evidence:
                raise ValueError(f"duplicate evidence for artifact: {item.artifact_id}")
            evidence[item.artifact_id] = item
        result = audit_subject(
            graph,
            evidence,
            str(case["subject_id"]),
            int(case["now_epoch"]),
        )
        residual_terminal_ids = sorted(path.node_ids[-1] for path in result.residual_paths)
        invalid_evidence_ids = sorted(
            artifact_id for artifact_id, check in result.evidence_checks if not check.valid
        )
        expected = case["expected"]
        checks = {
            "invalid_evidence_ids": invalid_evidence_ids
            == sorted(str(value) for value in expected["invalid_evidence_ids"]),
            "residual_terminal_ids": residual_terminal_ids
            == sorted(str(value) for value in expected["residual_terminal_ids"]),
            "status": result.status is AuditStatus(str(expected["status"])),
        }
        results.append(
            {
                "case_id": case_id,
                "checks": checks,
                "invalid_evidence_ids": invalid_evidence_ids,
                "passed": all(checks.values()),
                "residual_terminal_ids": residual_terminal_ids,
                "status": result.status.value,
            }
        )
    return {
        "authorship": str(payload["authorship"]),
        "cases": results,
        "fixture_sha256": hashlib.sha256(raw).hexdigest(),
        "generator_independent": bool(payload["generator_independent"]),
        "passed": all(result["passed"] for result in results),
        "schema_version": FIXTURE_SCHEMA,
        "total": len(results),
    }
