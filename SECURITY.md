# Security model and verified controls

## Phase 7 closeout verification boundary — 3 November 2026

The owner reports opening the private viewer; this is not independent automated SSO/session evidence.
Native metadata still permits exactly one owner, no groups and no external visitors. No deployment,
audience, cloud network or production-upload restriction was changed. Fresh local cloud browser tests
verify fail-closed report hash checks, stale-response selection isolation and exact JSON/PDF downloads
in addition to all five evidence displays. See [DEPLOYMENT_VERIFICATION.md](DEPLOYMENT_VERIFICATION.md).

The report SHA-256 values detect mismatches against the shipped catalogue; they do not authenticate
a maliciously replaced catalogue and report together. Native source/version provenance and protected
publication remain the deployment trust root. A matching local artifact is not proof of live bytes.
The existing anonymous HTTPS probes establish denial for the five tested routes, not all possible
paths, interactive sign-in, cookie attributes or logout invalidation. Current image security evidence
is retained from Phase 6 and successful CI; no fresh container scan is claimed for this docs/test change.

The upload-enabled service requires a separately qualified runtime and release evidence. Sites
static hosting must receive no parser, executor authority, upload route or PDF credentials. The next
phase requirements, threat boundaries and acceptance gates are in [NEXT_PHASE_PLAN.md](NEXT_PHASE_PLAN.md).
No production readiness or permission to enable untrusted ingress is implied by this closeout.

## Phase 7 private synthetic presentation boundary

Only an independent static presentation tier is published. It contains allowlisted synthetic report
JSON and static HTML/CSS/JS, no Python/parser code, arbitrary URL/path inputs, upload controls,
controller/executor socket, cloud credential, backend route or server-side write operation. Reports
and downloads are the actual Phase 6 worker outputs. SHA-256 verification fails closed on report
changes; rendering uses textContent, not report-supplied HTML. The page CSP allows same-origin
scripts/fetches and bundled data PNGs, denies forms/object embedding and loads no third-party assets.
Blob download URLs are revoked after use. There are no user temporary files to retain or delete.

Sites owns HTTPS/authentication/session handling before static asset access. The native policy is
owner-only (one owner, no groups/external visitors); no audience expansion or auth-bypass endpoint
was introduced. Platform service access returned by the native connection is used only for intended
QA and must be bound to the exact origin. It is never stored in source, browser JS, traces or screenshots.
An automated service-auth browser probe is not equivalent to an interactive owner SSO/cookie test.
The artifact has ten bounded static assets, five cases and no dynamic execution/resource queue;
provider resource/quota limits apply. This is not a claim of container/worker isolation on Sites.

Native publication succeeded, but Codex's network policy blocks HTTPS to the deployed hostname.
GitHub Actions independently verified real TLS and anonymous HTTP 403 denial at the homepage,
health, catalogue, JavaScript and report routes (run `41608991009`). The proof is retained in
`evaluation/phase7/anonymous-route-proof.json`. Session/cookie/header behavior, authorized health and
authenticated page/report access remain explicitly unverified. No proxy, policy or authentication
bypass was attempted. Protected hosted validation distinguishes service access from interactive SSO;
it was skipped without its protected identity binding. CI never falls back to public access or embeds a credential.

The existing Streamlit/Docker worker/controller architecture, resource limits and production gates
are unchanged. Production uploads remain externally disabled. A private view of synthetic snapshots
does not approve handling untrusted PDFs or substitute for a qualified production hosting assessment.

## Current Phase 6 image assessment — 3 November 2026

The fresh rebuilt baseline (Debian 12.15, image `3b48b51bce27`) still had 2 CRITICAL/36 HIGH OS
package records across 13 CVEs, with no Debian fixes listed. The full scan also identified setuptools
70.3.0 through pip's embedded build SBOM; it was absent from the actual installed distribution list.
Both the complete original scan and fresh installed-dependency audit are retained, without deletion
or alteration, in `evaluation/phase6/`. [CVE_ANALYSIS.md](evaluation/phase6/CVE_ANALYSIS.md) and its JSON
record each CVE, severity, affected versions, available fix, final package replacement/absence,
references, CVSS and qualified exploitability context. Runtime reachability was not independently
proved and was never used to waive a finding.

The selected runtime is official Ubuntu 26.04 LTS, pinned to
`sha256:6a06111c3b0a8600feadb270aec771dc239bf407b25625f93f44ab00e11f4d3c`, with vendor-maintained Python
3.14.4, Poppler and native libraries. Existing forensic Python versions are preserved. Chainguard
registry access was denied by cloud policy; Alpine lacks compatible PyMuPDF/OpenCV musl wheels;
Debian 12 and the previously evaluated Debian 13 retain known findings. Ubuntu was selected only
after scanning the completed forensic runtime and exercising its real imports/tools, not from a base scan.
Source-package backports/affectedness differ by vendor: numeric versions alone are not patch proof.

Exact final image: `sha256:99179020dfe24c921cbd75603df7cfae4afa490ae621c9d2cd54967cc3a84a28`.
Trivy 0.76.1, immutable scanner digest recorded in `scripts/scan_image.sh`, used DB v2 updated
2026-11-03 07:14 UTC. Fresh full scan: **0 CRITICAL, 0 HIGH, 56 MEDIUM, 11 LOW**; 171 OS packages
and language packages were analyzed. Installed Python audit: **20 distributions, 0 advisories**.
The image ID is matched to the scan, and all original high/critical CVEs must disappear entirely,
even if another distribution assigns them a lower severity. Complete evidence is in
`evaluation/phase6/final/`; candidate evidence is explicitly separate.

Pip's executable/module/vendor tree was genuinely uninstalled after installation in the same image
layer, resolving its unnecessary build-SBOM finding and reducing runtime tooling. Venv bootstrap
packages were purged; no compiler/make/pip remains. Installed-package metadata and all retained SBOMs
remain intact. Scanning covers OS and language packages with no severity/unfixed filtering or ignore
entries. CI now fails when any high/critical finding remains. The UI uses a separate dependency-build
stage so it does not require an installer in the final worker. Controller and synthetic viewer bases
were updated as well; their actual full-image scans remain mandatory in CI.

91 Codex regression/isolation tests passed; 12 browser cases run separately. Tests include genuine
signatures, shadow/revision changes, image forensics, actual Poppler/MuPDF execution in the final
network-isolated worker, cgroup/rlimit controls and cleanup. Native Python 3.14 joins the retained
3.11/3.12 CI matrix. Medium/low findings and all hosting/identity/kernel/audit limitations remain.
**Image admission is not deployment approval.** External ingress stays disabled until the independent
private TLS, identity, authorization, restricted executor and audit gates are verified.

## Historical security records (superseded image counts)

SignGuard parses hostile PDFs with native libraries. Forensic accuracy and safe execution are
separate properties. **No public deployment is approved by this work.**

## Current Codex recovery and synthetic viewer boundary

The exact final worker ID is recorded in `evaluation/cloud-recovery/final-image.json`; the fresh
`os-final-worker.json` metadata was checked against that ID. The unfiltered OS scan reports
**2 CRITICAL and 36 HIGH** findings despite available package upgrades. The separate installed-image
Python audit reports no known vulnerabilities. Old Codespaces/Phase 4 scans are provenance, not
proof of current security. No ignored/unfixed vulnerability filter clears the release gate.

`synthetic_demo.py` only selects five fixed package-resource IDs. It rejects all other IDs and
verifies PDF/report digests before presenting automatically generated isolated-worker results.
It never invokes a parser, worker, shell, network fetch or controller. Missing/inconsistent bundles
stop with an error. The demo image contains Streamlit and its dependencies plus the catalogue;
it omits forensic parser libraries, broker/executor modules and credentials. No upload, URL or path
widget exists. This reduces the demo's attack surface; it does not waive image or external-route gates.
The underlying Streamlit framework still serves HTTP/WebSockets and must be patched and protected
before any externally reachable deployment. Synthetic input provenance is not safe-hosting proof.

Generation is an administrator/CI operation on checked synthetic fixtures using a trusted image ID.
The displayed execution controls describe that generation run, not a live analysis at viewing time.
Reports do not invent controller audit receipts. Production upload authentication, restricted RPC,
resource limits and fail-closed behavior remain unchanged. Synthetic Compose binds cloud loopback
only and grants no daemon/socket access. No service has been exposed to untrusted users.

## Controls implemented and exercised in Codex Cloud

- One-request worker protocol with closed field names, strict base64 decoding, 25 MiB primary PDF,
  60 MiB combined decoded input, 82 MiB transport and 5 MiB report limits. No remote command,
  arbitrary audit path, filesystem path, or trust-root option is accepted by the worker protocol.
- Disposable Docker worker: UID/GID 65532, `--network=none`, read-only root, no bind mounts or
  credentials, dropped capabilities, no-new-privileges, 64 MiB noexec/nosuid temporary filesystem,
  1 GiB memory with no extra swap, one CPU quota, 30-second CPU ulimit and 32-task PID limit.
  Runtime tests verified non-root execution, read-only root, blocked external connection and CPU
  ulimit; an actual 2 GiB allocation was killed under the 1 GiB cgroup limit. PID exhaustion,
  seccomp bypass and kernel isolation have not been adversarially certified.
- Supervisor: minimal environment, no inherited cloud/proxy credentials, private mode-0700 temporary
  directory, CPU/address-space/file-size/open-file/core-dump limits, 60-second wall deadline,
  process-group killing and secure temporary-file cleanup. Tests exercised memory, CPU, output,
  wall-time, descendant termination, credential stripping and rejection when the single slot is busy.
- Local subprocess mode explicitly reports `rlimits_only`, with network/filesystem isolation false.
  It is a development fallback, never a production sandbox. Production configuration refuses it.
- Private controller uses constant-time service-token comparison, a single active analysis, backlog
  four, socket read deadlines, bounded input/output and no user-selectable image/command. Health
  is liveness only and does not attest that the worker daemon or identity provider is ready.
  The controller image built and passed local health plus missing-token/empty-input denial probes;
  end-to-end Compose routing with a restricted daemon and real identity provider remains untested.
- UI production gate requires Streamlit OIDC login, boolean `email_verified=true` and an explicit
  email allowlist. Broker credentials remain in UI/controller only, not workers. Identity-claim
  authorization is unit tested; actual OIDC login/logout and tenant integration remain unverified.
- UI errors are generic. Controller logs contain only event, random request ID and completion
  status; no document names, text, hashes, tokens, raw parser errors or report contents are logged.
  Broker redirects are disabled, URL schemes validated, and cleartext transport limited to the
  configured private controller/loopback. TLS is required across other trust boundaries.

## Dependency and static scanning

`evaluation/phase3/dependency-audit-before.json` records the scanner's Pillow 12.3.0 advisories.
Pillow was upgraded to 13.0.0; pip was also upgraded after its advisories were found. A subsequent
`pip-audit --skip-editable` scan of the installed environment reported no known vulnerabilities.
The full output is preserved in `dependency-audit-after.json`; this is a point-in-time advisory
check, not proof of absence of vulnerabilities. Python dependency constraints and CI were updated.

Bandit reports no medium/high findings. Low-severity subprocess/exec findings remain reviewed in
`bandit-all.json`: command lists use no shell, input fields cannot become executables, Poppler
arguments are fixed except privately generated paths, and the Docker image/name are controlled
by trusted deployment code. The launcher intentionally executes a trusted command after setting
rlimits. These primitives remain privileged and require review whenever command construction changes.
An exact phase4 worker OS scan is recorded below. A penetration test and software supply-chain
attestation remain incomplete.

## Mandatory production gates still open

1. Provision a dedicated, patched worker host/rootless daemon or restricted execution service.
   The prepared controller currently mounts a Docker API socket, which is a privileged trust
   boundary even when mounted read-only. Do not mount it into the UI or expose the controller.
   Restrict controller authority and isolate its host from application data/production credentials.
2. Complete actual OIDC provider registration, HTTPS redirect/cookie validation, allowlist/tenant
   policy, logout/revocation tests and authenticated reverse-proxy rate/size/time limits.
3. Add per-user/tenant quotas, distributed concurrency limits if scaled, abuse monitoring and
   adversarial load tests. The implemented one-process slot/backlog are not distributed limits.
4. Review default seccomp/kernel/cgroup enforcement, OS image CVEs, signed image provenance,
   deployment digests and external storage permissions. Cgroup CPU quota limits scheduling;
   wall/CPU deadlines and memory controls remain separately necessary.
5. Define encrypted retention/deletion rules for any future persistence and external audit anchors.
   Current workers retain no uploaded documents after completion. Explicit report downloads can
   contain sensitive evidence and are returned only within the request's authenticated session.

Report security problems privately to the repository owner through GitHub's private vulnerability
reporting if enabled. Do not publish real signed documents or credential material in issues.

## Phase 4 verified boundary and release status

The complete browser path now exercises the restricted Unix executor RPC; the controller has no
Docker socket or Docker CLI, and the UI has neither privileged socket. RPC accepts only the four
bounded analysis byte fields and rejects operation/image/command injection before any worker starts.
The host executor is still privileged and requires a dedicated restricted daemon/host in deployment.
A restrictive umask initially made its group directory inaccessible; explicit directory/socket modes
fixed this integration defect and are exercised by actual controller-to-executor browser tests.

Uploads are unavailable before application authentication. Preview credentials use salted scrypt,
constant-time comparison, bounded attempts and a 15-minute session. Controller concurrency is one
active job, four connection threads, backlog four, and ten authenticated-principal attempts/minute.
These are single-instance controls, not distributed quotas. Browser tests exercise incorrect login,
logout, oversized uploads, unsupported inputs, concurrent requests, quotas and fail-closed outage.

Generated PNG/PDF evidence is produced inside the worker, bounded by the JSON/media limits and returned
in-memory to the authenticated session. JSON/PDF downloads persist across reruns. The controller
appends a local hash-chain receipt without retaining source uploads or logging document contents.
External audit anchoring, durable retention policy and production identity integration remain gates.

An actual Trivy OS scan was added. Initial scanner startup failures (cache permissions and its own
1 GiB memory cap) were not treated as successful scans. The fresh, no-cache phase4 Debian 12.15
worker scan found 2 CRITICAL and 36 HIGH OS findings without published fixes. See
`evaluation/phase4/os-scan-worker-phase4-reassessment-2026-11-02.json`. The separate locked
Python dependency audit found no known vulnerabilities; a Trivy all-package pass also read stale
third-party SBOM language entries that do not match installed packages and is not used to override
the OS gate. Release remains blocked. This is separate from the PDF workers' unchanged limits.
No claim of safe external deployment follows from successful functional tests or screenshots.

The Codex loopback browser run used a host UI process sharing the trusted test UID/filesystem;
it is not proof that the UI itself is sandboxed. Its PDF workers were isolated and no external
route was opened. The CI all-container path must pass before claiming UI filesystem separation.
Application widget authorization alone does not protect every Streamlit HTTP endpoint: an authenticated
private gateway must protect uploads, WebSockets and downloads before any untrusted-user ingress.

Quota integration canaries use a 600-second window so slow VFS worker startups do not roll the window
during the test; the deployed default remains ten attempts per 60 seconds. Invalid authenticated
requests also consume quota and are used to check admission without timing-dependent extra workers.
The regression test separately checks default-window expiry. No forensic thresholds were changed.

Static-scan review: Bandit B103 is explicitly scoped on the Unix socket's `0660` mode. Group write
is required for the dedicated controller group to connect; the parent is `0750`, world access is
absent, and production group membership is restricted. Changing it to owner-only breaks the tested
UID boundary. This is a documented context-specific permission finding, not a global scanner skip
or an OS-vulnerability waiver. The unsuppressed finding is retained in reviewed scan evidence.
