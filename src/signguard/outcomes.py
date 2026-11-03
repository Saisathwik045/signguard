"""Safe structured unsupported results; never an authenticity assertion."""
import hashlib


def unsupported_report(pdf, error):
    return {"schema_version": 3, "sha256": hashlib.sha256(pdf).hexdigest(),
            "structure": {"classification": "unsupported", "refined_classification": "unsupported", "signatures": []},
            "revision_analysis": [], "visual_comparisons": [], "visual_evidence": [],
            "image_forensics": {"automatic": {"localization": {"candidates": [], "limitations": [str(error)]}}},
            "assessment": {"analysis_status": "unsupported", "verdict": "inconclusive", "alert": False,
                "authenticity_established": False, "identity_decision": "abstain",
                "authorization_decision": "inconclusive", "unsupported_checks": [error.code],
                "reasons": [str(error)], "findings": [{"code": error.code.upper(), "severity": "info",
                    "evidence": "input_validation", "explanation": str(error)}]},
            "input_error": {"code": error.code, "message": str(error)}}
