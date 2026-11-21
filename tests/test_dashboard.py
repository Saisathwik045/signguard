"""Dashboard boundaries, exact evidence downloads and honest historical evaluation."""
import hashlib
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from signguard.dashboard import PAGES, evaluation_data
from signguard.demo import CASES, load_case, load_downloads

ROOT = Path(__file__).resolve().parents[1]


def test_evaluation_is_the_exact_historical_source_not_new_scores():
    data = evaluation_data()
    assert data["measured_date"] == "2026-11-02"
    for record in data["splits"]:
        raw = (ROOT / record["source_path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == record["source_sha256"]
        assert json.loads(raw) == record["summary"]
    holdout = data["splits"][2]["summary"]
    assert holdout["all_alert"]["fn"] == 5
    assert holdout["supported_alert"]["fn"] == 0
    assert holdout["localization"]["fp"] == 15


@pytest.mark.parametrize("case", CASES)
def test_downloads_preserve_original_input_and_report_hashes(case):
    document, raw = load_downloads(case)
    report, provenance = load_case(case)
    assert hashlib.sha256(document).hexdigest() == provenance["pdf_sha256"]
    assert hashlib.sha256(raw).hexdigest() == provenance["report_sha256"]
    assert json.loads(raw) == report


def test_all_gallery_pages_remain_read_only_even_with_live_flag(monkeypatch):
    monkeypatch.setenv("SIGNGUARD_LIVE_UPLOADS_ENABLED", "true")
    app = AppTest.from_file(str(ROOT / "synthetic_demo.py")).run()
    for page in PAGES:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception
        assert not app.get("file_uploader")
        assert not app.text_input and not app.chat_input
    app.sidebar.radio[0].set_value("Evaluation").run()
    app.main.radio[0].set_value("Supported alert cases").run()
    assert not app.exception


@pytest.mark.parametrize("backend,auth", [("limited", "false"), ("limited", "true"), ("broker", "false")])
def test_live_flag_cannot_enable_unisolated_or_unauthenticated_uploads(monkeypatch, backend, auth):
    monkeypatch.setenv("SIGNGUARD_LIVE_UPLOADS_ENABLED", "true")
    monkeypatch.setenv("SIGNGUARD_BACKEND", backend)
    monkeypatch.setenv("SIGNGUARD_REQUIRE_AUTH", auth)
    monkeypatch.setenv("SIGNGUARD_AUTH_MODE", "gateway")
    monkeypatch.delenv("SIGNGUARD_GATEWAY_TOKEN", raising=False)
    app = AppTest.from_file(str(ROOT / "app.py")).run()
    assert not app.exception
    assert not app.get("file_uploader")
    assert app.error


def test_unsupported_result_has_json_only_and_no_invented_images():
    from signguard.input_policy import InputRejected
    from signguard.outcomes import unsupported_report
    app = AppTest.from_string('''
import streamlit as st
from signguard.dashboard import render_report
render_report(st.session_state.test_report)
''')
    app.session_state.test_report = unsupported_report(b"%PDF-broken", InputRejected("malformed_pdf", "Malformed PDF"))
    app.run()
    assert not app.exception
    assert len(app.get("download_button")) == 1
    assert not app.get("imgs")
    assert app.subheader[0].value == "Unsupported document"


def test_nonvisual_tampering_explanation_and_integrity_are_not_identity():
    app = AppTest.from_file(str(ROOT / "synthetic_demo.py")).run()
    app.selectbox[0].select("tampered").run()
    assert not app.exception
    assert any("leave the page looking unchanged" in w.value for w in app.warning)
    metrics = {m.label: m.value for m in app.metric}
    assert metrics["Signed-byte integrity"] == "Fail"
    assert metrics["Signer identity"] == "Not established"


def test_visual_candidate_and_ela_limitations_are_visible():
    app = AppTest.from_file(str(ROOT / "synthetic_demo.py")).run()
    app.selectbox[0].select("visual_only").run()
    assert not app.exception
    assert any("Candidate regions: 1" in item.value for item in app.markdown)
    assert any("do not preserve original JPEG compression history" in item.value for item in app.warning)
    residuals = next(item.value for item in app.dataframe if "ELA applicability" in item.value.columns)
    assert residuals["ELA applicability"].tolist() == ["not_applicable_to_original_compression"]
