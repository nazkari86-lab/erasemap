# Structured Prior-Art and Patent Review

Snapshot date: 2026-08-23

## Erasure Tomography update

The ET-specific query family added combinations of `data deletion`, `right to erasure`, `erasure
verification`, `tomography`, `group testing`, `Boolean probes`, `hidden data flow`, `synthetic test
subject`, `recovery`, and `regeneration`. The closest technical foundations found were Boolean
network tomography/failure localization, error-correcting nonadaptive group testing, synthetic
deletion-test subjects, dependency-aware meaningful erasure, and verification-obligation data
models.

No reviewed source implemented the complete ET contract of bounded coded deletion/recovery probes,
fail-closed exact support certification, recurrence-mechanism localization, PCUG/TRE translation,
and physical post-control replay. This is a targeted negative search result, not proof that no such
publication or patent exists. General group testing, tomography, synthetic subjects, canaries,
data-flow mapping, and deletion verification remain excluded from the novelty claim.

## Scope and method

This is a reproducible structured search, not a legal freedom-to-operate opinion and not a complete
systematic review of subscription databases. Searches covered Google Patents, arXiv, PMLR,
OpenReview, ACM-indexed results, W3C/NIST standards, and backward references from identified surveys.

Query families combined:

- `machine unlearning` with `verification`, `proof`, `audit`, `residual`, and `lineage`;
- `data deletion` with `provenance graph`, `derived data`, `backup`, and `proof`;
- `right to be forgotten` with `lineage`, `model`, `backup`, and `verification`;
- patent searches for the same concepts and their synonyms.
- `robust optimization` and `uncertain set cover` with `deletion`, `erasure`, `topology`, and
  `regeneration`; deletion testing with `test subject`, `token`, `canary`, and `restore`.

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
| Lee, *Temporal Program Logic for Data* (2024) | Temporal deletion and retention policies in program logic | Prevents claiming invention of temporal deletion invariants |
| MUTE, *When Unlearning Fails* (2026) | Post-training influence echo in self-improving federated agent networks | Overlaps future re-emergence, but not heterogeneous storage transition auditing or costed stabilization |
| K9db (OSDI 2023) | Ownership-aware storage and compliant derived views by construction | Prevents claiming invention of erasability-by-design or compliant caches |
| Degel & Lutter, *A Robust Formulation of the Uncertain Set Covering Problem* (2013) | Minimum-cost set covering under uncertain coverage coefficients | Prevents claiming invention of robust covering or uncertainty envelopes |

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
| GB2562767A | Right-to-erasure-compatible encrypted backups and restoration |
| US10733148B2 | Predicate deletion and tombstone markers during compaction |
| US20210406398A1 / US11354435B2 | Synthetic test subjects, unique tokens, and post-deletion interactions used to detect retained personal data |

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

The RSE extension adds a second, separately testable composition hypothesis:

> Given a declared finite transition catalogue and fail-closed observed coverage, subject-specific
> reachable-closure checking can expose a shortest future regeneration witness and exact selection
> can find the least-cost set of registered guards that removes every registered witness.

This does not claim invention of temporal logic, tombstones, backup-aware deletion, reachability,
minimum cuts, or data-resurrection prevention separately. A targeted 2026-08-23 search did not find
the full heterogeneous DB/cache/vector/backup/model composition, but that search is not sufficient
for a worldwide-first or freedom-to-operate claim.

The TRE extension adds a third composition hypothesis:

> For a finite declared envelope of plausible topology shifts, one subject-scoped control set can
> be selected by exact all-scenario replay, accompanied by the shortest adversarial regeneration
> witness and the additional declared cost paid for robustness over nominal MSC.

This does not claim invention of robust optimization, uncertain set cover, network interdiction,
topology ensembles, mutation testing, canary users, or tombstones. The targeted search did not find
the exact combination of heterogeneous temporal erasure semantics, fail-closed evidence coverage,
all-scenario exact stabilization, and a reproducible adversarial witness. That absence is only a
working novelty boundary, not a priority or freedom-to-operate conclusion.

The GhostGraph extension adds a fourth composition hypothesis:

> Inside a frozen finite recovery-graph grammar, exact temporal interventions can preserve the full
> version space, select a one-step minimax separating query, fail closed on indistinguishable or
> outside-catalogue traces, and translate every justified survivor into robust erasure controls.

This does not claim invention of active causal discovery, optimal experiment design, network
tomography, version spaces, system identification, provenance discovery, canary users, or graph
repair. The current review has not established that this exact erasure-specific composition is
absent from every paper or patent claim. The repository therefore claims an implemented working
composition and testable hypothesis, not world priority, patentability, or freedom to operate.

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

For GhostGraph, the external author must choose the hidden graph structure and operate the trace
adapter without exposing truth or future traces to the project. The v2 seal/interactive-run/reveal/
sign kit is readiness evidence; until a genuine bundle passes technical and identity/conflict
review, its status remains `NOT_COLLECTED`.

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
- <https://ethz.ch/content/dam/ethz/special-interest/infk/chair-program-method/pm/documents/Education/Theses/Andrew_Lee_MA_report.pdf>
- <https://arxiv.org/abs/2607.28829>
- <https://www.usenix.org/system/files/osdi23-albab.pdf>
- <https://patents.google.com/patent/GB2562767A/en>
- <https://patents.google.com/patent/US10733148B2/en>
- <https://optimization-online.org/2013/06/3926/>
- <https://patents.google.com/patent/US20210406398A1/en>
