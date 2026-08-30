# Task-Agnostic Identity-Unlearning v2

## Research question

Can a biometric system remove one person's training influence while preserving the unchanged task
of face verification, and can EraseMap distinguish this from an output-only deletion?

Unlike v1 class deletion, v2 does not use disappearance of an identity label as its endpoint. The
training classifier supervises a 512→128 local embedding encoder, but evaluation uses normalized
embeddings, same/different-person pairs, representation similarity, privacy attacks, and distance
to exact retraining. The pretrained MobileFaceNet input backbone remains frozen and outside the
unlearning claim.

## Pre-registered design

The protocol was committed as `028a872` before the first v2 run. A performance-only pair-sampling
change and a negative-pool correctness fix were committed before a result existed. The LFW
evaluation then required a clean tree and wrote a lock before training:

- code revision: `9fb62df8c3056c312b690ca096536a0b6ae6a931`
- protocol SHA-256: `55e6f38fdc3edfb12004a223445511cee2f8674e786a5a6215e51051385a681e`
- five seeds × twenty forgotten identities = 100 deletion trials per dataset
- five methods per deletion = 500 method evaluations per dataset
- 2,000 bootstrap resamples for every reported 95% interval

Methods were stale deployment, output-head-only retraining, gradient ascent, EraseMap-LGU, and
exact retraining. LGU ranks parameters by forgotten-sample gradient influence, updates only the
top 25%, applies controlled forgetting, and distills retained representations toward the original
model.

## Evaluation result

| Method | Retained AUC | TAR at FAR 1% | MIA AUC | Embedding MSE to exact | CKA to exact | Speedup |
|---|---:|---:|---:|---:|---:|---:|
| Stale | 0.99395 | 0.93671 | 0.67391 | 0.002041 | 0.99056 | n/a |
| Head only | 0.99395 | 0.93671 | 0.45293 | 0.002041 | 0.99056 | 1.64× |
| Gradient ascent | 0.96387 | 0.71355 | 0.54908 | 0.002835 | 0.87404 | 3.24× |
| **EraseMap-LGU** | **0.99301** | **0.92280** | **0.50521** | **0.002381** | **0.98685** | **3.78×** |
| Exact retraining | 0.99424 | 0.93751 | 0.47527 | 0 | 1 | 1× |

LGU passed all frozen criteria. Its retained AUC was 0.12 percentage points below exact, MIA was
near chance, and it was 3.78× faster. Its TAR cost was larger—1.47 percentage points—so exact
retraining remains the strongest utility reference.

The 95% intervals were:

- LGU retained AUC: 0.99277–0.99325; exact: 0.99401–0.99447.
- LGU TAR: 0.92060–0.92492; exact: 0.93606–0.93891.
- LGU MIA AUC: 0.48553–0.52370; exact: 0.45269–0.49694.
- LGU speedup: 3.71×–3.84×.

The head-only encoder is mathematically unchanged from stale: both have the same embedding MSE,
CKA, verification AUC, and TAR. Its lower confidence-based MIA therefore cannot be interpreted as
removal of training influence. This is the central counterexample EraseMap exposes.

Gradient ascent again overscrubbed: TAR fell by 22.40 percentage points relative to exact. Its
higher speed is therefore not a valid engineering success.

## System audit result

The independent core holdout ran 660 method trials over graph sizes 10, 100, and 1,000, five unseen
seeds, eleven clean/fault conditions, and four audit methods. EraseMap had:

- false `COMPLETE`: 0%;
- residual recall: 100%;
- precision: 100%;
- exact faulty-node recall: 100%;
- benchmark failures: 0;
- mean runtime: 0.82 ms.

Receipt-only auditing falsely declared 96.67% of faulty cases complete; flat checklists falsely
completed 60%; untyped traversal falsely completed 40%.

The production-like eGov simulator additionally enrolled 25 anonymous citizens into real SQLite,
vector-index, cache, AES-GCM backup, and model-lineage artifacts. Five sequential deletion
requests were `INCOMPLETE` after source-only deletion and `COMPLETE` after remediation. All twenty
retained citizens stayed intact, all chained Ed25519 receipts verified, and a modified receipt was
rejected.

## Strict interpretation

These are strong controlled results, not a certified privacy guarantee or production validation.
The confidence-based MIA is only one attacker. MIA values below 0.5 can be inverted, so distance
from 0.5 and comparison with exact matter more than direction. The evaluation reuses an already
downloaded LFW corpus, although v2 code and criteria were frozen before this v2 evaluation. The
pretrained face backbone was not trained or unlearned locally. An authorized institutional pilot
and a genuinely unseen third dataset remain external evidence requirements.

## Research context

- [NeurIPS 2023 Machine Unlearning Competition](https://neurips.cc/virtual/2023/competition/66581)
- [Task-agnostic personal-identity unlearning benchmark](https://arxiv.org/abs/2311.02240)
- [Face identity unlearning for retrieval via embedding dispersion](https://openaccess.thecvf.com/content/WACV2026W/LENS-2026/html/Zakharov_Face_Identity_Unlearning_for_Retrieval_via_Embedding_Dispersion_WACVW_2026_paper.html)
