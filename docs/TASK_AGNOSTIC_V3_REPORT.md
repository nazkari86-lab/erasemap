# EraseMap task-agnostic v3 report

## Question and claim boundary

The v3 experiment asks whether a bounded-cost retained-only restart becomes closer to an exact
retrain than a stale model for the forgotten identity, while preserving retained verification and
remaining no more distinguishable than exact under a paired privacy audit. It does not establish
formal deletion privacy or production FaceID/eGov validation.

The evaluated v3 candidate starts from a fresh deterministic initialization and trains for 60
epochs using retained identities only. Exact retraining uses the same initialization and optimizer
for 200 epochs. Unlike the historical influence-selective update, no forgotten-identity example is
present in any candidate optimization step.

## What v3 corrected

- Forgotten-identity and retained-sample embedding MSE are separate endpoints; the global average
  no longer hides a weak forgotten result.
- The primary gate requires actual improvement over stale on forgotten MSE, not only
  non-inferiority to an earlier candidate.
- Privacy is paired by `(seed, anonymous_forget_subject)` for every attack. The gate is the largest
  per-attack paired 95% bootstrap upper bound, not a difference between two separately averaged
  worst attacks.
- Identity-deletion LiRA trains 16 shadows per deletion: in-shadows contain all training examples
  of the identity and out-shadows omit the identity and its output class. Its statistic is
  self-match-free within-identity embedding cohesion.
- Full anonymous trial rows are published as deterministic `.jsonl.gz` files beside machine-
  readable summaries.

Frozen v3 code revision: `fd3d3790834f5cc942c80db38e6cf2a2cb002ca4`.
Protocol SHA-256: `e8b718115588e678dc751f9f0283b2405ac2543f73870357660dc399d271d303`.

## Frozen v3 results

Each row contains 100 identity-deletion requests (five seeds × 20 identities). Lower MSE ratios and
paired privacy upper bounds are better. The gates were forgotten ratio ≤ 1.0, retained ratio ≤
1.01, maximum paired privacy upper bound ≤ 0.10, retained AUC delta ≥ −0.01, speedup ≥ 1.5, and a
stale-minus-exact identity-LiRA separation ≥ 0.05.

| Split | Status | Forgotten MSE / stale | Retained MSE / stale | Max paired privacy upper CI | Retained AUC delta | Speedup |
|---|---:|---:|---:|---:|---:|---:|
| Olivetti development | PASS | 0.1344 | 0.1522 | 0.0762 | −0.00129 | 3.35× |
| LFW locked confirmation | PASS | 0.1090 | 0.1308 | 0.0264 | −0.00125 | 3.56× |
| MUFAC content-unseen confirmation | **FAIL** | 0.0874 | 0.0952 | 0.0545 | **−0.01324** | 3.37× |

MUFAC passed every deletion, privacy, distance, and speed gate. It failed only the preregistered
retained-utility bound by 0.00324 AUC. The failure is retained publicly; v3 therefore supports
strong results on development and locked LFW, but not a universal three-dataset claim.

## Adaptive v3.1 ablation

After observing the MUFAC v3 utility miss, v3.1 increased only the candidate budget from 60 to 80
epochs. Revision `11ad43ce4533314ef774e1f4a500d4158246f4c2` and protocol SHA-256
`1db1c52a95a080a8b0c2bb52cef7c16feaf70ed0b6c7e95db333dfe140905599` were committed before the LFW
v3 result was inspected. Thus LFW is a preregistered confirmation for v3.1; MUFAC is explicitly an
adaptive re-evaluation, not a fresh holdout.

| Split | Status | Forgotten MSE / stale | Retained MSE / stale | Max paired privacy upper CI | Retained AUC delta | Speedup |
|---|---:|---:|---:|---:|---:|---:|
| Olivetti development | **FAIL** | 0.1284 | 0.1469 | **0.1220** | −0.00137 | 2.48× |
| LFW preregistered confirmation | PASS | 0.0805 | 0.1004 | 0.0246 | −0.00106 | 3.00× |
| MUFAC adaptive re-evaluation | **FAIL** | 0.0710 | 0.0784 | 0.0651 | **−0.01226** | 2.50× |

Longer training was not a monotonic fix. It slightly improved MUFAC utility but did not pass the
gate, and it made Olivetti identity-deletion LiRA significantly more distinguishable from exact.
The 60-epoch v3 candidate remains the primary method; v3.1 is a negative ablation showing a real
utility–privacy trade-off.

## Fully trainable pixel backbone

The separate `erasemap-trainable-pixel-backbone-v1` protocol trains both convolutional layers, the
embedding layer, and classifier directly from Olivetti pixels. All trainable parameter groups
received non-zero gradients. Across 15 deletion requests, the 56-epoch candidate achieved:

- forgotten MSE ratio to stale: 0.02270 (95% CI 0.01546–0.03155);
- retained MSE ratio to stale: 0.02053 (95% CI 0.01293–0.03059);
- retained verification AUC delta to exact: −0.02056;
- speedup: 1.42× (95% CI 1.41–1.43).

This closes the frozen-backbone experimental gap on a small locally trained CNN. It does not show
that the method works on a production-scale pretrained biometric foundation model.

## Reproducibility and remaining external work

Tracked summaries and full anonymous trials are under `benchmark/results/task-agnostic-v3/`,
`benchmark/results/task-agnostic-v31/`, and `benchmark/results/trainable-pixel-backbone-v1/`.
`scripts/reproduce_release.sh core` runs deterministic software gates; the `face-open` profile
rebuilds the open face experiments. A monthly/manual GitHub Actions job executes the frozen
pixel-backbone benchmark and uploads its result.

The remaining decisive evidence is an evaluator-controlled hidden graph suite and an authorized
pilot against real component probes. The repository provides their contracts but does not label
either one as completed independent validation.
