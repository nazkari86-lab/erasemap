from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

from erasemap.external_cases import build_source_cases
from erasemap.external_evaluator import evaluate_public_cases, planner_records
from erasemap.holdout_commitment import (
    create_output_directory,
    load_commitment,
    public_cases,
    verify_reveal,
)
from erasemap.holdout_report import score_holdout
from erasemap.source_lock import canonical_json, load_source_manifest


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.write_text(canonical_json(payload) + "\n")


def git_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def family_metrics(result: dict[str, Any], cases_by_id: dict[str, Any]) -> dict[str, object]:
    records = result["records"]
    families = sorted({case.family for case in cases_by_id.values()})
    output: dict[str, object] = {}
    for family in families:
        pcug = [
            item
            for item in records
            if item["method"] == "pcug" and cases_by_id[item["case_id"]].family == family
        ]
        noncomplete = [
            item for item in pcug if cases_by_id[item["case_id"]].truth_verdict.value != "COMPLETE"
        ]
        false_complete = sum(item["verdict"] == "COMPLETE" for item in noncomplete)
        output[family] = {
            "false_complete": false_complete,
            "noncomplete": len(noncomplete),
            "trials": len(pcug),
        }
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default="benchmark/external-sources-v1.json")
    parser.add_argument("--protocol", default="benchmark/pcug-source-locked-holdout-v1.json")
    parser.add_argument(
        "--commitment", default="benchmark/commitments/pcug-source-locked-holdout-v1.json"
    )
    parser.add_argument("--output", default="outputs/source-locked-holdout-v1")
    args = parser.parse_args()
    output = create_output_directory(args.output)
    cases = build_source_cases(load_source_manifest(args.sources))
    protocol_hash = file_hash(Path(args.protocol))
    commitment = load_commitment(args.commitment)
    verify_reveal(commitment, cases, protocol_hash)
    public = public_cases(cases)
    records = evaluate_public_cases(public)
    result = score_holdout(cases, records)
    result["family_metrics"] = family_metrics(result, {case.id: case for case in cases})
    result["claim_boundary"] = (
        "Independently sourced structures; project-authored mappings and execution; no production "
        "Face ID, eGov, bank, school, or government access."
    )
    write_json(output / "evaluation-records.json", [asdict(record) for record in records])
    write_json(output / "planning-records.json", planner_records(public))
    write_json(
        output / "revealed-answers.json",
        [
            {
                "expected_path": list(case.expected_path) if case.expected_path else None,
                "id": case.id,
                "truth_verdict": case.truth_verdict.value,
            }
            for case in cases
        ],
    )
    write_json(output / "summary.json", result)
    provenance = {
        "commitment_hash": file_hash(Path(args.commitment)),
        "evaluator_revision": git_revision(),
        "protocol_hash": protocol_hash,
        "source_manifest_hash": file_hash(Path(args.sources)),
    }
    write_json(output / "PROVENANCE.json", provenance)
    manifest = {
        path.name: file_hash(path)
        for path in sorted(output.iterdir())
        if path.name != "MANIFEST.sha256.json"
    }
    write_json(output / "MANIFEST.sha256.json", manifest)
    print(canonical_json({"decision": result["decision"], "output": str(output)}))
    return 0 if result["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
