# Blinded external challenge

This package is for an evaluator who is independent of the EraSeMap author.

1. The evaluator writes cases with public topology under `case` and private `truth_verdict` plus
   `expected_path` beside it.
2. The evaluator runs `seal.py seal`. The public package contains encrypted answers and a SHA-256
   commitment, but no plaintext labels.
3. The evaluator keeps the printed key outside the EraSeMap repository and gives only the public
   package to the project author.
4. EraSeMap produces answer-blind records once.
5. The evaluator reveals answers, verifies the commitment, and scores the frozen records.

The independent evaluator must control case authorship, labels, key, reveal timing, and final
signature. A package created by the EraSeMap author is useful for testing but is not independent
evidence. Do not include personal data, credentials, private infrastructure names, or biometric
samples in a public package.

