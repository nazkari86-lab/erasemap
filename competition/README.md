# Competition defense package

- `EraSeMap_RU.pptx`: canonical 13-slide Russian defense deck with a uniform warm-paper organic-tech visual system, high-contrast Arial typography, speaker notes, project comparison charts, and a one-request walkthrough for first-time listeners.
- `build_organic_presentation.js`: editable PptxGenJS source for the deck; `assets/readable_*.png` contains the large, presentation-readable charts generated from `benchmark/evidence-charts-v1.json`.
- `../docs/JURY_DEFENSE_RU.md`: 30-second and 3-minute spoken versions.
- `../docs/JURY_DEFENSE_10_MIN_RU.md`: complete timed defense with demo cues.
- `../docs/JUDGE_QA_RU.md`: concise answers to adversarial judge questions.
- `../docs/COMPETITION_EVIDENCE_SCORECARD.md`: claim-to-evidence scorecard and fixed score events.
- `paper/EraSeMap_scientific_paper_RU.pdf` and `.docx`: complete Russian scientific paper.
- `paper/EraSeMap_scientific_paper_EN.pdf` and `.docx`: synchronized English scientific paper.
- `paper/EraSeMap_scientific_paper_RU.md` and `_EN.md`: auditable manuscript sources.
- `submission/`: public submission copies, bilingual abstract, theses, supervisor-review draft,
  registration-data draft, and the human-only pre-submission checklist.
- `Nurlanuly_Dulat_EraSeMap_Submission.zip`: self-contained public package with checksums and
  offline demonstrations. It intentionally contains no private identifiers or contact details.

Before presenting, rebuild the live artifact from the exact checkout:

```bash
erasemap showcase --repo-root . --output outputs/jury-showcase-v1
```

To rebuild the editable deck itself, install the pinned Node dependency and run:

```bash
cd competition
npm ci
npm run build
```

If the evidence JSON changes, regenerate the chart assets first with `python3 make_readable_assets.py`.

To rebuild the public archive after rebuilding documents and demonstrations:

```bash
python3 competition/submission/build_submission_archive.py
```

The deck distinguishes project-authored, local real-process, formal, source-locked, and genuinely
external evidence. Do not change the independence score from 7.8 until an accepted external result
exists under `external_results/`.
