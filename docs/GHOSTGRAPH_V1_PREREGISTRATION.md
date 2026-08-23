# GhostGraph v1 preregistration

Date committed: 2026-08-23

## Question

Can an exact active planner recover a hidden bounded subject-resurrection graph, or its complete
observable path class, with zero false confident outputs and fewer executed probes than the frozen
non-adaptive experiment set?

## Frozen domain

The confirmatory domain contains six project-authored hypotheses over six typed state locations and
seven optional transitions. Seven feasible experiments expose four checkpoints across three time
buckets. The trace-error budget is zero. All graphs, experiment costs, limits, case IDs, metrics,
gates, invalid-run rules, core file hashes, and the reveal commitment are frozen in
`benchmark/ghostgraph-v1.json`.

The hypotheses include direct, alternative two-hop, three-hop, combined, no-recurrence, and
path-equivalent graphs. One negative truth graph contains a transition outside the allowed edge
catalogue whose predicted trace is outside the frozen prediction union. A second negative case
invalidates subject isolation. These must produce `OUT_OF_HYPOTHESIS` and `UNVERIFIED`, not a
convenient graph.

## Prospective separation

This preregistration is committed before the confirmatory runner and before
`benchmark/ghostgraph-v1-reveal.json`. The canonical reveal commitment is
`sha256:917ce6de187f5a78beb2d81829be01500675e07f5c53646fb39d04c0df3f896c`.
Development uses seeds 101 and 103; the confirmatory seed is 23082026. The first confirmatory output
is append-only. A source, protocol, metric, gate, stopping-rule, or reveal change creates v2.

## Stopping and verdict rule

A negative observation alone is not terminal. Execution continues while an unused experiment
separates surviving hypotheses. It stops only when the exact planner has no separating experiment or
when no hypothesis survives. A singleton is `GRAPH_DISCOVERED`; multiple graphs with the same
relevant paths are `PATH_CLASS_DISCOVERED`; materially different inseparable graphs remain the full
`EQUIVALENCE_CLASS`.

## Primary gates

- zero false confident outputs;
- at least three exact uniquely identifiable graph recoveries;
- at least one correct path-class recovery;
- 100% true-graph containment for every in-model non-singleton output;
- one outside-hypothesis detection and one missing-evidence `UNVERIFIED` result;
- zero production/oracle planner mismatches;
- zero post-control recurrence;
- zero retained-subject loss; and
- fewer adaptive probe executions than executing all seven frozen experiments for every case.

The equal-budget random, greedy pair-count, passive-lineage, exhaustive, and flat ET baselines are
reported without claiming that the one-step minimax rule is globally decision-tree optimal.

## Claim boundary

This is a project-authored bounded prospective experiment. A passing result would support exact
finite hidden-graph discovery under the frozen grammar and evidence assumptions. It would not prove
open-world discovery, production FaceID/eGov behavior, independent validation, legal compliance,
world priority, patentability, or freedom to operate.
