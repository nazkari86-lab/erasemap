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


@dataclass(frozen=True, slots=True)
class QA:
    question: str
    answer: str


@dataclass(frozen=True, slots=True)
class DeletionFold:
    block_indices: tuple[int, ...]
    block_commitments: tuple[str, ...]
    direct: tuple[Mapping[str, object], ...]
    perturbed: tuple[Mapping[str, object], ...]


@dataclass(frozen=True, slots=True)
class DevelopmentView:
    folds: tuple[DeletionFold, ...]
    holdout: tuple[QA, ...]
    world_facts: tuple[QA, ...]
    real_anchor: tuple[QA, ...]
    real_test: tuple[QA, ...]


@dataclass(frozen=True, slots=True)
class ConfirmationView:
    primary: DeletionFold
    replication: DeletionFold
    holdout: tuple[QA, ...]
    world_facts: tuple[QA, ...]
    real_test: tuple[QA, ...]


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


def _qa_rows(rows: Sequence[Mapping[str, object]]) -> tuple[QA, ...]:
    return tuple(QA(_text(row, "question"), _text(row, "answer")) for row in rows)


def _protocol(path: Path) -> Mapping[str, object]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("protocol must be a JSON object")
    if value.get("status") != "FROZEN_BEFORE_FIRST_V3_GPU_RUN":
        raise ValueError("protocol is not frozen")
    return cast(Mapping[str, object], value)


def _author_blocks_config(protocol: Mapping[str, object]) -> Mapping[str, object]:
    value = protocol.get("author_blocks")
    if not isinstance(value, dict):
        raise ValueError("protocol author_blocks are missing")
    return cast(Mapping[str, object], value)


def _validated_blocks(
    direct_rows: Sequence[Mapping[str, object]],
    perturbed_rows: Sequence[Mapping[str, object]],
    protocol: Mapping[str, object],
) -> tuple[AuthorBlock, ...]:
    config = _author_blocks_config(protocol)
    rows_per_author = config.get("rows_per_author")
    commitments = config.get("commitments")
    if not isinstance(rows_per_author, int) or not isinstance(commitments, list):
        raise ValueError("invalid author-block protocol")
    validate_perturbed_alignment(direct_rows, perturbed_rows, expected_answers=5)
    blocks = partition_author_blocks(direct_rows, rows_per_author=rows_per_author)
    actual = [block.commitment for block in blocks]
    if actual != commitments:
        raise ValueError("author block commitment drift")
    return blocks


def _indices(config: Mapping[str, object], field: str) -> tuple[int, ...]:
    value = config.get(field)
    if not isinstance(value, list) or not all(isinstance(item, int) for item in value):
        raise ValueError(f"invalid {field} author indices")
    return tuple(cast(list[int], value))


def _fold(
    indices: tuple[int, ...],
    blocks: tuple[AuthorBlock, ...],
    perturbed_rows: Sequence[Mapping[str, object]],
) -> DeletionFold:
    if not indices or len(set(indices)) != len(indices):
        raise ValueError("deletion fold must contain distinct authors")
    try:
        selected = tuple(blocks[index] for index in indices)
    except IndexError as exc:
        raise ValueError("author index is out of range") from exc
    direct = tuple(row for block in selected for row in block.rows)
    perturbed = tuple(
        perturbed_rows[index * len(blocks[0].rows) + offset]
        for index in indices
        for offset in range(len(blocks[0].rows))
    )
    return DeletionFold(
        block_indices=indices,
        block_commitments=tuple(block.commitment for block in selected),
        direct=direct,
        perturbed=perturbed,
    )


def load_development_view(
    direct_rows: Sequence[Mapping[str, object]],
    perturbed_rows: Sequence[Mapping[str, object]],
    *,
    protocol_path: Path,
    holdout_rows: Sequence[Mapping[str, object]],
    world_fact_rows: Sequence[Mapping[str, object]],
    real_anchor_rows: Sequence[Mapping[str, object]],
    real_test_rows: Sequence[Mapping[str, object]],
) -> DevelopmentView:
    protocol = _protocol(protocol_path)
    config = _author_blocks_config(protocol)
    blocks = _validated_blocks(direct_rows, perturbed_rows, protocol)
    raw_pairs = config.get("development_pairs")
    if not isinstance(raw_pairs, list):
        raise ValueError("development pairs are missing")
    pairs: list[tuple[int, ...]] = []
    for pair in raw_pairs:
        if not isinstance(pair, list) or not all(isinstance(item, int) for item in pair):
            raise ValueError("invalid development pair")
        pairs.append(tuple(cast(list[int], pair)))
    visible = {index for pair in pairs for index in pair}
    sealed = {
        *_indices(config, "primary_confirmation"),
        *_indices(config, "replication_confirmation"),
        *_indices(config, "future_reserve"),
    }
    if visible & sealed:
        raise ValueError("development and sealed author blocks overlap")
    return DevelopmentView(
        folds=tuple(_fold(pair, blocks, perturbed_rows) for pair in pairs),
        holdout=_qa_rows(holdout_rows),
        world_facts=_qa_rows(world_fact_rows),
        real_anchor=_qa_rows(real_anchor_rows),
        real_test=_qa_rows(real_test_rows),
    )


def compute_selection_commitment(selection: Mapping[str, object]) -> str:
    payload = {key: value for key, value in selection.items() if key != "selection_commitment"}
    return _sha256_bytes(_canonical(payload))


def _load_selection(path: Path, expected_protocol_sha256: str) -> Mapping[str, object]:
    if not path.is_file():
        raise ValueError("selection commitment is required before confirmation")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("selection commitment must be a JSON object")
    selection = cast(Mapping[str, object], value)
    if selection.get("protocol_sha256") != expected_protocol_sha256:
        raise ValueError("selection protocol hash mismatch")
    if not isinstance(selection.get("selected_path_id"), str):
        raise ValueError("selection path is missing")
    if selection.get("selection_commitment") != compute_selection_commitment(selection):
        raise ValueError("selection commitment digest mismatch")
    return selection


def load_confirmation_view(
    direct_rows: Sequence[Mapping[str, object]],
    perturbed_rows: Sequence[Mapping[str, object]],
    *,
    protocol_path: Path,
    selection_path: Path,
    expected_protocol_sha256: str,
    holdout_rows: Sequence[Mapping[str, object]],
    world_fact_rows: Sequence[Mapping[str, object]],
    real_test_rows: Sequence[Mapping[str, object]],
) -> ConfirmationView:
    protocol = _protocol(protocol_path)
    actual_protocol_sha256 = _sha256_file(protocol_path)
    if actual_protocol_sha256 != expected_protocol_sha256:
        raise ValueError("protocol hash drift")
    _load_selection(selection_path, expected_protocol_sha256)
    config = _author_blocks_config(protocol)
    blocks = _validated_blocks(direct_rows, perturbed_rows, protocol)
    primary = _indices(config, "primary_confirmation")
    replication = _indices(config, "replication_confirmation")
    reserve = set(_indices(config, "future_reserve"))
    if set(primary) & set(replication) or (set(primary) | set(replication)) & reserve:
        raise ValueError("confirmation and reserve author blocks overlap")
    return ConfirmationView(
        primary=_fold(primary, blocks, perturbed_rows),
        replication=_fold(replication, blocks, perturbed_rows),
        holdout=_qa_rows(holdout_rows),
        world_facts=_qa_rows(world_fact_rows),
        real_test=_qa_rows(real_test_rows),
    )


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
