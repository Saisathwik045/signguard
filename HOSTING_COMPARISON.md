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
