"""Static presentation QA; hosted mode uses origin-bound service access, never a public fallback."""
import base64
import hashlib
import json
import os
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from scripts.build_private_viewer import build
from signguard.demo import CASES, load_case

pytestmark = pytest.mark.skipif(os.environ.get("SIGNGUARD_PRIVATE_SITE_TESTS") != "1",
                                reason="Explicit cloud browser job required")


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    url = os.environ.get("SIGNGUARD_SITE_URL")
    if url:
        address = urlsplit(url)
        if address.scheme != "https" or not address.hostname or address.path not in {"", "/"}:
            raise ValueError("Hosted QA requires an exact HTTPS origin")
        yield url.rstrip("/"), True
        return
    root = tmp_path_factory.mktemp("private-site")
    directory = build(root)
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", False
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_five_real_reports_and_downloads(site):
    from playwright.sync_api import expect, sync_playwright
    origin, hosted = site
    token = os.environ.get("SIGNGUARD_SITE_BEARER", "")
    if hosted and not token:
        pytest.fail("Hosted authorized QA requires protected service access")
    artifacts = Path(os.environ.get("SIGNGUARD_SITE_ARTIFACTS", "site-artifacts"))
    artifacts.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("SIGNGUARD_CHROMIUM_PATH"))
        page = browser.new_page(accept_downloads=True, viewport={"width": 1440, "height": 1800})

        def route_request(route):
            address = urlsplit(route.request.url)
            if address.scheme+"://"+address.netloc != origin:
                route.abort()
                return
            headers = {**route.request.headers}
            if token:
                headers["OAI-Sites-Authorization"] = "Bearer "+token
            route.continue_(headers=headers)

        page.route("**/*", route_request)
        response = page.goto(origin)
        assert response.status == 200
        expect(page.get_by_role("heading", name="Inspect the evidence.")).to_be_visible()
        expect(page.locator("#cases button")).to_have_count(5)
        assert page.locator('input,textarea,form').count() == 0
        evidence = []
        for case_id in CASES:
            page.locator(f'#cases button[data-id="{case_id}"]').click()
            expect(page.locator("#shown")).to_contain_text("Evidence verified")
            expected, _ = load_case(case_id)
            expect(page.locator("#classification")).to_have_text(expected["structure"]["refined_classification"])
            expect(page.locator("#verdict")).to_have_text(expected["assessment"]["verdict"].replace("_", " ").title())
            # The UI changes classification/verdict before enabling the current report downloads.
            expect(page.locator(f'#cases button[data-id="{case_id}"]')).to_have_attribute("aria-current", "true")
            page.wait_for_function("""() => {
                const images=[...document.querySelectorAll('#evidence img')];
                return images.length && images.every(i=>i.complete && i.naturalWidth>0);
            }""")
            if case_id == "shadow_modified":
                expect(page.get_by_alt_text("Signed revision snapshot, page 1")).to_be_visible()
            with page.expect_download() as value:
                page.get_by_role("button", name="Download JSON", exact=True).click()
            report = json.loads(Path(value.value.path()).read_text())
            assert report["sha256"] == expected["sha256"]
            with page.expect_download() as value:
                page.get_by_role("button", name="Download PDF", exact=True).click()
            pdf = Path(value.value.path()).read_bytes()
            assert pdf == base64.b64decode(expected["pdf_report"]["base64"])
            page.get_by_role("heading", name="Inspect the evidence.").scroll_into_view_if_needed()
            page.screenshot(path=str(artifacts / f"{case_id}.png"), full_page=True)
            evidence.append({"case": case_id, "pdf_sha256": report["sha256"],
                             "download_pdf_sha256": hashlib.sha256(pdf).hexdigest()})
        browser.close()
    (artifacts / "browser-evidence.json").write_text(json.dumps({"origin": origin, "hosted": hosted,
        "authorization_scope": "Origin-bound platform service bearer, not interactive owner SSO" if hosted else "Cloud loopback static fixture server",
        "uploads_enabled": False, "outbound_origins_allowed": [origin], "cases": evidence}, indent=2)+"\n")
