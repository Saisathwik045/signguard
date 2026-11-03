"""Cloud-only source/archive preparation when native Sites helpers are unavailable.

Read a short-lived native source credential from hidden stdin. Never persist it in
Git configuration, a file, the source archive, or logs. Publication remains a native
owner-private Sites operation, not a public deployment CLI.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    if sys.stdin.isatty():
        import termios
        attributes = termios.tcgetattr(sys.stdin)
        attributes[3] &= ~termios.ECHO
        termios.tcsetattr(sys.stdin, termios.TCSANOW, attributes)
    print("Ready for native Site credential JSON on hidden stdin", flush=True)
    credential = json.loads(sys.stdin.readline())
    remote = urlsplit(credential["remote_url"])
    if remote.scheme != "https" or remote.username or remote.password:
        raise ValueError("Expected credential-free HTTPS repository URL")
    if credential.get("auth_mode") not in {"http_extra_header", "work_proxy"}:
        raise ValueError("Unsupported native authentication mode")
    env = dict(os.environ)
    for key in ("GIT_TRACE", "GIT_TRACE_CURL", "GIT_CURL_VERBOSE"):
        env.pop(key, None)
    env.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_COUNT="1",
               GIT_CONFIG_KEY_0="credential.helper", GIT_CONFIG_VALUE_0="")
    if credential.get("auth_mode") == "http_extra_header":
        env.update(GIT_CONFIG_COUNT="2", GIT_CONFIG_KEY_1="http.extraHeader",
                   GIT_CONFIG_VALUE_1="Authorization: Bearer "+credential["token"])

    def git(*parts):
        result = subprocess.run(["git", *parts], check=False, cwd=args.directory, env=env, capture_output=True)
        if result.returncode:
            raise RuntimeError("Native source operation failed: "+parts[0])
        return result.stdout.decode().strip()

    git("ls-remote", credential["remote_url"])
    if args.probe:
        print(json.dumps({"source_authentication": "verified"}))
        return
    manifest = json.loads((args.directory / ".openai/hosting.json").read_text())
    if not (args.directory / ".git").exists():
        git("init", "-b", credential["branch"])
        git("config", "user.name", "SignGuard Cloud Automation")
        git("config", "user.email", "signguard-cloud@users.noreply.github.com")
        git("remote", "add", "origin", credential["remote_url"])
    git("add", ".openai/hosting.json", "artifact-checksums.json", "dist")
    if git("status", "--porcelain"):
        git("-c", "commit.gpgsign=false", "commit", "-m", "Publish verified synthetic-only viewer")
    git("push", "origin", "HEAD:"+credential["branch"])
    commit = git("rev-parse", "HEAD")
    git("diff", "--exit-code", "HEAD")
    if args.archive is None:
        raise ValueError("Archive output is required")
    git("archive", "--format=tar.gz", "--output="+str(args.archive.resolve()), "HEAD",
        ".openai/hosting.json", "artifact-checksums.json", "dist")
    print(json.dumps({"project_id": manifest["project_id"], "commit_sha": commit,
                      "archive": str(args.archive.resolve())}), flush=True)


if __name__ == "__main__":
    main()
