from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, cast

SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
REQUIRED = {
    "algorithm_commit",
    "attestation",
    "evidence",
    "independent_evaluator",
    "organization_alias",
    "pilot_id",
    "preregistered_at",
    "schema_version",
    "systems",
}


def validate_manifest(payload: dict[str, Any]) -> dict[str, object]:
    if set(payload) != REQUIRED:
        raise ValueError("pilot manifest schema mismatch")
    if payload["schema_version"] != "erasemap-production-pilot-v1":
        raise ValueError("unsupported pilot schema")
    for field in ("algorithm_commit", "organization_alias", "pilot_id", "preregistered_at"):
        if not isinstance(payload[field], str) or not payload[field]:
            raise ValueError(f"{field} is required")
    evaluator = payload["independent_evaluator"]
    if not isinstance(evaluator, dict) or set(evaluator) != {
        "affiliation",
        "controlled_case_authorship",
        "controlled_labels",
        "name_or_pseudonym",
    }:
        raise ValueError("independent_evaluator schema mismatch")
    if not evaluator["controlled_case_authorship"] or not evaluator["controlled_labels"]:
        raise ValueError("evaluator must control case authorship and labels")
    systems = payload["systems"]
    if not isinstance(systems, list) or len(systems) < 2:
        raise ValueError("at least two independently queried systems are required")
    system_ids: list[str] = []
    for system in systems:
        if not isinstance(system, dict) or set(system) != {
            "connector",
            "data_class",
            "id",
            "synthetic_or_consented",
        }:
            raise ValueError("system schema mismatch")
        if system["synthetic_or_consented"] not in {"synthetic", "consented"}:
            raise ValueError("pilot data must be synthetic or consented")
        system_ids.append(str(system["id"]))
    if len(system_ids) != len(set(system_ids)) or any(not item for item in system_ids):
        raise ValueError("unique non-empty system ids are required")
    evidence = payload["evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("evidence is required")
    artifact_ids: list[str] = []
    for artifact in evidence:
        if not isinstance(artifact, dict) or set(artifact) != {
            "artifact_id",
            "collected_by",
            "contains_personal_data",
            "sha256",
            "stage",
            "system_id",
        }:
            raise ValueError("evidence artifact schema mismatch")
        if artifact["contains_personal_data"] is not False:
            raise ValueError("manifest must not contain personal-data artifacts")
        if artifact["stage"] not in {"before", "after_source_delete", "after_remediation"}:
            raise ValueError("invalid evidence stage")
        if artifact["system_id"] not in system_ids:
            raise ValueError("evidence refers to unknown system")
        if not isinstance(artifact["sha256"], str) or not SHA256.fullmatch(artifact["sha256"]):
            raise ValueError("invalid evidence SHA-256")
        artifact_ids.append(str(artifact["artifact_id"]))
    if len(artifact_ids) != len(set(artifact_ids)):
        raise ValueError("duplicate evidence artifact id")
    attestation = payload["attestation"]
    if not isinstance(attestation, dict) or set(attestation) != {
        "algorithm_unchanged_after_reveal",
        "no_project_author_label_access_before_freeze",
        "signed_by",
    }:
        raise ValueError("attestation schema mismatch")
    passed = bool(
        attestation["algorithm_unchanged_after_reveal"]
        and attestation["no_project_author_label_access_before_freeze"]
        and attestation["signed_by"]
    )
    stages = {str(item["stage"]) for item in cast(list[dict[str, Any]], evidence)}
    return {
        "decision": "READY" if passed and len(stages) == 3 else "INCOMPLETE",
        "evidence_artifacts": len(evidence),
        "evidence_stages": sorted(stages),
        "pilot_id": payload["pilot_id"],
        "schema_version": "erasemap-production-pilot-validation-v1",
        "systems": len(systems),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an EraSeMap production-pilot manifest")
    parser.add_argument("manifest")
    parser.add_argument("--output")
    args = parser.parse_args()
    payload = json.loads(Path(args.manifest).read_text())
    if not isinstance(payload, dict):
        raise ValueError("pilot manifest must be an object")
    result = validate_manifest(payload)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered)
    else:
        print(rendered, end="")
    return 0 if result["decision"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
