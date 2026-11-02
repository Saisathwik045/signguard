"""Verify independent PDF readers, content boundaries and the real Streamlit viewer."""
import base64
import hashlib
from pathlib import Path

import pymupdf
import pytest
from streamlit.testing.v1 import AppTest

from signguard.demo import CASES, load_case

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"genuine_signed": ("cryptographic", "inconclusive"),
            "tampered": ("cryptographic", "tampering_detected"),
            "shadow_modified": ("cryptographic", "review_required"),
            "visual_only": ("visual_candidate", "inconclusive"), "unsigned": ("unsigned", "inconclusive")}


@pytest.mark.parametrize("case_id", CASES)
def test_actual_bundled_reports_and_independent_pdf_reader(case_id):
    report, provenance = load_case(case_id)
    assert (report["structure"]["refined_classification"], report["assessment"]["verdict"]) == EXPECTED[case_id]
    assert not report["assessment"]["authenticity_established"]
    pdf = base64.b64decode(report["pdf_report"]["base64"], validate=True)
    with pymupdf.open(stream=pdf, filetype="pdf") as document:
        assert len(document) >= 2
        assert "SignGuard forensic triage report" in document[0].get_text()
    for item in report["visual_evidence"]:
        image = base64.b64decode(item["base64"], validate=True)
        assert image.startswith(b"\x89PNG\r\n\x1a\n")
    assert provenance["worker_image_id"].startswith("sha256:")
    if case_id == "genuine_signed":
        assert all(s["intact"] and s["valid"] for s in report["structure"]["signatures"])
    if case_id == "shadow_modified":
        assert any(p["changed_fraction"] > 0 for c in report["visual_comparisons"] for p in c.get("pages", []))
        assert any(e["label"] == "Signed revision snapshot" for e in report["visual_evidence"])


@pytest.mark.parametrize("untrusted", ["../genuine_signed", "/tmp/pdf", "https://example.test/a.pdf", "", "unknown"])
def test_no_user_paths_or_urls(untrusted):
    with pytest.raises(ValueError, match="Unknown"):
        load_case(untrusted)


def test_bundle_digest_failure_is_closed(monkeypatch):
    monkeypatch.setattr(hashlib, "sha256", lambda _: type("WrongDigest", (), {"hexdigest": lambda self: "0"*64})())
    with pytest.raises(ValueError, match="integrity"):
        load_case("genuine_signed")


def test_streamlit_all_cases_have_no_ingestion_or_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Synthetic viewer tried to execute an analysis backend")
    monkeypatch.setattr("signguard.client.analyze_upload", forbidden)
    monkeypatch.setattr("signguard.container_runner.analyze_container", forbidden)
    monkeypatch.setattr("signguard.pipeline.analyze_pdf", forbidden)
    app = AppTest.from_file(str(ROOT / "synthetic_demo.py")).run()
    for case_id in CASES:
        app.selectbox[0].select(case_id).run()
        assert not app.exception
        assert not app.get("file_uploader")
        assert not app.text_input and not app.chat_input
        assert len(app.get("download_button")) == 2
        assert app.subheader[0].value == EXPECTED[case_id][1].replace("_", " ").title()


def test_missing_bundle_displays_error_without_fallback(monkeypatch):
    def unavailable(case_id):
        raise ValueError("bundle unavailable")
    monkeypatch.setattr("signguard.demo.load_case", unavailable)
    app = AppTest.from_file(str(ROOT / "synthetic_demo.py")).run()
    assert not app.exception
    assert "No analysis fallback" in app.error[0].value
    assert not app.get("download_button")
