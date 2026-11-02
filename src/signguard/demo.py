"""Read-only synthetic catalogue. No parser, network client or execution backend."""
import hashlib
import json
from importlib.resources import files

CASES = {
    "genuine_signed": "Genuine cryptographically signed",
    "tampered": "Tampered signed bytes",
    "shadow_modified": "Shadow-modified signed document",
    "visual_only": "Visual-only signature",
    "unsigned": "Unsigned document",
}


def load_case(case_id):
    """Select fixed package resources by allowlisted ID; fail closed on missing/stale data."""
    if case_id not in CASES:
        raise ValueError("Unknown synthetic example")
    root = files("signguard").joinpath("demo_assets")
    manifest = json.loads(root.joinpath("manifest.json").read_text())
    entry = manifest["cases"][case_id]
    document = root.joinpath(case_id+".pdf").read_bytes()
    raw_report = root.joinpath(case_id+".json").read_bytes()
    if (hashlib.sha256(document).hexdigest() != entry["pdf_sha256"]
            or hashlib.sha256(raw_report).hexdigest() != entry["report_sha256"]):
        raise ValueError("Synthetic bundle integrity check failed")
    report = json.loads(raw_report)
    if (report["sha256"] != entry["pdf_sha256"]
            or report["execution_controls"].get("isolation") != "docker_disposable"
            or not report["execution_controls"].get("network_isolation")
            or not report.get("visual_evidence") or not report.get("pdf_report")):
        raise ValueError("Synthetic report provenance is incomplete")
    return report, {**entry, "worker_image_id": manifest["worker_image_id"],
                    "scope": "Bundled synthetic inputs; precomputed isolated-worker analysis"}
