# Task-Agnostic Identity-Unlearning v2.1

## What changed after adversarial review

Version 2.1 treats the earlier v2 result as historical evidence and corrects five weaknesses rather
than rewriting that record.

| Review finding | v2.1 response | Remaining boundary |
|---|---|---|
| LFW was not genuinely unseen | A MUFAC identity subset was selected by a committed hash rule from a pinned repository revision before any selected image was accessed | One public corpus is not an institutional pilot |
| The named primary endpoint did not gate `success` | The computed endpoint named by `primary_endpoint` must exist and pass `primary_endpoint_max`; a regression test enforces the contract | The 1% margin was selected on development data |
| One max-softmax MIA was weak | Confidence, energy, margin, and negative-entropy attacks are evaluated in both directions; the worst privacy advantage gates success | These are logit attacks, not a completed shadow-model LiRA study |
| `lineage_guided` overclaimed graph use | The neural method is now `influence_selective`; graph evidence separately selects exact, approximate, blocked, or no-action remediation and the required proofs | The graph does not identify individual neural parameters |
| 100% generated system benchmark was oversold | It is now described only as contract-conformance evidence; the real SQLite/index/cache/backup lab remains an integration rehearsal | Independently authored hidden pipelines are still needed |

The review also exposed a security issue outside the original five findings: plain SHA-256 of a
person identifier was vulnerable to offline dictionary search. The storage lab now uses
domain-separated HMAC-SHA-256, requires at least a 256-bit secret, and stores local commitment and
backup keys with mode `0600`.

## Frozen protocol and provenance

- Freeze commit: `e05e42fcdfe1ab50e3d535961fc6b972e682ff7d`
- Protocol SHA-256: `497e377d50c00eb33a30c3a716d040c48412c23620c73f572cdaa9eae4f981f9`
- MUFAC repository revision: `b643a1ff04960ace8f94dcd36006d7726049cf11`
- Selection: 60 eligible identity keys with the lowest domain-separated SHA-256 ranks
- External material: 572 images, resized to 128×128 before frozen MobileFaceNet extraction
- Per split: five seeds × twenty forgotten identities × five methods = 500 evaluations
- Uncertainty: 2,000 bootstrap resamples for each reported 95% interval

The external lock contains the freeze commit and protocol hash. The local manifest binds all 572
repository paths and file hashes, the prepared embedding bundle, and the source protocol. Face
pixels, embeddings, and subject keys remain outside Git.

## Success gates

All four gates must pass:

1. primary functional-embedding MSE ratio to stale ≤ 1.01;
2. retained verification AUC delta from exact ≥ −0.01;
3. worst four-attack privacy-advantage gap from exact ≤ 0.10;
4. speedup over exact retraining ≥ 1.5×.

The primary ratio is a non-inferiority test, not a claim that approximate unlearning is closer to
exact than stale. A ratio of 1.00 is equal; the frozen margin permits at most 1% higher MSE.

## Results

| Split | Status | Primary ratio | Privacy gap | Selective AUC | Exact AUC | Speedup |
|---|---:|---:|---:|---:|---:|---:|
| Olivetti development | PASS | 1.00483 | 0.08952 | 0.99957 | 0.99962 | 3.19× |
| LFW locked confirmation | PASS | 1.00467 | 0.02519 | 0.99398 | 0.99424 | 7.34× |
| MUFAC content-unseen external | PASS | 1.00326 | 0.07199 | 0.92624 | 0.92565 | 3.49× |

On MUFAC, the selective retained-AUC 95% interval was 0.92431–0.92802 and exact was
0.92379–0.92743. Selective worst-case privacy advantage was 0.62618 (0.58099–0.67261), while exact
was 0.55418 (0.50646–0.60406). The gap passed the registered equivalence threshold, but the high
absolute advantages show measurable membership leakage in both models. `PASS` therefore means
protocol non-inferiority to exact retraining, not privacy or erasure certification.

## Reproduction

```bash
.venv/bin/pip install -e '.[dev,face]'
PYTHONPATH=src python experiments/prepare_mufac_external.py
PYTHONPATH=src python experiments/task_agnostic_unlearning_v2.py \
  --protocol benchmark/task-agnostic-v21.json --split external \
  --output outputs/task-agnostic-v21-external
```

The preparation command refuses to overwrite an existing bundle, and non-development evaluation
requires a clean Git tree and a new output directory.

## Honest scientific conclusion

The strongest supported claim is now: under one frozen local protocol, influence-selective
unlearning was non-inferior to exact retraining on the registered functional, utility, privacy-gap,
and runtime gates across two known corpora and one content-unseen public corpus. It is not SOTA,
not a proof of complete deletion, not Face ID/eGov validation, and not yet a LiRA-grade privacy
evaluation. Exact retraining remains the preferred remediation whenever it meets the deadline.
