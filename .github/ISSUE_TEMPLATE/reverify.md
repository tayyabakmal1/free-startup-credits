---
title: Re-verify stale entries
labels: automated, re-verification
---

This issue is updated weekly. It is the queue, not a notification — nothing here
is urgent, but nothing here should sit for long either.

Run `python scripts/freshness.py` locally for the current list, or see the latest
workflow run for the rendered checklist.

**How to clear an item**

1. Open the entry's `official_source` in a real browser.
2. Confirm the benefit, the eligibility and the application path still match.
3. Either bump `last_verified` to today, or file what changed.

If a page is blocked or gated, set `verification_level: needs-manual-verification`
and remove any published amount — that is a correct outcome, not a failure.

If a programme has closed, do not delete the entry. Set `status: discontinued`
with a `discontinued_date`. A dated closure is one of the most valuable records
here: every stale competitor still lists it as live.
