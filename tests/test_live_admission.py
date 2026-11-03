"""Adverse protocol/audit tests independent of forensic document-generation patterns."""
import base64
import hashlib
import json
import threading
import urllib.error
import urllib.request

import pytest

from signguard import broker
from signguard.audit import verify_log
from signguard.client import validate_broker_report
from signguard.input_policy import InputRejected, decode_request, validate_inputs
from signguard.supervisor import encode_request
from tests.fixtures import unsigned


@pytest.mark.parametrize("optional", [
    {"baseline": b"not a PDF"}, {"signature_image": b"not an image"},
    {"reference_image": b"\x89PNG\r\n\x1a\n"+b"x"*(5*1024*1024)},
    {"baseline": b"%PDF-1.7\n"+b"x"*(25*1024*1024)},
])
def test_auxiliary_upload_policy(optional):
    with pytest.raises(InputRejected):
        encode_request(unsigned(), **optional)


@pytest.mark.parametrize("payload", [b'{"pdf":"JVBERi0=","pdf":"JVBERi0="}',
    b'{"pdf":null}', b'{"pdf":"!!"}', b'[]', b'{"pdf":"JVBERi0=","path":"/etc/passwd"}'])
def test_protocol_rejects_ambiguous_or_malformed_encoding(payload):
    with pytest.raises(InputRejected):
        decode_request(payload)


def test_encoded_round_trip_preserves_bytes():
    pdf = unsigned()
    assert decode_request(encode_request(pdf)) == {"pdf": pdf}
    with pytest.raises(InputRejected):
        validate_inputs({"pdf": "not bytes"})


@pytest.fixture
def controller(tmp_path, monkeypatch):
    calls = []
    audit = tmp_path / "audit.jsonl"
    monkeypatch.setenv("SIGNGUARD_BROKER_TOKEN", "synthetic-service-credential-"*2)
    monkeypatch.setenv("SIGNGUARD_AUDIT_PATH", str(audit))
    monkeypatch.setenv("SIGNGUARD_REQUESTS_PER_MINUTE", "100")
    broker._QUOTAS.clear()
    def execute(payload):
        calls.append(payload)
        return {"assessment": {"verdict": "inconclusive", "analysis_status": "completed"},
                "execution_controls": {"isolation": "docker_disposable", "network_isolation": True,
                    "filesystem_isolation": True, "executor_boundary": "restricted_unix_rpc"}}
    monkeypatch.setattr(broker, "execute_private", execute)
    server = broker.BoundedHTTPServer(("127.0.0.1", 0), broker.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def request(payload, *, token=True, principal="synthetic-owner", content_type="application/json"):
        headers = {"Content-Type": content_type}
        if token:
            headers["Authorization"] = "Bearer "+"synthetic-service-credential-"*2
        if principal is not None:
            headers["X-SignGuard-Principal"] = principal
        req = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/analyze", data=payload, headers=headers)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            response = opener.open(req, timeout=5)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, json.loads(response.read()), response.headers
    try:
        yield request, calls, audit
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        broker._QUOTAS.clear()


def test_controller_validation_precedes_executor_and_audits_rejection(controller):
    request, calls, audit = controller
    payload = json.dumps({"pdf": base64.b64encode(b"renamed executable").decode()}).encode()
    status, value, headers = request(payload)
    assert status == 400 and value["error"] == "invalid_pdf" and not calls
    assert headers["Cache-Control"] == "no-store"
    events = [json.loads(line)["event"] for line in audit.read_text().splitlines()]
    assert [event["status"] for event in events] == ["admitted", "rejected"]
    assert events[1]["principal_sha256"] == hashlib.sha256(b"synthetic-owner").hexdigest()
    assert "renamed executable" not in audit.read_text()
    assert verify_log(audit)[1] == 2


def test_controller_denies_unauthorized_missing_principal_and_wrong_content_type(controller):
    request, calls, audit = controller
    payload = encode_request(unsigned())
    assert request(payload, token=False)[0] == 403
    assert request(payload, principal=None)[0] == 400
    assert request(payload, content_type="text/plain")[0] == 400
    assert not calls and not audit.exists()


def test_audit_admission_failure_prevents_worker(controller, monkeypatch):
    request, calls, _ = controller
    monkeypatch.setattr(broker, "append_event", lambda *args: (_ for _ in ()).throw(OSError("synthetic sink outage")))
    status, value, _ = request(encode_request(unsigned()))
    assert status == 503 and value["error"] == "audit_unavailable" and not calls


def test_worker_failure_is_audited_without_sensitive_error(controller, monkeypatch):
    request, _, audit = controller
    def fail(payload):
        raise TimeoutError("synthetic private path must not leak")
    monkeypatch.setattr(broker, "execute_private", fail)
    pdf = unsigned()
    status, value, _ = request(encode_request(pdf))
    assert status == 422
    assert "private path" not in json.dumps(value)+audit.read_text()
    events = [json.loads(line)["event"] for line in audit.read_text().splitlines()]
    assert [event["status"] for event in events] == ["admitted", "failed"]
    assert events[-1]["input_sha256"] == hashlib.sha256(pdf).hexdigest()


def test_receipt_binds_result_and_client_rejects_changed_report(controller):
    request, _, audit = controller
    status, report, _ = request(encode_request(unsigned()))
    assert status == 200
    validate_broker_report(report)
    report["assessment"]["verdict"] = "tampering_detected"
    with pytest.raises(ValueError, match="receipt"):
        validate_broker_report(report)
    assert verify_log(audit)[1] == 2


def test_client_rejects_unisolated_report_before_receipt(controller):
    request, _, _ = controller
    report = request(encode_request(unsigned()))[1]
    report["execution_controls"]["network_isolation"] = False
    with pytest.raises(ValueError, match="isolation"):
        validate_broker_report(report)


def test_gateway_login_and_denial_never_cache_private_responses():
    from starlette.testclient import TestClient

    from signguard.preview_web import app
    with TestClient(app) as client:
        for path in ["/auth/login", "/media/synthetic-report.json"]:
            response = client.get(path)
            assert response.headers["Cache-Control"] == "no-store"
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert response.headers["X-Frame-Options"] == "DENY"
