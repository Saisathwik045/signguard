"""Authenticated UI; all PDF parsing/rendering stays across the isolated worker boundary."""
import base64
import hmac
import json
import os
import time

import streamlit as st

from signguard.client import analyze_upload, authorized
from signguard.preview_auth import verify

st.set_page_config(page_title="SignGuard", page_icon="🛡️")
st.title("SignGuard")
st.caption("PDF signature integrity and visual tampering triage")


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
pdf = st.file_uploader("PDF to inspect (up to 25 MiB, 50 pages)", type="pdf", on_change=clear_report)
baseline = st.file_uploader("Optional known baseline PDF", type="pdf", on_change=clear_report)
candidate = st.file_uploader("Optional manual signature crop", type=["png", "jpg", "jpeg"], on_change=clear_report)
reference = st.file_uploader("Optional reference signature crop", type=["png", "jpg", "jpeg"], on_change=clear_report)
if st.button("Analyze", disabled=pdf is None):
    clear_report()
    try:
        if pdf.size > 25*1024*1024:
            raise ValueError("Input limit")
        with st.spinner("Analyzing in a disposable isolated worker…"):
            result = analyze_upload(pdf.getvalue(), principal=principal,
                                    baseline=baseline.getvalue() if baseline else None,
                                    signature_image=candidate.getvalue() if candidate else None,
                                    reference_image=reference.getvalue() if reference else None)
        st.session_state.report = result
    except Exception:  # noqa: BLE001 -- no parser/host/credential details are returned to the browser
        st.error("Analysis could not complete: unsupported input, worker limit, quota, or service configuration error.")

if "report" in st.session_state:
    result = st.session_state.report
    st.subheader(result["assessment"]["verdict"].replace("_", " ").title())
    st.write("Classification: "+result["structure"]["refined_classification"])
    for reason in result["assessment"]["reasons"]:
        st.write(reason)
    for item in result.get("visual_evidence", []):
        st.image(base64.b64decode(item["base64"]), caption=f"{item['label']} — page {item['page']}")
    automatic = result["image_forensics"]["automatic"]
    st.write(f"Automatic candidate regions: {len(automatic['localization']['candidates'])}")
    if result.get("audit_receipt"):
        st.caption("Controller audit head: "+result["audit_receipt"]["head"])
    st.download_button("Download JSON report", json.dumps(result, indent=2), file_name="signguard-report.json",
                       mime="application/json", on_click="ignore")
    if result.get("pdf_report"):
        st.download_button("Download PDF report", base64.b64decode(result["pdf_report"]["base64"]),
                           file_name="signguard-report.pdf", mime="application/pdf", on_click="ignore")
    with st.expander("Structured evidence"):
        st.json({k: v for k, v in result.items() if k not in {"pdf_report", "visual_evidence"}})
