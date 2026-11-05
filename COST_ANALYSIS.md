# Strict ₹0 financial controls — Phase 10

As of 5 November 2026 (IST), the authorized incremental hosting/infrastructure budget is **₹0**. No card was entered, paid resource created, cloud account upgraded, domain registered or billable registry published. Existing subscriptions, historical charges, connected Sites entitlements and account-wide storage are not visible through the available tools; no zero account balance is asserted.

| Component | Planned additional charge | Exposure and response |
| --- | --- | --- |
| Existing private synthetic Site | No new deployment or account change | Existing contractual cost is unknown; repository code cannot certify the platform subscription. Preserved as required. |
| Already-provided Codex workspace | No new infrastructure provisioned | Existing ChatGPT/Codex plan or credits are outside this hosting estimate; no upgrade or credit purchase requested. |
| Standard public-repo Actions compute | ₹0 published compute price | Account state, logs, artifacts/caches and unrelated usage can still matter. New jobs fail closed until owner budget confirmation; no private/larger runner fallback. |
| Actions remote artifacts/cache | No new uploads/cache saves configured | Uploads/cache settings removed. Historical storage/charges are not erased by this change and old-branch workflows remain historical code. Do not delete evidence or claim a refund. |
| AWS / paid network / paid storage | Prohibited | Active apply/publication jobs removed; direct delivery script fails before provider access. Phase 9 files retained for history only. |
| Oracle / Google / other new provider | Not used | No card/authorization/upgrade/provisioning requested. Free labels or trial credits are not proof of permanent safe hosting. |

The **target incremental cost is ₹0**. Actual account-level cost cannot be guaranteed by an environment variable or this document. An explicit platform-enforced no-spend control is required before a CI runner starts. No billable fallback is permitted if limits are exhausted.

## Minimum browser-only action before CI can run

No action is required to continue opening the existing private synthetic viewer. For new Actions evaluation:

1. Open [GitHub billing](https://github.com/settings/billing) → **Budgets and alerts**. Review/create an account-wide **Actions** budget of **$0**, with **Stop usage when budget limit is reached** enabled, covering compute and storage. Alerts alone are insufficient. Review existing storage and any overriding organization rules. If the UI cannot enforce zero spending for all relevant usage, **keep the workflows disabled**; do not choose a positive limit or add payment details.
2. After independently confirming that protection (or an authoritative no-payment/no-overage account block), open repository **Settings → Secrets and variables → Actions → Variables**, and set `SIGNGUARD_ZERO_SPEND_CONFIRMED` to `true`. This is an owner attestation, not an API-verified budget. No token or secret is entered. Never set it merely because the repository is public. Remove/set false when the account protection changes.
3. After merging the reviewed PR, the owner can choose **Actions → Zero-cost synthetic development → Run workflow**, select one of the five fixed synthetic cases, and inspect its result summary. The full test/scan jobs also become eligible. If GitHub stops them at the hard limit, leave them stopped. The job does not create a public service or accept private PDFs.

This repository cannot configure or read billing budgets with the connected GitHub permissions, and no new account authorization was invented. The workflows are intentionally gated rather than run on an unverifiable billing assumption. [GitHub's budget instructions](https://docs.github.com/en/billing/how-tos/set-up-budgets) explain the hard-stop option; [current storage guidance](https://github.blog/changelog/2026-08-27-actions-retention-will-cover-checks-workflow-runs-and-statuses/) makes clear why retention is a financial concern.

## Execution limits and release decision

Cloud local regression, financial/identity/input contracts and current Python dependency audit were executed. Fresh Docker image builds/full scans and isolated-worker/browser integration require more workspace disk than the current roughly 0.46 GiB free, or a verified no-spend CI run. Chromium installation was attempted and denied by the enforced outbound policy (`cdn.playwright.dev`, HTTP 403 Domain forbidden). No alternative hostname, proxy bypass or TLS bypass was used. Docker daemon access is available, but only a base image is cached; no final image scan result is fabricated.

The prepared native ARM build/test/scan is unexecuted. ARM wheel and base-manifest metadata are compatibility evidence only. Previous Phase 9 zero-critical/high scans remain historical evidence, not current-image proof. The private viewer's code/assets/access policy are unchanged; authenticated hosted browser availability was not independently rechecked during Phase 10.

**Live private arbitrary-PDF uploads remain unavailable.** Missing private transfer, access-controlled fresh-report storage, durable externally anchored audit, verified host isolation and zero-cost hosting authority block a complete asynchronous or live service. A synthetic project evaluation is the permitted fallback. Do not route private submissions through public GitHub issues, artifacts, caches, workflow inputs or logs.
