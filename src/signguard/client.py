"""UI-to-worker boundary, with fail-closed production configuration."""
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from .supervisor import MAX_OUTPUT, analyze_limited, encode_request


class AnalysisServiceError(RuntimeError):
    """Only fixed, non-sensitive controller status explanations cross into the UI."""


def authorized(claims, allowlist):
    return bool(claims.get("email_verified") is True and claims.get("email") in allowlist)


def analyze_upload(pdf, *, principal="private-session", **optional):
    if os.environ.get("SIGNGUARD_BACKEND", "limited") != "broker":
        if os.environ.get("SIGNGUARD_REQUIRE_AUTH") == "true":
            raise RuntimeError("Production requires isolated broker backend")
        return analyze_limited(pdf, **optional)
    url = os.environ.get("SIGNGUARD_BROKER_URL", "")
    token = os.environ.get("SIGNGUARD_BROKER_TOKEN", "")
    if not url or len(token) < 32:
        raise RuntimeError("Private worker broker is not configured")
    address = urlsplit(url)
    if (address.scheme not in {"http", "https"} or not address.hostname or address.username
            or address.password or address.query or address.fragment or address.path not in {"", "/"}):
        raise ValueError("Invalid private broker URL")
    if address.scheme == "http" and address.hostname not in {"controller", "localhost", "127.0.0.1"}:
        raise ValueError("Cleartext broker transport must use the private controller or loopback")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    request = urllib.request.Request(url+"/analyze", data=encode_request(pdf, **optional),
                                     headers={"Authorization": "Bearer "+token,
                                              "Content-Type": "application/json", "X-SignGuard-Principal": principal})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=70) as response:
            body = response.read(MAX_OUTPUT+1)
    except urllib.error.HTTPError as exc:
        messages = {400: "The upload request was rejected by input validation.",
                    403: "The private analysis service denied this request.",
                    413: "The upload exceeds the analysis service size limit.",
                    429: "Analysis capacity or per-user quota reached. Retry later.",
                    503: "The audit service is unavailable; no result can be released."}
        raise AnalysisServiceError(messages.get(exc.code, "The isolated analysis failed or exceeded a worker limit.")) from None
    if len(body) > MAX_OUTPUT:
        raise ValueError("Worker response exceeds limit")
    report = json.loads(body)
    validate_broker_report(report)
    return report


def validate_broker_report(report):
    """Reject mismatched receipts or unsafe backend substitutions before displaying results."""
    if not isinstance(report, dict):
        raise TypeError("Invalid analysis report")
    controls = report.get("execution_controls", {})
    if (controls.get("isolation") != "docker_disposable" or controls.get("network_isolation") is not True
            or controls.get("filesystem_isolation") is not True
            or controls.get("executor_boundary") != "restricted_unix_rpc"):
        raise ValueError("Required worker isolation evidence is missing")
    receipt = report.get("audit_receipt", {})
    unsigned = {key: value for key, value in report.items() if key != "audit_receipt"}
    actual = hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    claimed = receipt.get("report_digest", "")
    if not isinstance(claimed, str) or not hmac.compare_digest(actual, claimed):
        raise ValueError("Controller audit receipt does not match the report")
    head = receipt.get("head", "")
    if not isinstance(head, str) or len(head) != 64 or any(c not in "0123456789abcdef" for c in head):
        raise ValueError("Controller audit head is invalid")
