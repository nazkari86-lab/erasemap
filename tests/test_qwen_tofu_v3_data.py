from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from experiments.qwen_tofu_v3_data import (
    AuthorBlock,
    ConfirmationView,
    DevelopmentView,
    build_author_lock,
    compute_selection_commitment,
    load_confirmation_view,
    load_development_view,
    load_jsonl,
    partition_author_blocks,
    row_fingerprint,
    validate_perturbed_alignment,
)

PROTOCOL = Path("benchmark/qwen-tofu-kaggle-v3.json")


def _rows(authors: int = 3, rows_per_author: int = 20) -> list[dict[str, object]]:
    return [
        {
            "answer": f"author-{author}-answer-{row}",
            "question": f"author-{author}-question-{row}",
        }
        for author in range(authors)
        for row in range(rows_per_author)
    ]


def _perturbed(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            **row,
            "paraphrased_answer": f"p-{index}",
            "paraphrased_question": f"pq-{index}",
            "perturbed_answer": [f"wrong-{index}-{value}" for value in range(5)],
        }
        for index, row in enumerate(rows)
    ]


def _protocol_for_rows(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    protocol = json.loads(PROTOCOL.read_text())
    protocol["author_blocks"]["commitments"] = [
        block.commitment for block in partition_author_blocks(rows, rows_per_author=20)
    ]
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol))
    return path


def _write_selection(path: Path, protocol_sha256: str) -> None:
    selection = {
        "protocol_sha256": protocol_sha256,
        "selected_path_id": "rbep-t1-k05-s20",
    }
    selection["selection_commitment"] = compute_selection_commitment(selection)
    path.write_text(json.dumps(selection))


def test_partition_rejects_incomplete_twenty_row_author() -> None:
    with pytest.raises(ValueError, match="divisible by 20"):
        partition_author_blocks(_rows(rows_per_author=19), rows_per_author=20)


def test_partition_is_disjoint_and_commitment_stable() -> None:
    rows = _rows()
    first = partition_author_blocks(rows, rows_per_author=20)
    second = partition_author_blocks(rows, rows_per_author=20)
    assert first == second
    assert isinstance(first[0], AuthorBlock)
    assert len(first) == 3
    assert len({block.commitment for block in first}) == 3
    assert set(first[0].fingerprints).isdisjoint(first[1].fingerprints)


def test_fingerprint_ignores_unrelated_semantic_fields() -> None:
    row = _rows(authors=1)[0]
    assert row_fingerprint(row) == row_fingerprint(
        {**row, "paraphrased_answer": "different", "perturbed_answer": ["x"]}
    )


def test_duplicate_rows_are_rejected() -> None:
    rows = _rows(authors=1)
    rows[-1] = rows[0]
    with pytest.raises(ValueError, match="duplicate row fingerprint"):
        partition_author_blocks(rows, rows_per_author=20)


def test_perturbed_alignment_checks_order_and_schema() -> None:
    rows = _rows(authors=1)
    validate_perturbed_alignment(rows, _perturbed(rows), expected_answers=5)
    reversed_rows = list(reversed(_perturbed(rows)))
    with pytest.raises(ValueError, match="alignment"):
        validate_perturbed_alignment(rows, reversed_rows, expected_answers=5)
    malformed = _perturbed(rows)
    malformed[0]["perturbed_answer"] = ["only-one"]
    with pytest.raises(ValueError, match="answer count"):
        validate_perturbed_alignment(rows, malformed, expected_answers=5)


def test_author_lock_assigns_disclosed_confirmation_and_reserve() -> None:
    rows = _rows(authors=20)
    lock = build_author_lock(
        rows,
        _perturbed(rows),
        rows_per_author=20,
        expected_perturbed_answers=5,
    )
    assert len(lock["blocks"]) == 20
    assert lock["development_pairs"] == [[0, 1], [2, 3], [4, 5], [6, 7], [8, 9]]
    assert lock["primary_confirmation"] == [10, 11]
    assert lock["replication_confirmation"] == [12, 13]
    assert lock["future_reserve"] == [14, 15, 16, 17, 18, 19]


def test_jsonl_loader_rejects_non_objects(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl"
    path.write_text(json.dumps(["not", "an", "object"]) + "\n")
    with pytest.raises(ValueError, match="JSON object"):
        load_jsonl(path)


def test_development_view_exposes_only_declared_development_blocks(tmp_path: Path) -> None:
    rows = _rows(authors=20)
    protocol = _protocol_for_rows(tmp_path, rows)
    view = load_development_view(
        rows,
        _perturbed(rows),
        protocol_path=protocol,
        holdout_rows=rows[:4],
        world_fact_rows=rows[4:8],
        real_anchor_rows=rows[8:12],
        real_test_rows=rows[12:16],
    )
    assert isinstance(view, DevelopmentView)
    assert [fold.block_indices for fold in view.folds] == [
        (0, 1),
        (2, 3),
        (4, 5),
        (6, 7),
        (8, 9),
    ]
    assert all(len(fold.direct) == 40 for fold in view.folds)
    visible = {row_fingerprint(row) for fold in view.folds for row in fold.direct}
    sealed = {row_fingerprint(row) for row in rows[200:280]}
    assert visible.isdisjoint(sealed)


def test_confirmation_requires_matching_selection_commitment(tmp_path: Path) -> None:
    rows = _rows(authors=20)
    protocol = _protocol_for_rows(tmp_path, rows)
    protocol_sha256 = "sha256:" + hashlib.sha256(protocol.read_bytes()).hexdigest()
    selection = tmp_path / "selection.json"
    with pytest.raises(ValueError, match="selection commitment"):
        load_confirmation_view(
            rows,
            _perturbed(rows),
            protocol_path=protocol,
            selection_path=selection,
            expected_protocol_sha256=protocol_sha256,
            holdout_rows=rows[:4],
            world_fact_rows=rows[4:8],
            real_test_rows=rows[8:12],
        )
    _write_selection(selection, "sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="protocol hash"):
        load_confirmation_view(
            rows,
            _perturbed(rows),
            protocol_path=protocol,
            selection_path=selection,
            expected_protocol_sha256=protocol_sha256,
            holdout_rows=rows[:4],
            world_fact_rows=rows[4:8],
            real_test_rows=rows[8:12],
        )


def test_confirmation_view_exposes_only_two_sealed_blocks(tmp_path: Path) -> None:
    rows = _rows(authors=20)
    protocol = _protocol_for_rows(tmp_path, rows)
    protocol_sha256 = "sha256:" + hashlib.sha256(protocol.read_bytes()).hexdigest()
    selection = tmp_path / "selection.json"
    _write_selection(selection, protocol_sha256)
    view = load_confirmation_view(
        rows,
        _perturbed(rows),
        protocol_path=protocol,
        selection_path=selection,
        expected_protocol_sha256=protocol_sha256,
        holdout_rows=rows[:4],
        world_fact_rows=rows[4:8],
        real_test_rows=rows[8:12],
    )
    assert isinstance(view, ConfirmationView)
    assert view.primary.block_indices == (10, 11)
    assert view.replication.block_indices == (12, 13)
    assert len(view.primary.direct) == len(view.replication.direct) == 40
