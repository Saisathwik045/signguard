"""Private trusted controller; never publish this endpoint or its Docker socket."""
import hmac
import json
import logging
import os
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer

from .container_runner import analyze_container
from .supervisor import MAX_OUTPUT, MAX_REQUEST

_LOGGER = logging.getLogger(__name__)


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
        request_id = secrets.token_hex(12)
        self.connection.settimeout(10)
        try:
            payload = self.rfile.read(length)
            if len(payload) != length:
                raise ValueError("Truncated request")
            report = analyze_container(payload)
            self.reply(200, report)
            status = "completed"
        except Exception:  # noqa: BLE001 -- never expose parser or host details across service boundary
            self.reply(422, {"error": "analysis_failed_or_unsupported", "request_id": request_id})
            status = "failed"
        _LOGGER.info(json.dumps({"event": "analysis", "request_id": request_id, "status": status}))


class BoundedHTTPServer(HTTPServer):
    request_queue_size = 4

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(5)
        return connection, address


def main():
    if len(os.environ.get("SIGNGUARD_BROKER_TOKEN", "")) < 32:
        raise SystemExit("A private service token of at least 32 characters is required")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # Single active request, backlog four; upstream authenticated gateway must enforce quotas/read deadlines.
    server = BoundedHTTPServer((os.environ.get("SIGNGUARD_BROKER_HOST", "127.0.0.1"), 8080), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
