"""Real browser smoke test of the synthetic viewer, without external ingress."""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from signguard.demo import CASES, load_case
from tests.browser.stack import free_port

pytestmark = pytest.mark.skipif(os.environ.get("SIGNGUARD_DEMO_BROWSER") != "1",
                                reason="Explicit remote Chromium demo job required")
ROOT = Path(__file__).resolve().parents[2]


def test_synthetic_demo_real_browser(tmp_path):
    from playwright.sync_api import expect, sync_playwright
    artifacts = Path(os.environ.get("SIGNGUARD_DEMO_ARTIFACTS", str(ROOT / "demo-artifacts")))
    artifacts.mkdir(exist_ok=True)
    port = free_port()
    url = f"http://127.0.0.1:{port}"
    container = os.environ.get("SIGNGUARD_DEMO_CONTAINER") == "1"
    name = "sg-synthetic-browser-"+str(port)
    with (artifacts / "streamlit.log").open("w") as log:
        command = [sys.executable, "-m", "streamlit", "run", "synthetic_demo.py",
            "--server.address=127.0.0.1", f"--server.port={port}", "--browser.gatherUsageStats=false"]
        # Explicit cloud CI opt-in; always publish only to cloud loopback, never external ingress.
        if container:
            command = ["docker", "--host=unix:///var/run/docker.sock", "run", "-d", "--rm", "--name", name,
                "--publish", f"127.0.0.1:{port}:8501", "--read-only", "--cap-drop=ALL",
                "--security-opt=no-new-privileges", "--memory=512m", "--cpus=1", "--pids-limit=64",
                "--tmpfs=/tmp:rw,noexec,nosuid,size=32m", "--env=HTTP_PROXY=", "--env=HTTPS_PROXY=",
                "--env=ALL_PROXY=", "signguard-demo:synthetic"]
        process = subprocess.Popen(command, cwd=ROOT,
            env={"PATH": os.environ["PATH"], "LANG": "C.UTF-8", "PYTHONPATH": str(ROOT / "src")}, stdout=log, stderr=log)
        try:
            if container:
                # VFS creation is slow in nested cloud Docker: await creation before health polling/cleanup.
                process.wait(timeout=180)
                if process.returncode:
                    raise RuntimeError("Synthetic viewer container failed to start")
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for _ in range(120):
                try:
                    opener.open(url+"/_stcore/health", timeout=1).close()
                    break
                except OSError:
                    time.sleep(.5)
            else:
                raise RuntimeError("Synthetic viewer health deadline exceeded")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=os.environ.get("SIGNGUARD_CHROMIUM_PATH"))
                page = browser.new_page(accept_downloads=True, viewport={"width": 1440, "height": 1800})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)) if len(errors) < 100 else None)
                page.on("console", lambda message: errors.append(message.text) if message.type == "error" and len(errors) < 100 else None)
                try:
                    page.goto(url)
                    expect(page.get_by_role("heading", name="SignGuard synthetic demonstration", exact=True)).to_be_visible(timeout=60000)
                    for case_id, label in CASES.items():
                        page.get_by_role("combobox").click()
                        page.get_by_role("combobox").fill(label)
                        page.get_by_role("option", name=label, exact=True).click()
                        expect(page.get_by_text("Report shown: "+label, exact=True)).to_be_visible()
                        with page.expect_download() as sample:
                            page.get_by_role("button", name="Download sample PDF", exact=True).click()
                        import hashlib
                        assert hashlib.sha256(Path(sample.value.path()).read_bytes()).hexdigest() == load_case(case_id)[1]["pdf_sha256"]
                        page.get_by_role("tab", name="Visual evidence", exact=True).click()
                        expect(page.get_by_test_id("stImage").first).to_be_visible()
                        assert page.locator('input[type="file"]').count() == 0
                        page.wait_for_function("""() => {
                            const images = [...document.querySelectorAll('[data-testid="stImage"] img')];
                            return images.length > 0 && images.every(i => i.complete && i.naturalWidth > 0);
                        }""")
                        page.screenshot(path=str(artifacts / (case_id+"-evidence.png")), full_page=True)
                        page.get_by_role("tab", name="Reports", exact=True).click()
                        with page.expect_download() as download:
                            page.get_by_role("button", name="Download JSON report").click()
                        report = json.loads(Path(download.value.path()).read_text())
                        raw = Path(download.value.path()).read_bytes()
                        assert hashlib.sha256(raw).hexdigest() == load_case(case_id)[1]["report_sha256"]
                        assert download.value.suggested_filename == f"signguard-demo-{case_id}.json"
                        assert report["sha256"] == load_case(case_id)[0]["sha256"]
                        assert report["execution_controls"]["isolation"] == "docker_disposable"
                        with page.expect_download() as download:
                            page.get_by_role("button", name="Download PDF report").click()
                        import base64
                        assert Path(download.value.path()).read_bytes() == base64.b64decode(load_case(case_id)[0]["pdf_report"]["base64"])
                        page.get_by_role("tab", name="Findings", exact=True).click()
                        page.get_by_role("heading", name="SignGuard synthetic demonstration", exact=True).scroll_into_view_if_needed()
                        page.screenshot(path=str(artifacts / (case_id+".png")), full_page=True)
                    from signguard.dashboard import PAGES
                    for section in PAGES[1:]:
                        page.get_by_test_id("stSidebar").get_by_text(section, exact=True).click()
                        expect(page.get_by_role("heading", name={
                            "Project overview": "SignGuard project overview",
                            "Evaluation": "Evaluation & known limitations",
                            "Architecture & security": "Architecture & security",
                            "Presentation guide": "Presentation guide",
                        }[section], exact=True)).to_be_visible()
                        expect(page.get_by_text({
                            "Project overview": "What this project does not prove",
                            "Evaluation": "Evidence source and exact measured data",
                            "Architecture & security": "Private Streamlit hosting does not qualify the forensic worker architecture. Arbitrary hosted uploads remain blocked until identity, TLS, executor, quotas, audit, scans and operations gates pass.",
                            "Presentation guide": "1 minute · Live readiness and failure",
                        }[section], exact=True)).to_be_visible()
                        if section == "Evaluation":
                            expect(page.get_by_text("Two explicit modes", exact=True)).not_to_be_visible()
                            expect(page.get_by_role("heading", name="Confusion matrix", exact=True)).to_be_visible()
                        assert page.get_by_test_id("stException").count() == 0
                        assert page.locator('input[type="file"]').count() == 0
                        page.screenshot(path=str(artifacts / (section.split()[0].lower()+".png")), full_page=True)
                except Exception:
                    page.screenshot(path=str(artifacts / "failure.png"), full_page=True)
                    (artifacts / "failure-page.txt").write_text(page.locator("body").inner_text())
                    (artifacts / "failure-browser-errors.json").write_text(json.dumps(errors))
                    raise
                browser.close()
            (artifacts / "scope.json").write_text(json.dumps({"scope": "cloud_loopback_only",
                "deployed_external_url": None, "cases": list(CASES), "uploads_enabled": False,
                "runtime": "nonroot_readonly_container" if container else "cloud_process"}, indent=2)+"\n")
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            if container:
                subprocess.run(["docker", "--host=unix:///var/run/docker.sock", "logs", name],
                               check=False, stdout=log, stderr=log)
                subprocess.run(["docker", "--host=unix:///var/run/docker.sock", "rm", "-f", name],
                               check=False, capture_output=True)
