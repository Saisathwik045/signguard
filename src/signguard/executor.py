"""Narrow local execution service. Only this trusted host process can access the Docker daemon."""
import json
import os
import socket
import socketserver
import struct
import sys
from pathlib import Path

from .container_runner import analyze_container
from .supervisor import MAX_OUTPUT, MAX_REQUEST


def receive(stream, limit):
    header = stream.read(8)
    if len(header) != 8:
        raise ValueError("Truncated frame")
    length = struct.unpack("!Q", header)[0]
    if not 0 < length <= limit:
        raise ValueError("Frame limit exceeded")
    value = stream.read(length)
    if len(value) != length:
        raise ValueError("Truncated frame")
    return value


def send(stream, value):
    stream.write(struct.pack("!Q", len(value))+value)
    stream.flush()


def execute_private(payload):
    path = os.environ.get("SIGNGUARD_EXECUTOR_SOCKET")
    if not path:
        raise RuntimeError("Restricted executor socket is required; no direct Docker fallback")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(75)
        connection.connect(path)
        with connection.makefile("rwb") as stream:
            send(stream, payload)
            result = json.loads(receive(stream, MAX_OUTPUT))
    if result.get("error"):
        raise RuntimeError("Isolated analysis failed or input is unsupported")
    return result


class ExecutorHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(75)
        try:
            payload = receive(self.rfile, MAX_REQUEST)
            values = json.loads(payload)
            if not isinstance(values, dict) or "pdf" not in values or set(values)-{
                    "pdf", "baseline", "signature_image", "reference_image"}:
                raise ValueError("Invalid operation")
            if any(not isinstance(value, str) for value in values.values()):
                raise ValueError("Invalid value")
            # No image, command, path, environment, Docker flag or mount is accepted by this RPC.
            report = analyze_container(payload)
            report["execution_controls"]["executor_boundary"] = "restricted_unix_rpc"
            result = json.dumps(report, allow_nan=False).encode()
            if len(result) > MAX_OUTPUT:
                raise ValueError("Response limit")
        except Exception as exc:  # noqa: BLE001 -- log only a class, never input/parser details
            print(json.dumps({"event": "executor_failure", "error_class": type(exc).__name__}), file=sys.stderr, flush=True)
            result = b'{"error":"analysis_failed_or_unsupported"}'
        send(self.wfile, result)


def main():
    path = Path(os.environ.get("SIGNGUARD_EXECUTOR_SOCKET", "/run/signguard/executor.sock"))
    path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    if path.parent.stat().st_uid == os.getuid():
        path.parent.chmod(0o750)
    if path.exists():
        raise SystemExit("Refusing to replace an existing executor socket")
    server = socketserver.UnixStreamServer(str(path), ExecutorHandler)
    os.chmod(path, 0o660)  # nosec B103 -- dedicated controller group only; parent is 0750, no world access
    try:
        server.serve_forever()
    finally:
        server.server_close()
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
