from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
from typing import Any, cast

from cryptography.fernet import Fernet, InvalidToken


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


VERDICTS = frozenset({"COMPLETE", "INCOMPLETE", "UNVERIFIED"})


def _unique_ids(records: list[dict[str, Any]], location: str) -> tuple[str, ...]:
    ids: list[str] = []
    for record in records:
        case_id = record.get("id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{location} id is required")
        ids.append(case_id)
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate {location} id")
    return tuple(ids)


def seal_cases(payload: list[dict[str, Any]], key: bytes) -> dict[str, object]:
    public: list[dict[str, Any]] = []
    answers: list[dict[str, Any]] = []
    for case in payload:
        if set(case) != {"case", "expected_path", "truth_verdict"}:
            raise ValueError("each authored case requires case, expected_path, and truth_verdict")
        if not isinstance(case["case"], dict):
            raise ValueError("public case must be an object")
        public_case = cast(dict[str, Any], case["case"])
        if "truth_verdict" in public_case or "expected_path" in public_case:
            raise ValueError("truth leaked into public case")
        case_id = public_case.get("id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("public case id is required")
        family = public_case.get("family")
        if not isinstance(family, str) or not family:
            raise ValueError("public case family is required")
        if case["truth_verdict"] not in VERDICTS:
            raise ValueError("invalid truth verdict")
        expected_path = case["expected_path"]
        if expected_path is not None and (
            not isinstance(expected_path, list)
            or not all(isinstance(item, str) for item in expected_path)
        ):
            raise ValueError("expected_path must be null or an array of strings")
        public.append(public_case)
        answers.append(
            {
                "expected_path": case["expected_path"],
                "id": case_id,
                "truth_verdict": case["truth_verdict"],
            }
        )
    _unique_ids(public, "public case")
    answer_bytes = canonical(answers)
    encrypted = Fernet(key).encrypt(answer_bytes).decode()
    package: dict[str, object] = {
        "answer_commitment": sha256(answer_bytes),
        "case_count": len(public),
        "encrypted_answers": encrypted,
        "public_cases": public,
        "schema_version": "erasemap-external-blind-challenge-v1",
    }
    package["public_commitment"] = sha256(canonical(public))
    return package


def reveal_answers(package: dict[str, Any], key: bytes) -> list[dict[str, Any]]:
    public = cast(list[dict[str, Any]], package["public_cases"])
    if package.get("public_commitment") != sha256(canonical(public)):
        raise ValueError("public case commitment mismatch")
    try:
        raw = Fernet(key).decrypt(str(package["encrypted_answers"]).encode())
    except (InvalidToken, ValueError) as error:
        raise ValueError("invalid challenge key or encrypted answers") from error
    if sha256(raw) != package["answer_commitment"]:
        raise ValueError("answer commitment mismatch")
    answers = json.loads(raw)
    if not isinstance(answers, list):
        raise ValueError("revealed answers must be an array")
    return cast(list[dict[str, Any]], answers)


def freeze_predictions(
    package: dict[str, Any], predictions: list[dict[str, Any]]
) -> dict[str, object]:
    public = cast(list[dict[str, Any]], package["public_cases"])
    public_ids = _unique_ids(public, "public case")
    prediction_ids = _unique_ids(predictions, "prediction")
    if set(prediction_ids) != set(public_ids):
        raise ValueError("predictions must cover every public case exactly once")
    normalized: list[dict[str, Any]] = []
    for prediction in predictions:
        if set(prediction) != {"id", "shortest_path", "verdict"}:
            raise ValueError("prediction schema mismatch")
        if prediction["verdict"] not in VERDICTS:
            raise ValueError("invalid prediction verdict")
        path = prediction["shortest_path"]
        if path is not None and (
            not isinstance(path, list) or not all(isinstance(item, str) for item in path)
        ):
            raise ValueError("shortest_path must be null or an array of strings")
        normalized.append(prediction)
    normalized.sort(key=lambda item: str(item["id"]))
    return {
        "package_commitment": sha256(canonical(package)),
        "predictions": normalized,
        "predictions_commitment": sha256(canonical(normalized)),
        "schema_version": "erasemap-external-frozen-predictions-v1",
    }


def _wilson95(successes: int, trials: int) -> tuple[float, float] | None:
    if trials == 0:
        return None
    z = 1.959963984540054
    rate = successes / trials
    denominator = 1 + z * z / trials
    center = (rate + z * z / (2 * trials)) / denominator
    spread = z * math.sqrt(rate * (1 - rate) / trials + z * z / (4 * trials * trials))
    spread /= denominator
    return max(0.0, center - spread), min(1.0, center + spread)


def score_predictions(
    package: dict[str, Any],
    key: bytes,
    frozen: dict[str, Any],
    protocol: dict[str, Any],
) -> dict[str, object]:
    required_protocol = {
        "maximum_false_complete_wilson95_upper",
        "minimum_cases",
        "minimum_distinct_families",
        "minimum_exact_path_rate",
        "minimum_noncomplete_cases",
        "minimum_verdict_accuracy",
        "schema_version",
    }
    if set(protocol) != required_protocol or protocol["schema_version"] != (
        "erasemap-external-challenge-protocol-v1"
    ):
        raise ValueError("challenge protocol schema mismatch")
    integer_fields = (
        "minimum_cases",
        "minimum_distinct_families",
        "minimum_noncomplete_cases",
    )
    if any(
        not isinstance(protocol[field], int)
        or isinstance(protocol[field], bool)
        or protocol[field] <= 0
        for field in integer_fields
    ):
        raise ValueError("challenge count thresholds must be positive integers")
    rate_fields = (
        "maximum_false_complete_wilson95_upper",
        "minimum_exact_path_rate",
        "minimum_verdict_accuracy",
    )
    if any(
        not isinstance(protocol[field], (int, float))
        or isinstance(protocol[field], bool)
        or not 0 <= protocol[field] <= 1
        for field in rate_fields
    ):
        raise ValueError("challenge rate thresholds must be between zero and one")
    if protocol["minimum_noncomplete_cases"] > protocol["minimum_cases"]:
        raise ValueError("minimum non-complete cases cannot exceed total cases")
    if frozen.get("package_commitment") != sha256(canonical(package)):
        raise ValueError("frozen predictions refer to a different package")
    predictions = cast(list[dict[str, Any]], frozen["predictions"])
    if frozen.get("predictions_commitment") != sha256(canonical(predictions)):
        raise ValueError("prediction commitment mismatch")
    answers = reveal_answers(package, key)
    answer_by_id = {str(answer["id"]): answer for answer in answers}
    if set(answer_by_id) != {str(item["id"]) for item in predictions}:
        raise ValueError("answer and prediction ids differ")
    rows: list[dict[str, Any]] = []
    truth_noncomplete = 0
    false_complete = 0
    exact_verdict = 0
    exact_path = 0
    path_trials = 0
    for prediction in predictions:
        answer = answer_by_id[str(prediction["id"])]
        truth = str(answer["truth_verdict"])
        verdict = str(prediction["verdict"])
        is_false_complete = truth != "COMPLETE" and verdict == "COMPLETE"
        truth_noncomplete += int(truth != "COMPLETE")
        false_complete += int(is_false_complete)
        exact_verdict += int(truth == verdict)
        expected_path = answer["expected_path"]
        if expected_path is not None:
            path_trials += 1
            exact_path += int(expected_path == prediction["shortest_path"])
        rows.append(
            {
                "expected_path": expected_path,
                "false_complete": is_false_complete,
                "id": prediction["id"],
                "predicted_path": prediction["shortest_path"],
                "predicted_verdict": verdict,
                "truth_verdict": truth,
            }
        )
    interval = _wilson95(false_complete, truth_noncomplete)
    min_cases = int(protocol["minimum_cases"])
    min_families = int(protocol["minimum_distinct_families"])
    min_noncomplete = int(protocol["minimum_noncomplete_cases"])
    max_upper = float(protocol["maximum_false_complete_wilson95_upper"])
    min_accuracy = float(protocol["minimum_verdict_accuracy"])
    min_path_rate = float(protocol["minimum_exact_path_rate"])
    accuracy = exact_verdict / len(predictions)
    path_rate = exact_path / path_trials if path_trials else None
    gates = {
        "case_count": len(predictions) >= min_cases,
        "distinct_families": len({str(case["family"]) for case in package["public_cases"]})
        >= min_families,
        "false_complete_wilson95_upper": interval is not None and interval[1] <= max_upper,
        "exact_path_rate": path_rate is not None and path_rate >= min_path_rate,
        "noncomplete_count": truth_noncomplete >= min_noncomplete,
        "verdict_accuracy": accuracy >= min_accuracy,
    }
    return {
        "answer_commitment": package["answer_commitment"],
        "decision": "PASS" if all(gates.values()) else "FAIL",
        "exact_path_rate": path_rate,
        "false_complete": false_complete,
        "false_complete_rate": false_complete / truth_noncomplete if truth_noncomplete else None,
        "false_complete_wilson95": interval,
        "gates": gates,
        "package_commitment": frozen["package_commitment"],
        "predictions_commitment": frozen["predictions_commitment"],
        "protocol_commitment": sha256(canonical(protocol)),
        "rows": rows,
        "schema_version": "erasemap-external-challenge-score-v1",
        "total_cases": len(predictions),
        "distinct_families": len(
            {str(case["family"]) for case in cast(list[dict[str, Any]], package["public_cases"])}
        ),
        "truth_noncomplete": truth_noncomplete,
        "verdict_accuracy": accuracy,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("seal", "reveal", "freeze", "score"))
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--key-file")
    parser.add_argument("--key-file-out")
    parser.add_argument("--package")
    parser.add_argument("--protocol")
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    if args.command == "seal":
        payload = json.loads(Path(args.input).read_text())
        if not isinstance(payload, list):
            raise ValueError("authored cases must be an array")
        key = Fernet.generate_key()
        output.write_text(json.dumps(seal_cases(payload, key), indent=2, sort_keys=True) + "\n")
        encoded_key = base64.urlsafe_b64encode(key).decode()
        if args.key_file_out:
            key_output = Path(args.key_file_out)
            if key_output.exists():
                raise FileExistsError(f"refusing to overwrite {key_output}")
            key_output.write_text(encoded_key + "\n")
        else:
            print("EXTERNAL_EVALUATOR_KEY=" + encoded_key)
        return 0
    if args.command == "freeze":
        if not args.package:
            raise ValueError("--package is required for freeze")
        package = json.loads(Path(args.package).read_text())
        predictions = json.loads(Path(args.input).read_text())
        output.write_text(
            json.dumps(freeze_predictions(package, predictions), indent=2, sort_keys=True) + "\n"
        )
        return 0
    if not args.key_file:
        raise ValueError("--key-file is required for reveal")
    encoded = Path(args.key_file).read_text().strip()
    key = base64.urlsafe_b64decode(encoded)
    result: object
    if args.command == "score":
        if not args.protocol or not args.package:
            raise ValueError("--package and --protocol are required for score")
        package = json.loads(Path(args.package).read_text())
        frozen = json.loads(Path(args.input).read_text())
        protocol = json.loads(Path(args.protocol).read_text())
        result = score_predictions(package, key, frozen, protocol)
    else:
        package = json.loads(Path(args.input).read_text())
        result = reveal_answers(package, key)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
