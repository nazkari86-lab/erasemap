# EraSeMap bilingual usability kit

This packet tests whether an unfamiliar person can understand the deletion problem, choose the
three-valued verdict, identify the shortest residual path, and choose the next action. It contains
12 aligned English/Russian cards: four safe, four residual, and four insufficient-evidence cases.

The participant receives one language file and the response schema, never `gold-v1.json`. Generate
the card order with `randomized_order(participant_nonce, card_ids)` from `usability/score.py`.
Use a random pseudonymous participant ID. Do not collect names, contact details, biometrics,
government identifiers, or unrelated free text.

Mechanical verification:

```bash
PYTHONPATH=. python usability/verify.py
```

Scoring after a real evaluator places one JSON response per participant in a directory:

```bash
PYTHONPATH=. python usability/score.py --responses /path/to/responses
```

Fewer than ten participants always yields `INSUFFICIENT_SAMPLE`. With at least ten, every primary
endpoint must reach 80% accuracy for a technical `PASS`. This repository intentionally contains no
participant results; kit readiness is not evidence that people understood the project.
