"""Single-controller restart-safe quotas on encrypted persistent storage; no Redis required."""
import sqlite3
import time
from threading import Lock

_LOCK = Lock()


def allowed(path, key, limit, window):
    with _LOCK:
        return _allowed(path, key, limit, window)


def _allowed(path, key, limit, window):
    if limit < 1 or window <= 0:
        return False
    with sqlite3.connect(path, timeout=2, isolation_level=None) as database:
        database.execute("PRAGMA journal_mode=WAL")
        database.execute("PRAGMA synchronous=FULL")
        database.execute("CREATE TABLE IF NOT EXISTS attempts (principal TEXT, at REAL)")
        database.execute("CREATE INDEX IF NOT EXISTS attempts_lookup ON attempts(principal, at)")
        database.execute("BEGIN IMMEDIATE")
        now = time.time()
        database.execute("DELETE FROM attempts WHERE at <= ?", (now-window,))
        count = database.execute("SELECT count(*) FROM attempts WHERE principal=?", (key,)).fetchone()[0]
        principals = database.execute("SELECT count(DISTINCT principal) FROM attempts").fetchone()[0]
        known = count > 0
        accepted = count < limit and (known or principals < 1000)
        if accepted:
            database.execute("INSERT INTO attempts VALUES (?,?)", (key, now))
        database.commit()
        return accepted
