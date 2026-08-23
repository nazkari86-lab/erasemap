# Regeneration-Safe Erasure v1

## Result

The first project-authored development run passed all frozen gates on 20 fixed seeds. In every
trial, the online snapshot contained no subject record, cache entry, vector, or model reference,
yet the retained encrypted backup recreated the subject after the registered restore workflow.
RSE detected all 20 risks and returned `backup_restore` as the shortest witness. The exact Minimal
Stabilization Cut selected the cost-7 persistent subject tombstone rather than the cost-40 backup
destruction control. Replaying the real local restore and propagation workflow after installing the
tombstone produced 0/20 recurrences.

| Endpoint | Result | Frozen gate |
|---|---:|---:|
| Snapshot false-complete cases | 20/20 | 20 |
| RSE regeneration detections | 20/20 | 20 |
| Complete transition coverage records | 20/20 | 20 |
| Post-control recurrences | 0/20 | <= 0 |
| Maximum selected control cost | 7 | <= 7 |

## What ran

Each isolated trial used a real SQLite database, JSON cache, NumPy vector index, AES-GCM encrypted
backup with a subject-scoped key, and model manifest. The data were deterministic synthetic
16-dimensional vectors. The physical workflow enrolled a subject, removed all online copies while
retaining the recoverable backup, restored the source, and rebuilt its online derivatives. A second
replay installed a durable commitment-based tombstone before attempting the same restore.

The temporal checker separately evaluated the registered finite transition system. It explored the
reachable closure, returned a breadth-first shortest regeneration witness, failed closed on missing
sensors or unknown observed transitions, and exhaustively selected the minimum-cost permitted
control set.

Lean checks the conditional temporal composition theorem: if every real data-bearing transition is
covered by the registered relation and every registered transition preserves residual absence,
then every real reachable state remains residual-free. A separate checked counterexample shows
that local registered soundness does not prevent regeneration when the coverage premise is removed.
This is a theorem about the declared semantics, not proof that a deployment's sensors are complete.

## Interpretation boundary

This result establishes executable mechanism behavior in the named local lab. It does **not** show
that the online-only snapshot is stronger than the current PCUG audit: a PCUG deployment that
registers the recoverable backup as a current residual should already reject completion. RSE adds a
different claim: a presently non-residual latent carrier or closed node can be reopened by a future
registered transition.

The cases, transition catalogue, costs, sensors, implementation, and execution are all
project-authored. They do not increase independent evidence and do not establish a production
FaceID, eGov, banking, school, or government guarantee. `RSE_VERIFIED` is conditional on the
registered transition catalogue, adapter soundness, and verified declared sensors; silent systems
remain outside the guarantee.

## Reproduction

```bash
erasemap rse demo --seed 101
PYTHONPATH=src python experiments/run_regeneration_safe_erasure_v1.py
python scripts/verify_regeneration_safe_erasure_v1.py
```

The frozen protocol is `benchmark/regeneration-safe-erasure-v1.json`; machine-readable records are
under `outputs/regeneration-safe-erasure-v1/`.
