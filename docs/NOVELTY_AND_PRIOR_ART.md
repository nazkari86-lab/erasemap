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
