import json
import urllib.error

import pytest

from scripts.build_private_viewer import build
from scripts.probe_private_site import probe
from signguard.demo import CASES, load_case

SITE = "https://signguard-private-synthetic.knitdeck.chatgpt.site"


def test_static_artifact_has_only_allowlisted_assets(tmp_path):
    root = build(tmp_path)
    expected = {"index.html", "styles.css", "app.js", "catalogue.json", "health.json"}
    expected |= {f"reports/{case_id}.json" for case_id in CASES}
    assert {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()} == expected
    assert not list(root.rglob("*.py"))
    for case_id in CASES:
        assert json.loads((root / "reports" / (case_id+".json")).read_text()) == load_case(case_id)[0]
    health = json.loads((root / "health.json").read_text())
    assert health["cases"] == 5 and not health["uploads"] and not health["backend"]


def test_proxy_denial_cannot_be_reported_as_site_authentication(monkeypatch, tmp_path):
    class BlockedProxy:
        def open(self, *args, **kwargs):
            raise urllib.error.URLError("Tunnel connection failed: 403 Forbidden")
    monkeypatch.setattr("urllib.request.build_opener", lambda *args: BlockedProxy())
    with pytest.raises(urllib.error.URLError):
        probe(SITE, "", tmp_path, anonymous_only=True)
    assert not (tmp_path / "anonymous-route-proof.json").exists()


def test_public_response_cannot_pass_private_route_gate(monkeypatch, tmp_path):
    class PublicResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class PublicSite:
        def open(self, *args, **kwargs):
            return PublicResponse()
    monkeypatch.setattr("urllib.request.build_opener", lambda *args: PublicSite())
    with pytest.raises(ValueError, match="not denied"):
        probe(SITE, "", tmp_path, anonymous_only=True)


def test_service_access_cannot_be_sent_to_a_different_origin(tmp_path):
    with pytest.raises(ValueError, match="registered private Site"):
        probe("https://another-origin.test", "synthetic-test-credential", tmp_path)
