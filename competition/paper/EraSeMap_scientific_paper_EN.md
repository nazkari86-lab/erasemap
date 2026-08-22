# EraSeMap: Proof-Carrying Residual-Path Auditing and Minimum-Cost Remediation for Biometric Data Erasure

**Research paper — English version**
**Author:** ____________________
**Affiliation:** ____________________
**Supervisor:** ____________________
**Year:** 2026

## Abstract

Deleting a biometric record from the primary database does not necessarily remove its derived template, search index entry, cache copy, backup, audit replica, or influence on a trained model. This paper presents EraSeMap, a subject-scoped erasure auditor built around a Proof-Carrying Unlearning Graph (PCUG). It refuses to report completion while a residual path, failed verifier, unknown mandatory channel, or unsuccessful action replay remains. The method produces one of three verdicts—COMPLETE, INCOMPLETE, or UNVERIFIED—together with the shortest residual counterexample and a minimum-cost Counterfactual Deletion Cut (CDC). Residual paths define what may still be usable; typed verifier channels define required evidence; and a finite optimization problem selects the least-cost permitted action set whose simulated post-action state passes the same frozen audit. Lean 4 machine-checks conditional replay soundness and finite CDC optimality. The production branch-and-bound selector matched an exhaustive oracle in 3,072 of 3,072 systematic runs. In a project-authored mechanism stress test, EraSeMap produced 0/75 false-complete verdicts while a node-state-only typed audit produced 75/75. On a source-locked benchmark derived from five official external structures, EraSeMap produced 0/100 false completes and 25/25 correct completes, but tied the strongest typed baseline. In a preregistered local multi-service experiment using real PostgreSQL, Redis, and Qdrant processes, encrypted backups, and a ridge model, targeted CDC reached verified completion in 20/20 paired trials, retained all 249 non-deleted records per trial, matched rebuild-all ridge weights within 2.22 × 10⁻¹⁵, reduced written bytes by 94.62%, and achieved a 17.64× geometric-mean speedup over rebuild-all (paired bootstrap 95% CI: 16.39×–18.98×). A bounded adaptive face-unlearning experiment passed its frozen utility, privacy, and speed gates, but is not independent confirmation. The results support the feasibility and internal correctness of proof-carrying erasure auditing while leaving topology completeness, independent hidden evaluation, and production deployment as explicit open obligations.

**Keywords:** biometric erasure; machine unlearning; data lineage; verifiable deletion; residual path; minimum-cost remediation; fail-closed audit.

## 1. Introduction

Biometric systems rarely store a person’s data in one place. An enrollment image can generate a face template; the template can be indexed in a vector database and cached; training records can influence a model; backups can preserve earlier states; and an audit service can retain metadata. Removing only the source row can therefore create a dangerous false-complete claim: the interface says “deleted,” while a usable derivative remains.

This problem matters beyond one application. Identity proofing, border control, banking KYC, school access, and face verification use different infrastructure, but they share the same operational question: after a subject requests erasure, which reachable artifacts can still reproduce, match, restore, or statistically reveal the subject’s information? A deletion receipt alone cannot answer that question. A valid signature proves who signed a statement and that the statement was not altered; it does not prove that every underlying deletion action succeeded.

Machine unlearning addresses removal of training-data influence from models. Data provenance represents how entities and activities are connected. Proof-of-deletion research studies verifiable claims. Optimization methods can choose low-cost action sets. Each area solves part of the problem. EraSeMap studies a narrower systems question: can these components be combined into one subject-scoped, fail-closed contract that returns a reproducible verdict and an actionable correction instead of an unsupported promise? The core representation is the **Proof-Carrying Unlearning Graph (PCUG)**; its remediation object is the **Counterfactual Deletion Cut (CDC)**.

The research question is:

> Can a proof-carrying residual-path audit prevent false claims of complete biometric erasure and select a verified minimum-cost remediation plan across heterogeneous storage and model artifacts?

**Objective.** Develop and test a reproducible method that detects unresolved subject-level erasure obligations, explains the shortest known failure path, and selects a permitted low-cost correction that must pass a repeated audit.

**Object of study.** Operational data-erasure workflows in heterogeneous biometric information systems.

**Subject of study.** The relationship between typed lineage, mandatory quantitative evidence, replayed actions, false-complete decisions, and remediation cost.

**Hypothesis H1.** On cases where physical node states appear closed but a mandatory evidence or replay obligation fails, PCUG has a lower false-complete rate than an audit based only on typed node states. The null hypothesis is that PCUG provides no reduction.

**Hypothesis H2.** In a registered multi-service topology, exact CDC can use less measured time and fewer written bytes than rebuild-all while reaching the same replayed COMPLETE verdict and retaining the same non-deleted identities. The null hypothesis is that targeted CDC has no efficiency advantage under equal completion requirements.

The tasks are to formalize residual completion, implement the evaluator and optimizer, machine-check the bounded guarantees, compare against fixed baselines, measure a real-process system, and state the external-validity boundary.

The paper makes four bounded contributions:

1. A typed residual-path model that keeps physical artifacts, model influence, unknown evidence, and policy blocks semantically distinct.
2. A three-valued completion rule that fails closed, returns the shortest counterexample, and requires successful replay before accepting a correction.
3. A finite minimum-cost CDC formulation with a machine-checked optimality theorem and executable oracle conformance.
4. A layered evaluation covering controlled faults, official external structures, real local services, and a bounded face-unlearning channel, with negative results and independence limits preserved.

## 2. Related Work and Novelty Boundary

Cao and Yang introduced machine unlearning as a way to remove data and its lineage from learning systems [1]. Bourtoule et al. proposed SISA training to reduce retraining cost by isolating training state [2]. Sommer et al. framed unlearning verification as hypothesis testing [3]. Weng et al. proposed algorithm-level proof of unlearning with authenticated lineage [4], while Eisenhofer et al. studied cryptographically verifiable unlearning [5]. Chourasia and Shah showed that similarity to retraining is not automatically a complete privacy guarantee, especially across releases [6]. Zhang et al. demonstrated that verification mechanisms can be evaded by a dishonest provider [7]. Koloskova et al. developed certified neural-network unlearning under a separate formal guarantee model [8]. W3C PROV provides a standard vocabulary for entities, activities, agents, and derivations [9].

EraSeMap therefore does **not** claim to invent provenance graphs, lineage traversal, machine unlearning, exact retraining, proofs of deletion, signatures, shortest paths, set cover, or minimum cuts. Patent review also found prior claims covering lineage-aware deletion, derived locations, backups, and auditable deletion [10–12].

The working novelty claim is the tested composition:

> A subject-scoped, fail-closed residual-path contract combines registered physical artifacts, request-scoped model influence, mandatory quantitative verifier channels, replayed actions, and independently recomputed evidence into one three-valued verdict, shortest residual counterexample, and minimum-cost remediation plan.

This is a research hypothesis, not a “first in the world” declaration. A stronger novelty claim requires an independently authored hidden benchmark and a wider professional patent search.

## 3. System and Threat Model

### 3.1 Scope

The audited unit is one erasure request for one subject. The trusted boundary contains a registered topology, artifact-specific local verifiers, a frozen audit policy, and an evaluator that recomputes the result from canonical evidence. The operator may make mistakes, omit actions, or supply incomplete evidence. The model does not guarantee discovery of an unregistered service controlled by the same malicious provider. Topology completeness and verifier soundness are explicit assumptions rather than hidden promises.

### 3.2 Typed operational graph

Let the registered erasure topology be a finite directed graph

**G = (V, E, τ, s),**

where **V** is the set of artifacts, **E** is the set of propagation or derivation edges, **τ(v)** is the artifact type, and **s(v)** is its observed lifecycle state. Types include source record, biometric template, search-index entry, cache entry, backup copy, model influence, and audit receipt. Edges describe copying, derivation, indexing, backup, training use, or supersession.

For a subject **u**, let **Sᵤ ⊆ V** be the subject’s registered origins and let **Tᵤ ⊆ V** be artifacts that can still be used to match, restore, process, or reveal the subject. A path

**π = (v₀, v₁, …, vₖ)**

is an active residual path when **v₀ ∈ Sᵤ**, **vₖ ∈ Tᵤ**, every edge on the path is active under policy, and the terminal artifact has not been proven erased, safely blocked, expired, or unlearned. The residual set is

**Rᵤ(G) = {π | π is an active residual path for u}.**

This definition turns “something may remain” into a concrete counterexample. EraSeMap returns a shortest residual path

**π* = arg min₍π∈Rᵤ(G)₎ |π|,**

with deterministic tie-breaking. The shortest path is not claimed to be the most harmful path; it is the smallest actionable explanation.

### 3.3 Artifact-specific evidence

One generic receipt is insufficient because evidence depends on artifact type. A source row, template, or index entry requires a matching pre-deletion commitment and observed absence. A cache requires invalidation, propagation time, and observed absence. A backup requires expiry under policy or destruction of its encryption key. A model-influence node requires a frozen protocol, an exact-retraining reference, and quantitative utility/privacy checks. A blocked artifact requires an enforced processing control. A receipt requires a valid envelope, nonce, graph-root commitment, and chain.

Let **Cᵤ** be the mandatory verifier channels for request **u**. Each channel returns

**q(c) ∈ {PASS, FAIL, UNKNOWN}.**

UNKNOWN is not converted to success. It represents missing, expired, inaccessible, or not-yet-mature evidence.

### 3.4 Three-valued verdict

The verdict is

**INCOMPLETE**, if **Rᵤ(G) ≠ ∅** or at least one mandatory channel is FAIL;

**COMPLETE**, if **Rᵤ(G) = ∅** and every mandatory channel is PASS;

**UNVERIFIED**, otherwise—there is no established active residual, but at least one mandatory channel is UNKNOWN.

The order is deliberate. A known residual cannot be hidden by missing evidence elsewhere. COMPLETE requires both path closure and positive evidence. This is the fail-closed property.

## 4. Minimum-Cost Counterfactual Deletion Cut

When the verdict is not COMPLETE, the system constructs a finite catalog **A** of candidate actions. An action can delete a record, invalidate a cache, erase a backup key, rebuild an index, retrain or unlearn a model, or enforce a processing block. Each action **a** has a non-negative cost **c(a)** and a permission flag **p(a) ∈ {0,1}**.

For an action subset **B ⊆ A**, let **Apply(G,B)** denote the deterministically simulated post-action graph and evidence. Let **F** be the same frozen three-valued evaluator used for the original request. Feasibility is defined by replay, not by declared action coverage:

**Feasible(B) ⇔ (∀a ∈ B, p(a)=1) ∧ F(Apply(G,B)) = COMPLETE.**

The exact CDC is

**B* ∈ arg min₍B⊆A : Feasible(B)₎ Σₐ∈B c(a).**

Residual-coverage abstractions can help explain candidate actions, but set coverage alone is not accepted as proof: channel dependencies and interactions between actions can make nominal coverage insufficient. The frozen evaluator is therefore the authoritative feasibility predicate.

For at most 30 permitted actions, EraSeMap uses deterministic exact branch-and-bound over replay feasibility. Larger catalogs use a deterministic greedy fallback and are labeled non-optimal. Costs are fixtures unless a measured experiment explicitly calibrates them. A plan remains a counterfactual recommendation until its actions are executed in a disposable or authorized environment, topology and evidence are recollected, and the same audit is replayed. Only an observed replayed COMPLETE is accepted as completed remediation.

## 5. Formal Guarantees

### 5.1 Conditional replay soundness

Let **Rᵣₑₐₗ(u)** be the set of real active residuals and **Rᵣₑg(u)** the registered residuals. Assume:

1. **Topology completeness:** every real active residual is represented by an active registered residual.
2. **Path-closing soundness:** if a registered residual is declared closed, its represented real residual is inactive.
3. **Channel soundness:** PASS on a mandatory verifier implies the corresponding real-world obligation holds.
4. Replayed evaluation returns COMPLETE.

Then **Rᵣₑₐₗ(u) = ∅**, and every mandatory real-world obligation holds.

*Proof sketch.* COMPLETE implies that all registered residuals are closed and every mandatory channel passes. If a real active residual remained, topology completeness would map it to an active registered residual, contradicting closure plus path-closing soundness. Channel soundness transfers every registered PASS to its real obligation. Q.E.D.

This theorem is conditional by design. Without topology completeness, an omitted backup can remain while every registered path is closed. Without channel soundness, a verifier can return PASS while the obligation is false. Lean 4 contains checked counterexamples for both missing assumptions.

### 5.2 Finite CDC optimality

For a finite list of candidate action subsets, a deterministic feasibility predicate, and non-negative costs, the exhaustive selector returns no plan exactly when no listed plan is feasible; otherwise it returns a feasible plan whose cost is no greater than every listed feasible plan.

*Proof sketch.* The selector folds over a finite list while maintaining the cheapest feasible candidate observed so far. The invariant is true initially and preserved at every comparison. At termination, the stored candidate is feasible and no listed feasible candidate has smaller cost. Q.E.D.

Lean 4.33.1 machine-checks both results without `sorry` or `admit`. These theorems cover the abstract core, not Python semantics, driver correctness, or real topology discovery. The production Python selector is therefore tested separately against an exhaustive oracle.

## 6. Implementation

EraSeMap is implemented as a reproducible Python package with canonical JSON inputs and outputs. Decoding rejects missing or unknown fields, duplicate nodes or edges, unknown endpoints, and implicit cross-subject edges. Canonical sorting makes graph roots, receipts, and evidence bundles deterministic.

The output proof bundle includes the request and protocol identifiers, registered graph commitment, three-valued verdict, shortest residual path, verifier-channel decisions, selected actions and costs, replay result, evidence hashes, and an Ed25519 receipt chain. The signature covers a minimal envelope and intentionally excludes subject identifiers, biometric values, raw paths, and free text. The evaluator recomputes the verdict and plan from the evidence rather than trusting cached labels.

The repository includes 233 tests with 90.30% measured coverage in the full CI-equivalent test command, locked protocols, raw records, manifests, preregistrations, negative-result reports, a Lean project, command-line demonstrations, and CI gates. Engineering verification increases reproducibility but is not counted as independent scientific validation.

## 7. Experimental Methodology

### 7.1 Primary metric

The principal safety metric is the false-complete rate

**FCR = N(false COMPLETE on a non-complete case) / N(non-complete cases).**

Lower is better. A false complete is more dangerous than UNVERIFIED because it can stop remediation while a residual remains. For binomial endpoints, the reports use Wilson 95% intervals. For paired performance ratios, the multi-service experiment uses a deterministic paired bootstrap and reports the geometric mean because ratios are multiplicative.

### 7.2 Layer A: controlled mechanism stress

The project-authored stress set contains 100 cases: 25 genuinely complete and 75 non-complete. In every non-complete case, all subject-scoped physical nodes appear closed, but a mandatory model-evidence, unknown-verifier, or action-replay channel prevents completion. This isolates the mechanism that a node-state audit cannot express. Because the cases and algorithm share project authorship, the layer demonstrates internal mechanism behavior, not external generalization.

### 7.3 Layer B: source-locked external structures

The source-locked benchmark contains 125 unique cases derived from official structures in NIST SP 800-63A, W3C PROV-O, OpenSearch, MLflow, and PostgreSQL. There are 25 cases in each family; 100 are INCOMPLETE or UNVERIFIED and 25 are COMPLETE. Source excerpts, mappings, commitments, labels, raw records, and hashes are stored. The documents are external, but mappings, case construction, labeling, and execution are project-authored.

Comparators are PCUG, a complete typed-node audit, a flat checklist, a model-only check, and a receipt-only check. The preregistered primary gate requires the pooled false-complete Wilson upper bound to be at most 0.05.

### 7.4 Layer C: real-process multi-service experiment

The preregistered paired experiment launches PostgreSQL 15.18, Redis 8.8, and Qdrant 1.15.4; creates AES-GCM encrypted backup files; and trains a ridge model. Each trial contains 250 deterministic synthetic identities. After deleting one source identity from PostgreSQL, two strategies are compared on identical retained state:

- **Targeted CDC:** delete the vector, invalidate the cache, destroy the backup key, and remove exact ridge sufficient statistics.
- **Rebuild-all:** reconstruct every registered component from retained source data.

Five calibration seeds convert measured component time into integer microsecond costs. Twenty holdout seeds are then run once, with strategy order alternating by seed parity. Frozen gates require 20/20 replayed COMPLETE, no retained-identity loss, ridge weights matching rebuild-all within tolerance, and a paired-bootstrap speedup lower bound above 1.25×.

### 7.5 Layer D: bounded model-unlearning channel

The face experiment uses a trainable local embedding encoder over an external face dataset and compares stale, exact retraining, simple approximate baselines, and deletion-matched restart. The forgotten identity is excluded from every candidate optimization step. The adaptive MUFAC v3.2 run uses 120 candidate epochs versus 200 for exact retraining and evaluates 100 deletion requests, producing 500 method-trials on a frozen 572-image, 60-identity subset. Its six paired privacy statistics use confidence, negative entropy, margin, energy, identity-deletion likelihood ratio, and nearest-embedding signals; the protocol uses zero shadow models, so this is a bounded attack panel rather than a full adaptive shadow-model privacy audit.

Frozen gates include retained verification AUC difference of at least −0.01, mean speedup of at least 1.5×, maximum paired privacy-advantage upper confidence bound at most 0.10, and bounded embedding-error ratios. The 120-epoch budget was selected after earlier MUFAC results were known; v3.2 is therefore a method-improvement result, not untouched confirmation. Exact retraining remains the mandatory fallback when any dataset-specific gate fails.

## 8. Results

### 8.1 Mechanism and transfer

| Evaluation | EraSeMap / PCUG | Strongest comparison | Interpretation |
|---|---:|---:|---|
| Mechanism stress, 75 non-complete cases | 0/75 false complete | Typed node state: 75/75 | Shows value of mandatory channel and replay semantics on project-authored faults |
| Source-locked benchmark, 100 non-complete cases | 0/100; Wilson 95%: 0.0000–0.0370 | Complete typed audit: 0/100 | Passes transfer gate but does not beat the strongest baseline |
| Source-locked complete cases | 25/25 correct complete | Typed audit: 25/25 | No over-conservative failure on complete cases |

Flat checklist, model-only, and receipt-only methods each produced 100/100 false completes in the source-locked non-complete cases. This establishes that narrow component checks are insufficient. The tie with the complete typed audit is a scientifically important negative result: external-structure transfer is supported, but superiority of PCUG’s composition is not yet independently established.

### 8.2 Optimization correctness

The production branch-and-bound exact CDC selector was compared with an exhaustive oracle across 512 cost/permission catalogs and all six input orders, including zero-cost, tied-cost, forbidden-action, feasible, and infeasible cases. It matched the oracle in **3,072/3,072** runs with zero mismatches.

### 8.3 Measured multi-service performance

Targeted CDC reached replayed COMPLETE in **20/20** paired trials and preserved all **249** retained identities per trial. Ridge-model weights matched rebuild-all within **2.22 × 10⁻¹⁵**. The geometric-mean wall-clock speedup was **17.64×**, with paired-bootstrap 95% CI **[16.39×, 18.98×]**. Targeted remediation wrote **691,780 bytes**, compared with **12,849,080 bytes** for rebuild-all, a **94.62% reduction**.

These measurements show that minimum-cost targeted remediation can substantially reduce work in the registered local topology without weakening the same replayed completion criterion. They do not estimate cloud latency, block-device write amplification, network traffic, energy, or organizational downtime.

### 8.4 Model channel

MUFAC v3.2 passed all unchanged gates. Retained verification AUC was 0.91912, compared with 0.92565 for exact retraining, a difference of **−0.00653**. Mean speedup was **1.593×**. The maximum paired privacy-advantage upper confidence bound was **0.04091**. Forgotten and retained embedding-MSE ratios to stale were 0.03064 and 0.03348. These numbers support the bounded policy on the exposed subset, not general equivalence to exact retraining or a production privacy guarantee.

## 9. Discussion

The main practical result is not merely detection. A useful erasure system must answer three questions in one reproducible chain: What remains? Why is completion blocked? What is the least expensive permitted action set that actually reaches completion? The residual path answers the first two; CDC and replay answer the third.

The three-valued verdict also separates absence of evidence from evidence of absence. A binary system is tempted to treat “not observed” as “gone.” UNVERIFIED preserves uncertainty and keeps the request open. This matters for delayed backup expiry, unreachable services, missing model audits, and asynchronous cache invalidation.

The formal theorem clarifies rather than eliminates operational risk. It shows that COMPLETE is sound **if** the topology represents real residuals and local verifiers are sound. These conditions become deployment obligations that an organization can test, assign, and audit. The theorem does not make invisible infrastructure visible.

The strongest current evidence for added composition value remains internal: the mechanism stress set was designed to exercise mandatory channels and replay. The external-structure benchmark tied the strongest typed audit. Therefore, the next decisive experiment is not another feature or larger project-authored simulator. It is an independently authored hidden challenge containing edge, channel, replay, and hidden-artifact interactions, executed once against a frozen evaluator.

## 10. Threats to Validity and Limitations

**Topology completeness.** EraSeMap cannot prove deletion from an artifact absent from trusted instrumentation. A provider controlling topology, evidence, signer, and evaluator can hide a residual.

**Independence.** Official structures are externally sourced, but mappings and labels are project-authored. No independently authored hidden challenge has been completed.

**Baseline result.** PCUG did not outperform the strongest typed-node audit on the source-locked primary endpoint. Claims of general superiority are unsupported.

**Production transfer.** No Apple Face ID, Kazakhstan eGov, bank, school, border, or government production environment was accessed. Local real-process tests use synthetic identities.

**Model scope.** The adaptive face result follows exposed earlier runs. Its six privacy statistics use no shadow models. Deep-model behavior, adaptive shadow-model attacks, sequential deletions, retained-user privacy, and population shift require separate preregistered experiments.

**Performance scope.** The 17.64× result is local wall-clock performance on one Apple M4 laptop. The byte count measures application payload and replaced files, not full storage or network I/O.

**Novelty search.** The review is structured but not a complete systematic review or legal freedom-to-operate opinion. New publications and patents can narrow the claim.

## 11. Ethics and Responsible Use

Biometric data are sensitive and difficult to replace after compromise. A deletion auditor should minimize additional exposure. EraSeMap receipts exclude biometric values and subject identifiers; experiment records use synthetic identities where possible; face datasets are used only for bounded model evaluation; and production access requires authorization. The tool should not be presented as legal certification. It is an engineering and research mechanism for producing auditable evidence and explicit uncertainty.

A production deployment should separate the topology registrar, evidence producer, and evaluator; use least-privilege service accounts; rotate signing keys; log verifier versions; protect proof bundles; define backup expiry; and obtain institutional approval for human biometric data.

## 12. Reproducibility

The public repository contains code, frozen protocols, raw records, manifests, reports, Lean proofs, and CI configuration. The evidence evaluated in this paper is preserved in the public v0.3.1 history; protocol and raw-record manifests carry cryptographic hashes. Core reproduction commands are:

```bash
python -m pytest
lake build
python scripts/verify_formal_conformance.py --expected formal/conformance-v1.json --output /tmp/formal-conformance.json
python scripts/verify_measured_multiservice_v1.py
```

The measured service experiment additionally requires pinned PostgreSQL, Redis, Qdrant, and container dependencies. Reproduction verifies the published computation; it does not create independent authorship. No personal biometric data generated by the multi-service experiment are released because that experiment uses deterministic synthetic identities; the external face inputs remain governed by their original dataset terms.

## 13. Conclusion

EraSeMap demonstrates a practical and mathematically explicit way to audit biometric erasure across heterogeneous artifacts. A deletion request becomes a typed residual-path problem, completion becomes a conjunction of path closure and positive mandatory evidence, and correction becomes a minimum-cost action problem whose result must survive replay. The abstract guarantees are machine-checked; the optimizer conforms to an exhaustive oracle; real local services show substantial savings; and model influence is handled through a bounded quantitative gate with exact fallback.

The evidence supports reproducibility, internal correctness, and feasibility. It does not yet establish independent superiority or production-wide deletion. The strongest next result is an independently authored, frozen hidden challenge followed by an authorized organizational pilot. Preserving this boundary is not a weakness of the project; it is what makes its current claim scientifically defensible.

## References

[1] Y. Cao and J. Yang, “Towards Making Systems Forget with Machine Unlearning,” 2015 IEEE Symposium on Security and Privacy, pp. 463–480, 2015. DOI: 10.1109/SP.2015.35.

[2] L. Bourtoule et al., “Machine Unlearning,” 2021 IEEE Symposium on Security and Privacy, 2021. arXiv:1912.03817.

[3] D. M. Sommer, L. Song, S. Wagh, and P. Mittal, “Towards Probabilistic Verification of Machine Unlearning,” arXiv:2003.04247, 2020.

[4] J. Weng, S. Yao, Y. Du, J. Huang, J. Weng, and C. Wang, “Proof of Unlearning: Definitions and Instantiation,” arXiv:2210.11334, 2022.

[5] T. Eisenhofer, D. Riepel, V. Chandrasekaran, E. Ghosh, O. Ohrimenko, and N. Papernot, “Verifiable and Provably Secure Machine Unlearning,” IEEE Conference on Secure and Trustworthy Machine Learning (SaTML), 2025; arXiv:2210.09126v3.

[6] R. Chourasia and N. Shah, “Forget Unlearning: Towards True Data-Deletion in Machine Learning,” Proceedings of the 40th International Conference on Machine Learning, PMLR 202:6028–6073, 2023.

[7] B. Zhang, Z. Chen, C. Shen, and J. Li, “Verification of Machine Unlearning is Fragile,” Proceedings of the 41st International Conference on Machine Learning, PMLR 235:58717–58738, 2024.

[8] A. Koloskova, Y. Allouah, A. Jha, R. Guerraoui, and S. Koyejo, “Certified Unlearning for Neural Networks,” Proceedings of the 42nd International Conference on Machine Learning, PMLR 267:31275–31298, 2025.

[9] T. Lebo, S. Sahoo, and D. McGuinness, editors, “PROV-O: The PROV Ontology,” W3C Recommendation, 30 April 2013.

[10] U.S. Patent Application US20220414070A1, “Tracking Data Lineage and Applying Data Removal to Enforce Data Removal Policies,” 2022.

[11] U.S. Patent US11120156B2, “Privacy Preserving Data Deletion,” 2021.

[12] U.S. Patent US12456052B2, “Systems and Methods for Facilitating Verifiability of Machine Learning Model Unlearning,” 2025.

[13] D. Temoshok et al., “Digital Identity Guidelines: Identity Proofing and Enrollment,” NIST SP 800-63A-4, July 2025. DOI: 10.6028/NIST.SP.800-63a-4.

[14] EraSeMap, public repository and evidence archive, version 0.3.1, 2026: https://github.com/nazkari86-lab/erasemap.

## Appendix A. Notation

| Symbol | Meaning |
|---|---|
| G = (V,E,τ,s) | Registered typed erasure graph |
| u | Subject of one erasure request |
| Rᵤ(G) | Active residual paths for subject u |
| Cᵤ | Mandatory verifier channels |
| q(c) | PASS, FAIL, or UNKNOWN result for channel c |
| A | Finite catalog of candidate remediation actions |
| c(a) | Non-negative action cost |
| B | Selected action subset, B ⊆ A |
| Apply(G,B) | Deterministic post-action graph and evidence |
| F | Frozen three-valued evaluator |
| Feasible(B) | All selected actions are permitted and replay returns COMPLETE |
| FCR | False-complete rate |

## Appendix B. Claim–Evidence Map

| Claim | Evidence | Boundary |
|---|---|---|
| Replayed COMPLETE is conditionally sound | Lean theorem with explicit assumptions | Does not prove topology discovery or driver correctness |
| Exact CDC is minimum-cost over listed candidates | Lean finite optimality theorem | Only for the registered finite candidate set |
| Python exact CDC implements the finite contract | 3,072/3,072 oracle matches | Bounded systematic conformance, not Python formal semantics |
| Mandatory channels prevent a typed-node blind spot | 0/75 versus 75/75 mechanism stress | Project-authored development evidence |
| PCUG transfers to official external structures | 0/100 false complete; 25/25 complete | Strongest typed baseline tied; mappings are internal |
| Targeted remediation can be cheaper than rebuild-all | 17.64× speedup; 94.62% fewer bytes; 20/20 complete | One local machine and synthetic identities |
| Adaptive face candidate meets frozen bounded gates | −0.00653 AUC difference; 1.593×; privacy upper CI 0.04091 | Post-exposure adaptive result; exact fallback remains required |
