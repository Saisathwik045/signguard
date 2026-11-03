"""Real browser smoke test of the synthetic viewer, without external ingress."""
import contextlib
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
    artifacts = ROOT / "demo-artifacts"
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
            env={"PATH": os.environ["PATH"], "LANG": "C.UTF-8"}, stdout=log, stderr=log)
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
                page.goto(url)
                for case_id, label in CASES.items():
                    page.get_by_role("combobox").click()
                    page.get_by_role("combobox").fill(label)
                    page.get_by_role("option", name=label, exact=True).click()
                    expect(page.get_by_text("Report shown: "+label, exact=True)).to_be_visible()
                    expect(page.get_by_role("button", name="Download JSON report")).to_be_visible()
                    expect(page.get_by_test_id("stImage").first).to_be_visible()
                    assert page.locator('input[type="file"]').count() == 0
                    with page.expect_download() as download:
                        page.get_by_role("button", name="Download JSON report").click()
                    report = json.loads(Path(download.value.path()).read_text())
                    assert download.value.suggested_filename == f"signguard-demo-{case_id}.json"
                    assert report["sha256"] == load_case(case_id)[0]["sha256"]
                    assert report["execution_controls"]["isolation"] == "docker_disposable"
                    with page.expect_download() as download:
                        page.get_by_role("button", name="Download PDF report").click()
                    assert Path(download.value.path()).read_bytes().startswith(b"%PDF-")
                    page.get_by_role("heading", name="SignGuard synthetic demonstration", exact=True).scroll_into_view_if_needed()
                    page.wait_for_function("""() => {
                        const images = [...document.querySelectorAll('[data-testid="stImage"] img')];
                        return images.length > 0 && images.every(i => i.complete && i.naturalWidth > 0);
                    }""")
                    page.screenshot(path=str(artifacts / (case_id+".png")), full_page=True)
                browser.close()
            (artifacts / "scope.json").write_text(json.dumps({"scope": "cloud_loopback_only",
                "deployed_external_url": None, "cases": list(CASES), "uploads_enabled": False,
                "runtime": "nonroot_readonly_container" if container else "cloud_process"}, indent=2)+"\n")
        except Exception:
            with contextlib.suppress(Exception):
                if "page" in locals() and not page.is_closed():
                    page.screenshot(path=str(artifacts / "failure.png"), full_page=True)
                    (artifacts / "failure-page.txt").write_text(page.locator("body").inner_text())
            raise
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            if container:
                subprocess.run(["docker", "--host=unix:///var/run/docker.sock", "logs", name],
                               check=False, stdout=log, stderr=log)
                subprocess.run(["docker", "--host=unix:///var/run/docker.sock", "rm", "-f", name],
                               check=False, capture_output=True)
