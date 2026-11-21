"""Parser-free presentation shared by the inspection UI and synthetic gallery."""
import base64
import json
from importlib.resources import files

import streamlit as st

PAGES = ("Demo gallery", "Project overview", "Evaluation", "Architecture & security", "Presentation guide")
CASE_NOTES = {
    "genuine_signed": "Signed bytes are intact, but certificate identity is untrusted. Integrity is not proof of who signed.",
    "tampered": "The signed PDF header changed. The page can look identical while signed-byte integrity fails. No red visual region is required.",
    "shadow_modified": "A later revision reveals previously hidden content. Compare current and signed snapshots; this finding does not establish malicious intent.",
    "visual_only": "An uncertain visual signature candidate is present without a digital signature. Authorship and permission to reuse it remain unknown.",
    "unsigned": "No cryptographic signature is present. Inconclusive is an abstention, not a certificate of authenticity.",
}


def configure(mode):
    st.set_page_config(page_title="SignGuard · Evidence workspace", page_icon="🛡️", layout="wide")
    st.markdown("""<style>
    .stApp {background:#0b1620;color:#e5edf3}
    [data-testid="stHeader"] {background:#0b1620}
    h1,h2,h3 {letter-spacing:-.025em}
    [data-testid="stMetric"] {border:1px solid #29434f;border-radius:12px;padding:14px;background:#112331}
    [data-testid="stMetricValue"] {font-size:1.45rem}
    [data-testid="stMetricValue"] > div {white-space:normal;overflow-wrap:anywhere}
    .stButton button[kind="primary"] {background:#55d6bd;color:#071a21;border:0}
    [data-testid="stSidebar"] {background:#10232e}
    </style>""", unsafe_allow_html=True)
    st.sidebar.markdown("## SignGuard")
    st.sidebar.caption("PDF SIGNATURE & INTEGRITY LAB")
    st.sidebar.info("Saved synthetic results" if mode == "synthetic" else "Private inspection workspace")
    st.sidebar.caption("Integrity · revisions · visual evidence · audit")
    st.sidebar.caption("₹0 policy · no paid infrastructure")


def navigation(mode):
    return st.sidebar.radio("Workspace", PAGES if mode == "synthetic" else ("Inspect document", *PAGES))


def _state(value):
    return "Pass" if value is True else "Fail" if value is False else "Not established"


def render_report(report, *, context="live", raw_json=None, provenance=None, key="report", filename="signguard-report"):
    assessment = report["assessment"]
    structure = report["structure"]
    signatures = structure.get("signatures", [])
    unsupported = assessment.get("analysis_status") == "unsupported"
    st.subheader("Unsupported document" if unsupported else assessment["verdict"].replace("_", " ").title())
    st.caption("Classification: "+structure.get("refined_classification", structure.get("classification", "unknown")))
    if context == "synthetic":
        st.info("Saved worker-generated result. Selecting a case does not run a new analysis.")
    metrics = st.columns(4)
    integrity = "No signatures" if not signatures else (
        "Fail" if any(s.get("intact") is False for s in signatures) else
        "Pass" if all(s.get("intact") is True for s in signatures) else "Not established")
    for column, label, value in zip(metrics,
            ("Analysis coverage", "Digital signatures", "Signed-byte integrity", "Signer identity"),
            (assessment.get("analysis_status", "unknown").title(), len(signatures), integrity, "Not established"), strict=True):
        column.metric(label, value)
    st.caption("Integrity, certificate trust and permission to modify are separate questions. ELA and ORB are not forgery probabilities.")
    for reason in assessment.get("reasons", []):
        st.text(reason)
    if any(s.get("intact") is False for s in signatures):
        st.warning("Signed-byte integrity failed. A byte change can leave the page looking unchanged; visual differences are a separate check.")
    sections = st.tabs(["Findings", "Visual evidence", "Cryptography", "Revision timeline", "Reports", "Processing & audit"])
    with sections[0]:
        findings = assessment.get("findings", [])
        if not findings:
            st.info("No finding was reported by the available checks. This does not establish authenticity.")
        for finding in findings:
            with st.container(border=True):
                st.text(str(finding.get("severity", "info")).upper()+" · "+str(finding.get("code", "FINDING")).replace("_", " "))
                st.text(finding.get("explanation", "No explanation supplied"))
                with st.expander("Supporting evidence"):
                    st.json(finding.get("evidence"))
        if assessment.get("unsupported_checks"):
            st.warning("Incomplete checks: "+", ".join(assessment["unsupported_checks"]))
    with sections[1]:
        st.caption("Existing worker-rendered PNGs. Use the image fullscreen control to inspect details. Blue: uncertain candidate. Red: changed region.")
        evidence = report.get("visual_evidence", [])
        if not evidence:
            st.info("No image is available. Unsupported inputs do not receive invented previews.")
        columns = st.columns(2)
        for index, item in enumerate(evidence):
            with columns[index % 2]:
                st.text(item["label"])
                st.image(base64.b64decode(item["base64"], validate=True),
                         caption=f"{item['label']} — page {item['page']}", width="stretch")
        comparisons = [p for c in report.get("visual_comparisons", []) for p in c.get("pages", [])]
        if comparisons:
            st.dataframe([{"Page": p["page"], "Changed pixels (%)": round(p["changed_fraction"]*100, 4),
                           "Text changed": p.get("text_changed", False), "Annotation only": p.get("annotation_only", False)}
                          for p in comparisons], hide_index=True, width="stretch")
        st.caption("Mostly blank source pages are displayed faithfully. The viewer does not invent handwriting, highlights or missing evidence.")
        st.markdown("### Automatic visual triage")
        automatic = report.get("image_forensics", {}).get("automatic", {})
        localization = automatic.get("localization", {})
        candidates = localization.get("candidates", [])
        if automatic:
            st.write(f"Candidate regions: {len(candidates)} · Reuse pairs checked: {automatic.get('pairs_checked', 0)}")
            st.caption("Localization: "+localization.get("status", "unavailable")+" · Candidates are unverified visual regions, not identified signers.")
            if candidates:
                st.dataframe([{"Candidate": c.get("id"), "Page": c.get("page"),
                               "Bounds (page points)": str(c.get("bbox")),
                               "Uncertainty": c.get("uncertainty", "unverified"),
                               "Source": c.get("source", "unavailable")} for c in candidates], hide_index=True, width="stretch")
            residuals = [{"Candidate": c.get("candidate_id"), "ELA applicability": c["ela"].get("status"),
                          "Mean residual": c["ela"].get("mean_error"), "Maximum residual": c["ela"].get("max_error")}
                         for c in automatic.get("candidates", []) if c.get("ela")]
            if residuals:
                st.dataframe(residuals, hide_index=True, width="stretch")
                st.warning("Rendered PDF pixels do not preserve original JPEG compression history. ELA residuals here are descriptive and cannot establish forgery.")
            st.caption("ORB reuse evidence cannot establish who signed or whether copying was authorized. No matching proposal is not proof of no reuse.")
            with st.expander("Recorded localization, ELA and reuse evidence"):
                st.json(report["image_forensics"])
        else:
            st.info("Visual-triage measurements are unavailable for this result.")
    with sections[2]:
        if not signatures:
            st.info("No embedded cryptographic signature was found. A visible mark cannot substitute for one.")
        for signature in signatures:
            st.text("Signature field: "+signature.get("field", "Unnamed"))
            checks = [
                ("Signed-byte integrity", _state(signature.get("intact"))),
                ("Cryptographic signature mathematics", _state(signature.get("valid"))),
                ("Certificate trusted", "Trusted" if signature.get("trusted") is True else "Not established"),
                ("Coverage", str(signature.get("coverage", "Not established"))),
                ("Signed revision", str(signature.get("signed_revision", "Unknown"))),
                ("Modification policy", str(signature.get("modification_level", "Unknown"))),
                ("Trust mode", str(signature.get("trust_mode", "Unknown"))),
                ("Revocation", str(signature.get("revocation_state", "Not established"))),
            ]
            st.dataframe([{"Check": label, "Result": value} for label, value in checks], hide_index=True, width="stretch")
            st.caption("Certificate identity details beyond these recorded fields are unavailable. No certificate information is invented.")
    with sections[3]:
        revisions = report.get("revision_analysis", [])
        if not revisions:
            st.info("No incremental revision findings were recorded.")
        for revision in revisions:
            with st.container(border=True):
                st.text(f"Revision {revision['revision']} · {revision['category'].replace('_', ' ')}")
                st.text(revision.get("interpretation", "Review document context and signature policy."))
                st.caption(f"Changed objects: {revision.get('changed_objects', 'unknown')} · Freed objects: {revision.get('freed_objects', 'unknown')}")
                if revision.get("active_content_keys"):
                    st.warning("Active content: "+", ".join(revision["active_content_keys"]))
                if revision.get("pages"):
                    st.dataframe([{"Page": p["page"], "Changed pixels (%)": round(p["changed_fraction"]*100, 4),
                                   "Text changed": p.get("text_changed", False)} for p in revision["pages"]], hide_index=True)
    with sections[4]:
        st.markdown("### Download the analysis")
        st.caption("These buttons download actual reports. Browser Print only exports the interface layout.")
        st.download_button("Download JSON report", raw_json if raw_json is not None else json.dumps(report, indent=2),
                           file_name=filename+".json", mime="application/json", key=key+"-json", on_click="ignore")
        if report.get("pdf_report"):
            st.download_button("Download PDF report", base64.b64decode(report["pdf_report"]["base64"], validate=True),
                               file_name=filename+".pdf", mime="application/pdf", key=key+"-pdf", on_click="ignore")
        else:
            st.info("No PDF report is available. Download JSON for the structured unsupported reason.")
        st.caption("Input PDF SHA-256")
        st.code(report.get("sha256", "Unavailable"), language=None)
    with sections[5]:
        if context == "synthetic":
            st.warning("These controls describe historical report generation, not the current Streamlit hosting environment.")
        controls = report.get("execution_controls", {})
        if controls:
            st.dataframe([{"Control": k.replace("_", " "), "Recorded value": str(v)} for k, v in controls.items()], hide_index=True)
        else:
            st.info("Execution controls are not attested by this report.")
        if report.get("worker_measurements"):
            st.caption("Worker measurements"+(" · historical" if context == "synthetic" else ""))
            st.json(report["worker_measurements"])
        if report.get("audit_receipt"):
            st.markdown("**Controller audit receipt**")
            st.json(report["audit_receipt"])
            st.caption("The local chain still requires a trusted external anchor and durable recovery policy.")
        else:
            st.info("No controller audit receipt is present. A synthetic snapshot does not invent one.")
        if provenance:
            st.markdown("**Snapshot provenance**")
            st.json(provenance)
        with st.expander("Complete technical report"):
            st.json({k: v for k, v in report.items() if k not in {"visual_evidence", "pdf_report"}})


def render_gallery():
    from .demo import CASES, load_case, load_downloads
    st.title("SignGuard synthetic demonstration")
    st.write("Explore what the forensic engine found—and why it matters.")
    st.caption("Five fixed examples · precomputed results · no upload or live-analysis backend")
    case_id = st.selectbox("Synthetic example", list(CASES), format_func=CASES.get)
    try:
        report, provenance = load_case(case_id)
        document, raw_report = load_downloads(case_id)
    except (OSError, ValueError, KeyError):
        st.error("The verified synthetic bundle is unavailable. No analysis fallback is permitted.")
        return
    with st.container(border=True):
        st.markdown("**Case brief**")
        st.write(CASE_NOTES[case_id])
        st.caption(f"Bundled sample: {len(document)/1024:.1f} KiB · Result generated: {provenance.get('generated_at', 'historical; see manifest')}")
        st.download_button("Download sample PDF", document, file_name=case_id+".pdf", mime="application/pdf", on_click="ignore")
    render_report(report, context="synthetic", raw_json=raw_report, provenance=provenance,
                  key="gallery-"+case_id, filename="signguard-demo-"+case_id)
    st.caption("Report shown: "+CASES[case_id])


def evaluation_data():
    return json.loads(files("signguard").joinpath("dashboard_assets", "evaluation.json").read_text())


def render_evaluation():
    st.title("Evaluation & known limitations")
    data = evaluation_data()
    st.info(data["scope"]+". Measured "+data["measured_date"]+".")
    st.write("360 synthetic inputs; three splits; 24 construction families. Template IDs and document hashes differ across splits; concepts and generator families are shared.")
    population = st.radio("Scoring population", ["All cases, including unsupported", "Supported alert cases"], horizontal=True)
    metric = "all_alert" if population.startswith("All") else "supported_alert"
    rows = []
    for record in data["splits"]:
        values = record["summary"][metric]
        rows.append({"Split": record["split"], "Inputs": values["n"],
                     **{name.title()+" (%)": round(values[name]*100, 2) for name in ("accuracy", "precision", "recall", "f1")},
                     **{name.upper(): values[name] for name in ("tp", "tn", "fp", "fn")}})
    st.dataframe(rows, hide_index=True, width="stretch")
    st.bar_chart(rows, x="Split", y=["Accuracy (%)", "Recall (%)", "F1 (%)"], stack=False, height=260)
    st.warning("Unsupported inputs remain in the all-case denominator. No alert or an explicit error is not proof of authenticity. Supported-only scores exclude ambiguous/unsupported cases.")
    selected = st.selectbox("Inspect split", [r["split"] for r in data["splits"]], index=2)
    record = next(r for r in data["splits"] if r["split"] == selected)
    summary = record["summary"]
    counts = summary[metric]
    st.markdown("### Confusion matrix")
    st.dataframe([{"Actual": "Negative", "Predicted no alert": counts["tn"], "Predicted alert": counts["fp"]},
                  {"Actual": "Positive", "Predicted no alert": counts["fn"], "Predicted alert": counts["tp"]}], hide_index=True)
    st.markdown("### Localization and runtime")
    localization = summary["localization"]
    for column, label in zip(st.columns(3), ("precision", "recall", "f1"), strict=True):
        column.metric("Localization "+label, f"{localization[label]*100:.2f}%")
    st.dataframe([{"True proposals": localization["tp"], "False proposals": localization["fp"],
                   "Missed regions": localization["fn"]}], hide_index=True)
    timings = summary["seconds"]
    for column, label, value in zip(st.columns(3),
            ("Median analysis", "P95 analysis", "Process high-water RSS"),
            (f"{timings['median']:.4f} s", f"{timings['p95']:.4f} s", f"{summary['process_high_water_rss_mib']:.2f} MiB"), strict=True):
        column.metric(label, value)
    st.caption("Timings exclude generation and worker cold start. RSS is cumulative process high-water memory, not a per-document peak.")
    st.write("Holdout localization includes false proposals on stamps and scanned text. Ambiguous reuse can escape alerts. One renderer cannot cover every shadow attack. Real-world handwriting identity accuracy is not established.")
    st.caption("Dependency-upgrade revalidation is not a second untouched holdout. Later admission changes mean today's full source fingerprint differs from the historical source seal.")
    with st.expander("Evidence source and exact measured data"):
        st.json(record)


def render_security(mode):
    st.title("Architecture & security")
    st.write("Signed-byte integrity, revision changes and visual reuse answer different questions. SignGuard does not establish handwriting identity or permission to reuse a signature.")
    st.code("Allowed user → authenticated gateway → Streamlit UI\n  → private controller → restricted Unix RPC executor\n  → disposable PDF worker → bounded evidence + reports\nController → fsynced audit journal → external anchor (deployment gate)", language=None)
    if mode == "synthetic":
        st.info("This online gallery serves saved synthetic reports only. It has no arbitrary document input or worker authority.")
    st.dataframe([
        {"Boundary": "Identity", "Implemented": "Preview gateway; prepared OIDC/GitHub OAuth owner modes", "Remaining qualification": "Actual-origin login, denial, expiry and logout"},
        {"Boundary": "Worker", "Implemented": "Non-root, no network, read-only root, bounded CPU/memory/PIDs/time/output", "Remaining qualification": "Actual host and current exact-image scans"},
        {"Boundary": "Audit", "Implemented": "Fsynced chain and receipts; fail closed on audit failure", "Remaining qualification": "Durable retention, external anchors and recovery"},
        {"Boundary": "Cost", "Implemented": "₹0 policy; gated CI; no paid fallback", "Remaining qualification": "Account entitlements and a qualified free live runtime"},
    ], hide_index=True, width="stretch")
    st.warning("Private Streamlit hosting does not qualify the forensic worker architecture. Arbitrary hosted uploads remain blocked until identity, TLS, executor, quotas, audit, scans and operations gates pass.")
    st.write("The live pipeline does not retain raw uploads by default. Downloaded reports can contain sensitive evidence. Historical synthetic snapshots are bundled intentionally. No real documents or service secrets belong in GitHub or screenshots.")


def render_overview():
    st.title("SignGuard project overview")
    st.write("An Information Security project for explainable PDF signature integrity and visual tampering triage.")
    st.markdown("### The problem")
    st.write("A PDF can contain valid signed bytes and still have a changed current appearance. A drawn signature can be copied legitimately or without permission. These are different kinds of evidence, not a single authenticity score.")
    st.dataframe([
        {"Capability": "Cryptographic verification", "Evidence": "Signed-byte integrity, CMS validity, coverage and offline trust"},
        {"Capability": "Revision forensics", "Evidence": "Xref history, signed/current comparisons, metadata and annotation attribution"},
        {"Capability": "Visual triage", "Evidence": "Uncertain candidate localization, descriptive ELA and geometric ORB reuse"},
        {"Capability": "Secure processing", "Evidence": "Bounded admission, restricted executor, disposable workers and audit receipts"},
        {"Capability": "Evaluation", "Evidence": "Reproducible synthetic splits with errors, abstentions and false proposals retained"},
    ], hide_index=True, width="stretch")
    st.markdown("### Two explicit modes")
    st.write("Demo gallery presents saved worker results. The main project's Inspect document workflow requests fresh analysis through its authenticated private backend when qualified and explicitly enabled. This online gallery cannot perform that workflow.")
    st.markdown("### What this project does not prove")
    st.write("No handwriting identity recognition, forgery probability, guaranteed attack coverage, or field-accuracy claim. Container functional tests and historical clean scans do not certify a new production host.")


def render_guide():
    st.title("Presentation guide")
    st.write("A seven-minute walkthrough of implementation, evidence and limitations.")
    steps = [
        ("1 minute · Problem and architecture", "Explain integrity, revisions and visual reuse as different questions. Identify the UI/controller/executor/worker boundaries."),
        ("2 minutes · Three contrasting cases", "Compare genuine signed bytes with the tampered-header case, then the signed/current shadow snapshots. Invisible tampering need not have a red image box."),
        ("1 minute · Unsupported claims", "Show visual-only and unsigned cases. Explain inconclusive, untrusted identity and legitimate reuse."),
        ("1 minute · Reproducible evidence", "Download the sample and exact JSON/PDF. Show input hash, worker identity and whether a controller receipt exists."),
        ("1 minute · Evaluation", "Compare supported-only and all-case populations. Discuss false proposals, ambiguous reuse and synthetic-data limits."),
        ("1 minute · Live readiness and failure", "On a qualified private stack, analyze a synthetic input and an unsupported input. Explain fail-closed handling. Without that runtime, label this step unexecuted; never present a snapshot as fresh execution."),
    ]
    for title, text in steps:
        with st.container(border=True):
            st.markdown("**"+title+"**")
            st.write(text)


def render_page(page, mode):
    if page == "Demo gallery":
        render_gallery()
    elif page == "Project overview":
        render_overview()
    elif page == "Evaluation":
        render_evaluation()
    elif page == "Architecture & security":
        render_security(mode)
    elif page == "Presentation guide":
        render_guide()
