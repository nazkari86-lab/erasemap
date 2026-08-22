# Task-Agnostic v3.2 Adaptive MUFAC Report

Date: 2026-08-22

Result: **PASS on all unchanged v3 gates**

Evidence status: **adaptive follow-up**. MUFAC v3 and v3.1 outcomes were known before the 120-epoch
budget was selected. This result improves the method but is not a new independent confirmation.

## Method

Deletion-matched restart uses the same deterministic initialization and retained-identity data as
exact retraining, while completely excluding the forgotten identity from every optimization step.
v3.2 increases the candidate budget from 80 to 120 epochs; exact retraining remains 200 epochs.
All endpoint thresholds, attacks, seeds, subjects, and bootstrap rules are unchanged.

## Result

The run contained 500 method-trials across 100 deletion requests on the frozen 572-image,
60-identity MUFAC content-unseen subset.

| Endpoint | v3.2 result | Frozen gate | Decision |
|---|---:|---:|---|
| Retained verification AUC difference to exact | −0.00653 | ≥−0.01 | PASS |
| Mean speedup versus exact | 1.593× | ≥1.5× | PASS |
| Maximum paired privacy advantage upper CI | 0.04091 | ≤0.10 | PASS |
| Forgotten embedding MSE ratio to stale | 0.03064 | ≤1.0 | PASS |
| Retained embedding MSE ratio to stale | 0.03348 | ≤1.01 | PASS |
| Identity-LiRA stale minus exact | 0.49134 | ≥0.05 | PASS |

Candidate retained AUC was 0.91912 versus 0.92565 for exact retraining. Candidate retained CKA and
privacy outcomes remain reported in the raw result; passing the bounded gates is not equivalence to
exact retraining or a production privacy guarantee.

## Interpretation

v3.2 repairs the measured MUFAC utility failure while retaining a modest 1.59× speed advantage.
The exact-retrain fallback remains mandatory whenever the candidate fails a frozen dataset-specific
gate. Because the external dataset was already exposed by v3/v3.1, a new independently selected
dataset is still required for confirmatory evidence of the 120-epoch method.

Raw result: `outputs/task-agnostic-v32-adaptive-external/result.json`

