from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from external_temporal_challenge.core import (
    ANSWERS_SCHEMA,
    MANIFEST_SCHEMA,
    PREDICTIONS_SCHEMA,
    canonical_bytes,
    digest_bytes,
    read_object,
    validate_public_suite,
)


def score(
    public_path: Path,
    predictions_path: Path,
    answers_path: Path,
    manifest_path: Path,
    protocol_path: Path,
) -> dict[str, Any]:
    public_bytes = public_path.read_bytes()
    answer_bytes = answers_path.read_bytes()
    public = read_object(public_path)
    cases = validate_public_suite(public)
    answers = read_object(answers_path)
    predictions = read_object(predictions_path)
    manifest = read_object(manifest_path)
    protocol = read_object(protocol_path)
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ValueError("unsupported temporal commitment manifest")
    if manifest.get("public_cases_sha256") != digest_bytes(public_bytes):
        raise ValueError("public temporal suite commitment mismatch")
    if manifest.get("answers_sha256") != digest_bytes(answer_bytes):
        raise ValueError("temporal answer commitment mismatch")
    if answers.get("schema_version") != ANSWERS_SCHEMA:
        raise ValueError("unsupported temporal answer schema")
    if predictions.get("schema_version") != PREDICTIONS_SCHEMA:
        raise ValueError("unsupported temporal prediction schema")
    if set(predictions) != {
        "schema_version",
        "public_cases_sha256",
        "tested_erasemap_commit",
        "prediction_created_at_utc",
        "predictions",
    }:
        raise ValueError("temporal prediction fields do not match schema")
    if predictions["public_cases_sha256"] != digest_bytes(public_bytes):
        raise ValueError("temporal predictions are bound to another public suite")
    if re.fullmatch(r"[0-9a-f]{40}", str(predictions["tested_erasemap_commit"])) is None:
        raise ValueError("temporal prediction commit is not a full git revision")
    answer_items = answers.get("answers")
    prediction_items = predictions.get("predictions")
    if not isinstance(answer_items, list) or not isinstance(prediction_items, list):
        raise ValueError("temporal answers and predictions must be arrays")
    if any(
        not isinstance(item, dict)
        or set(item) != {"case_id", "verdict", "minimum_cost"}
        for item in answer_items
    ):
        raise ValueError("temporal answer fields do not match schema")
    prediction_fields = {
        "case_id",
        "verdict",
        "coverage_complete",
        "shortest_witness",
        "control_ids",
        "minimum_cost",
    }
    if any(
        not isinstance(item, dict) or set(item) != prediction_fields
        for item in prediction_items
    ):
        raise ValueError("temporal prediction item fields do not match schema")
    expected_ids = [item["case_id"] for item in cases]
    if [item.get("case_id") for item in answer_items] != expected_ids:
        raise ValueError("temporal answer case set or order mismatch")
    if [item.get("case_id") for item in prediction_items] != expected_ids:
        raise ValueError("temporal prediction case set or order mismatch")

    paired = list(zip(cases, answer_items, prediction_items, strict=True))
    correct = sum(answer["verdict"] == prediction["verdict"] for _, answer, prediction in paired)
    false_verified = sum(
        answer["verdict"] != "RSE_VERIFIED" and prediction["verdict"] == "RSE_VERIFIED"
        for _, answer, prediction in paired
    )
    cost_pairs = [
        (answer, prediction)
        for _, answer, prediction in paired
        if answer["minimum_cost"] is not None
    ]
    cost_matches = sum(
        int(answer["minimum_cost"]) == prediction["minimum_cost"]
        for answer, prediction in cost_pairs
    )
    families = {case["family"] for case in cases}
    nonverified = sum(answer["verdict"] != "RSE_VERIFIED" for answer in answer_items)
    metrics = {
        "case_count": len(cases),
        "family_count": len(families),
        "nonverified_case_count": nonverified,
        "accuracy": correct / len(cases),
        "false_verified_count": false_verified,
        "cost_case_count": len(cost_pairs),
        "cost_accuracy": cost_matches / len(cost_pairs) if cost_pairs else 1.0,
    }
    gates = protocol["gates"]
    gate_results = {
        "minimum_case_count": metrics["case_count"] >= int(gates["minimum_case_count"]),
        "minimum_family_count": metrics["family_count"]
        >= int(gates["minimum_family_count"]),
        "minimum_nonverified_case_count": metrics["nonverified_case_count"]
        >= int(gates["minimum_nonverified_case_count"]),
        "minimum_accuracy": metrics["accuracy"] >= float(gates["minimum_accuracy"]),
        "maximum_false_verified_count": metrics["false_verified_count"]
        <= int(gates["maximum_false_verified_count"]),
        "minimum_cost_accuracy": metrics["cost_accuracy"]
        >= float(gates["minimum_cost_accuracy"]),
    }
    if "require_independently_authored" in gates:
        required_independence = gates["require_independently_authored"]
        if not isinstance(required_independence, bool):
            raise ValueError("require_independently_authored gate must be boolean")
        gate_results["require_independently_authored"] = (
            public["author"]["independently_authored"]
            is required_independence
        )
    return {
        "schema_version": "erasemap-external-temporal-score-v1",
        "metrics": metrics,
        "gates": gate_results,
        "passed": all(gate_results.values()),
        "author": public["author"],
        "tested_erasemap_commit": predictions["tested_erasemap_commit"],
        "prediction_created_at_utc": predictions["prediction_created_at_utc"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = score(
        args.public, args.predictions, args.answers, args.manifest, args.protocol
    )
    encoded = canonical_bytes(result)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded)
    print(encoded.decode(), end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
