"""Host-root only: read Secrets Manager JSON from stdin and write bounded service env files."""
import argparse
import base64
import json
import os
import re
import secrets
import sys
from pathlib import Path


def write(values, target):
    if set(values) != {'oauth_client_id', 'oauth_client_secret'}:
        raise ValueError('Only OAuth application credentials belong in the browser-entered secret')
    if any(not isinstance(v, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,256}', v) for v in values.values()):
        raise ValueError('Invalid OAuth credential format')
    # Persist once, retain these across releases; rotating broker/session secrets is a separate action.
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    state = target/'generated.json'
    if state.exists():
        generated = json.loads(state.read_text())
    else:
        generated = {'gateway': secrets.token_urlsafe(32), 'broker': secrets.token_urlsafe(32),
                     'cookie': base64.b64encode(secrets.token_bytes(32)).decode()}
        state.write_text(json.dumps(generated))
        state.chmod(0o600)
    contents = {
        'ui.env': {'SIGNGUARD_GATEWAY_TOKEN': generated['gateway'], 'SIGNGUARD_BROKER_TOKEN': generated['broker'],
                   'SIGNGUARD_GITHUB_CLIENT_ID':values['oauth_client_id'],
                   'SIGNGUARD_GITHUB_CLIENT_SECRET':values['oauth_client_secret']},
        'controller.env': {'SIGNGUARD_BROKER_TOKEN': generated['broker']},

    }
    for name, content in contents.items():
        path = target/name
        path.write_text(''.join(key+'='+value+'\n' for key, value in content.items()))
        path.chmod(0o600)


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    write(json.load(sys.stdin), args.directory)
