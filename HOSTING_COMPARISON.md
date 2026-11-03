# Phase 9 full-architecture hosting comparison — 3 November 2026

No new provider account, paid resource, domain or upload endpoint was enabled. Prices are public list estimates, not an account quote or spend cap.

| Provider/plan | Published terms and expected cost | Complete architecture fit |
| --- | --- | --- |
| **AWS EC2 t3a.medium, us-east-1 — recommended** | 2 vCPU/4 GiB at $0.0376/hour: $27.45/730 hours; 100 GiB total gp3 $8; one public IPv4 $3.65; one secret ~$0.40; small ECR/S3 usage. **About $40/month plus variable requests/storage/transfer/taxes**. CPU credits use standard mode. | Normal x86 Linux VM supports a distinct rootless Docker daemon, cgroup v2 limits and fixed restricted RPC. Instance roles, short-lived GitHub OIDC, SSM without SSH, private encrypted audit storage and Secrets Manager avoid manual credential distribution. Actual host qualification still required. |
| AWS Lightsail 4 GiB | $24/month Linux bundle, 80 GiB disk, public IPv4 and 4 TB transfer allowance; storage/other services extra. | VM can run Docker, but the prepared instance-role/SSM/OIDC deployment fits EC2 more directly. Not selected. |
| DigitalOcean Basic 4 GiB/2 vCPU | $24/month, 80 GiB SSD; transfer/storage conditions apply. | Technically suitable Linux VM; would need separately prepared identity, secrets, deployment and durable audit integration. Not selected. |
| Oracle Always Free Ampere A1 | Current resource page lists 1,500 OCPU-hours/9,000 GiB-hours monthly (about 2 OCPU/12 GiB continuously); other Oracle documentation still lists older larger allowances. Account entitlement, capacity and idle reclamation apply. | An ARM VM may support isolation, but current images/native dependencies are qualified on x86, not A1. No account/capacity/ARM proof exists. **No verified free option for this complete tested stack**; this is not a claim free hosting is impossible in principle. |
| Cloud Run free request allowance | 180,000 vCPU-seconds, 360,000 GiB-seconds and two million requests/month; excess bills. | Frontend possible; the required disposable Docker execution needs a separate backend. Free allowance does not provide this architecture by itself. |
| Render Free | 750 instance-hours/workspace/month; idle sleep after 15 minutes. | No established separate privileged/rootless daemon host or durable host state for this design. |
| Existing connected Sites | Existing owner-private HTTPS static synthetic viewer. Account prices/quotas not exposed. | Preserved presentation only; cannot execute the Python/worker stack. |

Published sources checked: [EC2 T3/T3a](https://aws.amazon.com/ec2/instance-types/t3/), [EBS](https://aws.amazon.com/ebs/pricing/), [IPv4](https://aws.amazon.com/vpc/pricing/), [Secrets Manager](https://aws.amazon.com/secrets-manager/pricing/), [Systems Manager](https://aws.amazon.com/systems-manager/pricing/), [Lightsail bundles](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-bundles.html), [DigitalOcean](https://www.digitalocean.com/pricing/droplets), [Oracle resource allowances](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm), [Oracle conditions](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm), [Cloud Run](https://cloud.google.com/run/pricing), [Render](https://render.com/docs/free).

AWS is selected for the smallest maintainable **prepared** deployment, not the lowest headline VM price. No ALB, NAT gateway, Kubernetes or managed database is required. HTTPS can use [Let's Encrypt short-lived IP certificates](https://letsencrypt.org/2026/03/11/shorter-certs-certbot) without buying a domain. Actual issuance and renewal remain deployment gates. See [AWS runbook](deploy/aws/README.md).

---

Historical Phase 7 decision follows; its statement that production hosting is unselected is superseded by the Phase 9 recommendation above.

# Phase 7 hosting decision — 3 November 2026

Prices/limits below were checked against official sources on this date. They are not guarantees
about a particular account's remaining quota. No billing profile, paid service or domain was enabled.

| Option | Current verified terms | Architecture fit | Decision |
| --- | --- | --- | --- |
| Connected Sites / Cloudflare-backed static hosting | Existing connected service; owner-only access and HTTPS available. Tool contract states 128 MiB Worker isolates, HTTP connections only. Monetary pricing/account quotas are not exposed, so unlimited/free usage is not asserted. | Fixed read-only presentation tier only. No Python, Streamlit, daemon or isolated PDF workers. | Selected **only for the independent synthetic viewer**, using existing reports; not selected as a production worker host. |
| Render Free | 750 shared instance-hours/workspace/month; idle services sleep after 15 minutes. Managed TLS and two prior deploy rollbacks. Overage can bill with a payment method; without one services/builds suspend. | Python/container viewer possible with an application auth gateway. Existing privileged worker architecture is not established on this plan. No account/credential available here. | Not provisioned; cannot assume a bill-free connected account. |
| Hugging Face Spaces | Current docs say Docker/Gradio compute Spaces require a paid PRO/Team/Enterprise plan; static Spaces remain free. | Docker could host the viewer, but neither a free Docker entitlement nor the restricted daemon architecture is established. Static alternative still requires another account connection. | No paid plan or new account authorized/provisioned. |
| Google Cloud Run | Request-based free allowances: 180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million requests/month, aggregated by billing account; excess is billed. | Container viewer can fit; existing Unix/Docker worker execution would require a separately reviewed backend adapter. No cloud identity/billing authorization is bound. | Not provisioned. Free allowance is not a hard spend cap or billing approval. |
| Fly.io Machines | Pay-as-you-go; documented smallest always-on 256 MiB machine starts at $2.19/30 days in the lowest-priced regions; larger memory costs more. | A VM-based restricted executor needs a real isolation proof and suitable memory. No provider identity is connected. | Paid provisioning not authorized. |

Official sources:

- [Render free service limits](https://render.com/docs/free)
- [Hugging Face Spaces overview and current compute requirements](https://huggingface.co/docs/hub/spaces-overview)
- [Cloud Run pricing and free allowances](https://cloud.google.com/run/pricing)
- [Fly.io pricing](https://docs.fly.io/about/pricing)

The selected deployment is intentionally a separate static client for the verified synthetic report
bundle. It is not a claim that Sites supports the Python/Streamlit application or disposable workers.
Those implementations and all existing security restrictions remain in the repository. Production
hosting remains unselected until its isolation, identity, TLS and operational gates can be proved.
