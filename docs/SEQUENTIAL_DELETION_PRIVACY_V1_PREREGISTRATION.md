# Sequential deletion privacy v1 — preregistration

## Status and claim boundary

This document freezes the protocol **before** the first confirmatory run. The experiment is
project-authored and uses an externally published face dataset. It can support a new sequential
release result, but it cannot create independent evidence. The four attacks below use observed
release differences and no shadow models; they are not a complete adaptive privacy audit.

## Research question

Across five consecutive identity deletions, does a bounded deletion-matched restart remain close
to exact retraining in retained utility, forgotten-identity verification behavior, retained
representations, and retained-user membership exposure created by publishing successive models?

## Frozen design

- Dataset: Olivetti Faces, 40 identities and 400 images, loaded through scikit-learn.
- Inputs: the existing frozen 512-dimensional MobileFaceNet embeddings.
- Split: seven training and three testing images per identity, using the previously registered
  deterministic split seed.
- Independent units: five deletion sequences, each containing five without-replacement identity
  deletions; 25 release transitions in total.
- Exact reference: fresh model trained for 100 epochs on all identities retained at that step.
- Candidate: fresh model with the same initialization rule and retained data, trained for 60 epochs.
- A deleted identity is absent from every optimization step and from the candidate classifier.
- No threshold or hyperparameter may change after the result is observed.

## Retained-user privacy threat model

An observer receives two consecutive model releases and attempts to infer whether a still-retained
sample belonged to training. For every retained training and test sample, the experiment calculates
the absolute release-to-release change in confidence, energy, margin, and negative entropy. Each
signal is evaluated as a symmetric membership attack. Candidate-minus-exact advantage is paired by
sequence and deletion step; deterministic bootstrap 95% intervals are computed over all 25
transitions.

This measures additional exposure associated with the candidate relative to exact retraining. It
does not claim that exact retraining is private, and the report must preserve exact attack values.

## Frozen gates

All gates must pass:

1. Every deleted classifier class is absent after its deletion.
2. Candidate epoch-budget speedup is at least 1.5×.
3. Candidate retained-accuracy difference is at least −0.02 on every transition.
4. Maximum retained embedding MSE to exact is at most 0.001.
5. Maximum absolute forgotten-verification AUC gap to exact is at most 0.05.
6. The largest 95% upper confidence bound across the four paired privacy-advantage differences is
   at most 0.05.

The primary safety endpoint is gate 6. Failure of any gate requires exact retraining fallback and
must remain published as a negative result.

## Execution lock

The protocol, implementation, and tests must first be committed with no result files. The first
confirmatory run then requires a clean worktree and records the full code revision, protocol hash,
embedding hash, raw transition records, result hashes, and every gate. The output directory refuses
overwrite.

```bash
python -m experiments.sequential_deletion_privacy \
  --protocol benchmark/sequential-deletion-privacy-v1.json \
  --output benchmark/results/sequential-deletion-privacy-v1
```
