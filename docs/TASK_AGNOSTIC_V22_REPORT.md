# Task-Agnostic Identity-Unlearning v2.2

## Purpose

V2.2 closes the largest remaining local evaluation gap from the v2.1 critique: privacy was tested
with four output statistics but without trained shadow models or an embedding attacker. The
unlearning method, utility endpoint, primary 1% non-inferiority margin, and 0.10 privacy-equivalence
margin were not relaxed.

## Freeze and threat model

- Freeze commit: `979865e69cd0401e28048de6b26d78ea7265d75d`
- Protocol SHA-256: `e2f31e2aff31c8aa16e545503561545a59333c69b7f096dbe81ce358c3a47bc9`
- Six registered attacks: confidence, energy, margin, negative entropy, task-agnostic LiRA, and embedding nearest neighbour
- LiRA calibration: 16 shadow models per seed, 100 epochs each
- Every evaluated sample appears in exactly eight shadow models and is absent from exactly eight
- Per-sample in/out negative-entropy distributions are fitted as Gaussians
- The likelihood ratio is evaluated in both orientations and reports AUC plus TPR at FPR 1%
- The embedding attacker receives an auxiliary gallery of forgotten-member embeddings; exact self-matches are removed

This is an online, task-agnostic LiRA variant. It uses negative entropy because exact retraining has
no output class for the forgotten identity, so a true-label loss is not comparable across methods.
It is stronger than the previous max-softmax check but should not be described as the canonical
class-label LiRA protocol.

## Frozen results

Each row aggregates 100 identity deletions and 500 method evaluations.

| Split | PASS | Primary ratio | Worst privacy gap | LiRA AUC selective / exact | LiRA TPR@1% selective / exact | Embedding AUC selective / exact | Speedup |
|---|---:|---:|---:|---:|---:|---:|---:|
| Olivetti development | yes | 1.00483 | 0.01810 | 0.67095 / 0.65286 | 0.36857 / 0.37857 | 0.71762 / 0.72524 | 3.21× |
| LFW confirmation | yes | 1.00467 | 0.02055 | 0.59430 / 0.58748 | 0.13136 / 0.13981 | 0.59507 / 0.59082 | 7.04× |
| MUFAC external | yes | 1.00326 | 0.04079 | 0.69519 / 0.68865 | 0.42523 / 0.41825 | 0.73099 / 0.71931 | 3.51× |

For MUFAC, selective LiRA AUC had a bootstrap 95% interval of 0.67203–0.72148; exact was
0.66664–0.71085. Selective TPR@1% was 0.42523 (0.37331–0.47711); exact was 0.41825
(0.37304–0.46409). These intervals overlap substantially. The supported conclusion is
non-inferiority to exact under this threat model, not absence of membership leakage.

## Generator-independent system fixtures

`benchmark/manual-pipelines-v1.json` contains five manually specified, non-generated pipelines:
a stale government regional cache, an unreachable mobile secure template, a completed school
attendance deletion, a bank backup awaiting expiry, and a failed border-model audit. All five
matched their registered status, residual terminal, and invalid-evidence expectations.

These fixtures reduce coupling to EraseMap's random case generator, but they are explicitly
`project-authored`. They are not independent external evidence. The JSON contract and runner allow
an outside evaluator to provide a hidden suite without changing audit code.

## Reproduction

```bash
PYTHONPATH=src python experiments/task_agnostic_unlearning_v2.py \
  --protocol benchmark/task-agnostic-v22.json --split external \
  --output outputs/task-agnostic-v22-external
PYTHONPATH=src python experiments/run_manual_pipeline_benchmark.py
```

Non-development model evaluation requires a clean worktree and writes an immutable lock containing
the code revision and protocol hash.

## Remaining external blocker

Everything reproducible within the repository is implemented. The remaining high-value evidence
cannot be manufactured locally: an authorized institution must map its real stores and supply
signed probes, or an independent evaluator must author and withhold pipeline fixtures. Until then,
EraseMap is a strong research prototype, not a validated eGov, Face ID, bank, or government system.

## Research context

- [LiRA: Membership Inference Attacks From First Principles](https://arxiv.org/abs/2112.03570)
- [Task-agnostic identity unlearning and MUFAC](https://arxiv.org/abs/2311.02240)
- [Official MUFAC implementation](https://github.com/ndb796/machineunlearning)
