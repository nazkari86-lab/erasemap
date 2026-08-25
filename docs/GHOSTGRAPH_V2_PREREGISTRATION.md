# GhostGraph v2 preregistration

Date committed: 2026-08-25

GhostGraph v1 is immutable. Version 2 prospectively closes two documented v1 omissions: every
planner step must export the full candidate partition/score certificate, and every named baseline
must be executed and scored rather than merely listed.

Six frozen strategies receive the same graph catalogue, feasible experiment catalogue, cases,
trace semantics, and evidence rules. Adaptive strategies stop only when no unused query separates a
surviving pair or the version space is empty. The passive strategy executes no query. Exhaustive
executes all seven queries. Flat ET intentionally removes checkpoint/time structure and therefore
tests whether GhostGraph's structured trace contributes information.

The protocol, base/core hashes, case IDs, random seed, metrics, gates, stopping rule, and reveal
commitment are committed before v2 runner code and before the reveal file. Any post-reveal scientific
change creates v3. A passing result supports only the frozen project-authored finite domain.
