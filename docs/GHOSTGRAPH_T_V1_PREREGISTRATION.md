# GhostGraph-T v1 locked protocol

Freeze date: 2026-08-25. Status: frozen before the first benchmark result.

## Question

Can GhostGraph-T identify the minimum erasure-action equivalence class rather than reconstructing
irrelevant graph detail, reject a topology family outside its declared catalogue, and use fewer
probes and lower declared cost than nonadaptive exhaustive testing?

## New object

For graph `G`, `A(G)` is the complete set of minimum-cardinality operation cuts that intersect every
represented path from an initial recovery carrier to a residual sink. Graphs are action-equivalent
exactly when their `A(G)` values are equal. A safe graph has the singleton empty cut; a graph whose
initial carrier is already a residual sink is explicitly uncontrollable.

The finite catalogue is action-identifiable iff every two listed graphs with different action
signatures differ on at least one allowed temporal experiment. The implementation emits the exact
pair and shared trace vector when this condition fails. Lean proves the conditional soundness of an
action-homogeneous survivor set and the corresponding indistinguishable-pair impossibility result.

## Splits

- 120 instance-held-out cases: unseen graph instances inside six known families;
- 80 composition-held-out cases: unseen two-family recovery compositions;
- 50 family-held-out cases: retry replay is absent from the catalogue and success means only
  `OUT_OF_HYPOTHESIS`;
- 50 temporal-shift-held-out cases: an extra delayed-release transition is inside the declared
  temporal catalogue.

Irrelevant disconnected subgraphs create graph twins with identical erasure actions. They test that
the action objective stops without inventing exact-graph confidence. They do not count as new
recovery mechanisms.

## Algorithms

The exact global policy minimizes worst-case declared cost, then worst-case probe count, aggregate
child cost, and experiment ID over the complete finite decision tree. A separately structured
recursive oracle recomputes its root value. Baselines are one-step minimax, separated-pair greedy,
frozen random, nonadaptive exhaustive, exact-graph minimax, sink-only observation, and passive
declared lineage.

## Frozen gates

- 0 false-confident global-policy outputs across all 300 cases;
- 300/300 correct action or OOD decisions;
- 50/50 held-out-family OOD detections;
- zero exact-policy/oracle root mismatches;
- lower mean probe count and declared cost than exhaustive testing; and
- more resolved cases than the exact-graph-objective ablation.

Wilson 95% intervals are reported for false confidence. Zero observed events is not interpreted as
zero population risk.

## Boundary

This is a project-authored deterministic benchmark. It does not establish arbitrary unknown-
topology discovery, external independence, a production deployment, legal compliance, patentability,
or world priority. A family absent from the catalogue can only be rejected as OOD, not localized.
