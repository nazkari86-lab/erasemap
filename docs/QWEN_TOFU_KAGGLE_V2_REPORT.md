# Qwen–TOFU Kaggle v2 result

Date collected: 2026-08-26

Kernel: `hijima/erasemap-qwen-tofu-v2`, version 3

Frozen source commit: `a23ef65e48d084914bda76d8677e57b0a2c6de5e`

Frozen decision: **FAIL**

## Result

The first scientifically valid v2 execution completed the full development grid and five untouched
confirmation seeds on a Tesla P100. The offline verifier checked the bound protocol digest, source
commit, file manifest, raw per-example arrays, author-disjoint selection, candidate identity,
adapter commitments, seed lists, reload equality, every aggregate, all twelve gates, and both final
decisions. Kaggle versions 1 and 2 were infrastructure failures before scientific execution and are
not experimental results.

Development selected `ucsgp-f035-a025`. It passed all frozen development gates on two seeds, with
normalized exact-retraining recovery from 0.806 to 1.089. On the disjoint confirmation authors,
however, the same locked configuration overshot exact retraining on every seed: normalized recovery
ranged from **4.957 to 8.632**, outside the required **0.8–1.25** interval. This is a genuine
development-to-confirmation transfer failure.

| Frozen endpoint | Confirmation observation | Gate |
| --- | ---: | --- |
| Target memorization gain, minimum | 0.60225 | PASS, at least 0.10 |
| Exact forgetting lift, minimum | 0.13772 | PASS, at least 0.05 |
| Normalized exact recovery | 4.95677–8.63216 | **FAIL**, 0.8–1.25 on every seed |
| Candidate/exact paraphrase NLL gap, maximum | 0.85111 | **FAIL**, at most 0.20 |
| Candidate/exact truth-margin gap, maximum | 0.07598 | PASS, at most 0.20 |
| Candidate/exact retain NLL gap, maximum | 0.18609 | **FAIL**, at most 0.15 |
| World-fact NLL degradation, maximum | -4.27692 | PASS, at most 0.20 |
| Real-author NLL degradation, maximum | -3.70529 | PASS, at most 0.20 |
| Candidate/exact membership-AUC gap, maximum | 0.41250 | **FAIL**, at most 0.10 |
| Speedup versus exact retraining, minimum | 30.48x | PASS, at least 1.5x |
| Reload recurrence, maximum | 0 | PASS, at most 0.000001 |

Eight of twelve conjunctive gates passed. The same-environment v1 paired-gradient baseline also
returned **FAIL**: it remained much closer to exact and retained behavior, but recovered only
28.4–36.9% of exact forgetting and failed real-author and world-fact utility on at least one seed.
V2 therefore exposes the central trade-off rather than solving it: the baseline under-forgets,
whereas the selected UCSGP candidate forgets far too aggressively and no longer matches the exact
reference on retained, paraphrase, or membership endpoints.

## Interpretation

This result supports three narrow conclusions. First, the corrected semantic evaluator and
author-disjoint development/confirmation design can detect a failure that a development-only result
would miss. Second, UCSGP can create a large and fast measured change, but magnitude alone is not
valid unlearning: overshooting exact retraining by roughly five to nine times is a failure. Third,
EraSeMap's conjunctive model channel correctly remains incomplete despite excellent runtime, zero
reload recurrence, and several utility passes.

The negative world-fact and real-author degradation values mean those losses were lower than the
target losses; they do not rescue the method because exact-matched retention and membership gates
failed. No claim is made about removal from Qwen pretraining, certified privacy, arbitrary language
models, external replication, or production deployment. The v1 negative result remains unchanged.

## Reproduce verification

```bash
PYTHONPATH=src:. .venv/bin/python scripts/verify_qwen_tofu_kaggle_v2.py
```

The manifest-bound raw evidence is in `outputs/qwen-tofu-kaggle-v2/`.
