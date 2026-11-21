"""Authenticated inspection UI. PDF parsing remains behind the isolated broker."""
import hmac
import os
import time

import streamlit as st

from signguard.client import AnalysisServiceError, analyze_upload, authorized
from signguard.dashboard import configure, navigation, render_page, render_report
from signguard.input_policy import InputRejected, validate_inputs
from signguard.preview_auth import verify

configure("live")


def clear_report():
    for key in ("report", "report_latency"):
        st.session_state.pop(key, None)


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

page = navigation("live")
if page != "Inspect document":
    render_page(page, "live")
    st.stop()

st.title("Inspect the evidence.")
st.write("Inspect a PDF through the existing authenticated, isolated analysis pipeline.")
if os.environ.get("SIGNGUARD_LIVE_UPLOADS_ENABLED", "false") != "true":
    st.info("Private maintenance: live uploads are disabled pending verified release controls.")
    st.write("Use Demo gallery to explore saved examples, Evaluation for measured results, and Architecture & security for the processing boundary.")
    st.stop()
if os.environ.get("SIGNGUARD_BACKEND") != "broker" or os.environ.get("SIGNGUARD_REQUIRE_AUTH") != "true":
    st.error("Fresh inspection requires authentication and the isolated private broker. No development parsing fallback is enabled by this dashboard.")
    st.stop()

st.subheader("Inspect a PDF")
st.caption("25 MiB per PDF · 50 pages · 5 MiB per optional image · 60 MiB combined input. Password-protected PDFs are unsupported.")
pdf = st.file_uploader("PDF to inspect (up to 25 MiB, 50 pages)", type="pdf", on_change=clear_report)
with st.expander("Optional comparison inputs"):
    baseline = st.file_uploader("Optional known baseline PDF", type="pdf", on_change=clear_report)
    candidate = st.file_uploader("Optional manual signature crop", type=["png", "jpg", "jpeg"], on_change=clear_report)
    reference = st.file_uploader("Optional reference signature crop", type=["png", "jpg", "jpeg"], on_change=clear_report)
if st.button("Analyze", disabled=pdf is None, type="primary"):
    clear_report()
    started = time.perf_counter()
    try:
        values = {"pdf": pdf.getvalue()}
        for name, item in (("baseline", baseline), ("signature_image", candidate), ("reference_image", reference)):
            if item is not None:
                values[name] = item.getvalue()
        validate_inputs(values)
        with st.status("Analyzing in a disposable isolated worker…", expanded=True) as progress:
            st.write("Input passed parser-free admission. Waiting for the private controller and disposable worker.")
            result = analyze_upload(values.pop("pdf"), principal=principal, **values)
            st.session_state.report = result
            st.session_state.report_latency = time.perf_counter()-started
            progress.update(label="Analysis returned — review findings and limitations", state="complete", expanded=False)
    except InputRejected as exc:
        st.error("Upload rejected: "+str(exc))
    except AnalysisServiceError as exc:
        st.error("Analysis could not complete: "+str(exc))
    except Exception:  # noqa: BLE001 -- keep parser/host/credential details out of the UI
        st.error("Analysis could not complete: unsupported input, worker limit, quota, or service configuration error.")

if "report" in st.session_state:
    st.divider()
    if "report_latency" in st.session_state:
        st.caption(f"Request round trip: {st.session_state.report_latency:.2f} seconds · includes service/worker startup")
    else:
        st.caption("Request timing is unavailable for this saved session result.")
    render_report(st.session_state.report, context="live")
