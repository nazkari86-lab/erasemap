# EraSeMap Open Transfer Challenge v1 — First Confirmatory Report

**Run date:** 2026-08-23

**Decision:** `PASS`

**Run kind:** `LIVE_STOCK_SERVICES`

**Frozen protocol:** `sha256:cccd60621fe54982081026f52f5fb3bbfce6ac3a3b771279688447131d9c5317`

**Frozen core:** `sha256:04259491ac1c2459d59f44fb86a2557834995245161a6660564d65b4c599d03e`

**Execution commit:** `b99c672ea9743599b18b45114447d8454097069f`

## Question

Can one frozen subject-erasure decision contract avoid false-complete deletion decisions across
stock identity, ML-lineage, and biometric-vector service families under the same registered
evidence budget?

## What was executed

The first complete v1 run executed 60 registered cases: three stock service families, five frozen
seeds, and four fault states. Keycloak used synthetic identities. MLflow used synthetic subject
commitments. Qdrant used five confirmatory subjects from the public Olivetti faces source, selected
before the run and stored without a trained transform as 4,096-dimensional vectors.

| Family | Immutable image | Cases | Median remediation | Bytes rewritten |
|---|---|---:|---:|---:|
| Keycloak identity | `quay.io/keycloak/keycloak@sha256:f1f1f01e…` | 20 | 589.0 ms | 1,204,219 |
| MLflow lineage | `ghcr.io/mlflow/mlflow@sha256:9f9276e5…` | 20 | 2,519.3 ms | 1,555 |
| Qdrant biometric | `qdrant/qdrant@sha256:6ac48070…` | 20 | 19.2 ms | 327,680 |

The latency and byte values are secondary descriptive measurements. They do not rescue a failed
primary gate and are not production performance claims.

## Frozen primary result

| Gate or outcome | Observed | Requirement | Result |
|---|---:|---:|---|
| Exact case matrix | 60 cases / 3 families | 60 / 3 | PASS |
| EraSeMap false-complete | 0 | at most 0 | PASS |
| Coverage faults returned `UNVERIFIED` | 15 | exactly 15 | PASS |
| Post-control recurrence | 0 | at most 0 | PASS |
| Retained-user loss | 0 | at most 0 | PASS |
| Safe-case specificity drop | 0.0 | at most 0.0 | PASS |
| Exact-control/oracle mismatch | 0 | at most 0 | PASS |
| Frozen-core drift | 0 | at most 0 | PASS |
| Observed-process failures | 0 | at most 0 | PASS |

The native-success comparator produced 45 false-complete decisions: 15 in each family. The
typed-node comparator produced 5 false-complete decisions. EraSeMap produced none in this finite
registered matrix and preserved safe-case specificity at 1.0.

## Reproducibility and integrity

- `outputs/open-transfer-v1/trials.jsonl` contains all 60 canonical trial records.
- `outputs/open-transfer-v1/evidence/*.jsonl` contains redacted request/response observations from
  the live local stock services.
- `outputs/open-transfer-v1/assets/` contains the deterministic public-face asset and source
  provenance.
- `outputs/open-transfer-v1/PROVENANCE.json` hashes every required artifact.
- `scripts/verify_open_transfer_v1.py` rejects missing, extra, changed, or internally inconsistent
  artifacts and independently recomputes the gates from serialized trials.

Verification command:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/verify_open_transfer_v1.py \
  --result outputs/open-transfer-v1/result.json
```

## Exact claim boundary

This is project-authored transfer evidence on real local processes, immutable stock service images,
public or synthetic inputs, declared adapters, and finite project-authored fault states. It is not
an independently authored hidden challenge, a production pilot, an organization attestation, or
validation on actual Face ID, eGov, banking, school, or government infrastructure. It does not show
coverage of arbitrary unknown topologies.

The supported result is narrower: under the frozen v1 contract and case matrix, EraSeMap avoided
false-complete decisions across the three tested service families and selected the same minimum-cost
controls as the separate brute-force oracle, without observed retained-user loss or post-control
recurrence.
