# Qwen–TOFU Kaggle v1 result

Date collected: 2026-08-25  
Kernel: `hijima/erasemap-qwen-tofu-v1`  
Frozen decision: **FAIL**

## Result

The first valid three-seed GPU execution used the pinned Qwen2.5-1.5B base, TOFU snapshot, and
preregistered NF4 QLoRA procedure on a Tesla P100. The offline verifier recomputed every loss,
membership AUC, gate, artifact commitment, and the final decision from the downloaded raw arrays.

The original verifier reported seven of nine gates passed. A later semantic audit established that
one of those seven—the perturbed-answer gate—was not actually evaluated because the runner read
`answer` from the perturbed split instead of `paraphrased_answer` and `perturbed_answer`. The honest
post-audit accounting is six valid passes, two failures, and one unevaluable gate. The frozen
decision remains `FAIL`. The paired-gradient-difference candidate:

- recovered only 33.8–39.1% of the exact-reference direct forgetting lift;
- stayed close on retained-profile loss and membership AUC;
- reproduced exactly after save/reload with zero measured recurrence;
- failed the all-seed forgetting gate because one seed reached `0.04837` against the frozen `0.05`
  minimum;
- failed world-fact utility because degradation reached `0.45300` against the frozen `0.20`
  maximum. Two of three seeds exceeded that utility limit.

| Frozen endpoint | Observed | Gate |
| --- | ---: | --- |
| Target memorization gain, minimum | 0.59827 | PASS, at least 0.10 |
| Exact forgetting lift, minimum | 0.14026 | PASS, at least 0.05 |
| Candidate forgetting lift, minimum | 0.04837 | **FAIL**, at least 0.05 |
| Candidate/exact forget NLL gap, maximum | 0.09454 | PASS, at most 0.30 |
| Perturbed-answer comparison | identical to direct by construction error | **UNEVALUABLE** |
| Candidate/exact retained NLL gap, maximum | 0.00920 | PASS, at most 0.15 |
| Candidate/exact membership-AUC gap, maximum | 0.05750 | PASS, at most 0.10 |
| World-fact NLL degradation, maximum | 0.45300 | **FAIL**, at most 0.20 |
| Reload recurrence, maximum | 0 | PASS, at most 0.000001 |

## Interpretation

This is a useful negative result, not successful approximate unlearning. Exact adapter retraining
cleared its registered forgetting gate, while the candidate did not simultaneously satisfy
forgetting and general-utility requirements across all seeds. EraSeMap therefore correctly refuses
model-channel completion even though several similarity and persistence checks pass.

The result strengthens evidence that the fail-closed multichannel rule works on a real open
1.5-billion-parameter language model and external benchmark. It does not establish deletion from
Qwen pretraining, independent validation, certified privacy, production deployment, or superiority
of the candidate method. Thresholds remain unchanged and the failed first result remains public.
The semantic defect does not turn any failed endpoint into a pass; it narrows the supported claim
and motivates the separately frozen v2 protocol.

## Reproduce verification

```bash
PYTHONPATH=src:. .venv/bin/python scripts/verify_qwen_tofu_kaggle_v1.py
```

Bound artifacts are in `outputs/qwen-tofu-kaggle-v1/`.
