"""Real rootless worker probe for a disposable CI VM or approved cloud host."""
import argparse
import json
import os
import subprocess
from pathlib import Path

from signguard.container_runner import container_command, docker_prefix
from signguard.supervisor import Limits, run_limited


def check(image):
    info = json.loads(subprocess.check_output([*docker_prefix(), 'info', '--format', '{{json .}}'], text=True))
    if info['CgroupVersion'] != '2' or info['CgroupDriver'] != 'systemd' or not any(
            'rootless' in str(value) for value in info['SecurityOptions']):
        raise ValueError('Rootless daemon with enforceable cgroup v2 is mandatory')
    name = 'signguard-rootless-probe'
    command = container_command(image, name)
    program = '''import json,os,socket
from pathlib import Path
assert os.getuid()==65532
assert Path('/sys/fs/cgroup/memory.max').read_text().strip()=='1073741824'
assert Path('/sys/fs/cgroup/pids.max').read_text().strip()=='32'
assert Path('/sys/fs/cgroup/cpu.max').read_text().split()[0]!='max'
assert not any(k.startswith(('AWS_', 'AZURE_', 'GOOGLE_')) for k in os.environ)
try:
 Path('/forbidden').write_text('denied')
 raise AssertionError('Writable root')
except OSError: pass
s=socket.socket();s.settimeout(.2)
assert s.connect_ex(('1.1.1.1',443))!=0
print(json.dumps({'nonroot':True,'read_only':True,'network_none':True,'cgroup_limits':True,'credentials_absent':True}))'''
    try:
        raw, _ = run_limited(command[:-1]+['--entrypoint','python',image,'-c',program],
                             limits=Limits(memory=8*1024*1024*1024))
        return {'rootless_daemon_verified': True, 'worker': json.loads(raw),
                'socket': os.environ['SIGNGUARD_DOCKER_SOCKET'], 'production_ready': False}
    finally:
        subprocess.run([*docker_prefix(),'rm','-f',name],capture_output=True,check=False,timeout=10)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('image')
    parser.add_argument('output', type=Path)
    args=parser.parse_args()
    args.output.write_text(json.dumps(check(args.image), indent=2)+'\n')
