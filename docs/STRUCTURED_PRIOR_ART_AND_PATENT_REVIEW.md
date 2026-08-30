# Structured prior-art and patent review

Snapshot: 2026-08-30. This review records the closest known components of the single EraSeMap
FIND–ERASE–PROVE algorithm. It is not a complete systematic review or legal opinion.

## Search method

Search families combined `data deletion`, `right to erasure`, `lineage`, `derived data`, `backup`,
`machine unlearning`, `verification`, `proof`, `active testing`, `hidden data flow`, `temporal`, and
`regeneration`. Sources included arXiv, PMLR, OpenReview, W3C/NIST materials, Google Patents, and
backward references. Searches should be refreshed immediately before submission.

## Closest research

| Work | Established contribution | EraSeMap boundary |
|---|---|---|
| Cao & Yang, *Towards Making Systems Forget* (2015) | system unlearning across lineage | no claim to invent lineage-guided forgetting |
| Bourtoule et al., *Machine Unlearning* (2021) | SISA and efficient retraining structure | no claim to invent structured retraining |
| Sommer et al. (2020) | probabilistic unlearning verification | no claim to invent verification testing |
| Weng et al. (2022); Eisenhofer et al. (2025) | authenticated/cryptographic proofs of unlearning | no claim to invent proof-carrying unlearning |
| Chourasia & Shah (2023) | deletion/privacy guarantees and release-history risk | exact similarity is not treated as complete privacy |
| Zhang et al. (2024) | fragility of unlearning verification | malicious-provider and verifier limits are explicit |
| Koloskova et al. (2025) | certified neural-network unlearning | no certified-unlearning priority claim |
| W3C PROV | standard provenance vocabulary | no provenance invention claim |
| K9db (OSDI 2023) | ownership-aware compliant derived views | no erasability-by-design claim |
| Chakraborty et al. (PVLDB 2025) | meaningful dependent erasure | no minimum dependent-deletion priority claim |
| Temporal deletion policy work | temporal invariants and retention rules | no temporal-logic invention claim |
| Active/network tomography and version-space learning | intervention-based hidden-structure diagnosis | no general active-discovery priority claim |

## Closest patents

| Publication | Overlap excluded from novelty |
|---|---|
| US20220414070A1 / US12380071B2 | customer-data lineage graphs and deletion along derived paths |
| US20240012797A1 / US12475092B2 | lineage-aware retention and deletion graphs |
| US11120156B2 | auditable proof of deletion across stores |
| US20200387625A1 | primary/backup erasure using key destruction |
| GB2562767A | right-to-erasure-compatible backups |
| US10733148B2 | predicate deletion and tombstones |
| US20210406398A1 / US11354435B2 | synthetic subjects and post-deletion interactions |
| US20250190784A1 / US12456052B2 | staged model unlearning and verifiable deployment |

## Corrected contribution boundary

The project tests one narrower input/algorithm/output contract:

- **Input:** one subject, registered typed topology, mandatory physical/model verifiers, bounded
  recovery hypotheses, permitted actions, and registered future transitions.
- **Algorithm:** fail-closed active filtering, exact minimum sufficient physical/model action
  selection, and future recovery replay.
- **Output:** `COMPLETE_WITHIN_ENVELOPE`, `INCOMPLETE` with a counterexample, or `UNVERIFIED`, plus
  replayable evidence and a minimum-cost plan when one exists.

The targeted search did not identify the same complete composition. That negative search supports a
working novelty hypothesis only. It does not establish world priority, patentability, or freedom to
operate.

## Remaining novelty gate

An external evaluator must independently author hidden cases and operate the trace adapter without
revealing truth to the project. The frozen interactive handoff is readiness evidence; until an
accepted outside bundle passes source, signature, conflict, and scientific gates, status remains
`NOT_COLLECTED`.

## Primary links

- <https://www.w3.org/TR/prov-overview/>
- <https://www.yinzhicao.org/unlearning/UnlearningOakland15.pdf>
- <https://arxiv.org/abs/1912.03817>
- <https://arxiv.org/abs/2003.04247>
- <https://arxiv.org/abs/2210.09126>
- <https://arxiv.org/abs/2210.11334>
- <https://proceedings.mlr.press/v202/chourasia23a.html>
- <https://proceedings.mlr.press/v235/zhang24h.html>
- <https://proceedings.mlr.press/v267/koloskova25a.html>
- <https://www.usenix.org/system/files/osdi23-albab.pdf>
- <https://patents.google.com/patent/US20220414070A1/en>
- <https://patents.google.com/patent/US11120156B2/en>
- <https://patents.google.com/patent/US20210406398A1/en>
- <https://patents.google.com/patent/US12456052B2/en>
