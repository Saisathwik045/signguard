"""One request per process, bounded protocol, no user-selectable executable or audit path."""
import base64
import json
import os
import resource
import sys
import time

from .supervisor import MAX_INPUT, MAX_OUTPUT, MAX_REQUEST


def main():
    os.environ.clear()
    os.environ.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", LANG="C.UTF-8")
    request = sys.stdin.buffer.read(MAX_REQUEST+1)
    if len(request) > MAX_REQUEST:
        raise ValueError("Request size exceeded")
    values = json.loads(request)
    if not isinstance(values, dict) or "pdf" not in values or set(values)-{
        "pdf", "baseline", "signature_image", "reference_image"}:
        raise ValueError("Unsupported request shape")
    decoded = {key: base64.b64decode(value, validate=True) for key, value in values.items()}
    if sum(map(len, decoded.values())) > MAX_INPUT:
        raise ValueError("Input size exceeded")
    from .pipeline import analyze_pdf
    pdf = decoded.pop("pdf")
    started = time.perf_counter()
    report = analyze_pdf(pdf, **decoded)
    from .reporting import attach_reports
    attach_reports(pdf, report)
    report["worker_measurements"] = {"analysis_seconds": time.perf_counter()-started,
                                     "process_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024}
    result = json.dumps(report, allow_nan=False).encode()
    if len(result) > MAX_OUTPUT:
        raise ValueError("Output size exceeded")
    sys.stdout.buffer.write(result)


if __name__ == "__main__":
    main()
