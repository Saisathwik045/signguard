# Phase 7 deployment verification checklist

Recorded 3 November 2026 (Asia/Kolkata). Scope: trusted synthetic snapshots only.
Live URL: https://signguard-private-synthetic.knitdeck.chatgpt.site

## Evidence classes — do not combine into a hosted-login pass

| Check | Status | Evidence and limits |
| --- | --- | --- |
| Owner opens the real URL | USER-REPORTED | Owner explicitly reports a successful browser visit in this task; no independent recording supplied |
| Current main includes PR #7 | CONFIRMED | GitHub PR metadata says merged; fetched main `0c8f74c46d4519fa0f81c6c1de45c14dfe989b3d` |
| All four PR-head workflows | AUTOMATED PASS | Rechecked head `6db5970`: Cloud tests 41612159740, staging 41612159739, demo 41612159741, private viewer 41612159748 |
| Protected hosted validation | SKIPPED | Job metadata explicitly says skipped; never counted as hosted success |
| Deployment active, v2, same URL | CONTROL-PLANE CONFIRMED | Fresh native `get_site`; original native succeeded publication in `evaluation/phase7/deployment-v2.json` |
| Owner-only audience | CONTROL-PLANE CONFIRMED | One owner, zero groups/external visitors, revision 1; no access mutation |
| Anonymous actual HTTPS access denied | AUTOMATED PASS (prior head, rechecked CI) | `anonymous-live-routes` succeeded in run 41612159748; retained raw five-route HTTP 403 proof in `evaluation/phase7/anonymous-route-proof.json` |
| Regenerated artifact equals retained deployed source | AUTOMATED PASS | `diff -rq` over all ten `dist` assets vs native source checkout at `4c56398c75506e592237bb4a8fe358c8b72372e6`; checksums retained in closeout evidence |
| Live authenticated content equals retained source | UNVERIFIED | No authorized live content fetched; local equality cannot prove remote bytes |
| Five fixed document selections and correct findings | AUTOMATED ARTIFACT PASS | Real Chromium selects each and checks classification/verdict against bundled reports |
| Evidence-image references and shadow comparison | AUTOMATED ARTIFACT PASS | All displayed PNGs decode with nonzero width; signed shadow snapshot visible; no external image references |
| Exact JSON/PDF downloads | AUTOMATED ARTIFACT PASS | Five JSON SHA-256 checks against worker manifest and five exact decoded PDF-byte checks |
| Corrupted report rejection and recovery | AUTOMATED ARTIFACT PASS | Altered response rejected, report state cleared/hidden; later valid selection succeeds |
| Selection race protection | AUTOMATED ARTIFACT PASS | Delayed older response cannot replace new unsigned selection or its JSON download |
| No arbitrary upload/URL/path UI | AUTOMATED ARTIFACT PASS | Five fixed buttons, no input/textarea/form; fixed-asset build inventory; no backend |
| Interactive owner login/session/logout | UNVERIFIED independently | User visit is limited evidence; native service access would not constitute interactive SSO testing |
| Hosted screenshots/downloads | UNVERIFIED | Retained screenshots are cloud loopback artifact images, not authenticated hosted captures |
| Viewer version rollback drill | NOT EXECUTED | Version/source IDs retained; no deployment mutation in closeout |
| Live upload application | DISABLED / NOT DEPLOYED | Static Sites tier contains no analysis backend; production gates remain blocked |

## Fresh cloud execution and retained artifacts

Run through the existing Codex interpreter/Chromium in cloud only; no local user execution.
`ruff check .`, JS syntax check, static build and source-tree comparison passed. The focused
private-viewer suite passed **6 checks** (four unit contracts and two browser scenarios).
Its JUnit, SHA-256 inventory and `hosted: false` browser metadata are in
[evaluation/phase7-closeout](evaluation/phase7-closeout/). Existing Phase 7 screenshots remain
at `evaluation/phase7/`; these are artifact screenshots, not hosted login evidence.

An initial browser invocation hit the command sandbox's socket restriction. It was rerun successfully
with tool-level network permission while retaining the enforced cloud outbound allowlist and TLS.
The initial unrestricted regression invocation was interrupted after socket-restricted tests stalled;
its partial output is not counted as a pass. The completed permitted cloud regression produced
91 passed, zero failed, 18 explicitly opted-out Docker/other-browser cases. The combined final run passed **93 tests, zero failures, 16 explicit skips** in 36.28 seconds
with both private-viewer browser scenarios enabled; see `combined-junit.xml`. This avoids double
counting overlapping focused tests. The ordinary
Starlette test-client deprecation warning remains; no feature or security gate was weakened.

No fresh image rebuild or new image-scan count is asserted for this docs/test-only change. Existing
CI container/security workflows were rechecked, and Phase 6 raw evidence remains unchanged.

## Open checks and release boundaries

- [x] Preserve deployed v2 and owner-only policy without republishing.
- [x] Record owner observation separately from automation.
- [x] Recheck all four PR-head workflow conclusions and hosted-job skip.
- [x] Check report hashes, images, selections, ten downloads and adverse selection/hash behavior.
- [ ] Independently automate authorized hosted content/health and exact downloads.
- [ ] Exercise interactive owner login, session attributes, logout and revoked-session denial.
- [ ] Rehearse and verify rollback on an approved deployment window.
- [ ] Qualify production upload infrastructure and satisfy [NEXT_PHASE_PLAN.md](NEXT_PHASE_PLAN.md).

Current Codex policy remains restricted, custom allowed hosts empty, revision 3. No policy change,
proxy bypass, credential sharing, billing change, Codespaces or public-upload endpoint is needed
or introduced by this closeout. Do not mark open hosted checks complete based on this document.
