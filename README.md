# SignGuard

Python and Streamlit tooling for offline PDF signature integrity and visual tampering triage.
Phase 3 extends the merged implementation with reliability and worker hardening; the upload application remains undeployed.

## Phase 3 additions

Multiscale contrast/connected-component localization recovers faint ink and records regular graphics
separately, reducing the measured Phase 2 logo false alerts. Reports add `refined_classification`,
explicit identity abstention, ByteRange bounds checks, offline trust states and active-object findings.
The legacy broad class and existing API remain available. Do not infer forgery solely from visual matches.

A 360-input split benchmark (including malformed/unsupported cases) preserves source seals, input
hashes, JSON/CSV outcomes and graphical measurements in `evaluation/phase3/`. First-look holdout
outcomes and post-security-upgrade revalidation are distinguished. [RESULTS.md](RESULTS.md) compares
with Phase 2 and reports remaining stamp/scanned-text false proposals. These are synthetic results.

The UI delegates to a bounded disposable worker. Local cloud development uses an explicitly labeled
rlimits-only subprocess; prepared production configuration requires the isolated private broker and
verified OIDC allowlist. [SECURITY.md](SECURITY.md) distinguishes tested controls from remaining gates;
[DEPLOYMENT.md](DEPLOYMENT.md) describes private cloud definitions, health checks, secrets and rollback.
No public deployment occurred.

## Functionality

- **Cryptography:** pyHanko checks CMS signatures, byte integrity, revision coverage, modification
  policy and separately configured certificate trust. Validation is offline; the UI/CLI trust no
  certificates by default. Library callers can supply ASN.1 trust roots.
- **Automatic localization:** page rendering, native-text masking and non-text ink grouping propose
  signature candidate boxes, including vector strokes, with explicit uncertainty. Users need not
  crop signatures. Optional manual crops and reference images remain supported.
- **Revision forensics:** actual xref sections establish revision boundaries, including PDFs with
  misleading EOF text in streams. Adjacent revisions and signed-versus-current states are compared
  at 144 DPI, with changed regions, text differences and annotation-free render attribution. A narrow
  metadata allowlist distinguishes routine `/Info` updates from content or unexplained changes.
  Intermediate changes remain visible even if the current appearance restores the original.
- **Shadow-attack triage:** changed appearance/text with still-valid signed bytes produces a possible
  shadow-attack finding. Controlled hidden-content reveal and overlay attacks are evaluated.
- **Image evidence:** multi-quality ELA reports residual/tile statistics without asserting forgery.
  ORB uses mutual ratio-filtered matches, RANSAC, minimum inliers, spatial coverage and geometric
  checks. Repeated candidate regions generate review findings; legitimate reuse remains possible.
- **Explainable fusion:** version 3 JSON contains typed finding codes, severities, evidence,
  explanations, completeness state, revision analysis and localization uncertainty. Verdicts remain
  `tampering_detected`, `review_required`, or `inconclusive`; none establishes signer authenticity.
- **Audit:** optional POSIX-locked, fsynced SHA-256 chain. Save its returned head in a separate trusted
  system to detect truncation. Documents and crops are not automatically persisted by the UI.

For Phase 1 API compatibility, broad `visual_candidate` classification can still mean image
presence alone. `classification_basis` identifies that case; it must not be interpreted as a
confirmed signature. Candidate localization and alert metrics are measured separately.

## Cloud execution and evaluation

All development and verification can run in Codex Cloud and GitHub Actions; no local execution is
required. Commands below refer to the cloud checkout:

```sh
python -m pip install 'pip>=26.2,<27'
python -m pip install -c requirements-cloud.txt -e '.[dev]'
pytest -q
ruff check .
python -m benchmarks.evaluate --output benchmark-output --check
python scripts/generate_samples.py
signguard samples/signed.pdf --audit audit.jsonl
```

Pillow 13 and upgraded pip address the advisories found during Phase 3 scanning.
`requirements-cloud.txt` captures the tested Python 3.12 environment. Python 3.11 resolves compatible
versions from project bounds. GitHub Actions runs both versions, all regression tests and a
30-document benchmark smoke evaluation, uploading measurements and synthetic PDFs as artifacts.
The full benchmark constructs 150 PDFs across 15 families (140 unique hashes), using seed 20261102
and immutable public signed/encrypted templates. Template keys were discarded. Do not run
`scripts/create_benchmark_templates.py` when reproducing: it intentionally creates a new corpus version.

See [RESULTS.md](RESULTS.md) for measured precision, recall, F1, confusion matrices, errors and
unsupported cases. Raw source-hashed evidence is in `evaluation/summary.json`, `outcomes.json`,
and `manifest.json`. `scripts/render_results.py` regenerates the historical Phase 2 report; use `scripts/render_phase3_results.py` with the documented cloud output directories for current measurements.
Corpus generation imports no detector and labels are assigned by construction. Independent tests
use literal PDF syntax, vector curves, annotations, restoration history and image transforms.
These remain synthetic/development checks, not an external handwriting dataset evaluation.

## Python API and development UI

```python
from signguard import analyze_pdf
report = analyze_pdf(pdf_bytes)  # localization and region-pair forensics run automatically
report = analyze_pdf(pdf_bytes, baseline=known_original_bytes,
                     reference_image=reference_bytes, audit_path="audit.jsonl")
```

The prior `signature_image=` manual crop argument is retained. Reports preserve existing fields and
add `revision_analysis`, `image_forensics.automatic`, `assessment.findings`, and `analysis_status`.
Automatic candidate coordinates use rotated page points. Reuse alerts do not prove forgery.

`streamlit run app.py --server.address 0.0.0.0` starts the **development** interface inside an isolated
cloud environment. This is not a deployment instruction or a public hosting configuration.
Input limits and unsupported PDFs raise errors; the UI displays them instead of issuing a clean verdict.
No public upload endpoint has been deployed.

## Limits and deployment requirements

ELA on rendered crops cannot recover source JPEG compression history. ORB cannot determine
who signed or whether a repeated signature was authorized. Native-text masking can hide signatures
encoded as text, while logos/scanned text can become candidates. Faint/tiny/vertical marks can be
missed. One renderer cannot cover every PDF shadow attack or parser discrepancy. Legitimate
metadata updates are allowlisted conservatively; other updates may need human review.

Internal limits include 25 MiB PDFs, 50 pages, 2000-point page dimensions, 16 revisions, 12 signatures,
16-megapixel images, bounded rendering work, 24 candidates and 100 pair comparisons. A reached
candidate/pair limit is explicitly marked partial. Limits cannot replace worker isolation.

[ASSUMPTIONS.md](ASSUMPTIONS.md) defines trust and benchmark assumptions, exact application limits,
and the **unmet public deployment gate**: disposable network-isolated workers, external CPU/memory/
wall-clock/storage limits, authenticated tenant access, quotas, retention controls and patching.
[PROJECT_STATUS.md](PROJECT_STATUS.md) records implementation and verification status.
