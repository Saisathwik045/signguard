"""UI-to-worker boundary, with fail-closed production configuration."""
import json
import os
import urllib.request
from urllib.parse import urlsplit

from .supervisor import MAX_OUTPUT, analyze_limited, encode_request


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
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=70) as response:
        body = response.read(MAX_OUTPUT+1)
    if len(body) > MAX_OUTPUT:
        raise ValueError("Worker response exceeds limit")
    return json.loads(body)
