"""Security boundary contracts supplement real browser/container integration."""
import io
import json
import struct

import pytest

from signguard.executor import receive, send
from signguard.preview_auth import password_hash, verify


def test_preview_credential_is_salted_and_verified():
    password = "cloud-only-synthetic-password"
    first = password_hash(password)
    assert first != password_hash(password)
    assert verify(password, first)
    assert not verify("incorrect-cloud-password", first)
    assert not verify(password, "malformed")
    assert not verify("x"*257, first)


def test_short_preview_credential_rejected():
    with pytest.raises(ValueError):
        password_hash("short")


def test_executor_frame_limits_and_truncation():
    for value in [b"", struct.pack("!Q", 100)+b"truncated", struct.pack("!Q", 1000)]:
        with pytest.raises(ValueError):
            receive(io.BytesIO(value), 200)
    stream = io.BytesIO()
    send(stream, b"payload")
    stream.seek(0)
    assert receive(stream, 100) == b"payload"


def test_controller_rpc_has_no_docker_fallback(monkeypatch):
    from signguard.executor import execute_private
    monkeypatch.delenv("SIGNGUARD_EXECUTOR_SOCKET", raising=False)
    with pytest.raises(RuntimeError, match="no direct Docker fallback"):
        execute_private(b"{}")


def test_controller_quota_cannot_reset_with_same_principal(monkeypatch):
    from signguard.broker import _QUOTAS, quota_allowed
    _QUOTAS.clear()
    clock = [1000.0]
    monkeypatch.setattr('signguard.broker.time.monotonic', lambda: clock[0])
    monkeypatch.setenv("SIGNGUARD_REQUESTS_PER_MINUTE", "2")
    assert quota_allowed("synthetic-owner")
    assert quota_allowed("synthetic-owner")
    assert not quota_allowed("synthetic-owner")
    clock[0] += 61
    assert quota_allowed("synthetic-owner")
    _QUOTAS.clear()


def test_media_and_pdf_reports_are_generated_in_worker():
    import base64

    import pymupdf

    from signguard import analyze_pdf
    from signguard.reporting import attach_reports
    from tests.fixtures import unsigned
    report = attach_reports(unsigned(), analyze_pdf(unsigned()))
    assert report["visual_evidence"][0]["mime"] == "image/png"
    with pymupdf.open(stream=base64.b64decode(report["pdf_report"]["base64"]), filetype="pdf") as doc:
        assert "SignGuard forensic triage report" in doc[0].get_text()
    assert len(json.dumps(report)) < 5*1024*1024


def test_release_gate_rejects_unverified_template(tmp_path):
    from pathlib import Path

    from signguard.release_gate import check
    example = json.loads(Path('deploy/release.example.json').read_text())
    (tmp_path / 'release.json').write_text(json.dumps(example))
    with pytest.raises(ValueError, match='Mandatory'):
        check(tmp_path)


def test_executor_rejects_operation_injection_before_worker(monkeypatch):
    from signguard.executor import ExecutorHandler
    called = []
    monkeypatch.setattr('signguard.executor.analyze_container', lambda payload: called.append(payload))
    class Connection:
        def settimeout(self, timeout):
            pass
    handler = object.__new__(ExecutorHandler)
    handler.connection = Connection()
    payload = json.dumps({'pdf': 'JVBERi0=', 'command': 'forbidden'}).encode()
    handler.rfile = io.BytesIO(struct.pack('!Q', len(payload))+payload)
    handler.wfile = io.BytesIO()
    handler.handle()
    assert not called
    handler.wfile.seek(0)
    assert json.loads(receive(handler.wfile, 1024))['error'] == 'analysis_failed_or_unsupported'


def test_gateway_protects_raw_upload_and_media_routes():
    from starlette.testclient import TestClient

    from signguard.preview_web import app
    with TestClient(app) as client:
        assert client.get('/media/synthetic.json').status_code == 403
        assert client.post('/_stcore/upload_file/session/file', content=b'not-authenticated').status_code == 403


def test_gateway_denies_anonymous_websocket():
    from starlette.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    from signguard.preview_web import app
    with TestClient(app) as client, pytest.raises(WebSocketDisconnect), client.websocket_connect('/_stcore/stream'):
        pass
