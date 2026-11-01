# Project status — Phase 2

Implemented from merged `origin/main` commit `9cd579e` in the existing Codex Cloud environment,
on branch `feature/phase2-forensic-evaluation`. Phase 1 was preserved; its 14 tests still pass.
Verified on 2026-11-02 (Asia/Calcutta). No public deployment was performed.

## Delivered

- Automatic non-text ink localization with page/bounding-box provenance, explicit uncertainty,
  bounded candidate/pair work and automated region ELA/ORB checks; manual crops remain optional.
- Alpha/EXIF-aware image decoding, multi-quality ELA with rendered-source applicability warning,
  and mutual ORB matches with RANSAC, spatial support and plausible transform checks.
- Xref-anchored adjacent revision extraction, 144-DPI signed/current and adjacent comparisons,
  text/annotation attribution, changed-region boxes, narrow metadata-only classification, and
  possible-shadow/intermediate-history findings. Both pyHanko policy and independent metadata
  judgments remain visible. Metadata allowlisting rejects catalog aliases and non-scalar values.
- Schema version 2 evidence fusion with codes, severities, explanations, completeness flags and
  explicit authenticity limits. Phase 1 report fields and API parameters are retained.
- Fixed-seed benchmark: 150 PDFs across 15 families, 140 unique byte hashes, immutable public
  signed/encrypted templates, constructor-assigned labels, per-case outcomes, source/template
  hashes, per-class metrics, confusion matrices and explicit unsupported-case accounting.
- Independent regression construction using literal PDF syntax, vector curves, annotations,
  rotations, restoration history, misleading EOF markers, transformed and unrelated textures,
  catalog/Info aliasing and resource-limit cases.
- GitHub Actions regression suite and 30-document benchmark smoke, with uploaded evidence.
  Development Streamlit transport limits; detailed unmet deployment gate in ASSUMPTIONS.md.

## Executed evidence

- `pytest -q`: **31 passed** (14 Phase 1 + 17 new tests), Python 3.12.
- `ruff check .`: passed; `pip check`: no broken requirements; compileall and `git diff --check`: passed.
- `python -m benchmarks.evaluate --output /tmp/signguard-phase2-full --check`: **150 cases**, no
  unexpected errors on the 130 supported alert cases. Raw evidence copied to `evaluation/`.
- `python -m benchmarks.evaluate --per-family 2 --output /tmp/signguard-phase2-ci-smoke --check`:
  30-case smoke completed successfully with all controlled integrity/reuse positives and negative controls.
- Full corpus generation repeated into two independent directories: manifests and hashes identical;
  at least 100 unique documents asserted (actual 140). Ten indistinguishable signature/forgery pairs
  are intentional, explicitly unsupported, and included in all-case metrics.
- `python scripts/generate_samples.py`: four Phase 1 samples regenerated successfully.
- CLI with `/tmp/signguard-phase2-audit.jsonl`: JSON/audit smoke completed.
- Checked-in evaluation source hashes match current production/benchmark source files.

## Measured failures and limitations

Supported alert population (130): TP=50, TN=70, FP=10, FN=0; accuracy=92.31%, precision=83.33%,
recall=100%, F1=90.91%. All cases (150, including unsupported): accuracy=86.67%, precision=83.33%,
recall=83.33%, F1=83.33%; TP=50, TN=80, FP=10, FN=10. The ten encrypted errors are expected
unsupported inputs, not successful negative analyses. Ten single reused signatures without reference
or history produce no alert and are false negatives in the all-case view.

The ten alert false positives are legitimate repeated logos. Broad class accuracy is 80%, macro F1
79.05%; logo images are overcalled under the compatible Phase 1 image-presence label. Localization
has 40 TP, 30 FP and 10 FN (57.14% precision, 80% recall); faint ink is missed and logos overproposed.
No benchmark-specific threshold adjustments were made to hide these failures.

A wrong PyMuPDF incremental-save keyword was caught during benchmark execution and corrected to
the supported incremental `save` API. Alpha handling, metadata alias safety and richer history
attribution were implemented and checked with independent invariants. Tests/benchmark currently pass.

This remains a synthetic engineering evaluation, not real-world signature-identity validation or
complete coverage of shadow attacks. Generic pixel-level copy-move segmentation, trustworthy identity
recognition, cross-renderer validation, public hosting, worker isolation and authentication remain
incomplete or outside this implementation. See RESULTS.md and ASSUMPTIONS.md for exact scope.

## GitHub verification

Published branch: `feature/phase2-forensic-evaluation`.
Pull request: https://github.com/Saisathwik045/signguard/pull/2
The Phase 2 workflow is configured for Python 3.11 and 3.12; cloud execution above used Python 3.12.
GitHub Actions run [41338928885](https://github.com/Saisathwik045/signguard/actions/runs/41338928885)
passed on Python 3.11 and 3.12 for implementation/PDF-attribute commit `fe250fe`: dependency
installation, Ruff, all 31 tests, four sample PDFs, 30-case benchmark smoke and artifact uploads.
This status update changes documentation only; the final task report identifies the last checked run.

## Phase 2 exact file inventory

Created:

- `.gitattributes`
- `.streamlit/config.toml`
- `ASSUMPTIONS.md`
- `RESULTS.md`
- `benchmarks/__init__.py`
- `benchmarks/evaluate.py`
- `benchmarks/generate.py`
- `benchmarks/templates/SHA256SUMS.json`
- `benchmarks/templates/encrypted-00.pdf`
- `benchmarks/templates/encrypted-01.pdf`
- `benchmarks/templates/encrypted-02.pdf`
- `benchmarks/templates/encrypted-03.pdf`
- `benchmarks/templates/encrypted-04.pdf`
- `benchmarks/templates/encrypted-05.pdf`
- `benchmarks/templates/encrypted-06.pdf`
- `benchmarks/templates/encrypted-07.pdf`
- `benchmarks/templates/encrypted-08.pdf`
- `benchmarks/templates/encrypted-09.pdf`
- `benchmarks/templates/signed-00.pdf`
- `benchmarks/templates/signed-01.pdf`
- `benchmarks/templates/signed-02.pdf`
- `benchmarks/templates/signed-03.pdf`
- `benchmarks/templates/signed-04.pdf`
- `benchmarks/templates/signed-05.pdf`
- `benchmarks/templates/signed-06.pdf`
- `benchmarks/templates/signed-07.pdf`
- `benchmarks/templates/signed-08.pdf`
- `benchmarks/templates/signed-09.pdf`
- `evaluation/manifest.json`
- `evaluation/outcomes.json`
- `evaluation/summary.json`
- `scripts/create_benchmark_templates.py`
- `scripts/render_results.py`
- `src/signguard/localization.py`
- `tests/test_benchmark.py`
- `tests/test_phase2_independent.py`

Modified:

- `.github/workflows/tests.yml`
- `.gitignore`
- `PROJECT_STATUS.md`
- `README.md`
- `app.py`
- `src/signguard/images.py`
- `src/signguard/pdf.py`
- `src/signguard/pipeline.py`
- `tests/fixtures.py`

The ignored full generated corpus remains under `/tmp/signguard-phase2-full/pdfs`; Git stores only
immutable synthetic public templates and measurement JSON, not private keys or user uploads.

---

# Phase 1 historical record

Implemented and verified in the existing Codex Cloud environment on 2026-11-02 (Asia/Calcutta).
The original repository contained only `.gitignore` and an initial commit.

## Delivered

PDF classification; offline pyHanko integrity/trust/coverage/modification checks; xref-based
incremental revision counting; signed ByteRange coverage validation before historical rendering;
per-page visual change comparison; optional external baseline; ELA; ORB with RANSAC; explainable
evidence fusion; POSIX-locked hash-chain audit logging; CLI; Streamlit upload and JSON report UI;
GitHub Actions for Python 3.11/3.12 with synthetic PDF artifacts; pinned cloud dependency snapshot.

## Verification actually executed

- `pytest -q`: **14 passed**, Python 3.12.
- `ruff check .`: passed.
- `pip check`: no broken requirements.
- `python scripts/generate_samples.py`: generated unsigned.pdf, signed.pdf, shadow-update.pdf,
  and tampered.pdf in ignored `samples/`; ephemeral signing key was discarded.
- `signguard samples/unsigned.pdf --audit /tmp/signguard-smoke-audit.jsonl`: completed with JSON output.
- Python compileall completed for source, app, tests and sample generator.

Tests cover invalid inputs, unsigned/image-candidate classification, valid and explicitly trusted
signatures, untrusted certificates, signed revision rendering, visible incremental updates,
signed-byte tampering, unchanged/changed/added pages, ELA and ORB (including insufficient features),
end-to-end image evidence, audit mutation/truncation/refusal to append to corrupt logs, concurrent
audit writers, audited reports, and initial Streamlit rendering.

## Limits and remaining deployment work

GitHub Actions run 41337450218 passed on Python 3.11 and 3.12, including lint, tests,
sample generation and artifact uploads. Local Codex Cloud execution used Python 3.12. UI rendering
was exercised with Streamlit AppTest; no public deployment was performed. Visual comparisons
identify changes consistent with shadow attacks, not every attack family. Visual signatures
require supplied image crops; embedded images are candidates only. ELA/ORB are not a trained
forgery classifier or a biometric identity check. See README for rendering, trust, resource,
and audit anchoring limits. Public deployment requires authentication and worker resource isolation.

Published branch: `feature/signguard-analysis`. Pull request: https://github.com/Saisathwik045/signguard/pull/1

## Files created

- AGENTS.md
- README.md
- PROJECT_STATUS.md
- pyproject.toml
- requirements-cloud.txt
- app.py
- .github/workflows/tests.yml
- src/signguard/__init__.py
- src/signguard/pdf.py
- src/signguard/images.py
- src/signguard/pipeline.py
- src/signguard/audit.py
- src/signguard/cli.py
- tests/__init__.py
- tests/fixtures.py
- tests/test_signguard.py
- scripts/generate_samples.py

Modified `.gitignore` to exclude generated samples, the virtual environment and audit output.
