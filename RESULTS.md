# Results — preserved forensic evaluation and cloud integration

## Phase 9 infrastructure qualification — 3 November 2026

Started from merged Phase 8 main `b668a70`; no benchmark tuning or synthetic Site changes. Added AWS plan-only infrastructure tests, single-owner GitHub OAuth2/PKCE/session tests, persistent quota tests, rootless-daemon qualification and a real container TLS denial test. No AWS account credentials or spending authorization were available; no apply, public IP, real OAuth session, public certificate, actual AWS worker or rollback was tested.

A first local regression run had 131 passes, 21 explicit skips and one Poppler timeout: the managed filesystem did not permit its default Fontconfig cache. Verification is rerun with `XDG_CACHE_HOME` under `/tmp`, without relaxing PDF timeout/isolation. An earlier run before the added opt-in TLS test passed 132 tests with 20 explicit skips. With a writable temporary Fontconfig cache, the complete local suite passed **133 passed, 0 failed, 21 explicitly skipped** (Docker/browser jobs run separately), with two upstream deprecation warnings. New AWS/authentication contracts include 25 tests, including the hosted-smoke input-validation case. Actual rootless daemon qualification passed in [run 41690028592](https://github.com/Saisathwik045/signguard/actions/runs/41690028592); evidence is retained under `evaluation/phase9/rootless-evidence.json`. Final CI evidence is recorded separately; counts are not pooled across matrix repeats.

Two additional proxy candidates were rejected after **unsuppressed scans found one critical and 16 high findings combined** (including an unpatched Go JOSE finding). Full raw evidence is retained in `evaluation/phase9/rejected-proxies/`. Those images were never deployed. The final preparation reuses the existing scanned Python UI image for Authlib authentication and direct TLS instead of introducing those services; existing worker/controller/OS scan gates remain mandatory. Candidate findings are not final-image scan results.

[Container integration run 41690028541](https://github.com/Saisathwik045/signguard/actions/runs/41690028541) passed the 13 existing live-analysis browser cases and the new TLS gateway case. The latter negotiated TLS 1.3 with an explicitly trusted ephemeral CA and denied anonymous/spoofed HTTP requests; it did not execute actual GitHub login or contact an AWS endpoint. Fresh scans of the three actual CI service images reported **0 critical, 0 high** findings (151 medium/26 low combined); the worker Python dependency audit reported zero known findings. These are CI image results, not a scan of an unprovisioned AWS host. Curated JSON/JUnit evidence is retained under `evaluation/phase9/container-integration/`; raw scans/screenshots are in that run's authenticated-browser-evidence artifact.

See [AWS verification checklist](deploy/aws/VERIFICATION.md), [operations and rollback runbook](deploy/aws/README.md) and [hosting comparison](HOSTING_COMPARISON.md). Infrastructure mock tests, local gateway mocks and cloud-loopback browser checks do not satisfy actual AWS release gates. Production/live-upload readiness remains **BLOCKED**.

## Phase 8 engineering evaluation — 3 November 2026

This phase measures integration/security behavior, not new classification accuracy. Prior benchmark
scores and forensic thresholds remain unchanged. Inconclusive means no authenticity determination.

| Evidence | Observed result | Scope |
| --- | --- | --- |
| Codex regression | 108 passed / 0 failed / 20 explicit skips | Existing and new unit/security/forensic tests; Docker and separately opted-in browsers skipped |
| Focused Codex checks | 22 passed | Four private-viewer contracts, two artifact browser scenarios, 16 initial admission/audit cases; overlaps regression |
| Codex synthetic Streamlit browser | 1 passed | Five examples and report downloads in a cloud process; not container/hosted isolation |
| Actions live stack 41667811959 | 13 passed / 0 failed / 0 skipped | Actual container UI/controller, restricted RPC executor and disposable workers; cloud loopback HTTP |
| Live evidence validation | 7 JSON outcomes, 5 PDF pairs, 26 chained audit events | Digest, request/input identity, image ID and receipt linkage verified |
| Fresh CI scans, same live-stack run | Worker/UI/controller each 0 CRITICAL, 0 HIGH | Full unfiltered scan; MEDIUM/LOW remain |
| Actual hosted live upload | Not deployed | No private hosting/TLS/OIDC/executor qualification available |

The verified worker in that implementation live-stack run was
`sha256:d91db7534d7763daecc25e5532628d7c028362edf2b415de39bdace21045d6f9`.
Its full scan reports 56 MEDIUM/11 LOW; UI 56/11; controller 39/4. The combined 151 MEDIUM/26 LOW
counts across three images are not a per-worker count. Complete scan JSON and exact identifiers
are retained in the CI artifact and curated evidence. This is fresh Phase 8 evidence, not reused Phase 6
scan approval. Final-head workflow conclusions are recorded in the PR; later builds require their own
identity-bound scans. Installed worker dependencies are independently audited in the staging workflow.

The implementation head `9e9392d` passed all four workflows: Cloud tests `41667811761`, staging
`41667811959`, synthetic demo `41667811731` and private viewer `41667811758`. The exact browser worker's
20 installed Python distributions have **0 advisories**. The isolated-worker suite passed **25/0/0**,
including actual cgroup OOM confirmation. The test-case union across completed suites is **128 distinct
passing cases** (not the sum of overlapping counts); `evaluation/phase8/test-coverage.json` lists them.
Codex's single regression command still explicitly reports 20 skipped opt-in cases, covered by separate
cloud jobs/scenarios. Nineteen actual live-browser screenshots are retained, including six individually
captured forensic images. SHA-256 manifests, raw service scans, installed inventory/audit, JUnit,
seven JSON reports and audit chain are in `evaluation/phase8/`. Hosted validation remains unverified.

Coverage includes genuine signed (inconclusive/untrusted identity), tampered bytes (tampering detected),
shadow reveal (review required), visual candidate and unsigned (inconclusive), encrypted/malformed
(unsupported), renamed non-PDF and oversized rejection, unauthorized access, direct-media/logout
denial, concurrent/bounded quota requests, audit integrity and worker-broker outage without fallback.

Failed/incomplete attempts are retained honestly: the preliminary Codex live test had 1 pass/1 failure
when its 7.9 GiB VFS disk filled; local Docker probes had 23 pass/2 failures under the same resource
pressure and do not establish isolation/memory enforcement. One overlapping preliminary regression
was interrupted. The initial separate synthetic-container workflow timed out before its selector
appeared; a subsequent run also failed, leading to explicit bounded widget readiness and browser failure
capture before teardown. The static hosted viewer was never changed. Both the synthetic-container workflow and all other
workflows passed on implementation head `9e9392d`; the earlier failures remain historical failures.
One existing Starlette test-client warning remains.

No live-hosted TLS, production OIDC/session/tenant validation, rootless/dedicated executor qualification,
distributed quotas, durable audit anchoring or rollback rehearsal is claimed. The tested single-owner
preview gateway and hash-chain journal are useful integration evidence, not production readiness.

## Phase 6 fresh image verification — 3 November 2026

| Measure | Fresh Debian baseline | Actual final Ubuntu worker |
| --- | ---: | ---: |
| OS CRITICAL | 2 | 0 |
| OS HIGH | 36 | 0 |
| Full-scan language HIGH | 1 (pip build-SBOM setuptools) | 0 |
| OS MEDIUM / LOW | 117 / 105 | 56 / 11 |
| Installed Python dependency advisories | 0 | 0 |

Final image: `sha256:99179020dfe24c921cbd75603df7cfae4afa490ae621c9d2cd54967cc3a84a28`.
Scanner: Trivy 0.76.1, DB v2 updated 2026-11-03 07:14 UTC. Full original/candidate/final scans,
image identity, installed package inventory and per-CVE analysis are retained in `evaluation/phase6/`.
No OS/language scope exclusions, severity downgrades, unfixed filters, SBOM editing or exceptions
were used. Pip was removed as an actual runtime package, including its embedded vendor tree.
The verifier rejects a scan of a different image or any original high/critical CVE still present.

Final-image regression/isolation run: **91 passed, 0 failed, 12 explicit browser cases skipped**,
one existing Starlette deprecation warning. This includes the actual isolated Poppler/MuPDF probe.
The regenerated five-example synthetic browser scenario passed in 24.75 seconds, using cloud Chromium
with actual evidence PNG decoding and report downloads. The viewer in this Codex run is a cloud
process; Actions separately verifies container-hosted synthetic and authenticated upload browsers.
Python 3.14 compatibility is added to the existing CI matrix. Detector code and prior benchmark
results are unchanged; these are security/integration results, not a new accuracy evaluation.

Image gate: **PASS**. Production deployment: **BLOCKED** pending private TLS/routing, identity and
authorization, restricted executor authority, durable audit and operational readiness. No external URL exists.

## Historical results

## Codex recovery verification — 2026-11-02 UTC

No detector or benchmark-score tuning was performed. All four Codespaces commits through `2a89352`
were integrated from the published branch onto merged main `1afd853`. Fresh evidence is in
`evaluation/cloud-recovery/`; the recovered Codespaces scan files remain explicitly historical.

The final worker `sha256:976add9a3c886c519c2333f248d300eb27bd0961ea0f14201038055502dc8437`
was built in Codex Cloud with available OS updates and freshly scanned using pinned Trivy 0.76.1:
**2 CRITICAL, 36 HIGH, 116 MEDIUM, 105 LOW, 8 UNKNOWN** OS package findings. The scan's image ID
matches the tested image. No findings were suppressed; OS release admission is blocked.
The audit of packages actually installed in this worker found no known Python vulnerabilities.

Regression and enabled Docker controls: **84 passed, 12 explicit browser cases skipped**, with one
existing Starlette TestClient deprecation warning. Thirteen new demo checks cover all five actual
report classifications, digest/path rejection, PDF readability and no analysis-backend invocation.
The Docker checks also verify memory/PID/CPU configuration, tmpfs bounds, zero effective capabilities,
no-new-privileges and cleanup after a real worker failure. Real Chromium tests are separate; their
JUnit and screenshot artifacts distinguish cloud-process and container-hosted scope.
The Codex demo browser scenario passed in 14.63 seconds: five selections, ten actual report downloads,
decoded evidence images, no file inputs and five reviewed screenshots. Its viewer ran as a cloud
process; the full container browser scenario is assigned to Actions. A separate real demo-container
probe validated all bundles and absence of parser/backend modules. Cloud VFS disk exhaustion and
slow-start cleanup races were not counted as passes; the harness and cache usage were corrected.

The five synthetic demo examples produce the same verdicts listed in DEMO_GUIDE.md. They are
curated integration examples, not independent statistical evaluation or improved accuracy claims.
The viewer serves automatically generated snapshots and has no upload/URL/path interface.
No external URL, TLS route or hosted release is claimed by these tests.

Implementation commit `dfcba8b` also passed GitHub Actions runs
[41495818019](https://github.com/Saisathwik045/signguard/actions/runs/41495818019) (Python 3.11/3.12,
benchmark smoke, isolated-worker/static/dependency checks),
[41495817821](https://github.com/Saisathwik045/signguard/actions/runs/41495817821) (11 authenticated
container-stack browser tests in 58.17 seconds and all three image scans), and
[41495817951](https://github.com/Saisathwik045/signguard/actions/runs/41495817951) (31 focused checks,
one five-example **container-hosted** browser test in 5.95 seconds, worker/viewer scans and installed
dependency audit). Across overlapping suites, **96 distinct tests passed**. Fresh scans still block
admission: worker+viewer combined 4 CRITICAL/72 HIGH; worker+production UI+controller combined
6 CRITICAL/108 HIGH. These are aggregate image-package findings, not unique CVEs or the single
Codex worker count above. Functional workflow success is not security release approval.

## Historical Phase 3 results

Measured in Codex Cloud on 2026-11-02 (Asia/Calcutta).

## Direct replay of unchanged Phase 2 inputs

The labels and supported/all-case populations are unchanged. The 150-input replay is a regression
population already inspected during development, not a holdout. Broad classification now uses
the explicitly named `refined_classification`; the legacy image-presence field is retained.

| Metric | Phase 2 | Phase 3 replay |
| --- | ---: | ---: |
| Supported alert accuracy | 92.31% | 100.00% |
| All-case alert accuracy | 86.67% | 93.33% |
| Broad classification accuracy | 80.00% | 93.33% |
| Localization precision | 57.14% | 100.00% |
| Localization recall | 80.00% | 100.00% |
| Localization F1 | 66.67% | 100.00% |

The ten logo alerts and thirty false proposals from Phase 2 are eliminated on that same corpus;
the ten faint regions are recovered, and all ten controlled copied-signature cases still alert.
Ten single unauthorized-reuse cases remain visually ambiguous and produce no alert. Ten encrypted
PDFs remain unsupported. Unsupported cases were not relabeled or removed.

## Expanded split evaluation

360 inputs (345 valid synthetic PDFs plus 15 deliberately malformed PDF inputs), three splits
of 120 inputs, 24 families, and five variants per family. Template IDs and PDF hashes are disjoint
across splits. Within-split visual/unauthorized-intent ambiguity is deliberately retained.
Source PDFs/layout IDs differ across splits; generator families and attack concepts are shared.
This is a separate synthetic holdout, not an independent external dataset or field-accuracy estimate.

| Split | Supported N | Accuracy | Precision | Recall | F1 | FPR | FNR | All-case accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| development | 105 | 100.00% | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 95.83% |
| regression | 105 | 100.00% | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 95.83% |
| holdout | 105 | 100.00% | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 95.83% |

| Split | Localization TP/FP/FN | Precision | Recall | F1 | Broad class accuracy | Unsupported | Inconclusive |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| development | 50/15/0 | 76.92% | 100.00% | 86.96% | 83.33% | 12.50% | 66.67% |
| regression | 50/15/0 | 76.92% | 100.00% | 86.96% | 83.33% | 12.50% | 66.67% |
| holdout | 50/15/0 | 76.92% | 100.00% | 86.96% | 83.33% | 12.50% | 66.67% |

The holdout has 15 false proposals: five stamps, five scanned printed headers, and five extra
text-like regions on low-resolution scans. These remain counted as false proposals. Supported
alert false positives/negatives are zero in this synthetic holdout, with 30 TP and 75 TN. On all
120 inputs, five ambiguous reuse cases count as FN; ten malformed/encrypted negative-intent cases
error explicitly and are coded no-alert, not successful negative analyses. All-case recall is
85.71%; all-case F1 is 92.31%.
No unexpected supported-case exceptions occurred. Identity/authorization decisions explicitly abstain.

Full binary and broad-class confusion matrices and per-class precision/recall/F1 are in the split
summary JSON. Per-case outcomes, errors, ROI boxes, timings and classifications are in JSON and CSV.

## Freeze and security-upgrade chronology

The four detector source files were sealed before holdout results were opened; no detector
thresholds or rules were changed after seeing holdout results. The initial holdout ran with
Pillow 12.3.0. Dependency scanning then required Pillow 13.0.0 and pip upgrades. Initial holdout
outcomes are preserved separately, and final results are post-upgrade revalidation of those same
sealed PDF bytes. Revalidation is not another untouched holdout. Corpus ZIP and seal permit exact
input reproduction even if encoding libraries change. No external dataset was acquired.

## Timing and memory

| Split | Total analysis seconds | Median seconds | P95 seconds | Process high-water RSS MiB |
| --- | ---: | ---: | ---: | ---: |
| development | 10.745 | 0.0346 | 0.2582 | 146.61 |
| regression | 10.983 | 0.0377 | 0.2731 | 146.64 |
| holdout | 10.336 | 0.0370 | 0.2562 | 146.76 |

Timings exclude PDF generation and worker/container cold start. RSS is cumulative process high-water
RSS including native libraries, not isolated per-input peaks. `worker-controls.json` separately
records a disposable worker's measured analysis time and process peak RSS. Values depend on hardware.

![Synthetic benchmark comparison](evaluation/phase3/comparison.png)

## Cloud reproduction

```sh
python -m pip install -c requirements-cloud.txt -e '.[dev]'
python -m zipfile -e evaluation/phase3/corpus.zip phase3-output
python -m benchmarks.phase3 --output phase3-output --split holdout
pytest -q
```

For a newly generated corpus, choose a new output directory and run `--seal` before any `--split`.
Do not run `--create-templates` during reproduction: it creates new randomized signing/encryption
templates and defines a new corpus version. Public synthetic templates contain no private keys.
Runtime versions are stored in `evaluation/phase3/environment.json`. This evaluation is not a
certificate of safety, comprehensive attack coverage, or evidence of human handwriting identity.

## Phase 4 integration evidence (no benchmark retuning)

The Phase 3 detector fingerprint still matches its pre-holdout seal. No scoring population, threshold
or benchmark result was changed for Phase 4. This phase measures integration rather than accuracy.

A real remote Chromium run passed 11 end-to-end checks: anonymous/invalid login denial; signed,
byte-tampered, shadow-revealed, visual-only and unsigned uploads; evidence images; JSON/PDF downloads;
unsupported input; oversized upload rejection; logout; concurrent/quota handling; audit chain; and
broker-outage fail-closed behavior. Eleven screenshots and report artifacts were captured.

Codex used a non-root UI process due to its VFS disk limit, plus a containerized controller and
network-isolated disposable workers. The CI browser job uses all three containerized tiers. Its final
observed result is recorded in PROJECT_STATUS.md/the task report. The tested cloud loopback URL is not
a live user-accessible preview, and external OIDC/TLS/private forwarding remain unverified.

The first integration attempts found real routing and Unix-socket group-permission defects; these
were fixed before the successful run. Successful reports include verified digest/audit receipts,
worker isolation controls and a signed/current evidence pair for the shadow case. PDF downloads were
reopened and checked; no PDF report is offered when the analysis fails. Raw evidence is retained in
`evaluation/phase4/` and GitHub Actions artifacts. The OS scan is a separate unresolved release gate.

Final implementation verification: 70 non-browser tests and 11 remote gateway browser tests passed.
GitHub Actions run 41413174237 passed the full all-container UI/controller/executor/worker flow,
including direct anonymous/post-logout download denial, screenshots, downloads and OS scan collection.
Cloud tests run 41413174218 passed both Python versions and the isolated-worker/static/dependency job.
OS release admission remained blocked despite successful functional CI. The private live URL is absent.
