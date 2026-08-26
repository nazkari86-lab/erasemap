from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _text(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def row_fingerprint(row: Mapping[str, object]) -> str:
    return _sha256_bytes(
        _canonical({"answer": _text(row, "answer"), "question": _text(row, "question")})
    )


@dataclass(frozen=True, slots=True)
class AuthorBlock:
    index: int
    commitment: str
    fingerprints: tuple[str, ...]
    rows: tuple[Mapping[str, object], ...]


def partition_author_blocks(
    rows: Sequence[Mapping[str, object]], *, rows_per_author: int
) -> tuple[AuthorBlock, ...]:
    if rows_per_author < 1:
        raise ValueError("rows_per_author must be positive")
    if not rows or len(rows) % rows_per_author:
        raise ValueError(f"row count must be non-zero and divisible by {rows_per_author}")
    all_fingerprints = [row_fingerprint(row) for row in rows]
    if len(set(all_fingerprints)) != len(all_fingerprints):
        raise ValueError("duplicate row fingerprint")
    result: list[AuthorBlock] = []
    for index, start in enumerate(range(0, len(rows), rows_per_author)):
        block_rows = tuple(rows[start : start + rows_per_author])
        fingerprints = tuple(all_fingerprints[start : start + rows_per_author])
        commitment = _sha256_bytes(
            _canonical(
                {
                    "fingerprints": fingerprints,
                    "index": index,
                    "rows_per_author": rows_per_author,
                }
            )
        )
        result.append(AuthorBlock(index, commitment, fingerprints, block_rows))
    return tuple(result)


def validate_perturbed_alignment(
    direct_rows: Sequence[Mapping[str, object]],
    perturbed_rows: Sequence[Mapping[str, object]],
    *,
    expected_answers: int,
) -> None:
    if len(direct_rows) != len(perturbed_rows):
        raise ValueError("direct and perturbed alignment counts differ")
    if expected_answers < 1:
        raise ValueError("expected_answers must be positive")
    for index, (direct, perturbed) in enumerate(
        zip(direct_rows, perturbed_rows, strict=True)
    ):
        if row_fingerprint(direct) != row_fingerprint(perturbed):
            raise ValueError(f"direct/perturbed alignment mismatch at row {index}")
        _text(perturbed, "paraphrased_question")
        _text(perturbed, "paraphrased_answer")
        answers = perturbed.get("perturbed_answer")
        if not isinstance(answers, list) or len(answers) != expected_answers:
            raise ValueError(f"perturbed answer count mismatch at row {index}")
        if any(not isinstance(answer, str) or not answer.strip() for answer in answers):
            raise ValueError(f"perturbed answer must be non-empty at row {index}")


def build_author_lock(
    direct_rows: Sequence[Mapping[str, object]],
    perturbed_rows: Sequence[Mapping[str, object]],
    *,
    rows_per_author: int,
    expected_perturbed_answers: int,
) -> dict[str, object]:
    validate_perturbed_alignment(
        direct_rows,
        perturbed_rows,
        expected_answers=expected_perturbed_answers,
    )
    blocks = partition_author_blocks(direct_rows, rows_per_author=rows_per_author)
    if len(blocks) < 20:
        raise ValueError("v3 author lock requires at least 20 complete authors")
    return {
        "blocks": [
            {
                "commitment": block.commitment,
                "index": block.index,
                "row_count": len(block.rows),
            }
            for block in blocks
        ],
        "development_pairs": [[value, value + 1] for value in range(0, 10, 2)],
        "future_reserve": list(range(14, len(blocks))),
        "primary_confirmation": [10, 11],
        "replication_confirmation": [12, 13],
        "rows_per_author": rows_per_author,
        "schema_version": "erasemap-qwen-tofu-author-lock-v3",
    }


def load_jsonl(path: Path) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for index, line in enumerate(path.read_text().splitlines()):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"row {index} must be a JSON object")
        rows.append(cast(Mapping[str, Any], value))
    if not rows:
        raise ValueError("JSONL input must contain rows")
    return rows


def author_lock_from_files(
    forget_path: Path,
    perturbed_path: Path,
    *,
    rows_per_author: int = 20,
    expected_perturbed_answers: int = 5,
) -> dict[str, object]:
    result = build_author_lock(
        load_jsonl(forget_path),
        load_jsonl(perturbed_path),
        rows_per_author=rows_per_author,
        expected_perturbed_answers=expected_perturbed_answers,
    )
    result["sources"] = {
        "forget10_sha256": _sha256_file(forget_path),
        "forget10_perturbed_sha256": _sha256_file(perturbed_path),
    }
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the frozen Qwen-TOFU v3 author lock")
    parser.add_argument("--forget", type=Path, required=True)
    parser.add_argument("--perturbed", type=Path, required=True)
    args = parser.parse_args(argv)
    result = author_lock_from_files(args.forget, args.perturbed)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
