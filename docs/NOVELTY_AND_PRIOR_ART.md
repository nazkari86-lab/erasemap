# Novelty and prior-art boundary

EraseMap does not claim to invent data lineage, machine unlearning, exact retraining, membership
inference, deletion receipts, or biometric governance. Those components have substantial prior art:

- [W3C PROV](https://www.w3.org/TR/prov-overview/) standardizes machine-processable provenance of
  entities, activities, and agents, including derivation chains.
- Bourtoule et al., [Machine Unlearning](https://arxiv.org/abs/1912.03817), introduced SISA to
  reduce retraining cost by structuring training state.
- Chourasia et al., [Forget Unlearning](https://proceedings.mlr.press/v202/chourasia23a/chourasia23a.pdf),
  explains why similarity to retraining from a single released model is not a complete privacy
  guarantee.
- [NIST SP 800-63A](https://pages.nist.gov/800-63-4/sp800-63a.html) requires documented biometric
  retention/deletion processes and operationally representative evaluation.
- Zhang et al., [Verification of Machine Unlearning is Fragile](https://proceedings.mlr.press/v235/zhang24h.html),
  shows that a provider can retain information while passing some verification strategies.
- [Per-instance privacy for machine unlearning](https://openreview.net/forum?id=0A4Y9qRnu9)
  estimates item-level deletion privacy/difficulty; PCUG does not claim to invent per-item risk.
- [PURGE](https://arxiv.org/abs/2606.03808) includes self-regulating stopping criteria and
  representation erasure; adaptive stopping is therefore outside the PCUG novelty claim.
- [OriginBlame](https://arxiv.org/abs/2607.13037) connects provenance to precise forget-set
  construction; provenance-guided record selection is also outside the PCUG novelty claim.
- [Robust uncertain set covering](https://optimization-online.org/2013/06/3926/) formalizes
  minimum-cost covering under uncertainty; robust optimization itself is outside the TRE claim.
- [OneTrust's deletion-testing patent](https://patents.google.com/patent/US20210406398A1/en)
  describes test data subjects, unique tokens, and post-deletion interactions. Synthetic deletion
  canaries are therefore outside the novelty claim.

The research contribution being tested is narrower: a fail-closed, typed residual-path auditor
that connects operational biometric copies (source, template, index, cache, backup, model, receipt)
to artifact-specific evidence rules and produces the shortest actionable counterexample, while
the model branch is accepted only through a frozen, deletion-matched comparison against exact
retraining and paired privacy attacks.

The v3 `deletion_matched_restart` is an engineering method, not a new general unlearning theorem.
Its auditable property is simple: the forgotten identity is absent from every candidate optimization
step, and the only approximation is a preregistered smaller training budget. Its measured benefit
must therefore be reported only for the registered architecture and datasets. A production FaceID,
eGov, or government-system result requires independent instrumentation, authorization, a committed
hidden suite, and evaluation on the actual operational population.

Potential novelty should be presented as the combined system and evaluation contract, subject to a
formal literature/patent search by the student. It must not be presented as proof that no similar
system exists.

The expanded 2026-08-22 search found close patent prior art for lineage graphs that traverse derived
data and apply deletion policies (US20220414070A1 and US20240012797A1), plus auditable proof of
deletion across data stores (US11120156B2). Accordingly, lineage-aware deletion and deletion proof
are explicitly outside the novelty claim. See `docs/STRUCTURED_PRIOR_ART_AND_PATENT_REVIEW.md` for
the search protocol, closest works, patent publications, and corrected contribution boundary.

## PCUG working contribution boundary

Literature snapshot date: 2026-08-22. This is a targeted review, not a completed systematic or patent
search.

PCUG tests the composition of three parts:

1. registered deletion completeness over typed operational paths, where active physical artifacts,
   unknown edges, and quantitative influence claims remain distinct;
2. minimum-cost action selection whose declared transitions must succeed under replay rather than
   being trusted as static node coverage;
3. a signed multi-view proof bundle whose verdict, costs, paths, commitments, and model-channel
   decisions are independently recomputed.

The working claim is limited to this tested composition. PCUG does not claim invention of
provenance, min-cut, set cover, machine unlearning, exact retraining, per-instance privacy, hidden
evaluation, cryptographic commitments, digital signatures, or deletion receipts. If a work is found
that implements the same three-part input/algorithm/output contract under a comparable threat model,
the contribution must be narrowed or redesigned before competition submission.

Passing the controlled simulator can support only a statement about its registered faults and
semantics. External generalization requires separately sourced locked evidence. FaceID/eGov claims
require authorized production instrumentation; application-style labels are not production evidence
and are not independent scientific datasets.

## TRE working contribution boundary

Topology-Robust Erasure does not claim invention of uncertainty sets, robust set cover, robust
network interdiction, topology mutation, temporal reachability, tombstones, or synthetic deletion
tests. Its narrower hypothesis is that a subject-scoped RSE contract can select one exact
minimum-cost control set that passes fail-closed replay across every topology in a declared finite
uncertainty envelope, while returning a shortest adversarial regeneration witness and an explicit
robustness premium relative to nominal MSC.

The first prospective result supports only the eight project-authored scenarios and declared cost
catalogue. It cannot be generalized to arbitrary missing transitions or used as evidence that an
external system lies inside the envelope. A broader novelty claim still requires independent cases
and a professional patent search.

## Open stock-service transfer contribution boundary

The frozen v1 transfer result adds a narrower empirical contribution: the same family-neutral
three-valued decision and exact physical-control contract executed without service-specific scoring
changes on stock Keycloak identity lifecycle, MLflow run/artifact lineage, and Qdrant biometric
vectors. It caught temporal or derivative failures that native success missed in all three families
and failures that a complete typed-node snapshot audit missed in the registered recovery cases.

This is evidence for compositional portability, not a claim that using Keycloak, MLflow, Qdrant,
face vectors, snapshots, garbage collection, lineage adapters, or deletion testing is new. The
services, public Olivetti input, and underlying operations are prior components. The mappings,
faults, and execution remain project-authored, so the result cannot establish independent novelty,
production relevance, world priority, or coverage of arbitrary unknown infrastructures. Those
claims still require external authorship, an authorized pilot, and a broader professional patent
review.

## Erasure Tomography working contribution boundary

Erasure Tomography does not claim invention of group testing, disjunct matrices, Boolean network
tomography, active probes, deletion canaries, synthetic users, data-flow discovery, or coded test
design. Relevant close foundations include:

- Galesi and Ranjbar,
  [Counting and localizing defective nodes by Boolean network tomography](https://arxiv.org/abs/2101.04403),
  localizes network failures from Boolean path outcomes;
- D'yachkov et al.,
  [Error-correcting nonadaptive group testing with disjunct matrices](https://doi.org/10.1016/S0166-218X(97)80002-9),
  provides the error-correcting coding foundation;
- Chakraborty et al.,
  [Meaningful Data Erasure in the Presence of Dependencies](https://www.vldb.org/pvldb/vol18/p3435-chakraborty.pdf),
  computes principled minimal dependent deletion when dependency rules are supplied;
- [Chava: A Verification-Aware Data Model](https://openreview.net/attachment?id=uB2AIgYgym&name=pdf)
  carries verification obligations and evidence with processed data; and
- OneTrust's cited deletion-testing patent already covers synthetic test subjects and tokens.

The targeted search did not find the same tested input/algorithm/output contract: coded
synthetic-subject deletion/recovery workflows, an exact fail-closed bounded-support certificate,
localization of a recurrence mechanism, translation into PCUG/TRE, and physical post-control replay.
That absence supports a high working novelty score but is not proof of world priority or
patentability.

The first result is deliberately narrow. Its catalogue has four project-authored mechanisms,
`k=1`, and `e=0`; three probes are only one fewer than four individual checks, and random/greedy
coded baselines also succeed at three in this small domain. The contribution claim is therefore the
erasure-specific fail-closed composition and demonstrated topology-acquisition layer, not a better
general group-testing code.
