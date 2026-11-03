"""Operator-only host qualification. Never turn a missing control into a passed gate."""
import argparse
import json
import os
import subprocess
from pathlib import Path


def check():
    endpoint = 'unix:///run/user/1001/docker.sock'
    command = ['runuser', '-u', 'signguard-executor', '--', 'docker', '--host='+endpoint]
    info = json.loads(subprocess.check_output([*command, 'info', '--format', '{{json .}}'], text=True))
    if info.get('CgroupVersion') != '2' or info.get('CgroupDriver') != 'systemd':
        raise ValueError('Rootless cgroup v2/systemd resource enforcement is required')
    if not any('rootless' in str(item) for item in info.get('SecurityOptions', [])):
        raise ValueError('Rootful worker daemon is forbidden')
    if subprocess.check_output(['id', '-u', 'signguard-executor'], text=True).strip() != '1001':
        raise ValueError('Executor UID mismatch')
    groups = subprocess.check_output(['id', '-Gn', 'signguard-executor'], text=True).split()
    if 'docker' in groups or 'sudo' in groups:
        raise ValueError('Executor must not have rootful Docker or sudo authority')
    path = Path('/var/lib/signguard/audit')
    if not os.path.ismount(path):
        raise ValueError('Encrypted retained audit volume is not mounted')
    return {'host_static_preflight': True, 'rootless': True, 'cgroup_v2': True,
            'live_worker_probes_required': True, 'tls_auth_browser_required': True,
            'external_ingress_approved': False, 'production_ready': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(check(), indent=2)+'\n')
