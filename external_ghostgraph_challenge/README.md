# External GhostGraph blind challenge v2

This kit lets a person outside EraSeMap author hidden deletion-resurrection graphs and answer only
the adaptive probes selected by the frozen project code. Neither hidden graph IDs nor traces are in
the public input. After the run, the evaluator reveals the suite and signs a source-bound manifest.

The repository contains **no completed external submission**. Until a real outside evaluator authors,
seals, runs, reveals, and signs one, the only valid status is `NOT_COLLECTED`.

## Why v2 is stronger

Version 1 hid expected labels but exposed all observation traces before execution. Version 2 is an
interactive blind protocol: `active.py` selects the next minimax probe; an evaluator-controlled
adapter returns only that probe's trace. `verify_v2.py` later recomputes every planner decision,
oracle decision, trace, version space, verdict, source hash, commitment, and Ed25519 signature.

## Evaluator workflow

1. Clone a clean repository commit and record its full 40-character SHA.
2. Independently author at least five hidden cases covering every kind in `protocol-v2.json`.
   Declare a real name, contact, affiliation, non-membership, and hidden-case authorship. Use only
   synthetic subject commitments and systems you are authorized to test.
3. Seal the suite and keep the truth plus Fernet key private:

   ```bash
   python -m external_ghostgraph_challenge.seal seal \
     --suite truth-reveal.json --sealed sealed.bin --public public.json \
     --commitment commitment.json --key secret.key
   ```

4. On the evaluator-controlled machine, start the loopback reference adapter (or implement the same
   two-field JSON interface against an authorized test system):

   ```bash
   python -m external_ghostgraph_challenge.adapter_server \
     --suite truth-reveal.json --core-protocol benchmark/ghostgraph-live-v2.json
   ```

5. Give the project only `public.json`, `commitment.json`, `sealed.bin`, and the adapter URL. Run:

   ```bash
   python -m external_ghostgraph_challenge.active \
     --public public.json --core-protocol benchmark/ghostgraph-live-v2.json \
     --adapter-url http://127.0.0.1:8765 --output result.json
   ```

6. Reveal the suite. Copy every `required_source_files` entry into `source/` unchanged. Create
   `manifest.json` with `evaluator_name`, `evaluator_contact`, `clean_commit`, `result_sha256`, and
   an exact `source_sha256` mapping.
7. Generate a fresh evaluator key and sign the canonical manifest:

   ```bash
   python -m external_ghostgraph_challenge.attest generate \
     --private-key evaluator-private.pem --public-key evaluator-public.txt
   python -m external_ghostgraph_challenge.attest sign \
     --manifest manifest.json --private-key evaluator-private.pem --output attestation.json
   ```

8. Put the seven JSON/binary artifacts and `source/` in one directory, then run
   `python -m external_ghostgraph_challenge.verify_v2 --submission SUBMISSION`.

A valid technical result is still `TECHNICALLY_VALID_PENDING_IDENTITY_REVIEW`. A human must verify
identity, conflicts, authorization, independence, and relevance. Never commit a project-authored
suite or project-controlled signature as independent validation. The v1 scripts remain only for
reproducibility of the older non-interactive protocol; new evidence should use v2.
