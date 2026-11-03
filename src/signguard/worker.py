"""One request per process, bounded protocol, no user-selectable executable or audit path."""
import json
import os
import resource
import sys
import time

from .input_policy import InputRejected, decode_request
from .outcomes import unsupported_report
from .supervisor import MAX_OUTPUT, MAX_REQUEST


def main():
    os.environ.clear()
    os.environ.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", LANG="C.UTF-8")
    request = sys.stdin.buffer.read(MAX_REQUEST+1)
    if len(request) > MAX_REQUEST:
        raise ValueError("Request size exceeded")
    decoded = decode_request(request)
    from .pipeline import analyze_pdf
    pdf = decoded.pop("pdf")
    started = time.perf_counter()
    from PIL import Image, UnidentifiedImageError
    from pyhanko.pdf_utils.misc import PdfReadError
    try:
        report = analyze_pdf(pdf, **decoded)
        from .reporting import attach_reports
        attach_reports(pdf, report)
    except InputRejected as exc:
        report = unsupported_report(pdf, exc)
    except PdfReadError:
        report = unsupported_report(pdf, InputRejected("malformed_pdf", "Strict PDF structure validation failed."))
    except (UnidentifiedImageError, Image.DecompressionBombError):
        report = unsupported_report(pdf, InputRejected("unsupported_image", "An optional image cannot be decoded within limits."))
    report["worker_measurements"] = {"analysis_seconds": time.perf_counter()-started,
                                     "process_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024}
    result = json.dumps(report, allow_nan=False).encode()
    if len(result) > MAX_OUTPUT:
        raise ValueError("Output size exceeded")
    sys.stdout.buffer.write(result)


if __name__ == "__main__":
    main()
