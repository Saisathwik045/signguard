# AWS staging preparation — Phase 9

Status: configuration prepared; no AWS account identity, paid resources, public certificate or live-upload URL exists in this task. The independent synthetic Site is unchanged. This is a single-owner staging design, not a multi-tenant production service.

## Architecture

One Canonical Ubuntu 24.04 x86_64 EC2 t3a.medium in us-east-1 hosts the existing UI and private controller images. The UI terminates HTTPS using Uvicorn, authenticates through GitHub OAuth2/PKCE, and authorizes immutable GitHub user ID `220234042`. OAuth credentials/tokens never reach workers. Opaque, hashed, expiring sessions and one-use OAuth state persist on encrypted storage. No HTTP or development-auth fallback is enabled. Existing Authlib/ASGI dependencies avoid adding separate proxy images.

The controller has no exposed port, internet route or Docker socket. Its fixed Unix RPC reaches a systemd executor under UID 1001, without sudo or rootful Docker group membership. This executor uses a separate rootless Docker daemon. Each PDF worker retains non-root UID, no network, read-only root, dropped capabilities, no-new-privileges, CPU/memory/PID limits, timeout and cleanup. Cgroup v2/systemd delegation is mandatory; unsupported hosts fail preflight. The long-lived UI/controller also have bounded memory, CPU, PID and tmpfs resources. Root-owned release automation is privileged; only reviewed protected-main code may use SSM deployment authority.

There is no Kubernetes, load balancer, NAT gateway, Redis or database service. SQLite quotas and sessions are suitable for this one-host pilot; horizontal scaling requires shared admission state. A separate encrypted retained EBS volume stores audit/quota/session state. Controller and auth use separate bind mounts. Hash-chain audit snapshots upload every minute to private, versioned, encrypted S3 with seven-day governance Object Lock and no runtime delete/bypass permission. This is periodic anchoring, **not synchronous durable acknowledgment before every report**. Host loss can lose the unanchored interval. S3 lifecycle expires snapshots after 30 days and noncurrent versions after a further 30 days; retention/privacy policy requires owner review.

## Files and safety defaults

- `bootstrap.cfn.json`: GitHub environment-bound OIDC role, instance profile and retained encrypted Terraform-state bucket. Reuses an existing GitHub OIDC provider when supplied. No compute or secret values.
- `main.tf`, `tests/security.tftest.hcl`: plan-tested infrastructure, ECR/Secrets Manager references, no-resource default. `spending_authorized=false` and `allow_private_ingress=false` are independent defaults. No SSH ingress.
- `host/`: Docker/rootless setup, metadata firewall, persistent-volume validation, release install, TLS issuance/renewal and audit timers.
- `scripts/render_aws_staging.py`: fixed digest-only service wiring with `SIGNGUARD_LIVE_UPLOADS_ENABLED=false`. No workflow option enables uploads.
- `scripts/aws_delivery.py`: immutable ECR publication, source SHA-256 verification and tag-checked SSM deployment. No secret values in release manifests or Terraform state.
- `scripts/aws_host_preflight.py`, `scripts/check_rootless_worker.py`: actual host/worker qualification, not static claims.

## Browser-only authorization and execution sequence

The owner does not run terminal commands. An authorized cloud operator/agent executes the prepared workflows after these browser actions:

1. Explicitly approve approximately **USD 40/month plus variable usage and taxes**. No hard budget cap is implied. If not approved, leave both infrastructure flags false.
2. In ChatGPT **Settings → Codex Cloud → Environments → signguard → Edit → Advanced → OIDC → Add → AWS/Create connection**, connect an AWS role for the approved account. Use the issuer, audience and subject shown by that screen to configure its AWS trust. Bind that connection and start a new task. The Cloud connection trust is distinct from GitHub's OIDC trust; do not reuse GitHub claims for Codex. Never paste access keys into chat.
3. With the connected identity the agent can install the reviewed bootstrap through AWS APIs, select the standard Canonical non-Marketplace AMI, and configure the GitHub `aws-staging` environment. It must require owner review and restrict deployments to protected main. Variables: `AWS_ACCOUNT_ID`, `AWS_DEPLOY_ROLE_ARN`, `AWS_AMI_ID` (plus publish inputs listed in the workflow). The prepared GitHub role trusts exactly `repo:Saisathwik045/signguard:environment:aws-staging`. Merge/review the preparation PR first.
4. Run protected workflow `plan`, review actual cost/resources, then explicitly approved `apply`. The first apply should leave maintenance ingress closed. Inspect SSM/bootstrap, volume and rootless qualification before opening maintenance ports. No resource has been applied here.
5. Once the actual static IP is known, register a GitHub OAuth App in **GitHub Settings → Developer settings → OAuth Apps** with homepage `https://ACTUAL_IP` and callback `https://ACTUAL_IP/auth/callback`. Store its client ID/secret directly in AWS Secrets Manager `signguard/staging/runtime`, using the exact JSON fields accepted by `write_aws_runtime_secrets.py`; never put values in repository, workflow variables, chat or Terraform.
6. Separately approve maintenance ingress: port 80 only serves standalone ACME challenge issuance; port 443 serves authenticated maintenance. Certbot 5.9 supports short-lived IP certificates, so no domain purchase is needed. Certificate issuance/renewal must actually succeed before any HTTPS claim. The root-owned ACME account key is never mounted into UI. Twice-daily renewals copy only leaf material and restart UI.
7. Protected `publish-stage` builds/scans the actual three existing service images, pushes immutable ECR digests and installs through SSM. It always leaves live uploads disabled. Review host preflight and real-rootless worker output before signed-in tests. Automatic pull-request jobs never provision resources.
8. Execute actual-origin TLS, GitHub owner login, non-owner denial, session expiry/logout, upload denial, private controller reachability denial, retained-audit restoration, quota restart, load, timeout and cleanup probes. Later enable uploads only in a separately reviewed change after every mandatory gate is met. This workflow deliberately cannot enable them.

Account connection may require exact AWS API host allowlisting under the existing outbound policy. Request only concrete necessary hosts after account/region are known; never disable TLS verification or open unrestricted internet.

## Rollback and incident procedure

Preparation only; no live rollback drill has occurred. Keep immutable release manifests/source archives and previous image digests. On an incident, first disable external ingress with the reviewed Terraform flag (or stop UI through SSM), preserve audit volume/S3 anchors and revoke sessions/OAuth credentials where compromised. Do not delete state, audit objects or the retained volume.

An authorized protected-main cloud operator selects a previously verified release, pulls its exact ECR digests, rescans all three images against current vulnerability databases and reruns regression/isolation smoke checks. A historic scan is insufficient. Reinstall the verified source bundle using its recorded SHA-256 and `stage-release.sh`; this restarts the executor and restores **maintenance-only** UI. Do not blindly apply old Terraform state or downgrade persistent schemas: assess compatibility and take an encrypted snapshot first. Verify HTTPS, authorization, image identities, controller denial, audit continuity and quotas before reopening authenticated maintenance. A failed fresh image gate keeps service offline. The GitHub workflow does not automatically choose or activate an old release.

For decommissioning, close ingress first and explicitly review retained EBS/S3/state resources, Object Lock, EIP and storage charges. Stopping EC2 alone does not stop storage/IPv4 costs. `prevent_destroy`/retention are intentional data-protection barriers, not automatic teardown.

## Required release evidence

Actual AMI ID, Docker/rootless versions and host patch scan; deployed image digests and fresh full scans; trusted public TLS and renewal test; real OAuth owner/non-owner browser checks; actual-rootless PDF analysis and cleanup; quota restart/concurrency; durable audit recovery/anchor failure; rollback drill; retention/cost approval. CI evidence does not replace these host-specific checks. The privileged SSM deployment role and host-wide outbound access need security review; PDF worker networking remains disabled.
