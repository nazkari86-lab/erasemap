from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from cryptography.fernet import Fernet, InvalidToken


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def seal_cases(payload: list[dict[str, Any]], key: bytes) -> dict[str, object]:
    public: list[dict[str, Any]] = []
    answers: list[dict[str, Any]] = []
    for case in payload:
        if set(case) != {"case", "expected_path", "truth_verdict"}:
            raise ValueError("each authored case requires case, expected_path, and truth_verdict")
        public_case = cast(dict[str, Any], case["case"])
        if "truth_verdict" in public_case or "expected_path" in public_case:
            raise ValueError("truth leaked into public case")
        case_id = public_case.get("id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("public case id is required")
        public.append(public_case)
        answers.append(
            {
                "expected_path": case["expected_path"],
                "id": case_id,
                "truth_verdict": case["truth_verdict"],
            }
        )
    answer_bytes = canonical(answers)
    encrypted = Fernet(key).encrypt(answer_bytes).decode()
    return {
        "answer_commitment": sha256(answer_bytes),
        "case_count": len(public),
        "encrypted_answers": encrypted,
        "public_cases": public,
        "schema_version": "erasemap-external-blind-challenge-v1",
    }


def reveal_answers(package: dict[str, Any], key: bytes) -> list[dict[str, Any]]:
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("seal", "reveal"))
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--key-file")
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
        print("EXTERNAL_EVALUATOR_KEY=" + base64.urlsafe_b64encode(key).decode())
        return 0
    if not args.key_file:
        raise ValueError("--key-file is required for reveal")
    package = json.loads(Path(args.input).read_text())
    encoded = Path(args.key_file).read_text().strip()
    key = base64.urlsafe_b64decode(encoded)
    output.write_text(json.dumps(reveal_answers(package, key), indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
