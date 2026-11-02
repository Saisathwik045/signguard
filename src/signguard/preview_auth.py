"""Single-owner private-preview credential gate. OIDC remains the production identity mode."""
import hashlib
import hmac
import secrets
import threading
import time
from collections import deque

_ATTEMPTS = deque()
_LOCK = threading.Lock()


def password_hash(password, salt=None):
    if len(password) < 20:
        raise ValueError("Preview password must have at least 20 characters")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return salt.hex()+":"+digest.hex()


def verify(password, encoded):
    if len(password) > 256:
        return False
    with _LOCK:
        now = time.monotonic()
        while _ATTEMPTS and now-_ATTEMPTS[0] > 60:
            _ATTEMPTS.popleft()
        if len(_ATTEMPTS) >= 20:
            return False
        _ATTEMPTS.append(now)
    try:
        salt, expected = encoded.split(":")
        if len(salt) != 32 or len(expected) != 64:
            return False
        actual = password_hash(password, bytes.fromhex(salt)).split(":")[1]
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False
