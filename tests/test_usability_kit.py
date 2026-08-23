from __future__ import annotations

import json
from pathlib import Path

from usability.score import load_gold, randomized_order, score_responses, wilson_interval
from usability.verify import verify_kit

ROOT = Path("usability")
GOLD = load_gold(ROOT / "gold-v1.json")


def perfect_response(index: int) -> dict[str, object]:
    nonce = f"participant-nonce-{index:02d}"
    order = randomized_order(nonce, sorted(GOLD))
    responses = []
    for card_id in order:
        answer = GOLD[card_id]
        responses.append(
            {
                "card_id": card_id,
                "explanation_choice": answer["explanation"],
                "verdict": answer["verdict"],
                "path_choice": answer["path"],
                "action_choice": answer["action"],
                "completion_ms": 30000 + index,
            }
        )
    return {
        "schema_version": "erasemap-usability-response-v1",
        "participant_id": f"participant_{index:02d}",
        "participant_nonce": nonce,
        "language": "ru" if index % 2 else "en",
        "consent": True,
        "started_at": "2026-08-23T00:00:00Z",
        "ended_at": "2026-08-23T00:20:00Z",
        "card_order": list(order),
        "responses": responses,
    }


def test_bilingual_packet_is_aligned_answer_blind_and_balanced() -> None:
    result = verify_kit(ROOT)
    assert result["verified"] is True
    assert result["card_count"] == 12
    assert result["truth_counts"] == {
        "COMPLETE": 4,
        "INCOMPLETE": 4,
        "UNVERIFIED": 4,
    }
    for name in ("cards-en.json", "cards-ru.json"):
        encoded = (ROOT / name).read_text().lower()
        assert '"truth"' not in encoded
        assert '"answer"' not in encoded


def test_order_is_nonce_deterministic_and_wilson_is_bounded() -> None:
    ids = tuple(sorted(GOLD))
    assert randomized_order("participant-nonce-01", ids) == randomized_order(
        "participant-nonce-01", ids
    )
    assert randomized_order("participant-nonce-01", ids) != randomized_order(
        "participant-nonce-02", ids
    )
    low, high = wilson_interval(8, 10)
    assert 0.0 < low < 0.8 < high < 1.0


def test_fewer_than_ten_participants_can_never_pass() -> None:
    result = score_responses([perfect_response(index) for index in range(9)], GOLD)
    assert result["decision"] == "INSUFFICIENT_SAMPLE"
    assert result["participant_count"] == 9
    assert all(item["accuracy"] == 1.0 for item in result["metrics"].values())


def test_ten_perfect_participants_pass_all_primary_endpoints() -> None:
    result = score_responses([perfect_response(index) for index in range(10)], GOLD)
    assert result["decision"] == "PASS"
    assert result["median_completion_seconds"] is not None
    assert all(item["total"] == 120 for item in result["metrics"].values())


def test_response_schema_has_no_identity_fields() -> None:
    schema = json.loads((ROOT / "participant-response-schema.json").read_text())
    properties = schema["properties"]
    assert {"name", "email", "phone", "biometric", "government_id"}.isdisjoint(properties)
