# Qwen–TOFU Kaggle v1 result

Date collected: 2026-08-25  
Kernel: `hijima/erasemap-qwen-tofu-v1`  
Frozen decision: **FAIL**

## Result

The first valid three-seed GPU execution used the pinned Qwen2.5-1.5B base, TOFU snapshot, and
preregistered NF4 QLoRA procedure on a Tesla P100. The offline verifier recomputed every loss,
membership AUC, gate, artifact commitment, and the final decision from the downloaded raw arrays.

Seven of nine gates passed. The paired-gradient-difference candidate:

- stayed close to exact adapter retraining on direct and perturbed forget loss;
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

## Reproduce verification

```bash
PYTHONPATH=src:. .venv/bin/python scripts/verify_qwen_tofu_kaggle_v1.py
```

Bound artifacts are in `outputs/qwen-tofu-kaggle-v1/`.
