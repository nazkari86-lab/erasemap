# EraSeMap novelty and prior-art boundary

Snapshot: 2026-08-30. This is a targeted review, not proof of worldwide priority or a legal
freedom-to-operate opinion.

## What is not claimed as new

EraSeMap does not claim invention of:

- data lineage, provenance graphs, derived-data discovery, or retention propagation;
- machine unlearning, exact retraining, SISA, membership inference, or certified unlearning;
- deletion receipts, proof of deletion, signatures, commitments, or hash chains;
- set cover, minimum cuts, shortest paths, active testing, group testing, version spaces, or
  temporal reachability;
- backups, tombstones, deletion canaries, synthetic subjects, or uncertainty envelopes.

Representative prior art includes W3C PROV, Cao and Yang's system unlearning, Bourtoule et al.'s
SISA, probabilistic and cryptographic unlearning verification, certified unlearning, dependency-
aware deletion, deletion-testing patents, and lineage-aware deletion patents. The structured table
is in [`STRUCTURED_PRIOR_ART_AND_PATENT_REVIEW.md`](STRUCTURED_PRIOR_ART_AND_PATENT_REVIEW.md).

## Working contribution

The testable contribution is one composition:

> A subject-scoped fail-closed algorithm can connect registered physical copies, derivatives,
> learned influence, bounded hidden recovery paths, future transitions, and replayable evidence into
> one three-valued verdict and a minimum-cost sufficient remediation plan.

It is exposed as three stages:

1. FIND returns a graph, a complete observable path class, or a fail-closed boundary result.
2. ERASE closes physical and model branches; fast unlearning passes only against exact-retraining
   and retained-utility/privacy gates.
3. PROVE blocks certification unless registered future recovery replay remains safe.

The novelty is not the union of many named subalgorithms. It is the enforced dependency between the
three stages: no lineage receipt, unlearning score, or empty snapshot can independently produce
`COMPLETE_WITHIN_ENVELOPE`.

## Evidence supporting the working claim

- Component baselines fail on frozen interaction cases: 0/60 EraSeMap false complete versus 5/60
  full typed audit and 45/60 native status.
- Active FIND reduces a bounded probe budget from 13 random or 49 exhaustive to 7, while tying the
  strong greedy baseline at 7.
- Exact ERASE matches exhaustive selection in 3,072/3,072 bounded orderings and substantially
  reduces measured work versus rebuild-all.
- PROVE detects 30/30 registered future risks that snapshot audit misses and matches its exhaustive
  oracle in 16,384/16,384 bounded configurations.
- Failed Qwen unlearning candidates remain failed; the model channel does not convert speed into a
  deletion claim.

## Boundary

The experiments use public inputs and real stock/local processes, but mappings, faults, and runs are
project-authored. A bounded graph catalogue is not arbitrary topology discovery. A conditional Lean
theorem is not evidence that an organization registered every store. Production FaceID/eGov and
independent hidden validation remain unestablished.

Before a peer-review-level priority claim, the project needs a systematic multi-database search,
professional patent review, and an independently authored hidden evaluation using the frozen blind
handoff.
