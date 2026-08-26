# Qwen–TOFU v3 Reference-Bounded Erasure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, freeze, execute, independently verify, and publish a Qwen–TOFU v3 candidate that controls v2 overscrubbing through reference-bounded training and robust author-disjoint path selection.

**Architecture:** A pure `llm_unlearning_v3` core owns interpolation, margins, robust intervals, deterministic selection, and gates. A GPU runner owns phase-isolated data loading, RBEP training, raw evaluation, and append-only output; an independent verifier recomputes author commitments, selection, metrics, gates, and decisions without importing the runner. The protocol and source commit are frozen before two untouched confirmation blocks are evaluated.

**Tech Stack:** Python 3.11+, PyTorch 2.5.1, Transformers, PEFT/QLoRA, bitsandbytes, Hugging Face Datasets, NumPy, pytest/Hypothesis, Ruff, mypy, Kaggle kernels, SHA-256 JSON manifests, existing DOCX/PDF paper builder, GitHub Actions.

---

## File map

- Create `src/erasemap/llm_unlearning_v3.py`: pure v3 data validation, interpolation-grid representation, normalized margins, contiguous robust-interval discovery, deterministic selection, gate aggregation.
- Create `tests/test_llm_unlearning_v3.py`: unit/property tests for pure core and rejection paths.
- Create `benchmark/qwen-tofu-kaggle-v3.json`: complete immutable protocol copied from v2 where required and extended with v3 author blocks, RBEP grid, path grid, secondary gates, and seeds.
- Create `docs/QWEN_TOFU_KAGGLE_V3_PREREGISTRATION.md`: human-readable frozen claim and failure policy.
- Create `tests/test_qwen_tofu_kaggle_v3_protocol.py`: exact protocol invariants and disjointness tests.
- Create `experiments/qwen_tofu_v3_data.py`: complete-author reconstruction, fingerprints, disclosed/confirmation/reserve split, semantic row construction.
- Create `experiments/qwen_tofu_v3_rbep.py`: bounded KL objective, delta ceiling, checkpoint materialization, adapter interpolation.
- Create `experiments/run_qwen_tofu_kaggle_v3.py`: phase-isolated orchestration and append-only evidence output.
- Create `tests/test_qwen_tofu_v3_data.py`: synthetic author-block and semantic-channel tests.
- Create `tests/test_qwen_tofu_v3_rbep.py`: stub-model objective, norm ceiling, and interpolation tests.
- Create `scripts/verify_qwen_tofu_kaggle_v3.py`: standalone offline verifier.
- Create `tests/test_qwen_tofu_kaggle_v3_verifier.py`: valid fixture and tamper tests.
- Create `kaggle/qwen-tofu-v3/run.py`: Kaggle entrypoint.
- Create `kaggle/qwen-tofu-v3/kernel-metadata.template.json`: GPU/network/dataset metadata.
- Create `scripts/kaggle_qwen_tofu_v3.sh`: clean freeze, submit, status, and non-overwriting collect workflow.
- Modify `.github/workflows/ci.yml`: add prospective protocol/core tests; add committed-result verifier only after collection.
- Modify `README.md`, `docs/SCIENTIFIC_CLAIM_MATRIX.md`, `docs/COMPETITION_EVIDENCE_SCORECARD.md`, and both paper sources only after a real result exists.

## Required execution order

Author commitments are data-derived, so the only intentional dependency crossing the numbered
sections is: complete Task 1, then Task 3 Steps 1–3 (author reconstruction and lock CLI), then Task
2 (protocol freeze), then return to Task 3 Steps 4–6. Continue with Tasks 4–10 in order. The protocol
is not called frozen and must not be committed until the lock CLI exists and its emitted commitments
are inserted. This ordering prevents unresolved commitments while still freezing the protocol
before training or confirmation code exists.

### Task 1: Pure robust-path selection core

**Files:**
- Create: `src/erasemap/llm_unlearning_v3.py`
- Create: `tests/test_llm_unlearning_v3.py`

- [ ] **Step 1: Write failing tests for contiguous feasible intervals**

```python
from erasemap.llm_unlearning_v3 import PathPoint, robust_intervals


def test_robust_intervals_require_three_contiguous_points() -> None:
    points = [
        PathPoint("p", 0.10, False, 0.0, 2.0, 0.1),
        PathPoint("p", 0.20, True, 0.2, 2.0, 0.1),
        PathPoint("p", 0.30, True, 0.3, 2.0, 0.1),
        PathPoint("p", 0.40, True, 0.4, 2.0, 0.1),
        PathPoint("p", 0.50, False, 0.0, 2.0, 0.1),
    ]
    intervals = robust_intervals(points, minimum_width=3)
    assert [[point.alpha for point in row] for row in intervals] == [[0.2, 0.3, 0.4]]


def test_two_feasible_points_are_not_selectable() -> None:
    points = [
        PathPoint("p", 0.10, True, 0.2, 2.0, 0.1),
        PathPoint("p", 0.20, True, 0.2, 2.0, 0.1),
    ]
    assert robust_intervals(points, minimum_width=3) == []
```

- [ ] **Step 2: Run the focused tests and confirm the missing-module failure**

Run: `PYTHONPATH=src:. .venv/bin/pytest tests/test_llm_unlearning_v3.py -q`

Expected: collection fails with `ModuleNotFoundError: erasemap.llm_unlearning_v3`.

- [ ] **Step 3: Implement the immutable path point and interval finder**

```python
from __future__ import annotations

from dataclasses import dataclass
from itertools import groupby
from operator import attrgetter


@dataclass(frozen=True, slots=True)
class PathPoint:
    path_id: str
    alpha: float
    feasible: bool
    minimum_margin: float
    minimum_speedup: float
    worst_exact_gap: float


def robust_intervals(
    points: list[PathPoint], *, minimum_width: int
) -> list[list[PathPoint]]:
    if minimum_width < 1:
        raise ValueError("minimum_width must be positive")
    ordered = sorted(points, key=attrgetter("path_id", "alpha"))
    intervals: list[list[PathPoint]] = []
    for _, path_rows_iter in groupby(ordered, key=attrgetter("path_id")):
        current: list[PathPoint] = []
        for point in path_rows_iter:
            if point.feasible:
                current.append(point)
            else:
                if len(current) >= minimum_width:
                    intervals.append(current)
                current = []
        if len(current) >= minimum_width:
            intervals.append(current)
    return intervals
```

- [ ] **Step 4: Add tests for deterministic ranking and interval medoid**

```python
from erasemap.llm_unlearning_v3 import select_robust_point


def test_selector_prefers_width_then_margin_then_gap_then_speed() -> None:
    selected = select_robust_point(
        {
            "a": [
                PathPoint("a", 0.1, True, 0.2, 5.0, 0.08),
                PathPoint("a", 0.2, True, 0.2, 5.0, 0.08),
                PathPoint("a", 0.3, True, 0.2, 5.0, 0.08),
            ],
            "b": [
                PathPoint("b", 0.1, True, 0.1, 9.0, 0.01),
                PathPoint("b", 0.2, True, 0.1, 9.0, 0.01),
                PathPoint("b", 0.3, True, 0.1, 9.0, 0.01),
                PathPoint("b", 0.4, True, 0.1, 9.0, 0.01),
            ],
        },
        minimum_width=3,
    )
    assert (selected.path_id, selected.alpha) == ("b", 0.2)
```

- [ ] **Step 5: Implement complete selector and normalized gate margins**

Implement `gate_margins(metrics, criteria)`, `summarize_path_point(trials, criteria)`, and
`select_robust_point(points_by_path, minimum_width)` so feasibility requires all twelve v2 gates on
every trial. Rank intervals by `(-width, -minimum_margin, worst_exact_gap, -minimum_speedup,
path_id)` and select the lower medoid at index `(len(interval) - 1) // 2`.

```python
def select_robust_point(
    points_by_path: dict[str, list[PathPoint]], *, minimum_width: int
) -> PathPoint:
    intervals = robust_intervals(
        [point for rows in points_by_path.values() for point in rows],
        minimum_width=minimum_width,
    )
    if not intervals:
        raise NoRobustCandidateError("no contiguous feasible alpha interval")
    ranked = sorted(
        intervals,
        key=lambda row: (
            -len(row),
            -min(point.minimum_margin for point in row),
            max(point.worst_exact_gap for point in row),
            -min(point.minimum_speedup for point in row),
            row[0].path_id,
        ),
    )
    winner = ranked[0]
    return winner[(len(winner) - 1) // 2]
```

- [ ] **Step 6: Add Hypothesis tests for ordering invariance, finite values, and no-candidate paths**

Run: `PYTHONPATH=src:. .venv/bin/pytest tests/test_llm_unlearning_v3.py -q`

Expected: all v3 core tests pass.

- [ ] **Step 7: Commit the pure core**

```bash
git add src/erasemap/llm_unlearning_v3.py tests/test_llm_unlearning_v3.py
git commit -m "feat: add robust bounded erasure path selector"
```

### Task 2: Freeze the v3 protocol and claim

**Files:**
- Create: `benchmark/qwen-tofu-kaggle-v3.json`
- Create: `docs/QWEN_TOFU_KAGGLE_V3_PREREGISTRATION.md`
- Create: `tests/test_qwen_tofu_kaggle_v3_protocol.py`

- [ ] **Step 1: Write protocol tests before creating the JSON**

```python
import json
from pathlib import Path


def test_v3_keeps_all_v2_primary_gates() -> None:
    v2 = json.loads(Path("benchmark/qwen-tofu-kaggle-v2.json").read_text())
    v3 = json.loads(Path("benchmark/qwen-tofu-kaggle-v3.json").read_text())
    assert v3["success_criteria"] == v2["success_criteria"]


def test_v3_freezes_two_confirmation_blocks_and_future_reserve() -> None:
    protocol = json.loads(Path("benchmark/qwen-tofu-kaggle-v3.json").read_text())
    blocks = protocol["author_blocks"]
    assert len(blocks["development_pairs"]) == 5
    assert len(blocks["primary_confirmation"]) == 2
    assert len(blocks["replication_confirmation"]) == 2
    used = {
        *sum(blocks["development_pairs"], []),
        *blocks["primary_confirmation"],
        *blocks["replication_confirmation"],
    }
    assert used.isdisjoint(blocks["future_reserve"])
```

- [ ] **Step 2: Run tests and confirm the missing-protocol failure**

Run: `PYTHONPATH=src:. .venv/bin/pytest tests/test_qwen_tofu_kaggle_v3_protocol.py -q`

Expected: `FileNotFoundError: benchmark/qwen-tofu-kaggle-v3.json`.

- [ ] **Step 3: Create the complete protocol**

The JSON must copy the pinned v2 model, dataset revisions, training settings, evaluation counts, and
success criteria by value. Add these frozen v3 fields:

```json
{
  "schema_version": "erasemap-qwen-tofu-kaggle-protocol-v3",
  "method": {
    "id": "reference-bounded-erasure-path",
    "temperatures": [1.0, 2.0],
    "keep_weights": [0.5, 1.0, 2.0],
    "cross_entropy_weight": 0.1,
    "learning_rate": 0.00005,
    "gradient_clip_norm": 1.0,
    "delta_norm_ratio_max": 0.35,
    "steps": 120,
    "checkpoint_steps": [20, 40, 60, 80, 100, 120],
    "alphas": [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.65, 0.80, 1.0],
    "minimum_contiguous_feasible_alphas": 3
  },
  "development_seeds": [20260828, 20260829],
  "confirmation_seeds": [20261001, 20261002, 20261003, 20261004, 20261005],
  "secondary": {
    "retain_only_steps": 40,
    "learning_rate": 0.00005,
    "forget_recovery_increase_max": 0.20
  }
}
```

Author IDs must be explicit fingerprint commitments generated by Task 3 Steps 1–3, not assumed
numeric dataset positions. Run the already-tested author-lock command once, insert its output with
`apply_patch`, and rerun the protocol tests before declaring or committing the protocol freeze.

- [ ] **Step 4: Write the preregistration in plain language**

Document the hypothesis, unchanged gates, exact formulas, disclosed development status, two sealed
confirmation blocks, deterministic selector, `NO_CANDIDATE`, primary/secondary separation, first-run
retention, and prohibited post-freeze changes. Include the protocol SHA-256 and source-parent commit.

- [ ] **Step 5: Validate JSON, gate equality, and prose consistency**

Run:

```bash
.venv/bin/python -m json.tool benchmark/qwen-tofu-kaggle-v3.json >/dev/null
PYTHONPATH=src:. .venv/bin/pytest tests/test_qwen_tofu_kaggle_v3_protocol.py -q
rg -n "0.8|1.25|1.5|five|twelve|NO_CANDIDATE" docs/QWEN_TOFU_KAGGLE_V3_PREREGISTRATION.md
```

Expected: JSON and tests pass; every frozen claim appears in the preregistration.

- [ ] **Step 6: Commit the protocol before runner implementation**

```bash
git add benchmark/qwen-tofu-kaggle-v3.json docs/QWEN_TOFU_KAGGLE_V3_PREREGISTRATION.md tests/test_qwen_tofu_kaggle_v3_protocol.py
git commit -m "experiment: preregister Qwen TOFU v3"
```

### Task 3: Author-block reconstruction and phase-isolated data

**Files:**
- Create: `experiments/qwen_tofu_v3_data.py`
- Create: `tests/test_qwen_tofu_v3_data.py`

- [ ] **Step 1: Write failing complete-block and overlap tests**

```python
import pytest

from experiments.qwen_tofu_v3_data import AuthorBlock, partition_author_blocks


def test_partition_rejects_incomplete_twenty_row_author() -> None:
    rows = [{"question": f"q{i}", "answer": "a", "author": "A"} for i in range(19)]
    with pytest.raises(ValueError, match="20 rows"):
        partition_author_blocks(rows, rows_per_author=20)


def test_partition_is_disjoint_and_commitment_stable(sample_tofu_rows) -> None:
    result = partition_author_blocks(sample_tofu_rows, rows_per_author=20)
    assert isinstance(result[0], AuthorBlock)
    assert len({row.commitment for row in result}) == len(result)
    assert not ({*result[0].fingerprints} & {*result[1].fingerprints})
```

- [ ] **Step 2: Implement canonical fingerprints and blocks**

```python
@dataclass(frozen=True, slots=True)
class AuthorBlock:
    commitment: str
    fingerprints: tuple[str, ...]
    rows: tuple[dict[str, object], ...]


def row_fingerprint(row: Mapping[str, object]) -> str:
    payload = json.dumps(
        {"question": row["question"], "answer": row["answer"]},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()
```

Group by a stable author-profile key available in TOFU rows; if the upstream schema lacks an explicit
key, group only consecutive complete 20-row blocks and bind every ordered row fingerprint. Reject
duplicate fingerprints, partial blocks, perturbed/direct mismatch, or protocol commitment drift.

- [ ] **Step 3: Implement a one-purpose author-lock CLI**

`python -m experiments.qwen_tofu_v3_data --protocol benchmark/qwen-tofu-kaggle-v3.json
--emit-lock /tmp/qwen-v3-author-lock.json` must print only canonical commitments and counts. It must
not train, score, or expose confirmation metrics.

- [ ] **Step 4: Implement explicit phase views**

```python
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
```

`load_development_view()` and `load_confirmation_view(selection_commitment)` are separate public
functions. Confirmation loading requires a valid selection commitment path and rejects absent or
mismatched hashes.

- [ ] **Step 5: Run focused tests**

Run: `PYTHONPATH=src:. .venv/bin/pytest tests/test_qwen_tofu_v3_data.py -q`

Expected: all data isolation and semantic-channel tests pass.

- [ ] **Step 6: Commit the data boundary**

```bash
git add experiments/qwen_tofu_v3_data.py tests/test_qwen_tofu_v3_data.py
git commit -m "feat: isolate Qwen TOFU v3 author blocks"
```

### Task 4: RBEP training and interpolation

**Files:**
- Create: `experiments/qwen_tofu_v3_rbep.py`
- Create: `tests/test_qwen_tofu_v3_rbep.py`

- [ ] **Step 1: Write failing tests for bounded KL and norm projection**

```python
import torch

from experiments.qwen_tofu_v3_rbep import bounded_rbep_loss, project_delta_norm


def test_rbep_loss_is_zero_when_candidate_matches_both_references() -> None:
    logits = torch.tensor([[[1.0, 2.0]]])
    mask = torch.tensor([[True]])
    loss = bounded_rbep_loss(
        candidate_forget=logits,
        base_forget=logits,
        candidate_keep=logits,
        target_keep=logits,
        keep_labels=torch.tensor([[1]]),
        answer_mask=mask,
        temperature=1.0,
        keep_weight=1.0,
        cross_entropy_weight=0.0,
    )
    assert torch.allclose(loss, torch.tensor(0.0), atol=1e-7)


def test_project_delta_norm_caps_ratio() -> None:
    target = {"x": torch.tensor([3.0, 4.0])}
    candidate = {"x": torch.tensor([9.0, 12.0])}
    projected = project_delta_norm(target, candidate, maximum_ratio=0.5)
    assert torch.linalg.vector_norm(projected["x"] - target["x"]) <= 2.5 + 1e-6
```

- [ ] **Step 2: Implement the token-masked KL objective**

Use `torch.nn.functional.kl_div` on temperature-scaled log probabilities, multiply by `T**2`, and
average only over answer-mask positions. Base and target reference logits are detached. Add retained
cross-entropy only when its frozen coefficient is nonzero. Reject empty masks and nonfinite loss.

- [ ] **Step 3: Implement whole-adapter norm projection and interpolation**

```python
def interpolate_adapter(
    target: Mapping[str, Tensor], candidate: Mapping[str, Tensor], *, alpha: float
) -> dict[str, Tensor]:
    if not 0.0 <= alpha <= 1.0 or set(target) != set(candidate):
        raise ValueError("invalid adapter interpolation")
    return {
        key: target[key] + alpha * (candidate[key] - target[key])
        for key in sorted(target)
    }
```

Preserve dtype/device, require identical shapes, and hash canonical CPU tensor bytes after saving.

- [ ] **Step 4: Implement the fixed RBEP trajectory**

`train_rbep_path()` accepts only protocol values, target/base models, development forget/keep rows,
and a seed. It saves only the declared checkpoint steps, applies gradient clipping, projects the
complete LoRA delta to the frozen norm ceiling after every optimizer step, and returns runtime plus
immutable checkpoint descriptors.

- [ ] **Step 5: Run CPU stub tests and a tiny real-model smoke test**

Run:

```bash
PYTHONPATH=src:. .venv/bin/pytest tests/test_qwen_tofu_v3_rbep.py -q
PYTHONPATH=src:. .venv/bin/python experiments/run_qwen_tofu_kaggle_v3.py --smoke --output /tmp/qwen-v3-smoke
```

Expected: unit tests pass; smoke output is labelled `NON_SCIENTIFIC_SMOKE`, contains no confirmation
decision, and verifies after Task 6.

- [ ] **Step 6: Commit RBEP training**

```bash
git add experiments/qwen_tofu_v3_rbep.py tests/test_qwen_tofu_v3_rbep.py
git commit -m "feat: add reference-bounded erasure training"
```

### Task 5: Phase-isolated experiment runner

**Files:**
- Create: `experiments/run_qwen_tofu_kaggle_v3.py`
- Create: `tests/test_qwen_tofu_v3_runner.py`

- [ ] **Step 1: Write runner state-machine tests**

```python
def test_confirmation_requires_committed_selection(tmp_path) -> None:
    runner = FakeRunner(tmp_path)
    with pytest.raises(ValueError, match="selection commitment"):
        runner.run_confirmation()


def test_no_candidate_writes_decision_without_loading_confirmation(tmp_path) -> None:
    runner = FakeRunner(tmp_path, development_feasible=False)
    summary = runner.run()
    assert summary["decision"] == "NO_CANDIDATE"
    assert runner.confirmation_load_count == 0
```

- [ ] **Step 2: Implement append-only phase transitions**

Use states `INITIAL -> DEVELOPMENT_COMPLETE -> SELECTION_COMMITTED -> CONFIRMATION_COMPLETE ->
SECONDARY_COMPLETE -> SEALED`. Each state file contains the previous state digest. Existing output
paths cause immediate refusal. Confirmation metrics are held only inside the confirmation phase and
never passed to the selector.

- [ ] **Step 3: Reuse semantic evaluation without importing v2 selection**

Extract or copy only stable batch-loss helpers from v2. V3 must not call `select_development_candidate`
or use v2 candidate criteria. Evaluate base, target, exact, candidate, and reloaded candidate on all
seven semantic channels and store per-example arrays.

- [ ] **Step 4: Implement development grid execution and selection proof**

For each temperature, keep weight, checkpoint, alpha, fold, and seed, write raw trials incrementally.
Summarize through `llm_unlearning_v3`, then write `selection.json` containing protocol hash, source
commit, selected path/checkpoint/alpha, interval endpoints, all ranking keys, and development digest.

- [ ] **Step 5: Implement primary, replication, baselines, and secondary phases**

The same selection runs on both confirmation blocks and all five seeds. Baselines are descriptive and
stored separately. Retain-only relearning begins from the saved candidate artifact and cannot alter
the primary summary.

- [ ] **Step 6: Seal canonical evidence**

Write the files declared by the design and a manifest that binds each committed JSON/JSONL file plus
the protocol digest. Record source commit, exact revisions, dependency versions, GPU, CUDA, Python,
wall times, adapter hashes, block commitments, and trial counts.

- [ ] **Step 7: Run runner tests and smoke execution**

Run: `PYTHONPATH=src:. .venv/bin/pytest tests/test_qwen_tofu_v3_runner.py -q`

Expected: all state, overwrite, leakage, and evidence-shape tests pass.

- [ ] **Step 8: Commit orchestration**

```bash
git add experiments/run_qwen_tofu_kaggle_v3.py tests/test_qwen_tofu_v3_runner.py
git commit -m "feat: orchestrate phase-isolated Qwen TOFU v3"
```

### Task 6: Independent verifier

**Files:**
- Create: `scripts/verify_qwen_tofu_kaggle_v3.py`
- Create: `tests/test_qwen_tofu_kaggle_v3_verifier.py`

- [ ] **Step 1: Write a minimal valid fixture test**

Build a deterministic fixture with two development paths, one robust interval, two confirmation
blocks, five seeds each, and small raw arrays. Assert the verifier recomputes `PASS` and returns the
selected alpha rather than trusting summary fields.

- [ ] **Step 2: Write one tamper test per trust boundary**

Parameterize mutations for manifest hash, protocol hash, source commit, author overlap, author
fingerprint, development seed, confirmation seed, selection alpha, selection ranking key, adapter
hash, raw loss, aggregate, gate, decision, secondary/primary mixing, and reload value. Every mutation
must raise `ValueError` containing the affected boundary name.

- [ ] **Step 3: Implement verifier-owned recomputation**

The verifier may import pure `llm_unlearning_v3` scoring primitives but must not import the runner,
data loader, training module, or published summary helpers. It reconstructs all trial metrics from
raw arrays, recomputes both block decisions and combined decision, replays robust selection, and
checks the exact file manifest.

- [ ] **Step 4: Add no-result and smoke modes**

Before a GPU result exists, `--protocol-only` verifies the frozen protocol and author commitments.
`--allow-smoke` accepts only a `NON_SCIENTIFIC_SMOKE` result and refuses to emit `PASS`. Default mode
requires all ten real confirmation trials.

- [ ] **Step 5: Run verifier tests and mutation coverage**

Run: `PYTHONPATH=src:. .venv/bin/pytest tests/test_qwen_tofu_kaggle_v3_verifier.py -q`

Expected: valid fixture passes and every mutation fails.

- [ ] **Step 6: Commit the verifier**

```bash
git add scripts/verify_qwen_tofu_kaggle_v3.py tests/test_qwen_tofu_kaggle_v3_verifier.py
git commit -m "feat: independently verify Qwen TOFU v3"
```

### Task 7: Kaggle freeze, wrapper, and infrastructure recovery

**Files:**
- Create: `kaggle/qwen-tofu-v3/run.py`
- Create: `kaggle/qwen-tofu-v3/kernel-metadata.template.json`
- Create: `scripts/kaggle_qwen_tofu_v3.sh`
- Modify: `tests/test_download_kaggle_kernel_output.py`

- [ ] **Step 1: Create a thin Kaggle entrypoint**

```python
from pathlib import Path
import sys

SOURCE = Path("/kaggle/input/erasemap-qwen-tofu-v3-source/erasemap-source")
sys.path.insert(0, str(SOURCE))

from experiments.run_qwen_tofu_kaggle_v3 import main

raise SystemExit(main(["--output", "/kaggle/working/qwen-tofu-v3"]))
```

The real entrypoint also resolves mounted model/dataset assets exactly as the verified v2 wrapper
does and records the mounted source revision before importing project code.

- [ ] **Step 2: Add a pinned kernel metadata template**

Enable one GPU, disable internet, use the existing pinned v1 assets dataset and a new versioned source
dataset, and keep kernel output public only if existing repository policy permits it.

- [ ] **Step 3: Implement `submit`, `status`, and `collect`**

Follow v2's safe behavior: refuse dirty source freeze; archive only committed HEAD; wait for dataset
indexing; include `ERASEMAP_CODE_REVISION`; refuse destination overwrite; download every paginated
file under `qwen-tofu-v3/`; run the standalone verifier after collection.

- [ ] **Step 4: Test pagination, missing source, overwrite refusal, and version labels**

Run:

```bash
PYTHONPATH=src:. .venv/bin/pytest tests/test_download_kaggle_kernel_output.py tests/test_qwen_tofu_kaggle_v3_verifier.py -q
bash -n scripts/kaggle_qwen_tofu_v3.sh
```

Expected: all tests pass and shell syntax is valid.

- [ ] **Step 5: Commit Kaggle tooling**

```bash
git add kaggle/qwen-tofu-v3 scripts/kaggle_qwen_tofu_v3.sh tests/test_download_kaggle_kernel_output.py
git commit -m "build: add Qwen TOFU v3 Kaggle workflow"
```

### Task 8: Freeze-quality audit and local release

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`

- [ ] **Step 1: Add prospective CI gates without claiming a result**

Add protocol/core/data/RBEP/verifier tests through the normal pytest suite and this explicit command:

```yaml
- run: PYTHONPATH=src:. python scripts/verify_qwen_tofu_kaggle_v3.py --protocol-only
```

Do not add default result verification until outputs are committed.

- [ ] **Step 2: Add README prospective instructions and boundaries**

Document `submit/status/collect`, source freeze behavior, `NO_CANDIDATE`, two confirmation blocks,
unchanged 12 gates, and that no v3 performance claim exists before collection.

- [ ] **Step 3: Run complete local QA**

Run:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy --strict src pilot external_challenge external_temporal_challenge external_transfer external_ghostgraph_challenge usability
.venv/bin/python -m pytest --cov=erasemap --cov=external_challenge --cov=external_temporal_challenge --cov=pilot --cov-report=term-missing --cov-fail-under=90
.venv/bin/python -m build
lake build
PYTHONPATH=src:. .venv/bin/python scripts/verify_qwen_tofu_kaggle_v3.py --protocol-only
```

Expected: Ruff and mypy pass; all tests pass; coverage is at least 90%; package and Lean builds pass;
protocol-only verifier succeeds.

- [ ] **Step 4: Commit the frozen executable study**

```bash
git add .github/workflows/ci.yml README.md
git commit -m "experiment: freeze executable Qwen TOFU v3"
git push origin main
```

- [ ] **Step 5: Verify remote delivery before GPU execution**

Confirm local HEAD equals `origin/main`, ahead/behind is `0/0`, worktree is clean, and GitHub Actions
for the freeze commit is successful. Record the full commit in the preregistration and source bundle.

### Task 9: One-shot Kaggle execution

**Files:**
- No tracked changes before a scientific result is available.

- [ ] **Step 1: Submit only the green frozen commit**

Run: `scripts/kaggle_qwen_tofu_v3.sh submit`

Expected: output names the kernel ID and the exact frozen full commit.

- [ ] **Step 2: Monitor without changing scientific inputs**

Run: `scripts/kaggle_qwen_tofu_v3.sh status`

If infrastructure fails before scientific execution, inspect logs and fix only reproducible wrapper,
asset-mount, dependency, or download faults. Do not change splits, seeds, grid, selector, objective, or
gates. Freeze and submit a new source commit with the infrastructure history retained.

- [ ] **Step 3: Collect the first completed scientific execution**

Run: `scripts/kaggle_qwen_tofu_v3.sh collect`

Expected: one append-only directory under `outputs/qwen-tofu-kaggle-v3`, followed by verifier output
of exactly `PASS`, `FAIL`, or `NO_CANDIDATE`.

### Task 10: Verify and publish the actual result

**Files:**
- Create: `docs/QWEN_TOFU_KAGGLE_V3_REPORT.md`
- Create: `outputs/qwen-tofu-kaggle-v3/*`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `docs/SCIENTIFIC_CLAIM_MATRIX.md`
- Modify: `docs/COMPETITION_EVIDENCE_SCORECARD.md`
- Modify: `competition/paper/EraSeMap_scientific_paper_EN.md`
- Modify: `competition/paper/EraSeMap_scientific_paper_RU.md`
- Rebuild: corresponding DOCX and PDF files

- [ ] **Step 1: Reverify from committed-size evidence only**

Run: `PYTHONPATH=src:. .venv/bin/python scripts/verify_qwen_tofu_kaggle_v3.py`

Inspect the manifest, raw arrays, selection proof, all five seeds for each confirmation block,
baseline trials, secondary trials, adapter commitments, and environment. Do not commit large adapter
weights when hashes plus downloadable Kaggle artifacts suffice.

- [ ] **Step 2: Write a result report that preserves every negative endpoint**

Report development interval, selected point, both block decisions, all 12 combined gates, per-seed
ranges, baselines, secondary recurrence, infrastructure attempts, source/protocol hashes, and claim
limits. If the result is `FAIL`, say `FAIL` in the title and first paragraph.

- [ ] **Step 3: Synchronize all claim surfaces**

Update README, claim matrix, scorecard, and English/Russian papers with the same numbers. Do not
increase independence. Do not call the method certified, pretraining deletion, general LLM
unlearning, or production validation. A PASS may strengthen the pinned model-method claim only.

- [ ] **Step 4: Add default result verification to CI**

```yaml
- run: PYTHONPATH=src:. python scripts/verify_qwen_tofu_kaggle_v3.py
```

- [ ] **Step 5: Rebuild bilingual papers**

Run the bundled workspace Python on `competition/paper/build_papers.py`, convert both DOCX files to
PDF with headless LibreOffice, inspect page counts, and confirm v3 metrics appear in extracted PDF
text.

- [ ] **Step 6: Run full QA again**

Repeat every command in Task 8 Step 3 plus default v3 result verification. Expected: all gates pass
at the engineering level even when the scientific result is `FAIL`.

- [ ] **Step 7: Commit and publish evidence**

```bash
git add .github/workflows/ci.yml README.md docs competition/paper
git add -f outputs/qwen-tofu-kaggle-v3/MANIFEST.sha256.json outputs/qwen-tofu-kaggle-v3/development.json outputs/qwen-tofu-kaggle-v3/selection.json outputs/qwen-tofu-kaggle-v3/summary.json outputs/qwen-tofu-kaggle-v3/trials.jsonl outputs/qwen-tofu-kaggle-v3/baseline_trials.jsonl outputs/qwen-tofu-kaggle-v3/secondary_trials.jsonl
git commit -m "experiment: publish Qwen TOFU v3 result"
git push origin main
```

- [ ] **Step 8: Verify final delivery**

Fetch `origin/main`; require identical local/remote HEAD, ahead/behind `0/0`, clean worktree, remote
evidence files present, and successful GitHub Actions for both test and formal jobs.
