"""Snapshot GitHub traffic and star data.

GitHub keeps referrer and view data for FOURTEEN DAYS only. If this is not
running before launch, there is no way to reconstruct afterwards which channel
actually produced the traffic -- the launch becomes unmeasurable.

Appends one JSON line per run to data-history/traffic.jsonl (git-ignored by
default; commit it if you want the history public).

    GITHUB_TOKEN=... python scripts/traffic_snapshot.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = os.environ.get("GITHUB_REPOSITORY", "tayyabakmal1/free-startup-credits")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
OUT = Path(__file__).resolve().parent.parent / "data-history" / "traffic.jsonl"

ENDPOINTS = {
    "views": "traffic/views",
    "clones": "traffic/clones",
    "referrers": "traffic/popular/referrers",
    "paths": "traffic/popular/paths",
}


def api(path: str = ""):
    # The repo endpoint is /repos/{owner}/{repo} with NO trailing slash -- the
    # REST API answers 404 for /repos/{owner}/{repo}/, so only join a sub-path
    # when there is one.
    url = f"https://api.github.com/repos/{REPO}"
    if path:
        url = f"{url}/{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "free-startup-credits-traffic",
            **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    if not TOKEN:
        print("ERROR: traffic endpoints need push access. Set GITHUB_TOKEN.", file=sys.stderr)
        print("       In Actions: GITHUB_TOKEN with `permissions: contents: read`.", file=sys.stderr)
        return 2

    snapshot: dict = {"repo": REPO}
    try:
        repo = api()
        snapshot["stars"] = repo.get("stargazers_count")
        snapshot["forks"] = repo.get("forks_count")
        snapshot["watchers"] = repo.get("subscribers_count")
        snapshot["pushed_at"] = repo.get("pushed_at")
    except urllib.error.HTTPError as exc:
        print(f"ERROR: repo lookup failed ({exc.code}). Does {REPO} exist yet?", file=sys.stderr)
        return 1

    for key, path in ENDPOINTS.items():
        try:
            snapshot[key] = api(path)
        except urllib.error.HTTPError as exc:
            snapshot[key] = {"error": exc.code}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(snapshot, ensure_ascii=False) + "\n")

    views = snapshot.get("views", {})
    print(f"{REPO}")
    print(f"  stars {snapshot.get('stars')}  forks {snapshot.get('forks')}")
    print(f"  views (14d) {views.get('count')} / {views.get('uniques')} unique")
    refs = snapshot.get("referrers") or []
    if isinstance(refs, list) and refs:
        print("  top referrers:")
        for r in refs[:8]:
            print(f"    {r.get('count'):>5}  {r.get('referrer')}")
    print(f"\n  appended -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
