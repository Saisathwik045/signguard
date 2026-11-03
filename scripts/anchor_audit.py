"""Host-only immutable S3 journal snapshots; no worker cloud credentials or document bytes."""
import argparse
import fcntl
import hashlib
import json
import subprocess
from pathlib import Path

from signguard.audit import verify_records


def snapshot(path):
    with Path(path).open('rb') as stream:
        fcntl.flock(stream, fcntl.LOCK_SH)
        raw = stream.read()
    head, count = verify_records(raw.decode().splitlines())
    # Journal event fields deliberately exclude document bytes/filenames.
    return raw, head, count


def anchor(path, bucket, cursor=None):
    raw, head, count = snapshot(path)
    if cursor and Path(cursor).exists() and Path(cursor).read_text().strip() == head:
        return {'unchanged': True, 'head': head, 'events': count}
    key = f'anchors/{count:012d}-{head}.jsonl'
    # stdin, never a shell command or reusable credentials file; IAM denies delete/bypass retention.
    subprocess.run(['aws', 's3', 'cp', '-', 's3://'+bucket+'/'+key, '--sse', 'AES256', '--only-show-errors'],
                   input=raw, check=True)
    if cursor:
        Path(cursor).write_text(head+'\n')
    return {'head': head, 'events': count, 'object_key': key, 'journal_sha256': hashlib.sha256(raw).hexdigest(),
            'scope': 'periodic_external_anchor_not_synchronous_result_release'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('journal', type=Path)
    parser.add_argument('bucket')
    parser.add_argument('--cursor', type=Path)
    args = parser.parse_args()
    print(json.dumps(anchor(args.journal, args.bucket, args.cursor), indent=2))
