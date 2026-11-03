# Deployment verification checklist

`Prepared` is not `verified on AWS`. No checkbox below is satisfied merely by Terraform validation.

| Gate | Evidence available now | Actual staging evidence required before uploads |
| --- | --- | --- |
| Source preservation | Started from merged PR #9/main b668a70; existing workflows retained | Deployed manifest equals approved main SHA |
| Cost/account authorization | Two explicit false-by-default infrastructure controls | Approved account, spending and maintenance ingress review |
| Infrastructure | Terraform validate/mock tests and CloudFormation lint | Real plan/apply, standard non-Marketplace AMI, encrypted volumes, no SSH/private service ports |
| Worker authority | Separate rootless-daemon workflow and fixed Unix socket contract | Dedicated UID 1001 has no sudo/rootful Docker membership; cgroup v2 delegation and exact-image worker probe |
| Forensics/UI | Existing cloud regression and container browser stack | Same immutable images execute genuine/tampered/shadow/visual/unsigned/unsupported through actual rootless stack |
| Authentication | Mocked GitHub exchange/state/PKCE/owner-ID/session/logout tests | Real provider owner login, different-account denial, expired/revoked WebSocket/HTTP sessions |
| HTTPS | Cloud loopback test with explicitly trusted ephemeral test CA | Actual IP certificate chain/hostname, automatic renewal and restart; no insecure bypass |
| Quotas/load | Persistent quota concurrency/failure tests; existing bounded browser stack | Restart persistence, saturation/recovery, CPU/memory/PID/storage limits on allocated host |
| Audit | Hash-chain validation/snapshot code; retained encrypted EBS/S3 definitions | Successful anchor, failure alerting, restoration, loss-window acceptance and retention approval |
| Image admission | Existing unsuppressed exact-image OS/Python gates | Fresh scans of deployed immutable digests plus updated host OS/daemon scan |
| Reports/cleanup | Existing JSON/PDF/evidence browser tests | Actual-origin authorized report downloads, expired-session denial, no cross-request leaks, timed-out worker cleanup |
| Rollback | Maintenance-first runbook and immutable release manifests | Rehearsal with current rescans, schema compatibility, audit continuity and no upload reactivation |

The synthetic Site is independent, owner-private and unchanged. The user's prior browser observation applies to that Site only. Cloud-loopback browser/TLS results do not prove an AWS endpoint or real OAuth login. No live upload endpoint is enabled by the prepared workflow. Mandatory gates remain blocked until actual-origin evidence is recorded and reviewed.
