"""Audit an immutable local runtime without installing pip into it."""
import argparse
import json
import subprocess
from pathlib import Path

PROGRAM = '''import importlib.metadata as m,importlib.util,json,os,platform,shutil,subprocess
print(json.dumps({"python":platform.python_version(),"uid":os.getuid(),
"pip_present":importlib.util.find_spec("pip") is not None,
"tools":{n:shutil.which(n) for n in ["gcc","make","pdfinfo","pdftoppm","pdfsig"]},
"python_packages":sorted([{"name":d.metadata["Name"],"version":d.version} for d in m.distributions()],key=lambda d:d["name"].lower()),
"os_packages":subprocess.check_output(["dpkg-query","-W","-f","${binary:Package}\\t${Version}\\n"],text=True)}))'''


def inventory(image, output):
    docker = ["docker", "--host=unix:///var/run/docker.sock"]
    image_id = subprocess.check_output([*docker, "image", "inspect", image, "--format", "{{.Id}}"], text=True).strip()
    data = json.loads(subprocess.check_output([*docker, "run", "--rm", "--network=none", "--read-only",
        "--cap-drop=ALL", "--security-opt=no-new-privileges", "--entrypoint=python", image_id, "-c", PROGRAM], text=True))
    data["image_id"] = image_id
    if data["pip_present"] or data["tools"]["gcc"] or data["tools"]["make"]:
        raise ValueError("Runtime contains unnecessary installer/compiler tools")
    output.mkdir(parents=True, exist_ok=True)
    (output / "inventory.json").write_text(json.dumps(data, indent=2)+"\n")
    (output / "installed-python.txt").write_text("\n".join(f"{p['name']}=={p['version']}" for p in data["python_packages"]
                                                       if p["name"].lower() != "signguard")+"\n")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    inventory(args.image, args.output)
