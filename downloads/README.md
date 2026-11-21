# Download the existing SignGuard project and synthetic dashboard

The complete project is available through GitHub's **Code → Download ZIP** on
this branch. The repository retains its forensic implementation, Streamlit apps,
private static viewer source, security configuration and historical evidence.

For the separate lightweight Streamlit demonstration, open
`signguard-streamlit-online.zip` in this folder and click **Download raw file**.
Extract it to a separate directory. It contains the existing `synthetic_demo.py`,
catalogue loader, five verified synthetic PDFs and precomputed reports, a minimal
Streamlit requirements file, configuration and deployment instructions.

The package has no arbitrary document upload controls, forensic parser, worker,
controller, credentials or live-analysis backend. JSON/PDF downloads and evidence
images come from the verified snapshots. The viewer sources are unchanged copies.

ZIP SHA-256:
`1c8a25d485232867cf430417496189f990fe147da16fe2bd45a0750fbf8d947e`

## Hosting is a separate action

This download does not deploy anything or reserve an online URL. No service,
public upload endpoint or paid resource is created by this change.

The proposed online host is free Streamlit Community Cloud, subject to account
availability and its private-app limit. To preserve private viewing, use a
separate private repository for the extracted package and verify access settings.
Do not deploy directly from this public repository: Community Cloud apps inherit
public visibility from public repositories by default. Stop if any payment,
upgrade or unapproved access change is required. Inactive free apps may sleep.

Use `synthetic_demo.py` as the demonstration entrypoint. The main project's
`app.py` is the live-analysis interface and must not be substituted for it.
Existing production release gates and the strict ₹0 policy remain in force.

The ZIP is a reviewed snapshot; later source or dependency updates need a new
package and validation. Its local checks are not hosted security qualification.
