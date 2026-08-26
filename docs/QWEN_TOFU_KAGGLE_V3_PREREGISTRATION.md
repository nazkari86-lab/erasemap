# Qwen–TOFU v3 preregistration: Reference-Bounded Erasure Path

Date frozen: 2026-08-26  
Protocol status: `FROZEN_BEFORE_FIRST_V3_GPU_RUN`  
Protocol SHA-256: `23c3e4fc68930cce97550260a57a63e05a197c5ca7347ac773a434b1e4c762e9`  
Source-parent commit: `b204bfee61fa7b7b544bb0f4ac9bb3881b8b51f0`

## Why this experiment exists

Qwen–TOFU v2 selected a candidate on disclosed development data but overscrubbed all five untouched
confirmation seeds. V3 tests one prospective correction: can a bounded path toward the base model
recover exact-retraining-like forgetting without damaging retained behavior? The previous negative
results stay published and are not reinterpreted.

The primary hypothesis is narrow: one development-selected RBEP point will pass all twelve unchanged
v2 gates on every one of five frozen seeds for both untouched two-author blocks. That means ten
conjunctive confirmation trials. One failed gate makes the combined decision `FAIL`.

## Frozen data boundary

The model is `Qwen/Qwen2.5-1.5B` at commit
`8faed761d45a263340a0528343f099c05c9a4323`; TOFU is pinned at commit
`324592d84ae4f482ac7249b9285c2ecdb53e3a68`. The direct and perturbed `forget10` files are bound by
their SHA-256 digests in the protocol.

TOFU contains twenty consecutive, complete profiles of twenty question/answer rows each. Every
profile is committed by the ordered SHA-256 fingerprints of those rows. The first ten disclosed
authors form five two-author development folds. Authors 10–11 are the sealed primary confirmation
block, authors 12–13 are the sealed replication block, and authors 14–19 remain unused future
reserve. The loader rejects incomplete blocks, duplicates, ordering drift, commitment drift, and
direct/perturbed mismatch.

Only development rows may be loaded before `selection.json` is committed. Confirmation loading
requires that commitment, and the selector has no confirmation input. Five confirmation seeds
(`20261001` through `20261005`) are disjoint from the two development seeds.

## Frozen method

Let `theta_t` be the trained target adapter, `theta_b` the pinned base reference, and `theta` the
candidate. On answer tokens of deleted authors, RBEP minimizes

`L_forget = T^2 KL(p_b^T(.|x) || p_theta^T(.|x))`.

On retained and real-author anchor tokens it minimizes

`L_keep = T^2 KL(p_t^T(.|x) || p_theta^T(.|x)) + 0.1 CE_theta(x,y)`.

The total loss is `L_forget + lambda L_keep`. The frozen development grid uses temperatures
`{1, 2}` and keep weights `{0.5, 1, 2}`. Training uses 120 steps, learning rate `5e-5`, gradient
clip 1.0, and a whole-LoRA-delta norm ceiling of 0.35 relative to the target adapter norm. The six
declared checkpoints are steps 20, 40, 60, 80, 100, and 120.

For each checkpoint `theta_u`, the fixed interpolation path is

`theta(alpha) = theta_t + alpha (theta_u - theta_t)`

at eleven preregistered alphas from 0.05 to 1.0. No checkpoint, alpha, temperature, weight, or seed
may be added after this freeze under v3.

## Exact deterministic selection

Every path point is evaluated on all five development folds and both development seeds against the
same twelve gates used for confirmation. A point is feasible only if every gate passes on every
trial. A path is selectable only when at least three adjacent declared alphas are feasible.

Intervals are ranked by: widest interval; largest worst-case normalized gate margin; lowest
worst exact-reference gap; highest minimum speedup; lexical path ID. The selected point is the lower
medoid of the winning interval. If no interval contains at least three feasible alphas, the result is
`NO_CANDIDATE`; confirmation is not loaded or executed. `NO_CANDIDATE` is not a scientific pass.

## Twelve unchanged primary gates

The v2 thresholds are copied by value into the v3 protocol:

1. target memorization gain at least 0.1;
2. exact-retraining forgetting lift at least 0.05;
3. candidate/exact normalized recovery from 0.8 through 1.25;
4. candidate/exact paraphrase NLL gap at most 0.2;
5. candidate/exact truth-margin gap at most 0.2;
6. candidate/exact retained NLL gap at most 0.15;
7. world-fact NLL degradation at most 0.2;
8. real-author NLL degradation at most 0.2;
9. candidate/exact membership-AUC gap at most 0.1;
10. speedup over exact retraining at least 1.5x;
11. retained recurrence after reload at most `1e-6`;
12. all computed values and required arrays must be valid and complete.

The final item is enforced structurally by the runner and verifier; the numerical criteria object is
exactly equal to v2. A `PASS` requires all numerical and structural gates on all ten candidate trials.
Primary and replication block decisions are also reported separately. V1 and v2 recipes are
descriptive baselines only and cannot change selection or the decision.

## Secondary relearning stress test

After sealing the primary outcome, the selected adapter receives 40 retain-only steps at learning
rate `5e-5`, followed by full reevaluation. A forget-recovery increase above 0.20 blocks any broad
tamper-resistance claim. This secondary endpoint cannot rescue or invalidate the frozen primary
decision.

## Failure and publication policy

Infrastructure failure is not a scientific result. The first completed, verifier-valid v3 run is
retained whether its decision is `PASS`, `FAIL`, or `NO_CANDIDATE`. Missing evidence, overlap,
nonfinite values, hash drift, phase leakage, incomplete seeds, reload mismatch, or manifest mismatch
is a verifier failure and can never become `PASS`.

After this freeze, changing any split, objective, grid, checkpoint, seed, threshold, tie-breaker, or
gate requires a separately disclosed v4. Confirmation results may not be used to modify v3.

## Claim boundary

Even a 12/12 `PASS` would show only a project-operated adapter-level result on one pinned 1.5B model
and one open benchmark. It would not prove deletion from Qwen pretraining, certified privacy,
cross-model generalization, independent replication, or production readiness.
