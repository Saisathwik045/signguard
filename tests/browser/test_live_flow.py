"""Real Chromium -> authenticated UI -> controller RPC -> disposable Docker worker."""
import base64
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import urllib.error
import urllib.request
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("SIGNGUARD_BROWSER_TESTS") != "1", reason="Explicit cloud browser job required")


@pytest.fixture(scope="module")
def cloud_stack():
    from playwright.sync_api import sync_playwright

    from benchmarks.generate import generate
    from tests.browser.stack import CloudStack
    artifacts = Path(os.environ.get("SIGNGUARD_BROWSER_ARTIFACTS", "browser-artifacts"))
    fixtures = artifacts / "fixtures"
    generate(fixtures, per_family=1)
    stack = CloudStack(artifacts)
    try:
        stack.start()
        with sync_playwright() as playwright:
            executable = os.environ.get("SIGNGUARD_CHROMIUM") or shutil.which("chromium")
            browser = playwright.chromium.launch(executable_path=executable, headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"])
            yield stack, browser, artifacts, fixtures
            browser.close()
    finally:
        stack.close()


@pytest.fixture
def signed_in(cloud_stack):
    from playwright.sync_api import expect
    stack, browser, _, _ = cloud_stack
    context = browser.new_context(accept_downloads=True, viewport={"width": 1280, "height": 1000})
    page = context.new_page()
    def record_failure(response):
        if response.status >= 400 and "/_stcore/" in response.url:
            from urllib.parse import urlsplit
            path = cloud_stack[2] / "http-errors.jsonl"
            with path.open("a") as stream:
                stream.write(json.dumps({"status": response.status, "path": urlsplit(response.url).path,
                                         "body": response.text()[:500]})+"\n")
    page.on("response", record_failure)
    page.goto(stack.url)
    page.get_by_label("Preview password").fill(stack.password)
    page.get_by_role("button", name="Sign in", exact=True).click()
    expect(page.get_by_role("button", name="Analyze", exact=True)).to_be_visible(timeout=20000)
    yield page
    context.close()


def test_01_authorization_and_session_denial(cloud_stack):
    from playwright.sync_api import expect
    stack, browser, artifacts, _ = cloud_stack
    context = browser.new_context(viewport={"width": 1280, "height": 1000})
    page = context.new_page(); page.goto(stack.url)
    expect(page.locator('input[type="file"]')).to_have_count(0)
    page.screenshot(path=str(artifacts / "01-unauthenticated.png"), full_page=True)
    page.get_by_label("Preview password").fill("incorrect-credential-for-test")
    page.get_by_role("button", name="Sign in", exact=True).click()
    expect(page.get_by_text("Access denied.", exact=False)).to_be_visible()
    expect(page.locator('input[type="file"]')).to_have_count(0)
    page.screenshot(path=str(artifacts / "02-denied.png"), full_page=True)
    context.close()


@pytest.mark.parametrize("family,verdict,classification", [
    ("genuine_signed", "Inconclusive", "cryptographic"),
    ("tampered_bytes", "Tampering Detected", "cryptographic"),
    ("shadow_reveal", "Review Required", "cryptographic"),
    ("visual_signature", "Inconclusive", "visual_candidate"),
    ("unsigned", "Inconclusive", "unsigned"),
])
def test_02_upload_evidence_and_downloads(cloud_stack, signed_in, family, verdict, classification):
    from playwright.sync_api import expect
    stack, _, artifacts, fixtures = cloud_stack
    page = signed_in
    page.locator('input[type="file"]').nth(0).set_input_files(str(fixtures / f"{family}-00.pdf"))
    page.get_by_role("button", name="Analyze", exact=True).click()
    expect(page.get_by_role("heading", name=verdict, exact=True)).to_be_visible(timeout=100000)
    expect(page.get_by_text("Classification: "+classification, exact=True)).to_be_visible()
    expect(page.locator('[data-testid="stImage"]').first).to_be_visible()
    page.screenshot(path=str(artifacts / f"03-{family}.png"), full_page=True)
    with page.expect_download() as download:
        page.get_by_role("button", name="Download JSON report", exact=True).click()
    media_url = download.value.url
    anonymous = signed_in.context.browser.new_context()
    try:
        assert anonymous.request.get(media_url).status == 403
    finally:
        anonymous.close()
    json_path = artifacts / f"{family}-report.json"
    download.value.save_as(str(json_path))
    report = json.loads(json_path.read_text())
    assert report["execution_controls"]["isolation"] == "docker_disposable"
    assert report["execution_controls"]["executor_boundary"] == "restricted_unix_rpc"
    assert report["visual_evidence"]
    if family == "shadow_reveal":
        assert any(v["label"] == "Signed revision snapshot" for v in report["visual_evidence"])
    for evidence in report["visual_evidence"]:
        assert base64.b64decode(evidence["base64"]).startswith(b"\x89PNG")
    page.wait_for_function("""() => {
        const images = [...document.querySelectorAll('[data-testid="stImage"] img')];
        return images.length && images.every(i => i.complete && i.naturalWidth > 0);
    }""")
    for index in range(len(report["visual_evidence"])):
        page.get_by_test_id("stImage").nth(index).screenshot(path=str(artifacts / f"03-{family}-evidence-{index}.png"))
    receipt = report.pop("audit_receipt")
    assert hashlib.sha256(json.dumps(report, sort_keys=True, separators=(",", ":")).encode()).hexdigest() == receipt["report_digest"]
    with page.expect_download() as download:
        page.get_by_role("button", name="Download PDF report", exact=True).click()
    pdf_path = artifacts / f"{family}-report.pdf"
    download.value.save_as(str(pdf_path))
    import pymupdf
    with pymupdf.open(pdf_path) as pdf:
        assert len(pdf) >= 2
        assert "SignGuard forensic triage report" in pdf[0].get_text()
    # Download reruns must preserve the verdict, rather than clearing the result.
    expect(page.get_by_role("heading", name=verdict, exact=True)).to_be_visible()
    assert stack.command("ps", "-a", "--filter", "name=signguard-job-", "--format", "{{.Names}}").stdout.strip() == ""
    if family == "unsigned":
        page.locator('input[type="file"]').nth(0).set_input_files(str(fixtures / "genuine_signed-00.pdf"))
        expect(page.get_by_role("button", name="Download JSON report")).to_have_count(0)


@pytest.mark.parametrize("kind", ["encrypted", "malformed"])
def test_03_unsupported_input(cloud_stack, signed_in, kind):
    from playwright.sync_api import expect
    _, _, artifacts, fixtures = cloud_stack
    if kind == "encrypted":
        signed_in.locator('input[type="file"]').nth(0).set_input_files(str(fixtures / "encrypted-00.pdf"))
    else:
        signed_in.locator('input[type="file"]').nth(0).set_input_files({"name": "malformed.pdf",
            "mimeType": "application/pdf", "buffer": b"%PDF-1.7\nnot-a-valid-PDF"})
    signed_in.get_by_role("button", name="Analyze", exact=True).click()
    expect(signed_in.get_by_role("heading", name="Unsupported document", exact=True)).to_be_visible(timeout=100000)
    with signed_in.expect_download() as item:
        signed_in.get_by_role("button", name="Download JSON report", exact=True).click()
    item.value.save_as(str(artifacts / f"{kind}-report.json"))
    report = json.loads(Path(item.value.path()).read_text())
    assert report["assessment"]["analysis_status"] == "unsupported"
    assert report["assessment"]["authenticity_established"] is False
    assert report["input_error"]["code"] == ("encrypted_pdf" if kind == "encrypted" else "malformed_pdf")
    assert report["execution_controls"]["isolation"] == "docker_disposable"
    expect(signed_in.get_by_role("button", name="Download PDF report")).to_have_count(0)
    signed_in.screenshot(path=str(artifacts / f"04-{kind}.png"), full_page=True)


def test_04_oversized_upload(cloud_stack, signed_in):
    from playwright.sync_api import expect
    _, _, artifacts, _ = cloud_stack
    signed_in.locator('input[type="file"]').nth(0).set_input_files({"name": "oversized.pdf",
        "mimeType": "application/pdf", "buffer": b"%PDF-1.7\n"+b"0"*(26*1024*1024)})
    expect(signed_in.get_by_text(re.compile(r"File must be.*25.*", re.IGNORECASE))).to_be_visible(timeout=15000)
    expect(signed_in.get_by_role("button", name="Analyze", exact=True)).to_be_disabled()
    signed_in.screenshot(path=str(artifacts / "05-oversized.png"), full_page=True)


def test_05_logout_clears_authorization(cloud_stack, signed_in):
    from playwright.sync_api import expect
    _, _, artifacts, fixtures = cloud_stack
    signed_in.locator('input[type="file"]').nth(0).set_input_files(str(fixtures / "unsigned-00.pdf"))
    signed_in.get_by_role("button", name="Analyze", exact=True).click()
    expect(signed_in.get_by_role("heading", name="Inconclusive", exact=True)).to_be_visible(timeout=100000)
    with signed_in.expect_download() as item:
        signed_in.get_by_role("button", name="Download JSON report", exact=True).click()
    url = item.value.url
    signed_in.get_by_role("link", name="Sign out", exact=True).click()
    expect(signed_in.get_by_label("Preview password")).to_be_visible()
    assert signed_in.request.get(url).status == 403
    expect(signed_in.locator('input[type="file"]')).to_have_count(0)
    signed_in.screenshot(path=str(artifacts / "06-signed-out.png"), full_page=True)


def test_06_private_controller_denial_load_and_audit(cloud_stack):
    from signguard.audit import verify_log
    from signguard.supervisor import encode_request
    stack, _, artifacts, fixtures = cloud_stack
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    payload = encode_request((fixtures / "unsigned-00.pdf").read_bytes())

    def request(token, payload_override=None):
        value = urllib.request.Request(stack.control_url+"/analyze", data=payload if payload_override is None else payload_override,
            headers={"Authorization": "Bearer "+token, "X-SignGuard-Principal": "load-probe", "Content-Type": "application/json"})
        try:
            with opener.open(value, timeout=100) as response:
                return response.status
        except urllib.error.HTTPError as exc:
            return exc.code

    assert request("incorrect-token") == 403
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        statuses = list(pool.map(request, [stack.token]*6))
    assert 200 in statuses and 429 in statuses
    # The same authenticated principal cannot reset its quota by opening new browser sessions.
    # Invalid authenticated requests consume quota too, without slow worker-start timing assumptions.
    for _ in range(12):
        statuses.append(request(stack.token, b"{}"))
    assert 429 in statuses[-6:]
    stack.command("cp", f"{stack.controller}:/var/lib/signguard/audit.jsonl", str(artifacts / "audit.jsonl"))
    head, count = verify_log(artifacts / "audit.jsonl")
    assert count >= 6
    (artifacts / "integration-results.json").write_text(json.dumps({"burst_and_quota_statuses": statuses,
        "audit_events": count, "audit_head": head, "audit_external_anchor": False,
        "worker_containers_remaining": stack.command("ps", "-a", "--filter", "name=signguard-job-", "--format", "{{.Names}}").stdout.strip()}, indent=2)+"\n")


def test_06b_renamed_nonpdf_is_rejected(cloud_stack, signed_in):
    from playwright.sync_api import expect
    _, _, artifacts, _ = cloud_stack
    signed_in.locator('input[type="file"]').nth(0).set_input_files({"name": "renamed.pdf",
        "mimeType": "application/pdf", "buffer": b"This is not a PDF despite its name."})
    signed_in.get_by_role("button", name="Analyze", exact=True).click()
    expect(signed_in.get_by_text("Upload rejected:", exact=False)).to_be_visible()
    expect(signed_in.get_by_role("button", name="Download JSON report")).to_have_count(0)
    signed_in.screenshot(path=str(artifacts / "06b-renamed-nonpdf.png"), full_page=True)


def test_07_broker_outage_fails_closed(cloud_stack, signed_in):
    from playwright.sync_api import expect
    stack, _, artifacts, fixtures = cloud_stack
    stack.command("stop", stack.controller)
    signed_in.locator('input[type="file"]').nth(0).set_input_files(str(fixtures / "unsigned-00.pdf"))
    signed_in.get_by_role("button", name="Analyze", exact=True).click()
    expect(signed_in.get_by_text("Analysis could not complete:", exact=False)).to_be_visible(timeout=30000)
    expect(signed_in.get_by_role("button", name="Download JSON report")).to_have_count(0)
    signed_in.screenshot(path=str(artifacts / "07-broker-down.png"), full_page=True)
