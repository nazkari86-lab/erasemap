from __future__ import annotations

import argparse
from pathlib import Path

from external_temporal_challenge.core import (
    ANSWERS_SCHEMA,
    MANIFEST_SCHEMA,
    PUBLIC_SCHEMA,
    SUITE_SCHEMA,
    canonical_bytes,
    digest_bytes,
    read_object,
    validate_public_suite,
)


def seal(authored_path: Path, output: Path) -> dict[str, object]:
    authored = read_object(authored_path)
    if authored.get("schema_version") != SUITE_SCHEMA:
        raise ValueError("unsupported authored temporal suite schema")
    if set(authored) != {"schema_version", "author", "cases"}:
        raise ValueError("authored temporal suite fields do not match schema")
    public_cases = []
    answers = []
    for item in authored["cases"]:
        if not isinstance(item, dict) or "expected" not in item:
            raise ValueError("every authored case requires expected labels")
        expected = item["expected"]
        if not isinstance(expected, dict) or set(expected) != {"verdict", "minimum_cost"}:
            raise ValueError("invalid authored expected labels")
        public_cases.append({key: value for key, value in item.items() if key != "expected"})
        answers.append(
            {
                "case_id": item.get("case_id"),
                "verdict": expected["verdict"],
                "minimum_cost": expected["minimum_cost"],
            }
        )
    public = {"schema_version": PUBLIC_SCHEMA, "author": authored["author"], "cases": public_cases}
    validate_public_suite(public)
    answer_payload = {"schema_version": ANSWERS_SCHEMA, "answers": answers}
    public_bytes = canonical_bytes(public)
    answer_bytes = canonical_bytes(answer_payload)
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "public_cases_sha256": digest_bytes(public_bytes),
        "answers_sha256": digest_bytes(answer_bytes),
        "case_count": len(public_cases),
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "public-cases.json").write_bytes(public_bytes)
    (output / "answers.private.json").write_bytes(answer_bytes)
    (output / "commitment-manifest.json").write_bytes(canonical_bytes(manifest))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("authored_suite", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(canonical_bytes(seal(args.authored_suite, args.output)).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
