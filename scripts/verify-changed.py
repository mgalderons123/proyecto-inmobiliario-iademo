#!/usr/bin/env python3
"""Run pytest only when its code inputs have changed since the last success."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CACHE_FILE = ROOT / ".cache" / "verification.json"
SOURCE_DIRS = ("apps", "PRY_INMOB", "tests", "scripts", "deploy")
SOURCE_FILES = (
    "conftest.py",
    "manage.py",
    "pytest.ini",
    "requirements.txt",
    "requirements-qa.txt",
    "requirements-production.txt",
    "Dockerfile",
    "Dockerfile.production",
    ".dockerignore",
    "compose.dev.yml",
    "compose.qa.yml",
    "compose.production.yml",
)
SOURCE_SUFFIXES = {".html", ".js", ".py", ".sh", ".txt", ".yml", ".yaml", ".conf"}


def iter_inputs():
    for directory in SOURCE_DIRS:
        for path in sorted((ROOT / directory).rglob("*")):
            if path.is_file() and path.suffix in SOURCE_SUFFIXES and "__pycache__" not in path.parts:
                yield path
    for filename in SOURCE_FILES:
        path = ROOT / filename
        if path.exists():
            yield path


def project_fingerprint(command):
    digest = hashlib.sha256()
    for path in iter_inputs():
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    digest.update(json.dumps(command, ensure_ascii=True).encode())
    digest.update(sys.version.encode())
    installed = sorted(
        (distribution.metadata["Name"].lower(), distribution.version)
        for distribution in importlib.metadata.distributions()
        if distribution.metadata["Name"]
    )
    digest.update(json.dumps(installed, ensure_ascii=True).encode())
    digest.update(os.environ.get("DJANGO_SETTINGS_MODULE", "PRY_INMOB.settings").encode())
    return digest.hexdigest()


def load_cache():
    try:
        return json.loads(CACHE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"version": 1, "successes": {}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Ignore a matching successful result")
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    pytest_args = args.pytest_args
    if pytest_args[:1] == ["--"]:
        pytest_args = pytest_args[1:]
    pytest = ROOT / ".venv" / "bin" / "pytest"
    command = [str(pytest if pytest.exists() else Path(sys.executable)), *pytest_args]
    if not pytest.exists():
        command[1:1] = ["-m", "pytest"]

    fingerprint = project_fingerprint(command)
    cached = load_cache()
    if not args.force and fingerprint in cached.get("successes", {}):
        result = cached["successes"][fingerprint]
        print(f"Verification unchanged; reusing successful result from {result['completed_at']}.")
        print("Command:", " ".join(command))
        return 0

    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode != 0:
        return completed.returncode

    from datetime import datetime, timezone

    cached.setdefault("successes", {})[fingerprint] = {
        "command": command,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    CACHE_FILE.parent.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cached, indent=2, sort_keys=True) + "\n")
    print(f"Stored successful verification {fingerprint[:12]}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
