# PCUG development report v1

Date: 2026-08-22

Evidence scope: `SYNTHETIC_SIMULATOR`

Protocol: `sha256:89da80c3f1a4773d81068336fd361145446d4b145a27ba9dd7f0c51f1a7ba0ca`

## Result

The registered development command produced 516 method-trial records with zero recorded exceptions:
480 audit records and 36 planning records. All 12 emitted complete proof bundles passed independent
signature, commitment, action-replay, path, channel, verdict, and cost verification.

These are controlled development results. Generator, faults, PCUG evaluator, and ground truth share
the same registered semantics. PCUG's perfect development result establishes implementation
consistency against those faults, not external generalization or production deletion.

## Audit endpoint

There were 96 trials per audit method: three seeds, four display adapters, and eight registered
states. Eighty-four trials per method were non-complete (`INCOMPLETE` or `UNVERIFIED`), and 12 were
genuinely complete. The four adapter labels use identical core semantics and are not independent
datasets.

| Method | False-complete rate | Wilson 95% interval | Non-complete recall |
|---|---:|---:|---:|
| PCUG | 0/84 = 0.000 | 0.000–0.0437 | 84/84 = 1.000 |
| Typed node audit | 24/84 = 0.286 | 0.200–0.390 | 0.714 |
| Model only | 48/84 = 0.571 | 0.465–0.672 | 0.429 |
| Flat checklist | 60/84 = 0.714 | 0.610–0.800 | 0.286 |
| Receipt only | 84/84 = 1.000 | 0.956–1.000 | 0.000 |

`UNVERIFIED` is not counted as complete. In particular, the unknown-model fault remains
`UNVERIFIED`, while single-view model verification misses the committed hidden
representation-recovery failure.

## Planning endpoint

There were 12 planning cases per method: three seeds and four display adapters. Every emitted plan
replayed to `COMPLETE` under simulator semantics.

| Planner | Mean registered cost | Optimality claim |
|---|---:|---|
| Exact CDC | 17.000 | Optimal for the bounded registered action catalogue |
| Greedy CDC | 17.000 | None; happened to match exact on these cases |
| Delete all | 48.667 | None |

Exact CDC reduced registered cost by 65.1% relative to delete-all on this development matrix. Costs
are protocol fixtures, not measured money, latency, energy, or operational burden. The equality of
greedy and exact is a result of these small cases and must not be generalized.

## Deterministic correctness evidence

- Exact CDC matches a brute-force subset oracle across generated small cost spaces.
- Zero-cost ties use cost, action count, and lexical ID ordering; a property test found and drove a
  correction to the original pruning rule.
- Deleting a source does not erase an already materialized child.
- Every active physical artifact is independently terminal for deletion.
- An unverified transition becomes `UNKNOWN` and cannot close a path.
- A shared model remains active; only the subject-scoped influence edge can become bounded.
- Missing or unknown mandatory channels prevent `COMPLETE`.
- A validly signed but false completion verdict is rejected by independent replay.
- Integer/float channel values are normalized before signing, preventing cross-process canonical
  JSON mismatches.

At the development snapshot, the full repository gate passed Ruff, strict mypy, 175 pytest tests,
and 90.27% total line coverage. The Python sdist and wheel built successfully and contained every
PCUG runtime module.

## Existing v3 model evidence through PCUG

The bridge recomputed three mandatory channels from the tracked v3 summaries while verifying the raw
v3 protocol hash. Strata were not pooled.

| Stratum | Forgotten MSE ratio | Privacy upper bound | Retained-AUC loss upper bound | Verdict |
|---|---:|---:|---:|---|
| Olivetti development | 0.13444 / 1.0 | 0.07619 / 0.10 | 0.00170 / 0.01 | PASS |
| Locked LFW | 0.10899 / 1.0 | 0.02643 / 0.10 | 0.00172 / 0.01 | PASS |
| Content-unseen MUFAC | 0.08736 / 1.0 | 0.05446 / 0.10 | 0.01711 / 0.01 | FAIL |

The composed result is therefore `INCOMPLETE`. PCUG preserves the external retained-utility failure
instead of averaging it away. This is an evidence-import result, not a new model run.

## Reproduction

```bash
.venv/bin/ruff check .
.venv/bin/mypy src/erasemap
.venv/bin/pytest --cov=erasemap --cov-report=term-missing --cov-fail-under=90
.venv/bin/python -m build

.venv/bin/erasemap pcug benchmark development \
  --protocol benchmark/pcug-protocol-v1.json \
  --output outputs/pcug-development-v1
.venv/bin/erasemap pcug verify-directory \
  outputs/pcug-development-v1/bundles \
  --public-key outputs/pcug-development-v1/public-key.pem
```

Expected development manifest (the exact code revision is committed inside each bundle):

```json
{"bundle_count":12,"evidence_scope":"SYNTHETIC_SIMULATOR","exception_count":0,"key_scope":"PUBLIC_DETERMINISTIC_SIMULATOR_KEY","protocol_hash":"sha256:89da80c3f1a4773d81068336fd361145446d4b145a27ba9dd7f0c51f1a7ba0ca","record_count":516,"split":"development"}
```

## Negative evidence and open gates

- No independent PCUG schema/topology source has been evaluated.
- No hidden PCUG holdout has been committed or opened.
- Fault families are project-authored and share evaluator semantics.
- Runtime and memory were not used as confirmatory endpoints in this development run.
- The controlled proof checker cannot detect unknown artifacts outside trusted instrumentation.
- Hidden probes reduce one verifier-gaming route but do not defeat a provider that controls all
  instrumentation, evidence, keys, and checker execution.
- The committed development signing key is deliberately public and deterministic for reproducible
  simulator evidence. It provides tamper/replay testability, not production signer identity.
- Existing MUFAC evidence fails retained utility.
- No Apple FaceID, eGov, bank, school, or government production system was accessed or validated.
