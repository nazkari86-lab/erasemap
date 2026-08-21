# EraseMap Integration Contract

EraseMap can audit a production identity service only when every registered data-bearing component
provides a probe and a remediation action. This contract is intentionally vendor-neutral: Face
ID-like access control, bank KYC, school attendance, and government identity services map their
internal names to the same artifact types.

| Component | Required probe | Acceptable evidence | Remediation |
|---|---|---|---|
| Enrollment database | Lookup by irreversible subject commitment | Signed absence result | Delete row and dependent records |
| Biometric template store | Template lookup | Signed absence result and store revision | Revoke and purge template |
| Search/vector index | Vector-ID lookup | Index generation plus absence result | Delete vector and compact index |
| Cache | Key lookup after propagation deadline | Invalidation event plus absence result | Purge all regions |
| Backup | Key and ciphertext inventory | Destruction proof for unique encryption key | Destroy key or expire backup |
| Model registry | Training-lineage lookup | Frozen unlearning benchmark reference | Retrain or approved unlearning method |
| Receipt ledger | Nonce and chain lookup | Ed25519 signature, graph root, previous hash | Reject replay or tampering |

## Minimal event envelope

```json
{
  "artifact_id": "vector-index-eu-1",
  "artifact_type": "SEARCH_INDEX_ENTRY",
  "commitment": "hmac-sha256:...",
  "event": "ABSENCE_CHECK",
  "issued_epoch": 1787356800,
  "observed_absent": true,
  "store_revision": "index-generation-481",
  "signature": "ed25519:..."
}
```

Raw names, national identifiers, face images, and embeddings must not enter an EraseMap receipt.
The integration uses domain-separated HMAC-SHA-256 with a secret key held in a KMS or HSM. Plain
SHA-256 of a name or national identifier is forbidden because a small identity space can be
searched offline. A `COMPLETE` result applies only to registered components that returned valid
evidence; an unreachable required probe produces `UNVERIFIED`, never `COMPLETE`.

## Local production-like simulator

The simulator enrolls 25 anonymous citizens into real SQLite, NumPy, JSON, AES-GCM, and model
lineage artifacts. It processes five sequential deletion requests, preserves all non-requesting
citizens, chains signed receipts, and verifies that a modified receipt is rejected.

```bash
PYTHONPATH=src python experiments/run_egov_pilot_simulator.py
```

This is an integration rehearsal and evidence-contract test. It is not a claim that Apple, eGov,
or any government system has exposed these probes or authorized EraseMap.
