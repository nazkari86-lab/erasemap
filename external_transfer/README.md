# External transfer handoff

This directory lets a genuinely external evaluator bind a hidden evaluation, raw evidence, and its
result to an identifiable signed manifest. Copy `manifest-template.json` into a separate result
directory, replace every placeholder, hash every evidence artifact, and sign the final manifest
with an evaluator-controlled Ed25519 key.

```bash
PYTHONPATH=. python external_transfer/attest.py generate \
  --private-key evaluator-private.pem --public-key evaluator-public.txt
PYTHONPATH=. python external_transfer/attest.py sign \
  --private-key evaluator-private.pem --manifest manifest.json --attestation attestation.json
PYTHONPATH=. python external_transfer/verify.py --submission /path/to/submission
```

Do not send the private key to the project author. A technically valid signature proves integrity
and key control, not identity or independence; those still require contact/conflict review. No
external result is claimed by this repository until a real identifiable evaluator submits one.
