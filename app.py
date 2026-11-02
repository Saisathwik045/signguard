"""Streamlit cloud interface. Uploaded documents are not persisted."""
import json

import streamlit as st

from signguard import analyze_pdf

st.set_page_config(page_title="SignGuard", page_icon="🛡️")
st.title("SignGuard")
st.caption("PDF signature integrity and visual tampering triage")
st.info("Visual similarity and compression artifacts cannot establish who signed a document. "
        "Certificate validation is offline; no trust roots are configured in this interface.")
pdf = st.file_uploader("PDF to inspect (up to 25 MiB, 50 pages)", type="pdf")
baseline = st.file_uploader("Optional known baseline PDF", type="pdf")
candidate = st.file_uploader("Optional manual crop override (automatic localization runs by default)", type=["png", "jpg", "jpeg"])
reference = st.file_uploader("Optional reference signature crop", type=["png", "jpg", "jpeg"])
if st.button("Analyze", disabled=pdf is None):
    try:
        with st.spinner("Checking signatures and rendered revisions…"):
            result = analyze_pdf(pdf.getvalue(), baseline=baseline.getvalue() if baseline else None,
                                 signature_image=candidate.getvalue() if candidate else None,
                                 reference_image=reference.getvalue() if reference else None)
        st.subheader(result["assessment"]["verdict"].replace("_", " ").title())
        for reason in result["assessment"]["reasons"]:
            st.write(reason)
        automatic = result["image_forensics"]["automatic"]
        st.write(f"Automatic candidate regions: {len(automatic['localization']['candidates'])}")
        st.caption("Candidate boxes are unverified regions in rotated page points. Logos and diagrams may appear.")
        st.json(result)
        st.download_button("Download evidence report", json.dumps(result, indent=2),
                           file_name="signguard-report.json", mime="application/json")
    except Exception as exc:  # noqa: BLE001 -- UI must surface parser failures
        st.error(f"Analysis could not complete: {type(exc).__name__}: {exc}")
