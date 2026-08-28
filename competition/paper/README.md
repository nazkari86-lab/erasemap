# EraSeMap bilingual scientific paper

This directory contains two synchronized, submission-ready manuscripts:

- `EraSeMap_scientific_paper_EN.docx` and `.pdf` — English version;
- `EraSeMap_scientific_paper_RU.docx` and `.pdf` — Russian version;
- matching `.md` files — auditable source text;
- `build_papers.py` — deterministic DOCX and figure builder;
- `assets/` — the four generated bilingual figures.

The manuscripts describe one public algorithm, EraSeMap, as five stages (map, discover, minimize,
verify over time, certify). PCUG, GhostGraph, CDC, RSE, MSC, and TRE are internal reproducibility
labels. The synchronized results figure compares the unified algorithm's relevant stage with
non-EraSeMap baselines without pooling incompatible experiments into one score.

Both papers use A4 pages, the same research question, synchronized falsifiable hypotheses, the same compact
mathematical model, the same experiment results, and the same limitation boundary. Personal author,
affiliation, and supervisor fields are intentionally blank because the repository does not contain
verified submission metadata.

## Rebuild

Run with the bundled workspace Python containing `python-docx` and Pillow:

```bash
python competition/paper/build_papers.py
```

Convert the DOCX files to PDF with LibreOffice or use the document rendering tool described by the
repository environment. The committed PDFs were rendered from the committed DOCX files and visually
checked page by page.

## Claim boundary

The paper reports project-authored mechanism evidence, independently sourced but project-mapped
structures, formal Lean results, local real-process measurements, a post-exposure adaptive model
result, first-run preregistered sequential-release and temporal results, the finite-envelope TRE
result, bounded Erasure Tomography local/Redis results, GhostGraph v2 active/live results, the
separately frozen GhostGraph-T 300-case action-identification result including its strong-baseline
tie, and the preregistered 60-case transfer study on digest-pinned stock Keycloak, MLflow, and
Qdrant services as separate evidence layers. It also retains both real Qwen–TOFU negative results:
the semantically audited v1 under-forgetting/utility failure and the corrected author-disjoint v2
overscrubbing transfer failure. The transfer layer uses public Olivetti vectors but
project-authored identities, mappings, faults, and execution. It does not claim certified privacy,
arbitrary unknown-topology coverage, a completed independently authored hidden challenge, or a production
FaceID/eGov/government deployment.
