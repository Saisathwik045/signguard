# Project status

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

The Actions matrix is configured; local cloud execution verified Python 3.12 only. UI rendering
was exercised with Streamlit AppTest; no public deployment was performed. Visual comparisons
identify changes consistent with shadow attacks, not every attack family. Visual signatures
require supplied image crops; embedded images are candidates only. ELA/ORB are not a trained
forgery classifier or a biometric identity check. See README for rendering, trust, resource,
and audit anchoring limits. Public deployment requires authentication and worker resource isolation.

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
