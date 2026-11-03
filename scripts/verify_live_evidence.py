"""Validate real cloud stack evidence; cannot establish external hosting or OIDC security."""
import argparse
import base64
import hashlib
import json
from pathlib import Path

from defusedxml import ElementTree

from signguard.audit import verify_log
from signguard.client import validate_broker_report

FAMILIES = ("genuine_signed", "tampered_bytes", "shadow_reveal", "visual_signature", "unsigned")


def verify(directory):
    directory = Path(directory)
    suites = ElementTree.parse(directory / "browser-junit.xml").getroot()
    cases = list(suites.iter("testcase"))
    if len(cases) < 13 or any(node.tag in {"failure", "error", "skipped"} for case in cases for node in case):
        raise ValueError("Incomplete live browser test evidence")
    stack = json.loads((directory / "stack.json").read_text())
    if stack["scope"] != "cloud_loopback_only" or stack["user_accessible_preview"] is not False:
        raise ValueError("Unexpected deployment-scope claim")
    head, count = verify_log(directory / "audit.jsonl")
    records = {record["hash"]: record["event"] for record in
               (json.loads(line) for line in (directory / "audit.jsonl").read_text().splitlines())}
    reports = []
    for family in (*FAMILIES, "encrypted", "malformed"):
        report = json.loads((directory / f"{family}-report.json").read_text())
        validate_broker_report(report)
        controls = report["execution_controls"]
        if controls.get("worker_image_id") != stack["worker_image_id"]:
            raise ValueError("Report does not bind the actual tested worker image")
        receipt = report["audit_receipt"]
        event = records[receipt["head"]]
        if (event["report_digest"] != receipt["report_digest"] or event["input_sha256"] != report["sha256"]
                or event["request_id"] != report["request_id"] or len(event["principal_sha256"]) != 64):
            raise ValueError("Report is not bound to its audit record")
        if report["assessment"]["authenticity_established"] is not False:
            raise ValueError("Unexpected authenticity assertion")
        if family in FAMILIES:
            pdf = (directory / f"{family}-report.pdf").read_bytes()
            if pdf != base64.b64decode(report["pdf_report"]["base64"], validate=True):
                raise ValueError("Downloaded PDF does not match report")
            if not report["visual_evidence"] or any(not base64.b64decode(item["base64"], validate=True).startswith(
                    b"\x89PNG\r\n\x1a\n") for item in report["visual_evidence"]):
                raise ValueError("Missing PNG evidence")
            for index in range(len(report["visual_evidence"])):
                screenshot = directory / f"03-{family}-evidence-{index}.png"
                if not screenshot.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("Missing real browser evidence screenshot")
        elif report["assessment"]["analysis_status"] != "unsupported":
            raise ValueError("Unsupported fixture classified as supported")
        reports.append({"family": family, "analysis_status": report["assessment"]["analysis_status"],
                        "report_file_sha256": hashlib.sha256((directory / f"{family}-report.json").read_bytes()).hexdigest()})
    result = {"browser_tests_passed": len(cases), "reports_verified": reports, "audit_events": count,
              "audit_head": head, "worker_image_id": stack["worker_image_id"],
              "scope": "cloud_loopback_only", "external_staging_verified": False,
              "tls_verified": False, "production_oidc_verified": False,
              "ui_filesystem_isolated": stack["ui_filesystem_isolated"], "production_ready": False}
    (directory / "live-verification.json").write_text(json.dumps(result, indent=2)+"\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    print(json.dumps(verify(parser.parse_args().directory), indent=2))
