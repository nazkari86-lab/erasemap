# Measured multi-service v1 preregistration

This protocol is frozen before the holdout experiment is implemented or executed. It compares a
targeted exact-CDC remediation with a rebuild-all baseline on identical synthetic identity states
held by real service processes.

## Systems and state

- PostgreSQL 15 is the source of retained embeddings and labels.
- Redis 8 is a cache process.
- Qdrant 1.15.4 is a pinned vector-database container.
- AES-GCM ciphertext and per-subject keys form a physical backup store.
- A ridge model is trained from registered sufficient statistics. Targeted removal subtracts the
  deleted row's statistics; rebuild-all recomputes them from retained PostgreSQL rows.

Every trial uses 250 synthetic subjects and 64-dimensional deterministic vectors. Source deletion
occurs before timed remediation. Both strategies start from equivalent derivative state. Strategy
order alternates by seed parity. Setup, audit, and teardown are not included in remediation time.

## Strategies

`targeted_exact_cdc` deletes one Qdrant point, one Redis key, one backup key, and one subject's model
sufficient-statistic contribution. `rebuild_all` reconstructs Qdrant, Redis, the recoverable backup
set, and model statistics from retained PostgreSQL state. Bytes rewritten count request/response
payloads and filesystem bytes created or replaced by each remediation.

## Frozen analysis

Five calibration seeds verify execution only and cannot support the final claim. Twenty unseen
holdout seeds are the sole confirmatory split. The primary paired endpoints are wall-clock speedup
and bytes-rewritten reduction. A paired bootstrap with 10,000 resamples and seed 90317 estimates the
95% speedup interval.

Success requires all of the following on holdout:

- both strategies reach PCUG `COMPLETE` on every trial;
- neither strategy loses retained identities;
- targeted and rebuild model weights differ by at most `1e-8`;
- targeted remediation rewrites at least 50% fewer bytes in aggregate;
- the paired speedup bootstrap 95% lower bound is at least 1.25.

The result will remain a local real-process experiment with synthetic records. It cannot be called
an organizational, eGov, Face ID, or production pilot.
