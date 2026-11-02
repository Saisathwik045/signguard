"""Actual adversarial process tests; no claim that rlimits create a sandbox."""
import json
import os
import sys
from pathlib import Path

import pytest

from signguard.client import authorized
from signguard.supervisor import Limits, analyze_limited, encode_request, run_limited
from tests.fixtures import unsigned


def test_real_limited_worker():
    report = analyze_limited(unsigned())
    assert not report["assessment"]["alert"]
    assert report["execution_controls"]["network_isolation"] is False


def test_worker_does_not_inherit_credentials(monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "synthetic-never-pass")
    output, _ = run_limited([sys.executable, "-c", "import os,json;print(json.dumps(sorted(os.environ)))"])
    assert "AWS_SECRET_ACCESS_KEY" not in json.loads(output)
    assert "HTTPS_PROXY" not in json.loads(output)


def test_os_memory_limit():
    with pytest.raises(RuntimeError):
        run_limited([sys.executable, "-c", "a=bytearray(256*1024*1024)"], limits=Limits(memory=64*1024*1024))


def test_os_cpu_limit():
    with pytest.raises(RuntimeError):
        run_limited([sys.executable, "-c", "while True: pass"], limits=Limits(cpu=1, wall=5))


def test_wall_timeout_and_secure_cleanup():
    before = set(Path("/tmp").glob("signguard-*"))
    with pytest.raises(TimeoutError):
        run_limited([sys.executable, "-c", "import time;time.sleep(10)"], limits=Limits(wall=.1))
    assert set(Path("/tmp").glob("signguard-*")) == before


def test_os_output_limit():
    with pytest.raises(RuntimeError):
        run_limited([sys.executable, "-c", "print('x'*100000)"], limits=Limits(output=1024))


def test_upload_protocol_rejects_nonpdf_and_unknown_options():
    with pytest.raises(ValueError):
        encode_request(b"not a PDF")
    with pytest.raises(ValueError):
        encode_request(unsigned(), command=b"malicious")


def test_authorization_requires_verified_allowlisted_identity():
    assert authorized({"email": "a@example.test", "email_verified": True}, {"a@example.test"})
    assert not authorized({"email": "a@example.test", "email_verified": False}, {"a@example.test"})
    assert not authorized({"email": "b@example.test", "email_verified": True}, {"a@example.test"})
    assert not authorized({"email": "a@example.test"}, {"a@example.test"})


def test_production_refuses_subprocess_fallback(monkeypatch):
    from signguard.client import analyze_upload
    monkeypatch.setenv("SIGNGUARD_REQUIRE_AUTH", "true")
    monkeypatch.setenv("SIGNGUARD_BACKEND", "limited")
    with pytest.raises(RuntimeError, match="isolated"):
        analyze_upload(unsigned())


@pytest.mark.skipif(os.environ.get("SIGNGUARD_DOCKER_TESTS") != "1", reason="Requires explicit cloud Docker job")
def test_container_runtime_controls():
    from signguard.container_runner import container_command
    from signguard.supervisor import Limits
    command = container_command("signguard-worker:phase3", "signguard-probe-tests")
    probe = '''import os,socket,json,resource
assert os.getuid()==65532
try:
 open('/forbidden','w').write('x')
 raise AssertionError('Root filesystem writable')
except OSError: pass
s=socket.socket();s.settimeout(.2)
assert s.connect_ex(('1.1.1.1',443))!=0
assert not any(k.startswith(('AWS_','AZURE_','GOOGLE_')) for k in os.environ)
print(json.dumps({'uid':os.getuid(),'root_readonly':True,'external_network_blocked':True,
'cpu_limit':resource.getrlimit(resource.RLIMIT_CPU)[0]}))'''
    output, _ = run_limited(command[:-1]+["--entrypoint", "python", command[-1], "-c", probe],
                            limits=Limits(memory=8*1024*1024*1024))
    assert json.loads(output)["cpu_limit"] == 30
    from signguard.container_runner import analyze_container
    report = analyze_container(encode_request(unsigned()))
    assert report["execution_controls"]["network_isolation"]


@pytest.mark.parametrize("address", ["file:///tmp/report", "http://public.example", "http://a:b@controller", "http://controller?q=secret"])
def test_broker_url_validation(monkeypatch, address):
    from signguard.client import analyze_upload
    monkeypatch.setenv("SIGNGUARD_BACKEND", "broker")
    monkeypatch.setenv("SIGNGUARD_BROKER_URL", address)
    monkeypatch.setenv("SIGNGUARD_BROKER_TOKEN", "s"*40)
    with pytest.raises(ValueError):
        analyze_upload(unsigned())


@pytest.mark.skipif(os.environ.get("SIGNGUARD_DOCKER_TESTS") != "1", reason="Requires explicit cloud Docker job")
def test_container_cgroup_memory_enforced():
    from signguard.container_runner import container_command
    command = container_command("signguard-worker:phase3", "signguard-memory-tests")
    probe = "a=bytearray(2*1024*1024*1024)"
    with pytest.raises(RuntimeError):
        run_limited(command[:-1]+["--entrypoint", "python", command[-1], "-c", probe],
                    limits=Limits(memory=8*1024*1024*1024, wall=15))


def test_queue_has_no_unbounded_wait():
    from signguard.supervisor import _SLOT
    assert _SLOT.acquire(blocking=False)
    try:
        with pytest.raises(RuntimeError, match="busy"):
            analyze_limited(unsigned())
    finally:
        _SLOT.release()


def test_timeout_terminates_descendant_group(tmp_path):
    pid_file = tmp_path / "child-pid"
    program = ("import subprocess,sys,time,pathlib;"
               "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);"
               f"pathlib.Path({str(pid_file)!r}).write_text(str(p.pid));time.sleep(30)")
    with pytest.raises(TimeoutError):
        run_limited([sys.executable, "-c", program], limits=Limits(wall=.5))
    pid = int(pid_file.read_text())
    status = Path(f"/proc/{pid}/stat")
    # SIGKILL delivery is asynchronous; observe bounded termination rather than a scheduler race.
    import time
    deadline = time.monotonic()+2
    while time.monotonic() < deadline:
        try:
            if status.read_text().split()[2] == "Z":
                return
        except FileNotFoundError:
            return
        time.sleep(.01)
    pytest.fail("Descendant remained live after process-group termination")
