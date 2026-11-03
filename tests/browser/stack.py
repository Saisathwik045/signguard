"""Cloud-only complete container stack; no external ingress or local-user execution."""
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from signguard.preview_auth import password_hash

ROOT = Path(__file__).resolve().parents[2]


def free_port():
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        return connection.getsockname()[1]


class CloudStack:
    def __init__(self, artifacts):
        self.artifacts = artifacts
        artifacts.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix="sg-integration-")
        self.path = Path(self.directory.name)
        self.rpc = self.path / "rpc"
        self.audit = self.path / "audit"
        self.rpc.mkdir(mode=0o750)
        os.chmod(self.rpc, 0o750)
        self.audit.mkdir(mode=0o770)
        os.chmod(self.audit, 0o770)
        self.password = secrets.token_urlsafe(24)
        self.token = secrets.token_urlsafe(32)
        self.gateway_token = secrets.token_urlsafe(32)
        self.prefix = "sg-int-"+secrets.token_hex(5)
        self.ui = self.prefix+"-ui"
        self.controller = self.prefix+"-controller"
        self.network = self.prefix+"-net"
        self.port, self.control_port = free_port(), free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.control_url = f"http://127.0.0.1:{self.control_port}"
        self.docker = [shutil.which("docker"), "--host=unix:///var/run/docker.sock"]
        self.process = None
        self.ui_process = None
        self.ui_log = None
        self.host_ui = os.environ.get("SIGNGUARD_BROWSER_UI_HOST") == "1"
        self.log = None

    def command(self, *args, check=True):
        result = subprocess.run([*self.docker, *args], check=False, capture_output=True, text=True)
        if check and result.returncode:
            raise RuntimeError("Container operation failed: "+args[0])
        return result

    def start(self):
        environment = {**os.environ, "SIGNGUARD_EXECUTOR_SOCKET": str(self.rpc / "executor.sock"),
                       "SIGNGUARD_WORKER_IMAGE": "signguard-worker:phase4"}
        self.log = (self.path / "executor.log").open("w")
        self.process = subprocess.Popen([sys.executable, "-m", "signguard.executor"], cwd=ROOT,
                                        env=environment, stdout=self.log, stderr=self.log, start_new_session=True)
        for _ in range(100):
            if (self.rpc / "executor.sock").exists():
                break
            if self.process.poll() is not None:
                raise RuntimeError("Executor failed to start")
            time.sleep(.1)
        self.command("network", "create", self.network)
        common = ["--network", self.network, "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                  "--tmpfs=/tmp:rw,noexec,nosuid,size=64m", "--memory=1g", "--pids-limit=64"]
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            common += ["--env", name+"="]
        self.command("run", "-d", "--name", self.controller, "--network-alias=controller", *common,
                     "--group-add", str(os.getgid()), "--publish", f"127.0.0.1:{self.control_port}:8080",
                     "--mount", f"type=bind,src={self.rpc},dst=/run/signguard,readonly",
                     "--mount", f"type=bind,src={self.audit},dst=/var/lib/signguard",
                     "--env", "SIGNGUARD_BROKER_TOKEN="+self.token,
                     "--env", "SIGNGUARD_EXECUTOR_SOCKET=/run/signguard/executor.sock",
                     "--env", "SIGNGUARD_AUDIT_PATH=/var/lib/signguard/audit.jsonl",
                     "--env", "SIGNGUARD_REQUESTS_PER_MINUTE=10", "--env", "SIGNGUARD_QUOTA_WINDOW_SECONDS=600",
                     "signguard-controller:phase4")
        if self.host_ui:
            ui_env = {"PATH": os.environ["PATH"], "LANG": "C.UTF-8", "OPENBLAS_NUM_THREADS": "1",
                      "SIGNGUARD_REQUIRE_AUTH": "true", "SIGNGUARD_AUTH_MODE": "gateway", "SIGNGUARD_GATEWAY_TOKEN": self.gateway_token,
                      "SIGNGUARD_COOKIE_SECURE": "false", "SIGNGUARD_WEB_PORT": str(self.port),
                      "SIGNGUARD_STREAMLIT_PORT": str(free_port()),
                      "SIGNGUARD_PREVIEW_PRIVATE_CONFIRMED": "true", "SIGNGUARD_BACKEND": "broker",
                      "SIGNGUARD_PREVIEW_PASSWORD_HASH": password_hash(self.password),
                      "SIGNGUARD_BROKER_URL": self.control_url, "SIGNGUARD_BROKER_TOKEN": self.token}
            self.ui_log = (self.path / "ui.log").open("w")
            self.ui_process = subprocess.Popen([sys.executable, "-m", "signguard.preview_web"],
                cwd=ROOT, env=ui_env, stdout=self.ui_log, stderr=self.ui_log, start_new_session=True)
        else:
            self.command("run", "-d", "--name", self.ui, *common,
                         "--publish", f"127.0.0.1:{self.port}:8501",
                         "--env", "SIGNGUARD_REQUIRE_AUTH=true", "--env", "SIGNGUARD_AUTH_MODE=gateway",
                         "--env", "SIGNGUARD_GATEWAY_TOKEN="+self.gateway_token,
                         "--env", "SIGNGUARD_COOKIE_SECURE=false", "--env", "SIGNGUARD_WEB_HOST=0.0.0.0",
                         "--env", "SIGNGUARD_PREVIEW_PRIVATE_CONFIRMED=true", "--env", "SIGNGUARD_BACKEND=broker",
                         "--env", "SIGNGUARD_PREVIEW_PASSWORD_HASH="+password_hash(self.password),
                         "--env", "SIGNGUARD_BROKER_URL=http://controller:8080",
                         "--env", "SIGNGUARD_BROKER_TOKEN="+self.token, "--entrypoint", "python", "signguard-ui:phase4",
                         "-m", "signguard.preview_web")
        self.wait_health(self.url+"/_stcore/health")
        self.wait_health(self.control_url+"/health")
        names = [self.controller] if self.host_ui else [self.ui, self.controller]
        inspections = json.loads(self.command("inspect", *names).stdout)
        assert all(m["Destination"] != "/var/run/docker.sock" for c in inspections for m in c["Mounts"])
        if not self.host_ui:
            assert not any(m["Destination"] == "/run/signguard" for m in inspections[0]["Mounts"])
        self.artifacts.joinpath("stack.json").write_text(json.dumps({"url": self.url, "scope": "cloud_loopback_only", "quota_attempt_limit": 10, "quota_window_seconds": 600,
            "user_accessible_preview": False, "ui_runtime": "nonroot_cloud_process" if self.host_ui else "container",
            "controller_has_docker_socket": False,
            "ui_has_executor_socket": None if self.host_ui else False,
            "ui_filesystem_isolated": not self.host_ui,
            "host_ui_limitation": "Trusted test UID shares host filesystem" if self.host_ui else None,
            "worker_image": "signguard-worker:phase4",
            "worker_image_id": self.command("image", "inspect", "signguard-worker:phase4", "--format", "{{.Id}}").stdout.strip()}, indent=2)+"\n")
        return self

    def wait_health(self, url):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for _ in range(120):
            try:
                with opener.open(url, timeout=1) as response:
                    if response.status == 200:
                        return
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(.5)
        raise RuntimeError("Stack health deadline exceeded")

    def close(self):
        try:
            self.command("cp", f"{self.controller}:/var/lib/signguard/audit.jsonl", str(self.artifacts / "audit.jsonl"), check=False)
            for name in (self.ui, self.controller):
                self.command("rm", "-f", name, check=False)
            self.command("network", "rm", self.network, check=False)
        finally:
            if self.ui_process is not None:
                self.ui_process.terminate()
                self.ui_process.wait(timeout=10)
            if self.ui_log is not None:
                self.ui_log.close()
            if self.process is not None:
                self.process.terminate()
                self.process.wait(timeout=10)
            if self.log is not None:
                self.log.close()
            self.directory.cleanup()
