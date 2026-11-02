"""Explainable evidence fusion with cryptographic and heuristic findings separated."""
import hashlib

from .audit import append_event
from .images import ela, orb_compare
from .localization import automatic_forensics
from .pdf import analyze_revisions, compare_visual, inspect_pdf, signed_revision_comparisons


def fuse(structure, comparisons, revisions=None, automatic=None):
    revisions, automatic = revisions or [], automatic or {}
    findings = []

    def add(code, severity, evidence, explanation):
        findings.append({"code": code, "severity": severity, "evidence": evidence,
                         "explanation": explanation})

    failed = any(s.get("intact") is False or s.get("valid") is False for s in structure["signatures"])
    if failed:
        add("CRYPTOGRAPHIC_FAILURE", "critical", "structure.signatures",
            "Signed bytes or cryptographic signature failed verification")
    for comparison in comparisons:
        if comparison.get("error"):
            add("COMPARISON_UNSUPPORTED", "warning", comparison, "A signed revision could not be compared")
        elif any(p["changed_fraction"] > 0 or p.get("text_changed") for p in comparison["pages"]):
            add("REVISION_VISUAL_CHANGE", "warning", comparison,
                "Visible or extracted text content changed from a signed revision or supplied baseline")
            if "signed_revision" in comparison and any(s.get("intact") and s.get("valid")
                    and s["signed_revision"] == comparison["signed_revision"] for s in structure["signatures"]):
                add("POSSIBLE_SHADOW_ATTACK", "warning", comparison,
                    "Signed bytes remain valid while current appearance or text differs; "
                    "consistent with a shadow attack or a legitimate later modification")
    for signature in structure["signatures"]:
        if signature.get("error") or signature.get("coverage") not in {"ENTIRE_FILE", "ENTIRE_REVISION"}:
            add("SIGNATURE_CHECK_INCOMPLETE", "warning", signature,
                "Signature validation or full-revision coverage could not be established")
        if signature.get("modification_level") == "OTHER":
            # pyHanko is stricter than the narrow metadata allowlist: expose both judgments.
            subsequent = [r for r in revisions if r["revision"] > signature["signed_revision"]]
            metadata_only = bool(subsequent) and all(r["category"] == "metadata_only" for r in subsequent)
            add("SIGNATURE_POLICY_CHANGE", "info" if metadata_only else "warning", signature,
                "pyHanko could not justify subsequent changes under its modification policy"
                + ("; independent narrow allowlist found only metadata changes" if metadata_only else ""))
        if not signature.get("trusted"):
            add("CERTIFICATE_UNTRUSTED", "info", signature.get("field"),
                "Signer identity is not established by configured offline trust roots")
    has_signature = bool(structure["signatures"])
    for revision in revisions:
        if revision["category"] == "metadata_only":
            add("METADATA_ONLY_UPDATE", "info", {k: v for k, v in revision.items() if k != "pages"},
                "Only allowlisted metadata objects changed; rendering and text are unchanged")
        elif revision["category"] == "visible_content_change" and not has_signature:
            add("UNSIGNED_REVISION_CHANGE", "warning", revision,
                "Content changed between unsigned revisions; authorization cannot be determined")
        elif (revision["category"] == "visible_content_change" and has_signature
              and revision["revision"] > min(s["signed_revision"] for s in structure["signatures"])):
            add("POST_SIGNATURE_CONTENT_CHANGE", "warning", revision,
                "Content changed after signing, including any intermediate changes later restored")
        elif revision["category"] == "annotation_change":
            add("ANNOTATION_UPDATE", "warning", revision,
                "Only annotation appearance changed; it may be legitimate but can conceal content")
        elif revision["category"] == "nonvisual_structural_change":
            add("NONVISUAL_UPDATE", "info", {k: v for k, v in revision.items() if k != "pages"},
                "Objects changed without a visible difference; this does not establish benign intent")
    for copy in automatic.get("copy_candidates", []):
        add("REPEATED_VISUAL_REGION", "warning", copy,
            "Geometrically consistent visual reuse detected; legitimate reuse remains possible")
    localization = automatic.get("localization", {})
    incomplete = localization.get("truncated") or automatic.get("pair_limit_reached")
    if incomplete:
        add("FORENSIC_BUDGET_REACHED", "warning", "image_forensics.automatic",
            "Candidate or pair limit reached; analysis is partial")
    alert = any(f["severity"] in {"warning", "critical"} for f in findings)
    verdict = "tampering_detected" if failed else "review_required" if alert else "inconclusive"
    reasons = [f["explanation"] for f in findings] or [
        "No tampering indicators found by available checks; authenticity is not established"]
    unsupported = [f["code"] for f in findings if f["code"] in {
        "COMPARISON_UNSUPPORTED", "SIGNATURE_CHECK_INCOMPLETE", "FORENSIC_BUDGET_REACHED"}]
    return {"verdict": verdict, "alert": alert, "reasons": reasons, "findings": findings,
            "analysis_status": "partial" if unsupported else "completed",
            "unsupported_checks": unsupported, "authenticity_established": False}


def analyze_pdf(data, baseline=None, signature_image=None, reference_image=None, audit_path=None,
                trust_roots=None):
    structure = inspect_pdf(data, trust_roots)
    comparisons = signed_revision_comparisons(data)
    revisions = analyze_revisions(data)
    if baseline is not None:
        comparisons.append({"baseline": "user_supplied", "pages": compare_visual(baseline, data)})
    automatic = automatic_forensics(data, reference_image)
    forensic = {"automatic": automatic}
    if signature_image is not None:
        forensic["ela"] = ela(signature_image)
        if reference_image is not None:
            forensic["orb"] = orb_compare(signature_image, reference_image)
    if structure["classification"] == "unsigned" and automatic["localization"]["candidates"]:
        structure["classification"] = "visual_candidate"
        structure["classification_basis"] = "localized_nontext_ink"
    report = {"schema_version": 2, "sha256": hashlib.sha256(data).hexdigest(),
              "structure": structure, "revision_analysis": revisions,
              "visual_comparisons": comparisons, "image_forensics": forensic,
              "assessment": fuse(structure, comparisons, revisions, automatic)}
    if audit_path is not None:
        report["audit_head"] = append_event(audit_path, report)
    return report
