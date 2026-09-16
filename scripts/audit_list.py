"""Measure link rot in any markdown list of programs.

Written to audit this project's own data on a schedule. It also reproduces the
published figures for the incumbent list, so anyone can check the claim in
docs/audits/ rather than taking it on trust.

    python scripts/audit_list.py --self
    python scripts/audit_list.py --url https://raw.githubusercontent.com/OWNER/REPO/master/README.md

Two things this deliberately does NOT do:

  * treat a 200 as proof a programme is alive. It is not. A vendor can be
    acquired or shut down while its marketing page stays up for years, which is
    why this prints a semantic-rot caveat with every run.
  * follow a cross-domain redirect silently. Landing on a different registrable
    domain is reported, because it is the strongest discontinuation signal
    available without reading the page.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UA = ("Mozilla/5.0 (compatible; free-startup-credits link auditor; "
      "+https://github.com/tayyabakmal1/free-startup-credits)")
LINK_RE = re.compile(r"\[[^\]]+\]\((https?://[^)\s]+)\)")
TIMEOUT = 25


def registrable(host: str) -> str:
    host = host.lower().removeprefix("www.")
    return ".".join(host.split(".")[-2:])


def check(url: str) -> dict:
    """Return the status of one URL, following redirects and noting brand hops."""
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "text/html,*/*"})
    result = {"url": url, "status": None, "final": url, "note": ""}
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            result["status"] = resp.status
            result["final"] = resp.url
    except urllib.error.HTTPError as exc:
        result["status"] = exc.code
        result["final"] = getattr(exc, "url", url)
    except Exception as exc:                        # DNS failure, TLS, timeout
        result["status"] = 0
        result["note"] = type(exc).__name__
        return result

    before, after = registrable(urlsplit(url).netloc), registrable(urlsplit(result["final"]).netloc)
    if before != after:
        result["note"] = f"cross-domain redirect to {after}"
    elif urlsplit(result["final"]).path.rstrip("/") in ("", "/") \
            and urlsplit(url).path.rstrip("/") not in ("", "/"):
        result["note"] = "redirected to the site root"
    return result


def classify(r: dict) -> str:
    if r["status"] == 0:
        return "unreachable"
    if r["status"] == 404 or r["status"] == 410:
        return "dead"
    if r["status"] in (403, 503):
        return "blocked"          # bot protection, not evidence of death
    if r["note"]:
        return "suspicious"
    if 200 <= r["status"] < 300:
        return "ok"
    return "other"


def collect_urls(text: str) -> list[str]:
    urls = []
    for url in LINK_RE.findall(text):
        host = urlsplit(url).netloc.lower()
        if host.endswith("github.com") or host.endswith("githubusercontent.com"):
            continue                       # self-links and badges, not programmes
        if url not in urls:
            urls.append(url)
    return urls


def self_urls() -> list[str]:
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
    from common import load_programs
    urls = []
    for prog in load_programs():
        for field in ("apply_url", "official_source"):
            u = prog.get(field)
            if u and u not in urls:
                urls.append(u)
    return urls


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--self", action="store_true", help="audit this repository's own data")
    src.add_argument("--url", help="raw markdown URL of a list to audit")
    src.add_argument("--file", help="local markdown file to audit")
    ap.add_argument("--json", help="write full results to this path")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    if args.self:
        urls, label = self_urls(), "free-startup-credits (this repository)"
    else:
        if args.url:
            req = urllib.request.Request(args.url, headers={"User-Agent": UA})
            text = urllib.request.urlopen(req, timeout=TIMEOUT).read().decode("utf-8", "replace")
            label = args.url
        else:
            text = open(args.file, encoding="utf-8").read()
            label = args.file
        urls = collect_urls(text)

    print(f"Auditing {len(urls)} program URLs from {label}\n")

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(check, urls))

    buckets: dict[str, list[dict]] = {}
    for r in results:
        buckets.setdefault(classify(r), []).append(r)

    total = len(results)
    dead = len(buckets.get("dead", []))
    suspicious = len(buckets.get("suspicious", []))
    blocked = len(buckets.get("blocked", []))

    for kind in ("dead", "suspicious", "unreachable", "blocked", "other"):
        rows = buckets.get(kind, [])
        if not rows:
            continue
        print(f"{kind.upper()} ({len(rows)})")
        for r in rows:
            extra = f"  [{r['note']}]" if r["note"] else ""
            print(f"  {r['status']:>3}  {r['url']}{extra}")
        print()

    pct = (dead / total * 100) if total else 0
    print(f"{'-' * 60}")
    print(f"  {total} URLs   ok {len(buckets.get('ok', []))}   "
          f"dead {dead} ({pct:.1f}%)   suspicious {suspicious}   blocked {blocked}")
    print()
    print("  A 200 does NOT mean the programme is alive. A vendor can be acquired")
    print("  or shut down while its marketing page stays up for years. This measures")
    print("  link rot only; semantic rot needs a human re-reading the page.")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"source": label, "total": total, "dead": dead,
                       "dead_pct": round(pct, 1), "suspicious": suspicious,
                       "blocked": blocked, "results": results}, fh, indent=2)
        print(f"\n  full results -> {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
