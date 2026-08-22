from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from erasemap.audit import audit_subject
from erasemap.codec import graph_from_json
from erasemap.domain import AuditStatus, Evidence, EvidenceKind


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
        metadata=tuple((str(key), str(value)) for key, value in payload.get("metadata", [])),
    )


def predict_public_package(package: dict[str, Any]) -> list[dict[str, object]]:
    if package.get("schema_version") != "erasemap-external-blind-challenge-v1":
        raise ValueError("unsupported public challenge package")
    raw_cases = package.get("public_cases")
    if not isinstance(raw_cases, list):
        raise ValueError("public_cases must be an array")
    predictions: list[dict[str, object]] = []
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise ValueError("public case must be an object")
        case = cast(dict[str, Any], raw_case)
        case_id = str(case.get("id", ""))
        try:
            required = {"evidence", "family", "graph", "id", "now_epoch", "subject_id"}
            if set(case) != required or not case_id:
                raise ValueError("public case schema mismatch")
            graph = graph_from_json(json.dumps(case["graph"]))
            evidence = {
                item.artifact_id: item
                for item in (
                    _evidence(cast(dict[str, Any], payload)) for payload in case["evidence"]
                )
            }
            result = audit_subject(
                graph,
                evidence,
                str(case["subject_id"]),
                int(case["now_epoch"]),
            )
            shortest = (
                list(
                    min(
                        result.residual_paths,
                        key=lambda path: (len(path.node_ids), path.node_ids),
                    ).node_ids
                )
                if result.residual_paths
                else None
            )
            verdict = result.status.value
        except Exception:
            shortest = None
            verdict = AuditStatus.UNVERIFIED.value
        predictions.append({"id": case_id, "shortest_path": shortest, "verdict": verdict})
    return sorted(predictions, key=lambda item: str(item["id"]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run frozen EraSeMap on a blinded public package")
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    package = json.loads(args.package.read_text())
    predictions = predict_public_package(package)
    args.output.write_text(json.dumps(predictions, indent=2, sort_keys=True) + "\n")
    print(f"wrote {len(predictions)} answer-blind predictions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
