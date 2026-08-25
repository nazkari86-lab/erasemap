# Qwen–TOFU Kaggle v2 adaptive preregistration

Date frozen: 2026-08-25, before the first v2 GPU execution.

## Why v2 exists

V1 remains a public negative result. Its candidate passed six valid gates, failed forgetting and
world-utility gates, and contained one invalid perturbed-answer gate because the evaluator read the
ordinary `answer` field from the perturbed split. V2 does not reinterpret or overwrite v1.

The v1 candidate recovered only 33.8–39.1% of the exact-reference forgetting lift. V2 therefore
replaces the loose absolute proximity criterion with normalized recovery relative to the target and
exact models.

## Locked design

- The target is a Qwen2.5-1.5B NF4 QLoRA adapter trained on TOFU `full`.
- The exact reference starts from the same frozen base and excludes the registered deletion rows.
- Development deletion rows are `forget05` minus every `forget01` row. Development utility and
  exact-reference training use `retain95`, so the reserved `forget01` authors are absent from both
  sides of selection. Confirmation uses only `forget01` with `retain99`, making method selection
  author-disjoint from the final deletion group.
- Six declared hyperparameter configurations are evaluated on two development seeds.
- A deterministic selection rule minimizes normalized gate violation, then prefers stronger exact
  recovery, lower utility damage, higher speed, and finally lexical candidate id.
- The selected configuration is evaluated once on five untouched confirmation seeds.
- The v1 paired-gradient-difference recipe is rerun as a same-environment baseline.

No confirmation metric may select a configuration or change a gate.

## Corrected semantic evaluation

The evaluator uses:

- `answer` for direct questions;
- `paraphrased_question` and `paraphrased_answer` for paraphrase transfer;
- all five values in `perturbed_answer` for false-answer separation;
- paired truth margin: mean perturbed-answer NLL minus paraphrased-answer NLL;
- retained profiles, held-out profiles, untouched TOFU world facts, and a disjoint real-author test
  partition;
- loss-based membership AUC, measured training time, and exact save/reload recurrence.

The 50 real-author anchor rows available to the candidate are disjoint from the 50 real-author test
rows. World-fact test rows are never used for optimization or selection.

## Candidate

Utility-Constrained Selective Gradient Projection (UCSGP) chooses forget-answer tokens using their
frequency ratio between forget and retain/anchor answers. It computes a utility gradient from
retain profiles and real-author anchors and a forgetting gradient only on selected answer tokens.
Whenever those gradients conflict, it removes the first-order utility-harming component of the
forgetting gradient before applying the update.

This is an empirical project candidate. The protocol does not claim that the composition is unique
in the literature or that gradient orthogonality provides certified deletion.

## Primary endpoint

For each seed:

\[
R_f = \frac{L_{candidate,forget}-L_{target,forget}}
           {L_{exact,forget}-L_{target,forget}}.
\]

`R_f = 0` means no measured movement from the target; `R_f = 1` matches the exact reference on this
endpoint. Confirmation requires `0.8 <= R_f <= 1.25` for every seed plus all eleven remaining
utility, transfer, privacy-proxy, efficiency, and persistence gates in the frozen JSON protocol.

## Claim boundary

A PASS would support only this pinned adapter-level procedure. A FAIL remains a valid result.
Neither outcome establishes pretraining-data deletion, certified privacy, an independent external
replication, or production FaceID/eGov validation.
