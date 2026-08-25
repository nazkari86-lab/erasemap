# Qwen–TOFU Kaggle v1 preregistration

Date frozen: 2026-08-25, before the first GPU execution.

## Question

Can a bounded unlearning update to a Qwen2.5-1.5B LoRA adapter approach an adapter trained from the
same frozen base without the requested TOFU profiles, while retaining unrelated profiles and world
facts? Can EraSeMap refuse `COMPLETE` whenever memorization, forget quality, retained utility,
membership-risk similarity, perturbed-query transfer, or reload recurrence fails its frozen gate?

## Design

- model: `Qwen/Qwen2.5-1.5B` base, pinned Hugging Face revision, NF4 QLoRA;
- source: pinned `locuslab/TOFU` revision;
- deletion unit: the official `forget01` subject group;
- target: fresh adapter trained on `full`;
- exact reference: fresh adapter trained from the identical base and seed on `retain99`;
- candidate: target adapter updated for 120 paired retain/forget gradient-difference steps;
- repetitions: three frozen seeds;
- evaluation: direct forget, perturbed forget, holdout, retained, perturbed retained, and world-fact
  conditional answer loss, plus a loss-based membership AUC and post-save/reload recurrence check.

The exact reference is exact only for the registered adapter-training procedure. Qwen pretraining is
frozen and is not claimed to be unlearned.

## Fail-closed rule

All gates in `benchmark/qwen-tofu-kaggle-v1.json` are conjunctive. A failed scientific gate produces
`FAIL`; missing, malformed, source-drifted, non-finite, seed-incomplete, or unrecomputable evidence
produces verifier rejection rather than `PASS`. The first valid GPU result is retained even if it is
negative. Thresholds are not changed after observing it.

## Independence boundary

TOFU and Qwen are external open inputs, but experiment design, execution, mappings, and analysis are
project-operated. A Kaggle GPU is real external compute, not an independent evaluator. This result
cannot change the 7.8/10 independence score.
