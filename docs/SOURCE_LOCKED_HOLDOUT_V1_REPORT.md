# Source-Locked Multi-System Holdout v1

Date: 2026-08-22

Decision: **PASS on the preregistered primary endpoint**

Evidence scope: **independently sourced structures, project-authored mappings and execution**

## Result

The one-shot evaluation contained 125 unique source-derived cases: 25 each for identity, ML,
provenance, recovery, and search structures. Twenty cases per family were ground-truth
`INCOMPLETE` or `UNVERIFIED`, giving 100 non-complete cases and 25 genuinely complete cases.

PCUG produced 0 false-complete verdicts in 100 non-complete cases. The two-sided Wilson 95%
interval for the false-complete rate is 0.0000–0.0370, below the preregistered 0.05 upper-bound
criterion. It correctly completed 25/25 genuinely complete cases and recorded zero exceptions.

| Method | False complete | Wilson 95% | Complete specificity |
|---|---:|---:|---:|
| PCUG | 0/100 | 0.0000–0.0370 | 25/25 |
| Typed node audit | 0/100 | 0.0000–0.0370 | 25/25 |
| Flat checklist | 100/100 | 0.9630–1.0000 | 25/25 |
| Model only | 100/100 | 0.9630–1.0000 | 25/25 |
| Receipt only | 100/100 | 0.9630–1.0000 | 25/25 |

Every source family separately had 0/20 PCUG false-complete verdicts. These per-family samples are
too small to meet the 0.05 Wilson upper-bound criterion independently; the confirmatory endpoint
was the preregistered pooled set of unique source-derived cases, not application display labels.

## What this improves

Unlike the earlier adapter benchmark, the five families use official structures from NIST SP
800-63A, W3C PROV-O, OpenSearch, MLflow, and PostgreSQL. FaceID/eGov/KYC/School names are not counted
as independent datasets. Source excerpts, mappings, protocol, case commitments, evaluator revision,
raw records, revealed answers, and file hashes are committed.

## Negative result and limitation

The typed-node baseline tied PCUG on the primary endpoint. The v1 cases therefore support
source-structure transfer and fail-closed correctness but do **not** establish that residual-path
composition outperforms a complete typed-node audit. Flat, model-only, and receipt-only baselines
failed, but the strongest baseline did not.

The official documents are external; extraction decisions, mappings, case construction, labels,
and execution were performed by this project. This is stronger than a shared-semantics simulator
but weaker than an independently authored and executed hidden holdout.

No Apple Face ID, Kazakhstan eGov, bank, school, or government production system was accessed.
Passing v1 cannot establish deletion of artifacts absent from trusted instrumentation and cannot
defeat a provider controlling the topology, evidence, signer, and evaluator.

## Integrity

- Preregistration commit: `2a759e3`
- One-shot evaluator revision: recorded in `outputs/source-locked-holdout-v1/PROVENANCE.json`
- Frozen commitment: `benchmark/commitments/pcug-source-locked-holdout-v1.json`
- Raw records and revealed answers: `outputs/source-locked-holdout-v1/`
- File hashes: `outputs/source-locked-holdout-v1/MANIFEST.sha256.json`

