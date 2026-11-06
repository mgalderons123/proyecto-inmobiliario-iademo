#!/usr/bin/env python3
"""Compare rendered public landings and cache successful comparisons."""

import argparse
import difflib
import hashlib
import json
import re
import subprocess
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CACHE_FILE = ROOT / ".cache" / "environment-comparison.json"
WATCH_PATHS = (
    ROOT / "apps" / "core" / "templates",
    ROOT / "apps" / "core" / "static",
    ROOT / "apps" / "core" / "views.py",
    ROOT / "PRY_INMOB",
)


class PageSummary(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.title = []
        self.h1 = []
        self.h2 = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        self.stack.append((tag, dict(attrs), []))

    def handle_data(self, data):
        for _tag, _attrs, content in self.stack:
            content.append(data)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] != tag:
                continue
            current_tag, attrs, content = self.stack.pop(index)
            text = " ".join("".join(content).split())
            if current_tag == "title":
                self.title.append(text)
            elif current_tag == "h1":
                self.h1.append(text)
            elif current_tag == "h2":
                self.h2.append(text)
            elif current_tag == "a":
                self.links.append((text, attrs.get("href")))
            break


def local_fingerprint():
    digest = hashlib.sha256()
    files = []
    for watched in WATCH_PATHS:
        files.extend(watched.rglob("*") if watched.is_dir() else [watched])
    for path in sorted(path for path in files if path.is_file() and "__pycache__" not in path.parts):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def qa_image_id(container):
    result = subprocess.run(
        ["docker", "inspect", container, "--format", "{{.Image}}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def fetch(url):
    request = urllib.request.Request(url, headers={"Accept-Language": "es"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status, response.read()


def normalize(body):
    return re.sub(rb"\.[0-9a-f]{12}\.(css|js)", rb".\1", body)


def summarize(body):
    parser = PageSummary()
    parser.feed(body.decode())
    return {
        "title": parser.title,
        "h1": parser.h1,
        "h2": parser.h2,
        "links": parser.links,
        "normalized_sha256": hashlib.sha256(normalize(body)).hexdigest(),
        "bytes": len(body),
    }


def load_cache():
    try:
        return json.loads(CACHE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev-url", default="http://127.0.0.1:4000/")
    parser.add_argument("--qa-url", default="http://127.0.0.1:4100/")
    parser.add_argument("--qa-container", default="casarent-qa-web-1")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    identity = {
        "version": 1,
        "dev_source": local_fingerprint(),
        "qa_image": qa_image_id(args.qa_container),
        "dev_url": args.dev_url,
        "qa_url": args.qa_url,
    }
    cached = load_cache()
    if not args.force and cached and cached.get("identity") == identity:
        print("Environment inputs unchanged; reusing successful comparison.")
        print(json.dumps(cached["result"], indent=2, ensure_ascii=False))
        return 0

    dev_status, dev_body = fetch(args.dev_url)
    qa_status, qa_body = fetch(args.qa_url)
    dev_normalized = normalize(dev_body)
    qa_normalized = normalize(qa_body)
    if dev_status != 200 or qa_status != 200 or dev_normalized != qa_normalized:
        print(f"Landing mismatch: dev={dev_status} qa={qa_status}")
        diff = difflib.unified_diff(
            dev_normalized.decode().splitlines(),
            qa_normalized.decode().splitlines(),
            fromfile="development",
            tofile="qa",
            n=2,
        )
        for line in list(diff)[:200]:
            print(line)
        return 1

    result = {"equal": True, "development": summarize(dev_body), "qa": summarize(qa_body)}
    CACHE_FILE.parent.mkdir(exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps({"identity": identity, "result": result}, indent=2, ensure_ascii=False) + "\n"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
