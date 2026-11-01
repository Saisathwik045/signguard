"""Keep hard integrity failures separate from heuristic evidence."""
import hashlib

from .audit import append_event
from .images import ela, orb_compare
from .pdf import compare_visual, inspect_pdf, signed_revision_comparisons


def fuse(structure, comparisons):
    reasons = []
    failed = any(s.get("intact") is False or s.get("valid") is False for s in structure["signatures"])
    unknown = (any(s.get("error") or s.get("coverage") not in {"ENTIRE_FILE", "ENTIRE_REVISION"}
                   or s.get("modification_level") == "OTHER" for s in structure["signatures"])
               or any(c.get("error") for c in comparisons))
    changed = any(p["changed_fraction"] > 0 for c in comparisons for p in c["pages"])
    if failed:
        reasons.append("Cryptographic integrity or signature verification failed")
    if changed:
        reasons.append("Rendered content differs from a signed revision or supplied baseline")
    if structure["incremental_updates"]:
        reasons.append("Incremental updates present; these may be legitimate")
    if unknown:
        reasons.append("At least one cryptographic check could not complete")
    verdict = "tampering_detected" if failed else "review_required" if changed or unknown else "inconclusive"
    if not reasons:
        reasons.append("No tampering indicators found by available checks; authenticity is not established")
    return {"verdict": verdict, "reasons": reasons}


def analyze_pdf(data, baseline=None, signature_image=None, reference_image=None, audit_path=None,
                trust_roots=None):
    structure = inspect_pdf(data, trust_roots)
    comparisons = signed_revision_comparisons(data)
    if baseline is not None:
        comparisons.append({"baseline": "user_supplied", "pages": compare_visual(baseline, data)})
    forensic = {}
    if signature_image is not None:
        forensic["ela"] = ela(signature_image)
        if reference_image is not None:
            forensic["orb"] = orb_compare(signature_image, reference_image)
    report = {"schema_version": 1, "sha256": hashlib.sha256(data).hexdigest(),
              "structure": structure, "visual_comparisons": comparisons, "image_forensics": forensic,
              "assessment": fuse(structure, comparisons)}
    if audit_path is not None:
        report["audit_head"] = append_event(audit_path, report)
    return report
