from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, cast

ENDPOINT_FIELDS = {
    "explanation": "explanation_choice",
    "verdict": "verdict",
    "path": "path_choice",
    "action": "action_choice",
}
GOLD_FIELDS = {
    "explanation": "explanation",
    "verdict": "verdict",
    "path": "path",
    "action": "action",
}


def randomized_order(nonce: str, card_ids: Sequence[str]) -> tuple[str, ...]:
    if re.fullmatch(r"[A-Za-z0-9_-]{16,128}", nonce) is None:
        raise ValueError("participant nonce is malformed")
    if len(card_ids) != len(set(card_ids)):
        raise ValueError("card ids must be unique")
    return tuple(
        sorted(
            card_ids,
            key=lambda card_id: hashlib.sha256(nonce.encode() + b"\0" + card_id.encode()).digest(),
        )
    )


def wilson_interval(
    successes: int, total: int, z: float = 1.959963984540054
) -> tuple[float, float]:
    if total <= 0 or successes < 0 or successes > total:
        raise ValueError("invalid binomial counts")
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    spread = (
        z
        * math.sqrt(proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total))
        / denominator
    )
    return max(0.0, center - spread), min(1.0, center + spread)


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO timestamp") from exc


def _validate_response(payload: Mapping[str, Any], card_ids: tuple[str, ...]) -> None:
    required = {
        "schema_version",
        "participant_id",
        "participant_nonce",
        "language",
        "consent",
        "started_at",
        "ended_at",
        "card_order",
        "responses",
    }
    if (
        set(payload) != required
        or payload.get("schema_version") != "erasemap-usability-response-v1"
    ):
        raise ValueError("participant response schema mismatch")
    if re.fullmatch(r"[A-Za-z0-9_-]{8,64}", str(payload["participant_id"])) is None:
        raise ValueError("participant id is malformed")
    nonce = str(payload["participant_nonce"])
    if payload["language"] not in {"en", "ru"} or payload["consent"] is not True:
        raise ValueError("language and consent are required")
    if _timestamp(payload["started_at"], "started_at") >= _timestamp(
        payload["ended_at"], "ended_at"
    ):
        raise ValueError("participant timestamps must increase")
    expected_order = randomized_order(nonce, card_ids)
    order = payload["card_order"]
    if not isinstance(order, list) or tuple(order) != expected_order:
        raise ValueError("card order does not match participant nonce")
    responses = payload["responses"]
    if not isinstance(responses, list) or len(responses) != len(card_ids):
        raise ValueError("participant must answer every card exactly once")
    response_ids = []
    response_fields = {
        "card_id",
        "explanation_choice",
        "verdict",
        "path_choice",
        "action_choice",
        "completion_ms",
    }
    for response in responses:
        if not isinstance(response, dict) or set(response) != response_fields:
            raise ValueError("card response schema mismatch")
        response_ids.append(response["card_id"])
        if (
            type(response["completion_ms"]) is not int
            or not 1 <= response["completion_ms"] <= 600000
        ):
            raise ValueError("card completion time is invalid")
    if tuple(response_ids) != expected_order:
        raise ValueError("responses must follow deterministic card order")


def score_responses(
    responses: Sequence[Mapping[str, Any]],
    gold: Mapping[str, Mapping[str, str]],
    *,
    minimum_participants: int = 10,
    minimum_accuracy: float = 0.8,
) -> dict[str, Any]:
    card_ids = tuple(sorted(gold))
    participant_ids: set[str] = set()
    nonces: set[str] = set()
    counts = {endpoint: 0 for endpoint in ENDPOINT_FIELDS}
    total = 0
    completion_times: list[int] = []
    for payload in responses:
        _validate_response(payload, card_ids)
        participant_id = str(payload["participant_id"])
        nonce = str(payload["participant_nonce"])
        if participant_id in participant_ids or nonce in nonces:
            raise ValueError("participant ids and nonces must be unique")
        participant_ids.add(participant_id)
        nonces.add(nonce)
        for response in cast(list[dict[str, Any]], payload["responses"]):
            answer = gold[str(response["card_id"])]
            for endpoint, response_field in ENDPOINT_FIELDS.items():
                counts[endpoint] += response[response_field] == answer[GOLD_FIELDS[endpoint]]
            total += 1
            completion_times.append(int(response["completion_ms"]))
    metrics: dict[str, Any] = {}
    for endpoint, correct in counts.items():
        if total:
            low, high = wilson_interval(correct, total)
            accuracy = correct / total
        else:
            low, high, accuracy = 0.0, 0.0, 0.0
        metrics[endpoint] = {
            "correct": correct,
            "total": total,
            "accuracy": accuracy,
            "wilson_95_low": low,
            "wilson_95_high": high,
        }
    participant_count = len(responses)
    if participant_count < minimum_participants:
        decision = "INSUFFICIENT_SAMPLE"
    elif all(metric["accuracy"] >= minimum_accuracy for metric in metrics.values()):
        decision = "PASS"
    else:
        decision = "FAIL"
    return {
        "schema_version": "erasemap-usability-score-v1",
        "decision": decision,
        "participant_count": participant_count,
        "minimum_participants": minimum_participants,
        "minimum_accuracy": minimum_accuracy,
        "metrics": metrics,
        "median_completion_seconds": (
            statistics.median(completion_times) / 1000.0 if completion_times else None
        ),
        "claim_boundary": (
            "A technical score does not establish participant independence, recruitment quality, "
            "or general population usability without evaluator review."
        ),
    }


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], payload)


def load_gold(path: Path) -> dict[str, dict[str, str]]:
    payload = _load_object(path)
    answers = payload.get("answers")
    if not isinstance(answers, list):
        raise ValueError("gold answers are missing")
    return {str(item["card_id"]): cast(dict[str, str], item) for item in answers}


def main() -> int:
    parser = argparse.ArgumentParser(description="Score answer-blind EraSeMap usability responses")
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--gold", type=Path, default=Path("usability/gold-v1.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    files = sorted(args.responses.glob("*.json"))
    result = score_responses([_load_object(path) for path in files], load_gold(args.gold))
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        if args.output.exists():
            raise FileExistsError(f"refusing to overwrite {args.output}")
        args.output.write_text(encoded)
    print(encoded, end="")
    return 0 if result["decision"] in {"PASS", "INSUFFICIENT_SAMPLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
