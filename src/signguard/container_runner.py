"""Trusted controller for disposable containers. Never expose its Docker socket to the UI."""
import json
import os
import re
import secrets
import shutil
import subprocess

from .supervisor import Limits, run_limited


def container_command(image, name):
    if not image or any(c.isspace() for c in image) or image.startswith("-"):
        raise ValueError("Invalid worker image")
    return [(shutil.which("docker") or "/usr/bin/docker"), "--host=unix:///var/run/docker.sock", "run", "--rm", "-i",
            "--name", name, "--pull=never", "--network=none", "--read-only", "--user=65532:65532",
            "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=32",
            "--memory=1g", "--memory-swap=1g", "--cpus=1", "--ulimit=cpu=30:30",
            "--ulimit=nofile=64:64", "--ulimit=core=0:0", "--tmpfs=/tmp:rw,noexec,nosuid,size=64m",
            "--env=HTTP_PROXY=", "--env=HTTPS_PROXY=", "--env=ALL_PROXY=", "--env=NO_PROXY=", "--env=http_proxy=", "--env=https_proxy=",
            "--env=all_proxy=", "--env=no_proxy=",
            image]


def analyze_container(payload, image=None):
    image = image or os.environ.get("SIGNGUARD_WORKER_IMAGE", "signguard-worker:phase3")
    inspected = subprocess.run([(shutil.which("docker") or "/usr/bin/docker"), "--host=unix:///var/run/docker.sock",
                                "image", "inspect", "--format", "{{.Id}}", image],
                               capture_output=True, text=True, timeout=10, check=True)
    image_id = inspected.stdout.strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise ValueError("Worker image identity unavailable")
    name = "signguard-job-"+secrets.token_hex(12)
    try:
        # Docker daemon uses the container cgroup limits; supervisor also bounds CLI/output/wall time.
        result, controls = run_limited(container_command(image_id, name), payload, Limits(cpu=60, memory=8*1024*1024*1024))
        report = json.loads(result)
        report["execution_controls"] = {**controls, "isolation": "docker_disposable",
                                        "network_isolation": True, "filesystem_isolation": True,
                                        "worker_image_id": image_id}
        return report
    finally:
        subprocess.run([(shutil.which("docker") or "/usr/bin/docker"), "--host=unix:///var/run/docker.sock", "rm", "-f", name],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
