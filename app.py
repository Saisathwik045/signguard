"""Authenticated UI; all PDF parsing/rendering stays across the isolated worker boundary."""
import base64
import hmac
import json
import os
import time

import streamlit as st

from signguard.client import AnalysisServiceError, analyze_upload, authorized
from signguard.input_policy import InputRejected
from signguard.preview_auth import verify

st.set_page_config(page_title="SignGuard · Live forensic lab", page_icon="🛡️", layout="wide")
st.markdown("""<style>
.stApp {background:#0b1620;color:#e5edf3}
[data-testid="stHeader"] {background:#0b1620}
h1,h2,h3 {letter-spacing:-.025em}
[data-testid="stMetric"] {border:1px solid #27404d;border-radius:12px;padding:16px;background:#112331}
.stButton button[kind="primary"] {background:#55d6bd;color:#071a21;border:0}
</style>""", unsafe_allow_html=True)
st.caption("SIGNGUARD / PRIVATE FORENSIC LAB")
st.title("Inspect the evidence.")
st.write("Live PDF integrity analysis · isolated processing · explainable findings")


def clear_report():
    st.session_state.pop("report", None)


principal = "development"
if os.environ.get("SIGNGUARD_REQUIRE_AUTH") == "true":
    mode = os.environ.get("SIGNGUARD_AUTH_MODE", "oidc")
    if mode == "gateway":
        expected = os.environ.get("SIGNGUARD_GATEWAY_TOKEN", "")
        if len(expected) < 32 or not hmac.compare_digest(st.context.headers.get("X-SignGuard-Gateway", ""), expected):
            st.error("Access denied: authenticated private gateway is required.")
            st.stop()
        principal = "private-preview-owner"
    elif mode == "preview_password":
        if (os.environ.get("SIGNGUARD_BACKEND") != "broker"
                or os.environ.get("SIGNGUARD_PREVIEW_PRIVATE_CONFIRMED") != "true"):
            st.error("Private preview configuration is incomplete.")
            st.stop()
        if time.time()-st.session_state.get("authenticated_at", 0) > 900:
            st.session_state.pop("authenticated_at", None)
            clear_report()
        if "authenticated_at" not in st.session_state:
            st.info("Private preview: sign in before uploading a document.")
            with st.form("sign_in"):
                password = st.text_input("Preview password", type="password", max_chars=256)
                submitted = st.form_submit_button("Sign in")
            if submitted:
                if verify(password, os.environ.get("SIGNGUARD_PREVIEW_PASSWORD_HASH", "")):
                    st.session_state.authenticated_at = time.time()
                    st.rerun()
                else:
                    st.error("Access denied. Invalid credential or login rate limit reached.")
            st.stop()
        principal = "private-preview-owner"
    elif mode == "oidc":
        if not st.user.is_logged_in:
            st.info("Sign in to access document uploads.")
            if st.button("Sign in"):
                st.login()
            st.stop()
        allowed = set(filter(None, os.environ.get("SIGNGUARD_ALLOWED_EMAILS", "").split(",")))
        if not authorized(dict(st.user), allowed):
            st.error("Access denied: this verified identity is not authorized.")
            if st.button("Sign out"):
                st.logout()
            st.stop()
        principal = st.user.email
    else:
        st.error("Unsupported authentication configuration.")
        st.stop()
    if mode == "gateway":
        st.markdown('<a href="/auth/logout" target="_self">Sign out</a>', unsafe_allow_html=True)
    elif st.button("Sign out"):
        st.session_state.clear()
        if mode == "oidc":
            st.logout()
        st.rerun()

st.info("Visual matches cannot establish who signed or whether reuse was authorized. "
        "Certificate verification is offline with no UI trust roots configured.")
st.subheader("Inspect a PDF")
st.caption("PDF bytes are validated before dispatch. Analysis runs in a disposable worker; optional crops are not required.")
pdf = st.file_uploader("PDF to inspect (up to 25 MiB, 50 pages)", type="pdf", on_change=clear_report)
with st.expander("Optional comparison inputs"):
    st.caption("Baseline: PDF up to 25 MiB. Signature images: PNG/JPEG up to 5 MiB each. Combined inputs: 60 MiB.")
    baseline = st.file_uploader("Optional known baseline PDF", type="pdf", on_change=clear_report)
    candidate = st.file_uploader("Optional manual signature crop", type=["png", "jpg", "jpeg"], on_change=clear_report)
    reference = st.file_uploader("Optional reference signature crop", type=["png", "jpg", "jpeg"], on_change=clear_report)
if st.button("Analyze", disabled=pdf is None, type="primary"):
    clear_report()
    try:
        with st.status("Analyzing in a disposable isolated worker…", expanded=True) as progress:
            st.write("Validating input and requesting private analysis. The worker performs PDF and image parsing.")
            result = analyze_upload(pdf.getvalue(), principal=principal,
                                    baseline=baseline.getvalue() if baseline else None,
                                    signature_image=candidate.getvalue() if candidate else None,
                                    reference_image=reference.getvalue() if reference else None)
            st.session_state.report = result
            progress.update(label="Analysis returned — review findings and limitations", state="complete", expanded=False)
    except InputRejected as exc:
        st.error("Upload rejected: "+str(exc))
    except AnalysisServiceError as exc:
        st.error("Analysis could not complete: "+str(exc))
    except Exception:  # noqa: BLE001 -- parser/host/credential details never reach the browser
        st.error("Analysis could not complete: unsupported input, worker limit, quota, or service configuration error.")

if "report" in st.session_state:
    result = st.session_state.report
    assessment = result["assessment"]
    unsupported = assessment["analysis_status"] == "unsupported"
    st.divider()
    st.subheader("Unsupported document" if unsupported else assessment["verdict"].replace("_", " ").title())
    st.write("Classification: "+result["structure"]["refined_classification"])
    columns = st.columns(3)
    columns[0].metric("Analysis coverage", assessment["analysis_status"].replace("_", " ").title())
    columns[1].metric("Cryptographic signatures", len(result["structure"]["signatures"]))
    columns[2].metric("Identity established", "No — abstain")
    for reason in assessment["reasons"]:
        st.write(reason)
    if unsupported:
        st.warning("No authenticity determination was made. See the structured JSON for the unsupported reason.")
    else:
        with st.expander("Cryptographic verification and certificate trust", expanded=True):
            signatures = result["structure"]["signatures"]
            if not signatures:
                st.write("No embedded cryptographic signature was found. A visual mark is not a cryptographic signature.")
            for signature in signatures:
                st.write({key: signature.get(key) for key in (
                    "field", "intact", "valid", "trusted", "coverage", "signed_revision",
                    "modification_level", "trust_mode", "revocation_state")})
            st.caption("Mathematical validity, certificate identity trust and permission to modify are separate decisions.")
        st.subheader("Visual evidence")
        st.caption("Blue boxes: uncertain signature candidates. Red boxes: changed regions. Colors are not forgery probabilities.")
        images = result.get("visual_evidence", [])
        evidence_columns = st.columns(2)
        for index, item in enumerate(images):
            evidence_columns[index % 2].image(base64.b64decode(item["base64"], validate=True),
                caption=f"{item['label']} — page {item['page']}")
        if not images:
            st.write("No evidence image was available within the rendering budget.")
    automatic = result["image_forensics"]["automatic"]
    st.write(f"Automatic candidate regions: {len(automatic['localization']['candidates'])}")
    with st.expander("Revision, shadow-attack and image-forensic findings"):
        st.json({"findings": assessment["findings"], "revisions": result["revision_analysis"],
                 "visual_comparisons": result["visual_comparisons"], "image_forensics": result["image_forensics"]})
        st.caption("ELA residuals and ORB reuse are heuristic evidence. Legitimate reuse, low-texture handwriting and partial budgets limit conclusions.")
    controls = result.get("execution_controls", {})
    st.caption("Processing boundary: "+controls.get("isolation", "unattested")+
               " · Network isolated: "+str(controls.get("network_isolation", False)))
    if result.get("audit_receipt"):
        st.caption("Controller audit head: "+result["audit_receipt"]["head"])
        st.caption("Local hash-chain receipt; external anchoring is not established.")
    st.download_button("Download JSON report", json.dumps(result, indent=2), file_name="signguard-report.json",
                       mime="application/json", on_click="ignore")
    if result.get("pdf_report"):
        st.download_button("Download PDF report", base64.b64decode(result["pdf_report"]["base64"], validate=True),
                           file_name="signguard-report.pdf", mime="application/pdf", on_click="ignore")
    with st.expander("Structured evidence"):
        st.json({k: v for k, v in result.items() if k not in {"pdf_report", "visual_evidence"}})
