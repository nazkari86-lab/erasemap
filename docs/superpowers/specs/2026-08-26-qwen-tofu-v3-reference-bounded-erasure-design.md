# Qwen–TOFU v3 reference-bounded erasure design

Date: 2026-08-26

Status: design approved in conversation; implementation and protocol freezing require a separate
reviewed plan.

## Objective

Build and prospectively evaluate a third adapter-level unlearning candidate that addresses the
specific v2 failure: a configuration that matched exact retraining on disclosed development authors
overscrubbed five author-disjoint confirmation seeds by 4.957–8.632 times. V3 must control the
magnitude of forgetting without using any v3 confirmation metric for method, checkpoint, or
hyperparameter selection.

The primary success claim is deliberately narrow:

> On the pinned Qwen2.5-1.5B and TOFU adapter procedure, the frozen v3 candidate passes all twelve
> unchanged v2 gates on every preregistered confirmation seed and both untouched author blocks.

No outcome establishes deletion from Qwen pretraining, certified privacy, arbitrary-model
generalization, external replication, or production readiness. A failed first run is retained.

## Decision summary

V3 uses a **Reference-Bounded Erasure Path (RBEP)** rather than further unbounded ascent. It creates
a bounded forget direction by aligning forget-token predictions toward the pinned base model,
preserves retain behavior by aligning to the target model, saves a fixed trajectory of candidate
checkpoints, and selects the center of a contiguous robust interpolation interval using disclosed
development evidence only.

This is a project method name, not a claim that bounded objectives, KL alignment, gradient conflict
handling, checkpoint selection, or weight interpolation are individually new. The potential
contribution is their fail-closed, exact-reference-calibrated, author-disjoint composition and the
prospective evidence it produces.

## Alternatives considered

1. **Adaptive dual-gradient optimization.** It can tune forgetting and utility constraints during
   training, but two development seeds provide a weak basis for stable dual dynamics. It adds
   optimizer risk before solving the more direct magnitude-calibration failure.
2. **Deletion-by-design adapter shards.** Dropping an author shard can make deletion cheap, but it
   changes the question from post-hoc unlearning of an already trained adapter. It is valuable as a
   future systems baseline, not the primary v3 candidate.
3. **RBEP, selected.** A bounded reference objective plus a preregistered interpolation path directly
   targets overscrubbing, preserves the existing target/exact comparison, and permits robust
   selection without inspecting confirmation.

## Frozen scientific boundary

V3 preserves these v2 invariants:

- model: `Qwen/Qwen2.5-1.5B` at revision
  `8faed761d45a263340a0528343f099c05c9a4323`;
- dataset: `locuslab/TOFU` at revision
  `324592d84ae4f482ac7249b9285c2ecdb53e3a68`;
- NF4 QLoRA target and exact-reference procedure;
- 256-token maximum length, rank-8 LoRA on `q_proj` and `v_proj`, three target/exact epochs;
- direct answer, correct paraphrase, all five perturbed answers, retain, holdout, world-fact,
  disjoint real-author, membership-AUC, runtime, and reload channels;
- all twelve numerical v2 gates, including per-seed normalized recovery in `[0.8, 1.25]` and
  speedup of at least `1.5x`;
- a conjunctive decision: one failed gate makes the scientific decision `FAIL`.

Protocol values may be copied into a new v3 JSON but never read indirectly from the mutable v2
file. The v3 protocol hash and source commit are frozen before any v3 GPU confirmation run.

## Author isolation

TOFU author identity is reconstructed from complete 20-row profile blocks and bound by ordered
question/answer fingerprints. The implementation must verify block completeness and must fail if
ordering, counts, fingerprints, or perturbed-answer alignment drift.

- **Disclosed development pool:** the ten authors already exposed through v1/v2 `forget01` and
  `forget05`. They may be reorganized into five two-author deletion folds because they are no longer
  eligible to provide new confirmation evidence.
- **Primary confirmation block:** the next two complete authors available in `forget10` but absent
  from `forget05`.
- **Replication confirmation block:** the following two complete authors from the same previously
  unused region.
- **Future reserve:** every remaining author in `forget10 - forget05` stays unused by v3.

The protocol stores only deterministic block commitments until the run bundle is frozen. Selection
code receives development rows only. Confirmation loaders and scorers live behind a separate phase
boundary and cannot return metrics to the selector.

## RBEP candidate

Let `theta_t` be the target adapter, `theta_b` the zero/full-free base adapter state, and `theta` the
candidate. For forget prompt tokens, the method minimizes a bounded divergence toward the base
distribution instead of maximizing cross-entropy without limit:

`L_forget(theta) = KL(p_b(.|x) || p_theta(.|x))`.

For retained and real-author anchor tokens it minimizes target-preservation divergence:

`L_keep(theta) = KL(p_t(.|x) || p_theta(.|x)) + gamma * CE_theta(x, y)`.

The training objective is `L_forget + lambda * L_keep`, with all coefficient choices declared in a
small development grid. The KL orientation, temperature, token mask, coefficient grid, optimizer,
step count, checkpoint schedule, and random seeds are frozen. Gradient clipping and a LoRA-delta
norm ceiling stop divergent paths. If the proposed step violates the norm ceiling, it is scaled to
the boundary rather than silently skipped.

The method saves a fixed set of trajectory checkpoints. Each aggressive checkpoint `theta_u`
defines a linear adapter path

`theta(alpha) = theta_t + alpha * (theta_u - theta_t)`, with `0 <= alpha <= 1`.

The alpha grid is declared before execution. Interpolation is applied to complete adapter tensors,
not selected layers, and every interpolated artifact receives a SHA-256 commitment.

## Robust development selection

Each candidate path is evaluated across all five disclosed two-author folds and frozen development
seeds. Selection uses exact retraining only in development. For every `(checkpoint, alpha)` pair,
the evaluator recomputes the same twelve gates used at confirmation.

A point is development-feasible only if all gates pass for every fold and seed. A path is selectable
only if it contains a contiguous interval of at least three feasible alpha values. This rejects a
single lucky point. The deterministic selector then chooses:

1. the path with the widest feasible alpha interval;
2. the largest minimum normalized gate margin across folds and seeds;
3. the lowest worst-case retain/paraphrase/membership gap;
4. the highest minimum speedup;
5. lexical candidate ID as the final tie-breaker.

The selected alpha is the interval medoid, not the strongest-forgetting endpoint. If no robust
interval exists, v3 stops with `NO_CANDIDATE` and confirmation is not run. This outcome is not a
scientific PASS and does not authorize changing the grid or gates under the same protocol version.

## Confirmation

The selected candidate ID, checkpoint, and alpha are written to a selection commitment before the
confirmation phase is allowed to load either untouched author block. The same locked selection is
then evaluated on:

- five new seeds for the primary block;
- the same five seeds for the replication block;
- the same-environment paired-gradient v1 recipe and frozen UCSGP v2 recipe as descriptive
  baselines; neither baseline participates in selection.

The headline decision is `PASS` only if all twelve gates pass on all ten candidate trials. Results
for the two blocks are also reported separately so a replication failure cannot be hidden by an
aggregate.

## Secondary stress tests

Secondary endpoints cannot rescue or invalidate the frozen primary decision, but they reveal
dormant knowledge and brittleness:

- retain-only fine-tuning followed by complete reevaluation to measure forget recurrence;
- prompt paraphrases and all registered false answers after the relearning probe;
- parameter-delta norm and layerwise concentration;
- per-author and worst-decile recovery, not only overall means;
- output-format and finite-value checks after every checkpoint.

The secondary preregistration sets thresholds before execution. Any relearning recurrence is
reported plainly and blocks broader tamper-resistance language even if the primary endpoint passes.

## Components and interfaces

1. `llm_unlearning_v3` contains pure validation, scoring, gate, interpolation-grid, robust-interval,
   and deterministic-selection functions. It imports no datasets or GPU libraries.
2. The v3 experiment runner owns dataset loading, model training, checkpoint materialization, phase
   isolation, evaluation, and append-only output production.
3. A standalone verifier owns manifest validation, source/protocol ancestry, author commitments,
   selection replay, raw-array shape checks, metric recomputation, gate recomputation, and decision
   recomputation. It does not import the runner.
4. The Kaggle wrapper freezes a clean git archive, records the exact commit, refuses overwrite, and
   distinguishes infrastructure failure from a scientific `FAIL`.
5. CI verifies committed results only after a first execution is collected; prospective CI tests
   validate the protocol and pure selection logic without fabricating GPU results.

## Output contract

The append-only result directory contains:

- `development.json` with every raw trial and robust-interval selection proof;
- `selection.json` committed before confirmation evaluation;
- `trials.jsonl` and `baseline_trials.jsonl` with per-example arrays for ten confirmation trials;
- `secondary_trials.jsonl` for relearning stress tests;
- `summary.json` with separate primary, replication, combined, baseline, and secondary sections;
- `MANIFEST.sha256.json` binding every committed evidence file and the protocol digest;
- environment metadata, model/dataset revisions, GPU, dependency versions, runtimes, adapter hashes,
  and full source commit.

Large model checkpoints remain downloadable Kaggle artifacts and are represented in the committed
evidence by their hashes. Raw arrays and all material needed for offline recomputation are committed.

## Failure handling

- Missing or malformed data, author overlap, source drift, nonfinite loss, incomplete seed list,
  selection/confirmation leakage, adapter-hash mismatch, reload mismatch, or manifest mismatch
  produces verifier failure, not `PASS`.
- Kaggle setup/download failures are labelled infrastructure failures and do not become scientific
  results.
- A completed, valid run with any failed gate is committed unchanged as scientific `FAIL`.
- No v3 threshold, split, seed, grid, objective, checkpoint, or tie-breaker changes after the source
  freeze. Any follow-up requires v4.

## Verification plan

Before GPU submission:

- unit/property tests for bounded metrics, interpolation, robust intervals, tie-breakers, and all
  rejection paths;
- protocol tests for exact v2 gate equality, author-block disjointness, fingerprint commitments,
  phase isolation, and confirmation blindness;
- CPU smoke execution using a tiny local model or deterministic stub, clearly marked non-scientific;
- Ruff, strict mypy, full pytest with at least 90% coverage, package build, and existing Lean build;
- frozen preregistration, design, implementation, and protocol committed to `main` with green CI.

After Kaggle completion:

- collect without overwriting;
- run the independent verifier from a clean checkout;
- inspect raw per-seed metrics and both block decisions;
- update README, reports, claim matrix, scorecard, and synchronized English/Russian papers with the
  actual `PASS`, `FAIL`, or `NO_CANDIDATE` result;
- add result verification to CI, rerun all local gates, rebuild DOCX/PDF, push to `main`, and require
  successful GitHub Actions.

## Success and honest scoring

Implementation quality can be completed locally. A scientific v3 score cannot be raised before the
one-shot GPU evidence exists. A 10/10 label is not assigned merely for 12/12 gates: a v3 PASS would
be a strong project-operated result on one pinned model and benchmark. Cross-model replication,
independent authorship, certified guarantees, and production evidence remain separate future
events.
