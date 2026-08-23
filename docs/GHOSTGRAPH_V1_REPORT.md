# GhostGraph v1 — active causal erasure discovery

## Plain-language problem

A deletion audit can check every storage path it already knows. It cannot name a recovery path that
was never registered. GhostGraph turns that missing-topology problem into a bounded experiment:
temporarily enable selected recovery operations, observe where a synthetic deleted subject
reappears over time, eliminate every graph that predicts a different trace, and choose the next
experiment that minimizes the largest remaining ambiguity.

The output is fail-closed: one graph, the complete indistinguishable path class, the complete broader
equivalence class, `OUT_OF_HYPOTHESIS`, `UNVERIFIED`, or scoped no-observed-recurrence. It never
selects a convenient representative from an ambiguous set.

## Frozen prospective result

The protocol and core hashes were committed before runner code; the runner was committed before the
reveal; and the first output was append-only.

| Metric | Observed |
|---|---:|
| Decision | PASS |
| Cases | 7 |
| Exact unique graph recoveries | 3 |
| Correct path-class recoveries | 1 |
| Outside-hypothesis detections | 1 |
| Missing-evidence `UNVERIFIED` | 1 |
| False confident outputs | 0 |
| Adaptive probes | 6 |
| Frozen exhaustive probes | 49 |
| Planner/oracle mismatches | 0 |
| Post-control recurrences | 0 |
| Retained-subject losses | 0 |

The multihop truth remains the two-member class `g-multi` / `g-multi-log`, because the added log
edge is irrelevant to the registered residual endpoint and unobservable at the frozen checkpoints.
Reporting both is a successful fail-closed result.

## Algorithm and mathematics

Let `H_t` be the surviving finite graph set after `t` observations. For candidate experiment `q`,
graphs are partitioned by predicted Boolean time trace. GhostGraph selects the lexicographic minimum
`(max bucket size, sum of squared bucket sizes, declared cost, experiment ID)`.

After trace `y_t`, the zero-error update is
`H_(t+1) = {h in H_t : d_H(trace(h,q_t), y_t) <= e}`, with frozen `e = 0`.

Execution stops only when `H_t` is empty or no unused experiment separates a surviving pair. A
negative trace alone is not terminal. A separately structured packed-bit oracle recomputes
prediction, filtering, path signatures, and planner choice. Exhaustive conformance covers 367
bounded configurations with zero mismatches.

Lean proves the conditional core: a sound listed truth survives filtering; singleton discovery is
sound; query-indistinguishable graphs have the same consistency decision; and an emitted finite
planner certificate satisfies its one-step minimax obligation. This does not prove that an unknown
production graph belongs to the catalogue.

## Contribution and boundary

PCUG asks whether deletion is complete on a registered graph. GhostGraph asks which bounded hidden
recovery graph explains recurrence traces. Every justified survivor becomes a separate TRE scenario;
exact robust controls are then physically replayed while preserving an unrelated synthetic subject.

The implemented composition is active temporal intervention design, full-class fail-closed
reporting, independent executable checking, and discovery-to-erasure-control translation. It does
not claim invention of causal discovery, tomography, active learning, lineage, or unlearning.

All graphs, mappings, cases, and execution are project-authored. This is not independent evidence or
a production FaceID/eGov pilot. The live four-service protocol is preregistered, but its result is
`NOT_COLLECTED` because Docker was unavailable. The external-author kit is executable; its result is
also `NOT_COLLECTED` until a real evaluator authors, seals, runs, reveals, and signs a bundle.
