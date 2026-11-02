# Phase 3 assumptions and remaining limits

The original Phase 2 assumptions are retained below as history. Current details and verified versus
unverified security controls are in SECURITY.md and DEPLOYMENT.md.

- Multiscale/local-contrast ink proposals and connected-component/line regularity reduce the known
  repeated-logo and faint-signature failures, but cannot reliably distinguish all stamps, scanned
  text, diagrams, handwriting-like logos or very faint marks. Rejected regular graphics are retained
  in JSON with reasons. No heuristic score is a calibrated signature probability.
- The legacy `classification` field remains compatible; `refined_classification` removes image-only
  inference from the new broad-class metric. Metric populations and ground truth are unchanged.
- Identity always abstains and authorization remains inconclusive from visual matching. Similar
  legitimate signatures cannot be declared unauthorized forgeries without external provenance.
- ByteRange ordering/bounds, pyHanko coverage/CMS checks and explicit offline trust states are separate.
  Revocation is not established from absent offline evidence. Active-object modifications, intermediate
  revisions, page/annotation differences and narrow metadata-only updates have separate findings.
  Poppler is an optional independent diagnostic, not a second root of trust; first-page rendering is
  approximate and not full cross-renderer attack coverage.
- The 360-input evaluation separates base/template IDs and document hashes across development,
  regression and synthetic holdout. Generator logic and attack concepts are still shared. No external
  legally validated real-signature dataset was obtained. Results must not be marketed as field accuracy.
- Detector source was frozen before the first holdout. A subsequent security-driven Pillow upgrade
  required revalidation on the same preserved inputs. The initial outcomes are retained; a second run
  on those inputs is not a new untouched holdout. No labels/populations/thresholds were changed to hide errors.
- Unsupported/malformed inputs and no-evidence/ambiguous cases remain explicitly reported. In all-case
  metrics, errors are coded no-alert: this can count a negative-intent unsupported input as TN, which
  is not a successful analysis. Both error rates and supported/all-case denominators are shown.
- All prior application limits remain; modified-object inspection is additionally bounded at 4096
  refs/revision and 64 reported object types. EOF reconstruction searches a bounded 64 KiB after a
  parsed xref section. Resource budgets can make otherwise valid inputs unsupported.
- Disposable Docker controls were exercised, including cgroup memory exhaustion. The subprocess mode
  has only rlimits and is not isolation. Actual OIDC/TLS/tenant enforcement, restricted production
  daemon authority, OS-image scanning and adversarial deployment load tests remain unverified.

---

# Phase 2 historical assumptions

## Evidence semantics

- The input is an untrusted PDF. Signature validity, certificate trust, modification policy,
  visual similarity and authorization are distinct questions. `inconclusive` never certifies a genuine document.
- Offline pyHanko validation uses only supplied trust roots and available evidence. The UI and
  CLI do not configure trust roots. Expired/revoked/untrusted identities cannot be resolved by image analysis.
- Automatic localization masks native PDF text and groups remaining ink. Every proposal is an
  **unverified candidate**, not a confidence-calibrated signature. Photos, logos, scanned text,
  charts and stamps can trigger proposals. Faint, tiny, vertical, native-text or heavily overlapping
  signatures may be missed. Candidate coordinates are in rotated page points, starting at the top left.
- Phase 1 broad classification is preserved: any embedded image can produce `visual_candidate`.
  `classification_basis` distinguishes image presence from localized ink. The benchmark penalizes
  logo misclassification rather than relabeling logos as true signatures.
- ELA depends on compression history. Multi-quality residuals and tile statistics are descriptive
  only; PDF rendering destroys the original compression history. Automatic crops report ELA as
  `not_applicable_to_original_compression` and never use it to assert tampering.
- ORB requires sufficient mutual matches, inlier support, spatial spread and plausible homography.
  It flags repeated visual regions; it cannot establish identity, consent or authorization. Logos
  and legitimate reused signatures remain false-positive risks. Low-texture strokes, small regions,
  severe transforms and recompression can yield false negatives. This is region-to-region reuse
  detection, not an exhaustive pixel-level copy-move detector for arbitrary photographs.
- A supplied reference crop is compared to automatically located candidates and retained as raw
  similarity evidence. A match to an authorized reference alone is not a forgery alert.
- A valid signed revision with changed current rendering/text is a possible shadow attack or a
  later legitimate edit. Annotation-only changes still require review because overlays can conceal text.
  Intermediate revisions are inspected even when the final state restores the original appearance.
- Metadata-only classification is a narrow allowlist: only standard scalar `/Info` entries and
  xref bookkeeping may change, with no rendering/text differences, freed objects, or root/encryption
  reference changes. XMP, catalog, page, script and unexplained object changes are not allowlisted.
  pyHanko's stricter policy result is preserved; a fully metadata-only chain lowers that finding
  to informational severity, without claiming that the signature policy approved the edit.
- One renderer at 144 DPI plus extracted text cannot cover all shadow attacks, invisible active
  content, parser discrepancies or very small/low-contrast changes. No real-world forensic validity
  or human handwriting recognition accuracy is claimed.

## Benchmark assumptions

The 150 cases (140 unique PDFs) have ground truth assigned by construction, never by detector
output. Ten ordinary visual-signature documents are byte-identical to single unauthorized-reuse
cases with different external intent. Without provenance/reference evidence these cannot be
separated; the latter are designated unsupported before evaluation. Ten encrypted inputs are
unsupported by the parser policy. Both groups remain visible in all-case metrics.

Faint signatures remain included in localization metrics and their misses are reported. Repeated
logos remain benign negatives even when they trigger reuse alerts. No cases were removed for
being difficult. An exception on a supported case is recorded separately and scored as no alert,
so a positive then becomes a false negative. An expected encrypted-input error is not a successful
negative classification. Broad class metrics include the `unsupported_error` prediction column.

Fixed seed 20261102, fixed geometry rules, immutable signed/encrypted public templates and
SHA-256 manifests make regeneration deterministic within the pinned Python 3.12 environment.
Template generation uses ephemeral cryptographic randomness and is deliberately a separate,
version-changing operation; private keys are discarded and never committed. Encryption template
passwords are public synthetic fixture values. Library/version changes can alter generated bytes.

The benchmark families are correlated synthetic variants, not a representative statistical sample.
Independent construction tests are development regressions, not an untouched third-party holdout.
No threshold fitting, learned model, randomized train/test split or external dataset evaluation
has been performed. RESULTS.md records the limitations and measured errors rather than claiming
real-world generalization.

## Implemented application-level limits

- PDF: 25 MiB, 1–50 pages, dimensions no larger than 2000 points per side; encrypted inputs rejected.
- At most 16 revisions and 12 embedded signatures; page count × revision count ≤160;
  total page area × revision count ≤30 million square points, checked before cryptographic validation.
- Per visual comparison: two render passes (with/without annotations), estimated render budget
  ≤120 million pixels. Localization: ≤30 million rendered pixels across pages at 108 DPI.
- Image: ≤16 megapixels; alpha composited on white and EXIF orientation honored.
- Up to 24 candidates and 100 pair comparisons. Reaching either budget produces an explicit
  partial-analysis finding. Revision/render/input limits raise explicit unsupported/budget errors.
- Streamlit transport: 25 MiB per upload and 50 MiB message limit, XSRF/CORS protections enabled,
  telemetry disabled. These settings are not authentication, decompression limits or process isolation.
- Audit logs use POSIX locks, canonical hash chains and fsync. A trusted external head is still
  necessary to detect truncation/replacement; an attacker who controls both log and anchor defeats this.

## Public deployment remains blocked by engineering requirements

**No public deployment was performed or authorized in Phase 2.** The following must be implemented
and tested before exposing a PDF upload endpoint:

1. Run each document in a disposable worker process/container under an unprivileged UID, with
   read-only root filesystem, isolated temporary storage, no host mounts, no outbound network,
   restricted syscalls/capabilities, and no cloud credentials. Parsing itself can be expensive before
   application checks run; PDF-native libraries process attacker-controlled compressed data.
2. Enforce external cgroup memory, CPU, wall-clock, disk and process limits, and kill the worker on
   exhaustion. Proposed initial load-test configuration: 1 GiB memory, 30 CPU seconds, 60-second
   wall timeout, 128 MiB temporary storage, 32 processes, and one analysis per worker. These are
   deployment targets, not limits currently enforced by the Python package.
3. Add authenticated OIDC/SSO access, verified tenant identity and authorization for every upload,
   report and reference image; secure sessions and CSRF protection. Streamlit CORS/XSRF settings
   alone do not provide authentication. Never expose a shared filesystem upload directory.
4. Bound queue length and concurrent requests, enforce per-user/tenant quotas and rate limits,
   validate MIME/content/size before queuing, cap JSON/report/download sizes, and protect against
   repeated expensive inputs and decompression bombs. Validate limits through adversarial load tests.
5. Define retention and deletion policy for documents, crops, reports, errors and logs. Use encrypted
   transport/storage where persistence is necessary; avoid raw document text in operational logs.
   Audit anchors must live in a separately controlled append-only system with tenant separation.
6. Keep parsers and dependencies patched; pin reviewed deployable versions, scan the container,
   test malformed/crashing inputs, monitor resource exhaustion, and review licensing and data access.
   No assurance is implied by passing this synthetic suite.
