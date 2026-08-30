# EraSeMap bilingual scientific paper

This directory contains two synchronized, submission-ready manuscripts:

- `EraSeMap_scientific_paper_EN.docx` and `.pdf` — English version;
- `EraSeMap_scientific_paper_RU.docx` and `.pdf` — Russian version;
- matching `.md` files — auditable source text;
- `build_papers.py` — deterministic DOCX and figure builder;
- `assets/` — the four generated bilingual figures.

The manuscripts describe one public algorithm, EraSeMap, as three stages (FIND, ERASE, PROVE).
PCUG, GhostGraph, CDC, RSE, and MSC are internal reproducibility labels. The synchronized results
figure compares the unified algorithm's relevant stage with
non-EraSeMap baselines without pooling incompatible experiments into one score.

Both papers use A4 pages, the same research question, synchronized falsifiable hypotheses, the same compact
mathematical model, the same experiment results, and the same limitation boundary. The public title
page contains the verified author, school, class, and supervisor metadata. Private identifiers and
contact details are intentionally excluded.

## Rebuild

Run with the bundled workspace Python containing `python-docx` and Pillow:

```bash
python competition/paper/build_papers.py
```

Convert the DOCX files to PDF with LibreOffice or use the document rendering tool described by the
repository environment. The committed PDFs were rendered from the committed DOCX files and visually
checked page by page.

## Claim boundary

The paper reports project-authored mechanism evidence, formal Lean results, local real-process
measurements, preregistered sequential-release and temporal results, bounded hidden-path discovery,
and the preregistered 60-case transfer study on digest-pinned stock Keycloak, MLflow, and Qdrant
services as separate evidence layers. It also retains both real Qwen–TOFU negative results:
the semantically audited v1 under-forgetting/utility failure and the corrected author-disjoint v2
overscrubbing transfer failure. The transfer layer uses public Olivetti vectors but
project-authored identities, mappings, faults, and execution. It does not claim certified privacy,
arbitrary unknown-topology coverage, a completed independently authored hidden challenge, or a production
FaceID/eGov/government deployment.
