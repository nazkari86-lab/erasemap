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
