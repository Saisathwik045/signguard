"""Durable opaque sessions and one-use OAuth state for a single-owner private deployment."""
import hashlib
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


def key(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Sessions:
    def __init__(self, path):
        self.path = str(path)
        with self.connection() as database:
            database.execute('CREATE TABLE IF NOT EXISTS entries (id TEXT PRIMARY KEY, kind TEXT, expires REAL, data TEXT)')

    @contextmanager
    def connection(self):
        if not Path(self.path).parent.is_dir():
            raise ValueError('Persistent session directory is required')
        database = sqlite3.connect(self.path, timeout=2)
        try:
            database.execute('PRAGMA synchronous=FULL')
            with database:
                yield database
        finally:
            database.close()

    def create(self, kind, data, lifetime):
        identifier = secrets.token_urlsafe(32)
        with self.connection() as database:
            database.execute('BEGIN IMMEDIATE')
            database.execute('DELETE FROM entries WHERE expires<=?', (time.time(),))
            if database.execute('SELECT count(*) FROM entries').fetchone()[0] >= 1000:
                raise ValueError('Authentication capacity reached')
            database.execute('INSERT INTO entries VALUES (?,?,?,?)', (key(identifier), kind, time.time()+lifetime, json.dumps(data)))
        return identifier

    def read(self, identifier, kind, consume=False):
        if not identifier or len(identifier) > 128:
            return None
        with self.connection() as database:
            database.execute('BEGIN IMMEDIATE')
            result = database.execute('SELECT expires,data FROM entries WHERE id=? AND kind=?', (key(identifier),kind)).fetchone()
            if consume:
                database.execute('DELETE FROM entries WHERE id=?', (key(identifier),))
        if not result or result[0] <= time.time():
            return None
        return json.loads(result[1])

    def revoke(self, identifier):
        if identifier:
            with self.connection() as database:
                database.execute('DELETE FROM entries WHERE id=?', (key(identifier),))
