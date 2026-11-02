"""Private trusted controller; never publish this endpoint or its Docker socket."""
import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
from collections import OrderedDict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .audit import append_event
from .executor import execute_private
from .supervisor import MAX_OUTPUT, MAX_REQUEST

_LOGGER = logging.getLogger(__name__)
_JOB = threading.BoundedSemaphore(1)
_QUOTAS = OrderedDict()
_QUOTA_LOCK = threading.Lock()


def quota_allowed(principal):
    key = hashlib.sha256(principal.encode()).hexdigest()
    with _QUOTA_LOCK:
        now = time.monotonic()
        if key not in _QUOTAS and len(_QUOTAS) >= 1000:
            return False  # No eviction that would let callers reset quotas with rotating identities.
        history = _QUOTAS.setdefault(key, deque())
        while history and now-history[0] >= float(os.environ.get("SIGNGUARD_QUOTA_WINDOW_SECONDS", "60")):
            history.popleft()
        if len(history) >= int(os.environ.get("SIGNGUARD_REQUESTS_PER_MINUTE", "10")):
            return False
        history.append(now)
        return True


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Never log paths, headers, request bodies, parser errors or report contents.

    def reply(self, status, value):
        body = json.dumps(value, allow_nan=False).encode()
        if len(body) > MAX_OUTPUT:
            status, body = 502, b'{"error":"output_limit"}'
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.reply(200 if self.path == "/health" else 404, {"status": "alive", "readiness": "not_attested"})

    def do_POST(self):
        token = os.environ.get("SIGNGUARD_BROKER_TOKEN", "")
        if len(token) < 32 or not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer "+token):
            self.reply(403, {"error": "forbidden"})
            return
        if self.path != "/analyze" or self.headers.get("Transfer-Encoding"):
            self.reply(400, {"error": "invalid_request"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not 0 < length <= MAX_REQUEST:
            self.reply(413, {"error": "input_limit"})
            return
        principal = self.headers.get("X-SignGuard-Principal", "private-session")[:256]
        if not quota_allowed(principal):
            self.reply(429, {"error": "quota"})
            return
        if not _JOB.acquire(blocking=False):
            self.reply(429, {"error": "worker_busy"})
            return
        request_id = secrets.token_hex(12)
        self.connection.settimeout(10)
        error_class = None
        try:
            payload = self.rfile.read(length)
            if len(payload) != length:
                raise ValueError("Truncated request")
            report = execute_private(payload)
            audit_path = os.environ.get("SIGNGUARD_AUDIT_PATH")
            if not audit_path:
                raise RuntimeError("Audit sink required")
            digest = hashlib.sha256(json.dumps(report, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            head = append_event(audit_path, {"request_id": request_id, "status": "completed",
                                           "report_digest": digest, "verdict": report["assessment"]["verdict"]})
            report["audit_receipt"] = {"head": head, "report_digest": digest,
                                        "anchoring": "controller_local_head_not_externally_anchored"}
            self.reply(200, report)
            status = "completed"
        except Exception as exc:  # noqa: BLE001 -- never expose parser or host details across service boundary
            error_class = type(exc).__name__
            self.reply(422, {"error": "analysis_failed_or_unsupported", "request_id": request_id})
            status = "failed"
        finally:
            _JOB.release()
        _LOGGER.info(json.dumps({"event": "analysis", "request_id": request_id, "status": status, "error_class": error_class}))


class BoundedHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    _connections = threading.BoundedSemaphore(4)

    def process_request(self, request, client_address):
        if not self._connections.acquire(blocking=False):
            request.sendall(b"HTTP/1.1 429 Too Many Requests\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            self.shutdown_request(request)
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._connections.release()

    request_queue_size = 4

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(5)
        return connection, address


def main():
    os.umask(0o077)
    if len(os.environ.get("SIGNGUARD_BROKER_TOKEN", "")) < 32:
        raise SystemExit("A private service token of at least 32 characters is required")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # Single active request, backlog four; upstream authenticated gateway must enforce quotas/read deadlines.
    if not os.environ.get("SIGNGUARD_EXECUTOR_SOCKET") or not os.environ.get("SIGNGUARD_AUDIT_PATH"):
        raise SystemExit("Restricted executor socket and audit sink are required")
    server = BoundedHTTPServer((os.environ.get("SIGNGUARD_BROKER_HOST", "127.0.0.1"),
                               int(os.environ.get("SIGNGUARD_BROKER_PORT", "8080"))), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
