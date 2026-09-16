"""Report entries due for re-verification.

Writes a markdown checklist for the weekly rolling issue. Deliberately reads the
wall clock -- unlike build.py, this is a point-in-time report, not generated
output that has to stay reproducible.
"""

from __future__ import annotations

import datetime as dt
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from common import REVERIFY_DAYS, STALE_INFO_DAYS, load_programs

REPO = "tayyabakmal1/free-startup-credits"


def main() -> int:
    today = dt.date.today()
    rows = []
    for prog in load_programs():
        lv = prog.get("last_verified")
        if not lv:
            continue
        age = (today - dt.date.fromisoformat(lv)).days
        if age >= STALE_INFO_DAYS:
            rows.append((age, prog))
    rows.sort(key=lambda r: -r[0])

    due = [r for r in rows if r[0] >= REVERIFY_DAYS]
    soon = [r for r in rows if r[0] < REVERIFY_DAYS]

    out = [
        f"Re-verification runs on a **{REVERIFY_DAYS}-day cycle**. "
        f"As of {today.isoformat()}:",
        "",
        f"- **{len(due)}** entries are overdue",
        f"- {len(soon)} are approaching the deadline",
        "",
        "Re-verifying means opening the vendor's page, confirming the terms still "
        "match, and updating `last_verified` — or filing what changed. A bot "
        "checking that the URL resolves is **not** a substitute: a page can return "
        "200 for years after the programme behind it closed.",
        "",
    ]

    def section(title: str, items: list) -> None:
        if not items:
            return
        out.append(f"### {title}")
        out.append("")
        for age, prog in items:
            flag = " ⚠️ blocked for bots — needs a real browser" if prog.get("bot_blocked") else ""
            out.append(
                f"- [ ] **{prog['company']} — {prog['program']}** · {age}d "
                f"([source]({prog['official_source']}) · "
                f"[edit](https://github.com/{REPO}/edit/main/{prog['_file']})){flag}"
            )
        out.append("")

    section("Overdue", due)
    section("Due soon", soon)

    if not rows:
        out = [f"All entries verified within the last {STALE_INFO_DAYS} days. "
               f"Nothing due as of {today.isoformat()}."]

    text = "\n".join(out)
    path = os.environ.get("FRESHNESS_OUT", "freshness.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    print(text)
    print(f"\n(written to {path})", file=sys.stderr)

    # Signal to the workflow whether an issue is warranted.
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as fh:
            fh.write(f"due={len(due)}\n")
            fh.write(f"total_flagged={len(rows)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
