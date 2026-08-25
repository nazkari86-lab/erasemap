# GhostGraph v2 — final local evidence report

Snapshot: 2026-08-25. This report records the prospective v2 strategy comparison, the separate
four-service transfer run, and the boundary of the still-uncollected external challenge. It does not
replace the immutable v1 result.

## Question

Can an erasure auditor actively distinguish a hidden data-resurrection graph, preserve the complete
set of observationally equivalent graphs when exact identification is impossible, detect traces
outside its hypothesis catalogue, and convert every justified survivor into controls that prevent
post-deletion recurrence?

## Frozen method

The v2 protocol fixes six strategies, one six-graph catalogue, seven feasible temporal experiments,
seven cases, a separate bit-oracle, stopping rules, evidence gates, source hashes, and a reveal
commitment. Every adaptive step exports the full candidate partition and score certificate. The
strategies receive identical cases and trace semantics:

1. active one-step minimax;
2. frozen random feasible order;
3. greedy separated-pairs;
4. passive declared-lineage;
5. flat Erasure Tomography without checkpoint/time structure;
6. nonadaptive exhaustive execution.

The output is fail-closed: a unique graph, the complete observable path class, `OUT_OF_HYPOTHESIS`,
or `UNVERIFIED`. A confident answer is invalid if it omits a trace-consistent graph. Controls are
derived from all justified survivors and physically replayed.

## Prospective bounded result

| Strategy | Probes | Exact graphs | Path classes | False confident | OUT | UNVERIFIED |
|---|---:|---:|---:|---:|---:|---:|
| Active minimax | 7 | 3 | 2 | 0 | 1 | 1 |
| Frozen random | 13 | 3 | 2 | 0 | 1 | 1 |
| Greedy separated-pairs | 7 | 3 | 2 | 0 | 1 | 1 |
| Passive declared-lineage | 0 | 0 | 0 | 1 | 0 | 1 |
| Flat Erasure Tomography | 16 | 3 | 2 | 1 | 0 | 1 |
| Nonadaptive exhaustive | 49 | 3 | 2 | 0 | 1 | 1 |

For active minimax, planner/oracle mismatches, post-control recurrence, and retained-subject loss
were all zero. Active reduced probes relative to frozen random and exhaustive, but tied greedy at
seven. This negative result is retained: v2 does not show that one-step minimax is better than the
strong greedy strategy in the frozen catalogue.

## Live stock-service transfer

A separately frozen run executed the active contract through digest-pinned Redis, Keycloak, MLflow,
and Qdrant containers using loopback-only ports and synthetic subject commitments. It completed five
cases in five probes, recovered three exact-or-path classes, detected one OUT case and one safe case,
and recorded zero false confidence, oracle mismatch, recurrence, retained loss, cleanup failure, or
managed container left after cleanup.

This is real-process transfer evidence, not a production FaceID/eGov deployment: the mappings,
hidden graphs, orchestration, and synthetic commitments were authored inside the project.

## Independent route

`external_ghostgraph_challenge` v2 hides both truth and traces. An evaluator-controlled HTTP adapter
answers only the probe selected by frozen project code. After reveal, the verifier recomputes the
planner and oracle choices, traces, version spaces, verdicts, source hashes, seal commitment, clean
commit, evaluator identity fields, Ed25519 signature, and nine evidence gates. A project-owned key is
explicitly rejected.

No outside evaluator has submitted a package. Status is therefore **`NOT_COLLECTED`**, and evidence
independence remains **7.8/10**. Local reruns, signatures, or additional project-authored cases cannot
raise that score.

## Reproduce

```bash
python scripts/verify_ghostgraph_v2.py
python scripts/verify_ghostgraph_live_v2.py
python -m external_ghostgraph_challenge.verify_v2 --help
```

The committed evidence is in `outputs/ghostgraph-v2/` and `outputs/ghostgraph-live-v2/`. A fresh
Docker execution is available through `scripts/reproduce_release.sh ghostgraph-live`.

## Claim boundary

The supported contribution is the implemented composition of bounded hidden recovery graphs,
active temporal deletion/recovery interventions, exact full-version-space certificates, fail-closed
class/OUT/UNVERIFIED outputs, and survivor-to-control replay. It is not a global decision-tree
optimality theorem, open-world discovery guarantee, proof of world priority, independent validation,
or production pilot.
