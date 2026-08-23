from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

FORBIDDEN_CARD_FIELDS = {"truth", "truth_class", "gold", "answer", "correct"}


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return cast(dict[str, Any], payload)


def verify_kit(root: Path) -> dict[str, Any]:
    protocol = _load(root / "protocol-v1.json")
    english = _load(root / "cards-en.json")
    russian = _load(root / "cards-ru.json")
    gold_path = root / "gold-v1.json"
    gold = _load(gold_path)
    schema = _load(root / "participant-response-schema.json")
    en_cards = english.get("cards")
    ru_cards = russian.get("cards")
    answers = gold.get("answers")
    if (
        not isinstance(en_cards, list)
        or not isinstance(ru_cards, list)
        or not isinstance(answers, list)
    ):
        raise ValueError("cards and gold must be arrays")
    en_ids = [item["id"] for item in en_cards]
    ru_ids = [item["id"] for item in ru_cards]
    gold_ids = [item["card_id"] for item in answers]
    if len(en_ids) != 12 or en_ids != ru_ids or en_ids != gold_ids or len(set(en_ids)) != 12:
        raise ValueError("bilingual card alignment mismatch")
    if any(FORBIDDEN_CARD_FIELDS & set(card) for card in (*en_cards, *ru_cards)):
        raise ValueError("participant cards expose a gold field")
    classes = Counter(item["truth_class"] for item in answers)
    if classes != Counter({"COMPLETE": 4, "INCOMPLETE": 4, "UNVERIFIED": 4}):
        raise ValueError("truth classes must be balanced 4/4/4")
    observed_gold_hash = "sha256:" + hashlib.sha256(gold_path.read_bytes()).hexdigest()
    if protocol.get("gold_sha256") != observed_gold_hash:
        raise ValueError("gold commitment mismatch")
    required = schema.get("required")
    if (
        not isinstance(required, list)
        or "participant_id" not in required
        or "responses" not in required
    ):
        raise ValueError("participant response schema is incomplete")
    return {
        "verified": True,
        "card_count": len(en_ids),
        "languages": ["en", "ru"],
        "truth_counts": dict(sorted(classes.items())),
        "gold_sha256": observed_gold_hash,
        "human_result_status": "NOT_COLLECTED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("usability"))
    args = parser.parse_args()
    print(json.dumps(verify_kit(args.root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
