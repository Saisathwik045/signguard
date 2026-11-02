"""Bounded supervisor with process-group timeout termination and temporary-output cleanup."""
import base64
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

MAX_INPUT = 60*1024*1024
MAX_REQUEST = 82*1024*1024
MAX_OUTPUT = 5*1024*1024
_SLOT = threading.BoundedSemaphore(1)


@dataclass(frozen=True)
class Limits:
    wall: float = 60
    cpu: int = 30
    memory: int = 1024*1024*1024
    output: int = MAX_OUTPUT


_DEFAULT_LIMITS = Limits()


def run_limited(command, payload=b"", limits=_DEFAULT_LIMITS):
    if len(payload) > MAX_REQUEST:
        raise ValueError("Request exceeds transport limit")
    # No inherited proxy, home, credential, token or cloud identity variables.
    environment = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8",
                   "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    launcher = [sys.executable, "-I", "-m", "signguard.limits", str(limits.cpu), str(limits.memory),
                str(limits.output), *command]
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="signguard-") as directory:
        os.chmod(directory, 0o700)
        with (Path(directory)/"input").open("w+b") as source, (Path(directory)/"output").open("w+b") as output, (
            Path(directory)/"error").open("w+b") as errors:
            source.write(payload)
            source.seek(0)
            process = subprocess.Popen(launcher, stdin=source, stdout=output, stderr=errors,
                                       env=environment, cwd=directory, start_new_session=True, close_fds=True)
            timed_out = False
            try:
                process.wait(timeout=limits.wall)
            except subprocess.TimeoutExpired:
                timed_out = True
            finally:
                # Also kill descendants after the parent exits (including inherited-output holders).
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            output.seek(0)
            result = output.read(limits.output+1)
            if timed_out:
                raise TimeoutError("Worker wall-clock limit exceeded")
            if process.returncode != 0 or len(result) > limits.output:
                raise RuntimeError("Worker failed or exceeded a resource/output limit")
    return result, {"elapsed_seconds": time.monotonic()-started, "isolation": "rlimits_only",
                    "network_isolation": False, "filesystem_isolation": False}


def encode_request(pdf, **optional):
    values = {"pdf": pdf, **{k: v for k, v in optional.items() if v is not None}}
    if set(values) - {"pdf", "baseline", "signature_image", "reference_image"}:
        raise ValueError("Unknown analysis option")
    if any(not isinstance(v, bytes) for v in values.values()) or sum(map(len, values.values())) > MAX_INPUT:
        raise ValueError("Invalid or oversized input")
    if not pdf.startswith(b"%PDF-") or len(pdf) > 25*1024*1024:
        raise ValueError("Expected PDF upload, at most 25 MiB")
    return json.dumps({k: base64.b64encode(v).decode("ascii") for k, v in values.items()}).encode()


def analyze_limited(pdf, **optional):
    if not _SLOT.acquire(blocking=False):
        raise RuntimeError("Worker busy; queue capacity is zero")
    try:
        payload = encode_request(pdf, **optional)
        result, controls = run_limited([sys.executable, "-I", "-m", "signguard.worker"], payload)
        report = json.loads(result)
        report["execution_controls"] = controls
        return report
    finally:
        _SLOT.release()
