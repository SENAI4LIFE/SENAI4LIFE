import base64
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "SENAI4LIFE/SENAI4LIFE"


def api(path, payload=None):
    command = ["gh", "api", f"/repos/{REPOSITORY}/{path}"]
    if payload is not None:
        command += ["--method", "PATCH" if path.startswith("git/refs/") else "POST", "--input", "-"]
    result = subprocess.run(command, input=json.dumps(payload) if payload is not None else None, check=True, capture_output=True, text=True, encoding="utf-8")
    return json.loads(result.stdout)


def publish():
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if api("git/ref/heads/main")["object"]["sha"] != head:
        raise RuntimeError("Main changed during refresh; the next run can refresh it")
    result = subprocess.check_output(["git", "diff", "--name-only", "--", "assets"], cwd=ROOT, text=True)
    changed = result.splitlines()
    if not changed:
        print("Profile assets are current")
        return
    tree = []
    for name in changed:
        path = ROOT / name
        if not name.startswith("assets/") or path.suffix != ".svg" or not path.is_file():
            raise ValueError("Only existing profile SVG assets can be refreshed")
        blob = api("git/blobs", {"content": base64.b64encode(path.read_bytes()).decode(), "encoding": "base64"})
        tree.append({"path": name, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    base = api(f"git/commits/{head}")
    updated = api("git/trees", {"base_tree": base["tree"]["sha"], "tree": tree})
    commit = api("git/commits", {"message": "Refresh profile data", "tree": updated["sha"], "parents": [head]})
    api("git/refs/heads/main", {"sha": commit["sha"], "force": False})
    print(f"Refreshed {len(changed)} profile assets")


if __name__ == "__main__":
    publish()
