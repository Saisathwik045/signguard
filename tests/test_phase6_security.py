"""Independent admission failures and a real isolated second-renderer check."""
import base64
import copy
import json
import os

import pytest

from scripts.verify_image_scan import verify


def clean_evidence():
    return {"CreatedAt": "2026-11-03T08:00:00Z", "Metadata": {"ImageID": "sha256:actual", "OS": {"Family": "ubuntu"}},
            "Results": [{"Class": "os-pkgs", "Packages": [{"Name": "python3", "Version": "3.14"}]}]}


def test_clean_image_does_not_approve_deployment():
    result = verify(clean_evidence(), {"image_id": "sha256:actual"})
    assert result["image_gate_passed"]
    assert result["deployment_readiness"] == "BLOCKED" and not result["external_ingress_enabled"]


def test_scan_for_another_image_is_rejected():
    with pytest.raises(ValueError, match="exact"):
        verify(clean_evidence(), {"image_id": "sha256:another"})


@pytest.mark.parametrize("level", ["CRITICAL", "HIGH"])
def test_any_runtime_or_python_high_finding_blocks(level):
    scan = clean_evidence()
    scan["Results"].append({"Class": "lang-pkgs", "Vulnerabilities": [{"Severity": level, "VulnerabilityID": "CVE-test"}]})
    with pytest.raises(ValueError, match="gate failed"):
        verify(scan, {"image_id": "sha256:actual"})


def test_original_cve_cannot_pass_by_changing_distro_severity():
    scan = clean_evidence()
    scan["Results"][0]["Vulnerabilities"] = [{"Severity": "LOW", "VulnerabilityID": "CVE-original"}]
    original = copy.deepcopy(scan)
    original["Results"][0]["Vulnerabilities"][0]["Severity"] = "CRITICAL"
    with pytest.raises(ValueError, match="original CVEs"):
        verify(scan, {"image_id": "sha256:actual"}, original)


def test_missing_os_inventory_is_not_a_zero_scan():
    scan = clean_evidence()
    scan["Results"] = []
    with pytest.raises(ValueError, match="inventory"):
        verify(scan, {"image_id": "sha256:actual"})


@pytest.mark.skipif(os.environ.get("SIGNGUARD_DOCKER_TESTS") != "1", reason="Explicit remote Docker job required")
def test_poppler_and_mupdf_inside_actual_isolated_worker():
    from signguard.container_runner import container_command
    from signguard.supervisor import Limits, run_limited
    from tests.fixtures import unsigned
    data = base64.b64encode(unsigned()).decode()
    program = ("import base64,json,importlib.util; from signguard.independent import inspect_independently; "
               "assert importlib.util.find_spec('pip') is None; "
               f"r=inspect_independently(base64.b64decode('{data}')); print(json.dumps(r))")
    image = os.environ.get("SIGNGUARD_WORKER_IMAGE", "signguard-worker:phase4")
    command = container_command(image, "signguard-phase6-poppler")
    output, _ = run_limited(command[:-1]+["--entrypoint", "python", image, "-c", program],
                            limits=Limits(memory=8*1024*1024*1024))
    result = json.loads(output)
    assert result["status"] == "completed" and result["page_count_agrees"]
    assert result["trust_validation"] == "disabled"
