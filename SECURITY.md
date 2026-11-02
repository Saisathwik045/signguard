# Security model and verified controls

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
