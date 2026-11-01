# SignGuard

Python tooling and a Streamlit interface for offline PDF signature and visual tampering triage.

## What it does

- Classifies PDFs as cryptographically signed, unsigned, or containing visual candidates (embedded images). An image is not automatically a signature; vector handwriting is not classified.
- Uses pyHanko to check CMS signatures, signed byte integrity, coverage, certificate trust, and modification policy. Certificate fetching is disabled. Library callers can supply ASN.1 certificate trust roots; the UI/CLI trust no certificates by default.
- Resolves incremental revisions through the PDF xref chain and renders each signed revision against the final document with PyMuPDF. Reports changed pixels per page and added/removed pages. A user-supplied baseline can also be compared.
- Computes JPEG error-level analysis (ELA) and ORB descriptor matches with RANSAC geometry on explicitly supplied signature crops.
- Fuses evidence into `tampering_detected` for cryptographic failures, `review_required` for visual differences or verification errors, and `inconclusive` otherwise. Raw evidence remains available in the JSON report.
- Offers an optional locked, fsynced SHA-256 audit chain through the Python API and CLI.

## Cloud execution

The project runs in Codex Cloud and GitHub Actions; no local installation is required.
In a cloud checkout, install with `python -m pip install -e '.[dev]'`.
Run `pytest -q`, `ruff check .`, and `python scripts/generate_samples.py`.
Start the web UI in that environment with `streamlit run app.py --server.address 0.0.0.0`.
Use `signguard samples/signed.pdf --audit audit.jsonl` for JSON output.
The Actions workflow tests Python 3.11 and 3.12 on Ubuntu and uploads generated sample PDFs.

## Python API

```python
from signguard import analyze_pdf
report = analyze_pdf(pdf_bytes, baseline=known_original_bytes,
                     signature_image=crop_bytes, reference_image=reference_bytes,
                     audit_path="audit.jsonl")
```

Inputs are limited to 25 MiB, 50 pages, and page dimensions of 2000 PDF points.
Images are limited to 16 megapixels. Encrypted PDFs are rejected. The UI keeps uploads
in memory and does not persist documents or append audit events automatically.

## Interpretation and limits

This is a research triage implementation, not a certified validator or handwriting identity model.
Incremental updates can be legitimate. Visual revision changes flag possible shadow attacks but
do not identify every shadow-attack technique; a hidden object that never changes rendering may
escape detection. Rendering uses one engine at 72 DPI and can miss tiny changes or renderer
inconsistencies. ELA depends on compression history and ORB similarity cannot prove authorship.
No calibrated forgery probability is claimed. Certificate revocation evidence may be unavailable
offline; mathematical validity and trust are reported separately. Invalid or unsupported inputs
can fail analysis explicitly rather than receiving a clean verdict.

The audit chain detects edited entries and broken links. Save its returned head in a separate
trusted system to detect truncation/replacement. It is not a signed or externally anchored ledger.
File locking uses POSIX `fcntl`, matching the Linux cloud target. Untrusted documents should be
processed in an isolated worker with external CPU/memory/time limits before public deployment;
the Streamlit app is a development interface, with no authentication or hosted deployment included.

Synthetic fixtures generate an ephemeral self-signed test identity and discard its private key.
Generated PDFs are ignored by Git and available as CI artifacts.
