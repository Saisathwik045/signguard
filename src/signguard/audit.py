"""Locked, fsynced hash-chain journal. Retain its head externally to detect truncation."""
import fcntl
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path


def digest(record):
    return hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def verify_records(lines, expected_head=None):
    previous = "0" * 64
    count = 0
    for line in lines:
        record = json.loads(line)
        claimed = record.pop("hash")
        if record["previous"] != previous or record["sequence"] != count or digest(record) != claimed:
            raise ValueError("Audit chain integrity failure")
        previous = claimed
        count += 1
    if expected_head is not None and previous != expected_head:
        raise ValueError("Audit head mismatch (possible truncation)")
    return previous, count


def verify_log(path, expected_head=None):
    with Path(path).open() as stream:
        fcntl.flock(stream, fcntl.LOCK_SH)
        return verify_records(stream, expected_head)


def append_event(path, event):
    with Path(path).open("a+", encoding="utf-8") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.seek(0)
        previous, count = verify_records(stream)
        record = {"sequence": count, "previous": previous,
                  "timestamp": datetime.now(UTC).isoformat(), "event": event}
        record["hash"] = digest(record)
        stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
        return record["hash"]
