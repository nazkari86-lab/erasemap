# Measured real-process multi-service v1 report

## Result

The first confirmatory run passed every preregistered gate on 20 paired holdout seeds. Targeted
exact-CDC remediation reached PCUG `COMPLETE` in all 20 trials, retained all 249 non-deleted
identities per trial, and matched the rebuild-all ridge-model weights within `2.22e-15`.

The geometric-mean wall-clock speedup was `17.64x`; the paired bootstrap 95% interval was
`[16.39x, 18.98x]`, above the frozen `1.25x` lower-bound gate. Targeted remediation wrote 691,780
application/filesystem bytes versus 12,849,080 for rebuild-all, a `94.62%` reduction.

## What was real

PostgreSQL 15.18 and Redis 8.8 ran as isolated local processes. Qdrant 1.15.4 ran from a pinned
container digest. Each trial stored 250 deterministic synthetic identities in PostgreSQL, Redis,
Qdrant, AES-GCM backup files, and a trained ridge model. PostgreSQL source deletion occurred before
timing. Both strategies were audited against the same retained source state.

Calibration used five declared seeds. It converted measured component time into integer
microsecond costs; `exact_cdc` then selected vector deletion, cache invalidation, backup-key
destruction, and exact ridge sufficient-statistic removal with solver status `OPTIMAL`. The 20
holdout seeds were executed once after the protocol, analysis, and implementation commits were
frozen. Strategy order alternated by seed parity.

## Interpretation limits

The bytes endpoint is application payload plus newly written/replaced filesystem bytes, not block
device I/O, network packet capture, energy, or storage-engine write amplification. Timing is local
wall-clock time on one Apple M4 laptop and does not estimate production latency or downtime.
Synthetic vectors and a ridge model make exact sufficient-statistic deletion possible; this result
does not transfer automatically to deep biometric models. The experiment establishes that measured
CDC optimization can materially reduce work in this registered local topology while preserving the
same verified completion—not that EraSeMap has been deployed by an organization.

Evidence:

- protocol: `benchmark/measured-multiservice-v1.json`;
- raw records: `outputs/measured-multiservice-v1/result.json`;
- provenance: `outputs/measured-multiservice-v1/PROVENANCE.json`;
- independent recomputation: `scripts/verify_measured_multiservice_v1.py`.
