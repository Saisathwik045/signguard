# Project status — Phase 4

Started from merged main `24d12ac`; PR #3 was confirmed merged and its checks passed.
Feature branch: `feature/phase4-private-integration`. All execution is remote. No paid infrastructure,
public ingress or user-accessible preview URL was created.

## Delivered integration

- Authentication before upload controls, session-backed verdicts, worker-generated bounded PNG
  evidence and downloadable JSON/PDF reports, signed/current images, clear unsupported/error states.
- Private controller -> group-restricted Unix executor RPC -> disposable Docker worker. The controller
  has no Docker CLI/socket; requests cannot supply images, commands, environment or mounts. The host
  executor remains trusted/privileged. The UI has no privileged socket in the container architecture.
- Bounded concurrency, per-principal quotas, protocol validation, local audit receipts with report
  digest verification, and explicit denial rather than unsafe parsing fallback during service outage.
- Additional private-preview HTTP/WebSocket gateway with opaque HttpOnly sessions, logout/expiry
  revocation, protected raw uploads/media routes, internal assertions and preserved Streamlit XSRF.
  Production OIDC remains separate; the preview gateway is single-owner, not multi-tenant SSO.
- Real Chromium automation, screenshots, synthetic reports, audit chain, separate loopback scope
  evidence, all-container CI, OS scans, and a false-by-default evidence-backed release validator.
- Browser-only Codespaces preparation, host executor service/Compose definitions, and DEMO_GUIDE.md.

## Actual verification and defects found

The final authenticated-gateway remote loopback browser run passed 11 tests across signed, tampered, shadow-modified,
visual-only, unsigned, unsupported and oversized inputs, downloads, login/logout, quota/concurrency,
audit and outage handling. The gateway tests include direct anonymous/post-logout media denial. Cloud JUnit records 70 passing
non-browser tests (11 browser cases explicitly skipped in that command) and 11 passing browser cases
in the separate live stack run: 81 distinct tested cases. GitHub Actions verification is recorded
below and in the final task report.

The non-browser suite and additional gateway contracts were executed in cloud; all 60 prior tests
remain present. Final measured cloud results: 70 non-browser checks passed, plus 11 passing browser
checks (81 distinct cases). The browser run includes anonymous and post-logout direct download denial.
Implementation commit `711a2c4` passed all GitHub Actions checks: Cloud tests run 41413174218 and
Private staging integration run 41413174237. The latter built all three containers, passed all browser
cases, completed all OS scans and uploaded artifacts. Functional green status does NOT override the
separately blocked release admission. Documentation/evidence refresh follows those verified checks. Explicit resource tests still exercise Docker CPU/memory/network/read-only behavior.
The final suite counts are reported from JUnit, not inferred from static test collection.

Real integration defects fixed: internal-only network prevented published loopback routing; umask
made the executor directory owner-only; health forwarding dropped Streamlit's XSRF cookie; fixed host
upstream ports collided across test runs; result state disappeared on rerun/download. Image layering
was reduced after the cloud VFS disk filled. A descendant-kill test now waits a bounded two seconds
for asynchronous SIGKILL delivery instead of racing the scheduler. Slow-worker quota tests use an
explicit longer window and invalid-request admission, preserving deployed defaults.

## Codespace resumption verification — 2026-11-02

The resumed `feature/codespace-private-readiness` worktree was clean and had no active build, scan,
or test process. A cached worker image and earlier scan reports were present. The worker image was
rebuilt successfully as `signguard-worker:phase3` (manifest
`sha256:90fce9b77e24c327fe9977b6bba23f4e8de39dce2e92b56a20633ece2a5dcee2`), then scanned with the
workflow-pinned Trivy image. The raw current-image report is
`evaluation/phase4/os-scan-codespace-2026-11-02.json`: Debian 12.15 has 2 CRITICAL and 36 HIGH
findings, all without a published fixed version. These remain release blockers.

`ruff check .` passed. Bandit reported 0 MEDIUM/HIGH and 14 LOW findings; pip-audit found no known
vulnerabilities across 88 installed dependencies. The Docker isolation suite passed 17 tests, and
the full regression suite passed 67 tests with 14 expected skips and one Starlette deprecation
warning. No upload service was started and no ports were opened.

## Private preview verification — 2026-11-02

The deployable worker target was rebuilt without cache from `deploy/Dockerfile.worker` as
`signguard-worker:phase4`, image ID
`sha256:55db3e12417e6eff8015447632313acad08f2980ec59a911d010c30fbb0cdf69` (Debian 12.15).
Pinned Trivy 0.76.1's OS-only scan is preserved at
`evaluation/phase4/os-scan-worker-phase4-reassessment-2026-11-02.json`: 2 CRITICAL and 36 HIGH
findings, none with a published fix. This is the deployment blocker; a zero-critical/high
source-review result does not clear an OS-image gate.

The earlier all-package scan reported five Python HIGH findings from an inaccurate third-party
SBOM (for example, msgpack and setuptools are absent from this image, and its installed urllib3 is
2.8.0). Trivy warned that the SBOM can be inaccurate. `pip-audit --skip-editable -r
requirements-cloud.txt` found no known Python dependency vulnerabilities. Keep these results
distinct: OS CVEs block image admission; the SBOM's stale language entries are not treated as
installed packages or as evidence that the OS scan passed.

The worker image build passed. The Docker isolation suite passed 17 tests against the phase4 tag;
`ruff check .` passed and `pytest -q` passed 67 tests with 14 expected skips and one Starlette
deprecation warning. Five synthetic PDFs were generated at runtime and analyzed by phase4
disposable workers: genuine signed and unsigned were inconclusive, byte tampering was detected,
shadow reveal required review, and visual-only signature evidence remained inconclusive. Every
report included a generated PDF report and `docker_disposable`/network-isolation controls; no
worker containers remained. Gateway authentication-denial, raw-upload/media-route protection, and
worker report-generation tests passed. The full browser workflow (including authenticated report
downloads) was not run against this image.

On the final reassessment, the no-cache phase4 worker rebuild and UI/controller image builds passed.
The 17 Docker isolation tests passed again against the rebuilt worker; `ruff check .`, the 67-pass
regression suite (14 expected skips), Bandit (0 MEDIUM/HIGH), and the locked `pip-audit` scan also
passed. The OS admission script still reports 38 blockers (2 CRITICAL, 36 HIGH). The three images
were built but no service was started.

The full browser stack was not started: the restricted RPC executor/socket and required mount
configuration are absent, preview and broker secrets are unset, and the Codespaces ports API
returned HTTP 404 while `gh` is unauthenticated. No private port forward or browser URL could be
verified. `.devcontainer/devcontainer.json` requests notification-based forwarding and PRIVATE
visibility for 8501; 8080 remains ignored. This setting does not prove an active private route.
No listener or upload service was started.

Even a synthetic-only preview must meet the image gate: the upload UI does not technically restrict
input to generated fixtures. It also needs a verified GitHub-authenticated PRIVATE/TLS route, the
authenticated gateway on every upload/media/WebSocket/download path, bounded worker execution via
the restricted RPC boundary, and runtime-only credentials. Production-only gates remain the real
OIDC/tenant integration, a dedicated restricted/rootless executor host, distributed abuse quotas,
durable audit anchoring/retention, image provenance and deployment-domain operations.

The Codex browser run uses a non-root host UI process because the 7.9 GiB VFS disk cannot keep all
runtime images live together. That process shares the trusted test UID/filesystem and is NOT proof of
UI sandboxing. Controller and PDF workers are containers. CI uses containers for all tiers and must
pass before claiming full containerized UI separation. Test URLs are real loopback URLs, not public
or user-reachable private preview URLs. Only synthetic documents are used in screenshots/artifacts.

## Security release blockers — not waived

- Exact deployable Debian 12 worker OS scan: 36 HIGH and 2 CRITICAL findings. The earlier phase3
  Codespace report and phase4 all-package report are retained as historical evidence, not substitutes
  for the current phase4 OS-only scan. An evaluated Debian 13 alternative had 45 HIGH findings and
  was not adopted. No exceptions or hidden/ignored findings were used to enable ingress.
- Real cloud private routing/TLS and authenticated external browser probes are unavailable. Current
  proxy denies CONNECT to `api.github.com`; no verified Codespaces/hosting identity is bound. GitHub
  repository connector access works, but does not authorize Codespaces management or a paid host.
- Production OIDC/tenant integration, dedicated restricted/rootless executor-host authority, durable
  audit anchoring/retention and deployment-specific adversarial/load review remain open.
- Shared password preview login is single-owner only; Secure cookies are disabled ONLY in ephemeral
  HTTP loopback tests. Real staging requires TLS, Secure cookies and protection of all service paths.

## Evidence and reproducibility

`evaluation/phase4/` retains screenshots, representative JSON/PDF, JUnit, audit chain, report/isolation
summaries and OS findings. GitHub's authenticated-browser artifact additionally retains all downloads
and fixtures. `Private staging integration` builds/tests the complete stack; OS admission is reported
separately from functional success. No action publishes an ingress or provisions hosting.

The Phase 3 forensic detector still matches its pre-holdout source seal. No benchmark population,
label, score, or detector threshold was modified. See RESULTS.md, SECURITY.md, DEPLOYMENT.md and
DEMO_GUIDE.md for measured scope and the minimum browser-authorized cloud handoff.

---

# Phase 3 historical record

Started from merged main `481a939` on `feature/phase3-reliability-hardening`, in the existing
Codex Cloud environment. Verified on 2026-11-02 (Asia/Calcutta). No public deployment performed.

## Implemented

- Multiscale/local-contrast ink detection with connected-component and line-regularity evidence;
  regular graphics are separated with rejection reasons. Faint candidates are recovered without
  changing the ORB match thresholds. Identity explicitly abstains; visual reuse never proves forgery.
- Backward-compatible legacy class plus a separately named refined classification, schema v3,
  ByteRange bounds/order validation, explicit offline trust/revocation state, suspicious active-object
  findings, and optional bounded independent Poppler render/signature checks.
- 360-input reproducible split benchmark: development/regression/holdout, 120 each; 345 valid PDFs
  and 15 malformed PDF inputs; distinct template/base IDs and document hashes across splits. Detector
  source sealed before first holdout. Initial and post-security-upgrade holdout outcomes are separate.
- JSON, CSV, source/template/input hashes, sealed corpus ZIP, standalone PNG/SVG charts, execution
  timing and explicitly qualified native-inclusive RSS measurements. No external real-world dataset.
- One-request worker, closed bounded protocol, sanitized environment, process-group deadlines,
  OS rlimits, disposable Docker non-root/no-network/read-only/no-capability configuration, cgroup
  memory limits, and bounded concurrency/queue. UI production mode refuses subprocess fallback.
- Private broker, generic errors/content-free security events, service-token authentication,
  OIDC verified-email allowlist integration, prepared Compose/Docker definitions and build-only CI/CD.
- Pillow 13 and pip upgrades fixed the advisories discovered by dependency scanning. Runtime and
  development audit now reports no known vulnerabilities; Bandit has no medium/high findings.

## Tests and evidence actually executed

- **60 passed**, including Docker tests, in one Codex Cloud run (`SIGNGUARD_DOCKER_TESTS=1 pytest -q`).
  JUnit evidence: `evaluation/phase3/cloud-tests.xml`. This preserves all 31 previous tests.
- Non-Docker run: 58 passed, 2 explicitly skipped container tests; separate worker suite: 17 passed.
- Existing 150-input benchmark replay, all 360 expanded inputs, and post-upgrade revalidation ran.
  `ruff check .`, `pip check`, compileall and whitespace checks passed.
- Poppler independently accepted an untampered synthetic signature and detected byte tampering;
  page-count/first-page render comparison passed its diagnostic tolerance.
- Actual adversarial tests: OS CPU/address-space/output limits, wall timeout and descendant killing,
  temporary cleanup, credential stripping, busy-slot rejection, production fallback rejection,
  broker URL validation, Docker UID/read-only/network tests and a cgroup OOM allocation.
- All three images built in cloud. Worker analysis and UI/controller health succeeded with no
  public ports. Controller denied missing service credentials (403) and empty authorized input (413).
  Controller health used no Docker socket; full Compose/OIDC analysis routing is not yet verified.
  Image IDs and control/measurement/health evidence are in `evaluation/phase3/`.
- Building all images exhausted the 7.9 GiB cloud root disk. Removing only disposable images/cache
  recovered space. Source, templates, benchmark evidence and user work were preserved.

## Results and known failures

Unchanged Phase 2 replay: supported alert accuracy 92.31% → 100%; all-case accuracy 86.67% → 93.33%;
refined broad accuracy 80% → 93.33%; localization precision/recall 57.14%/80% → 100%/100% on the
known regression inputs. Labels and populations were not changed; broad class uses the explicit new
refined field while the original image-presence class is retained. This replay is not a holdout.

Expanded holdout (120 inputs): supported alerts 30 TP, 75 TN, 0 FP, 0 FN (105 supported inputs).
All-case accuracy 95.83%, precision 100%, recall 85.71%, F1 92.31%. Five ambiguous unauthorized-reuse
cases produce no alert; five encrypted and five malformed inputs error explicitly. Their negative
intent/no-alert coding is not successful analysis. Supported/all-case populations and errors are separate.

Holdout localization: 50 TP, 15 FP, 0 FN; precision 76.92%, recall 100%, F1 86.96%. Remaining false
proposals: five stamps, five scanned printed headers and five extra text regions on low-resolution
scans. Broad accuracy is 83.33% on all inputs. All split confusion matrices, unsupported/inconclusive
rates, per-class metrics and timing/RSS are retained. See RESULTS.md for exact measured evidence.

The first holdout used Pillow 12.3.0; advisory-driven upgrades required subsequent revalidation on
identical sealed bytes. Detector source still matches the original seal; no tuning followed holdout
results. Revalidation is not a second untouched holdout. Synthetic generation concepts remain shared;
this does not establish real-world handwriting identity or comprehensive shadow-attack accuracy.

## Deployment readiness and remaining work

**Not ready for unrestricted public upload deployment.** Tested worker limits are distinct from a
production security attestation. Still required: actual OIDC/provider/tenant/TLS testing, dedicated
restricted/rootless worker daemon authority, distributed/per-user quotas and staging/load tests,
OS/base-image CVE review, retention and audit-anchor policy, hosting/domain authorization and secrets.
The controller's Docker socket is privileged and must remain on a dedicated trusted boundary.

SECURITY.md distinguishes implemented/tested controls from documented gates. DEPLOYMENT.md supplies
cloud-only build, private architecture, secret templates, health checks and rollback requirements.
Published pull request: https://github.com/Saisathwik045/signguard/pull/3
GitHub Actions run 41399149839 passed on Python 3.11/3.12 and in the isolated-worker security job,
including dependency/static scans, Poppler checks, regression/benchmark smoke and container tests.
Later export/health-documentation changes and stricter smoke gating are checked in the final task report.
The exact changed-file inventory is in `evaluation/phase3/FILE_INVENTORY.txt`.

---

# Phase 2 historical record

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
