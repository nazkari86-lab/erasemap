# Structured Prior-Art and Patent Review

Snapshot date: 2026-08-22

## Scope and method

This is a reproducible structured search, not a legal freedom-to-operate opinion and not a complete
systematic review of subscription databases. Searches covered Google Patents, arXiv, PMLR,
OpenReview, ACM-indexed results, W3C/NIST standards, and backward references from identified surveys.

Query families combined:

- `machine unlearning` with `verification`, `proof`, `audit`, `residual`, and `lineage`;
- `data deletion` with `provenance graph`, `derived data`, `backup`, and `proof`;
- `right to be forgotten` with `lineage`, `model`, `backup`, and `verification`;
- patent searches for the same concepts and their synonyms.

Included items had to implement or formally define at least one relevant input/algorithm/output
component. Commentary without a technical mechanism was excluded. Titles, publication identifiers,
dates, URLs, overlap, and non-overlap are recorded below. Searches should be repeated immediately
before competition submission because 2025–2026 unlearning work is moving quickly.

## Closest research

| Work | Established contribution | Boundary relative to EraSeMap |
|---|---|---|
| Cao & Yang, *Towards Making Systems Forget with Machine Unlearning* (2015) | Unlearning across systems when lineage spans components | Prevents claiming invention of lineage-guided system forgetting |
| Bourtoule et al., *Machine Unlearning* (2021) | SISA partitioning and efficient retraining | Prevents claiming invention of structured retraining |
| Sommer et al., *Towards Probabilistic Verification of Machine Unlearning* (2020) | Formal hypothesis-testing view and backdoor verification | Prevents claiming invention of probabilistic unlearning verification |
| Eisenhofer et al., *Verifiable and Provably Secure Machine Unlearning* (2022/2025) | Cryptographic definition, SNARK/hash-chain proofs of update and unlearning | Prevents claiming invention of cryptographic proof-carrying unlearning |
| Weng et al., *Proof of Unlearning: Definitions and Instantiation* (2022) | Algorithm-level proof of unlearning with authenticated lineage and SGX-backed verification | Prevents claiming invention of lineage-authenticated proof of unlearning |
| Chourasia & Shah, *Forget Unlearning* (ICML 2023) | Sound deletion/privacy guarantees and release-history risks | Prevents treating retraining similarity as a complete privacy guarantee |
| Zhang et al., *Verification of Machine Unlearning is Fragile* (ICML 2024) | Provider can retain information while passing verification strategies | Requires an explicit malicious-provider limitation |
| Wang et al., *Machine Unlearning: A Comprehensive Survey* (2024) | Taxonomy including verification, privacy, and security | Confirms the breadth of established unlearning work |
| Koloskova et al., *Certified Unlearning for Neural Networks* (ICML 2025) | Certified neural-network unlearning | Prevents broad certified-unlearning novelty claims |
| Ahsan et al., *Forget and Explain* (2025/2026) | Explainability and graph-change evidence for GNN unlearning | Overlaps human-readable residual evidence, but focuses on GNN model internals |

## Closest patents

| Publication | Overlap that must not be claimed as new |
|---|---|
| US20220414070A1 / US12380071B2 | Graphs of customer-data lineage, traversal, derived locations, and deletion along paths |
| US20240012797A1 / US12475092B2 | Lineage-aware retention, correctness, transparency, verifiability, deletion graphs |
| US11120156B2 | Auditable privacy-preserving proof of deletion across multiple data stores |
| US20200387625A1 | Right-to-be-forgotten deletion across primary and backup copies using key erasure |
| WO2021174104A1 | Modification/deletion of selected personal data in time-series backup data lakes |
| US11108559B2 | Signed provenance attestations and proofs of object deletion |
| US20230350843A1 | Transaction-level retention inheritance through data lineage |
| US20260087104A1 | AI training/deployment data removal and an unlearning verification network |
| US20250190784A1 / US12456052B2 | DAG-like staged unlearning, hashes or zero-knowledge proofs for intermediate model instances, and verification that the resulting model reached production |

## Corrected novelty boundary

EraSeMap does **not** claim invention of:

- lineage graphs, provenance, deletion traversal, derived-data discovery, or retention propagation;
- machine unlearning, exact retraining, SISA, verification attacks, or certified unlearning;
- proof of deletion, signatures, hash chains, commitments, receipts, SNARK-style verification;
- minimum cuts, set cover, shortest paths, action planning, or counterexample generation alone.

The research hypothesis is the narrower composition:

> A subject-scoped, fail-closed residual-path contract can combine operational physical artifacts,
> request-scoped model influence, mandatory quantitative verification channels, replayed deletion
> actions, and independently recomputed evidence into one three-valued verdict, shortest residual
> counterexample, and minimum-cost remediation plan.

The project must demonstrate that the composition catches failures missed by strong component
baselines. The source-locked v1 holdout showed transfer but tied typed-node audit. The separately
labelled mechanism stress test exposes cases where all physical node states look complete while a
mandatory model/replay channel is failed or unknown; it is development evidence, not an independent
confirmation.

## Remaining novelty gate

Before asserting a peer-review-level novel contribution, an external evaluator must independently
author and freeze cases containing channel, edge, replay, and hidden-artifact interactions. PCUG
must outperform the strongest complete typed-node/replay baseline on that untouched set. A patent
professional must conduct jurisdiction-specific claim analysis before any commercialization or
patent filing.

## Primary links

- <https://www.yinzhicao.org/unlearning/UnlearningOakland15.pdf>
- <https://arxiv.org/abs/2003.04247>
- <https://arxiv.org/abs/2210.09126>
- <https://arxiv.org/abs/2210.11334>
- <https://proceedings.mlr.press/v202/chourasia23a.html>
- <https://openreview.net/forum?id=OkChMnjF6s>
- <https://proceedings.mlr.press/v267/koloskova25a.html>
- <https://arxiv.org/abs/2512.07450>
- <https://patents.google.com/patent/US20220414070A1/en>
- <https://patents.google.com/patent/US20240012797A1/en>
- <https://patents.google.com/patent/US11120156B2/en>
- <https://patents.google.com/patent/US20200387625A1/en>
- <https://patents.google.com/patent/WO2021174104A1/en>
- <https://patents.google.com/patent/US12456052B2/en>
