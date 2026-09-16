# Link rot in public startup-credits lists

**Measured 2026-09-14.** Reproduce with:

```bash
python scripts/audit_list.py --self
python scripts/audit_list.py --url https://raw.githubusercontent.com/dakshshah96/awesome-startup-credits/master/README.md
```

Every number below came from that script on that date. Nothing here is quoted
from a third party.

---

## Why this exists

This project claims its data is fresh. That claim is worth nothing unless it is
measurable, so the same tool that audits other lists audits this one, and both
results are published.

It also answers the reasonable question *"why build another one of these?"* with
evidence rather than opinion.

---

## Results

| List | Program URLs | Dead | Redirected to another brand | Blocked |
|---|---|---|---|---|
| `dakshshah96/awesome-startup-credits` (2,954★, last pushed 2024-08-10) | 52 | **5 (9.6%)** | 7 | 3 |
| **This repository** | 151 | **1 (0.7%)** | 5 | 3 |

### Dead links in the incumbent list

```
404  https://deepsource.io/startup-program/
404  https://www.agora.io/en/agora-for-startups/
404  https://www.stackpath.com/resources/propel-startup-program/
404  https://www.zenduty.com/early-stage-startup-program/
404  https://www.getcloudapp.com/elevate
```

### The more interesting failure: a 200 that means nothing

Eight of its entries return a perfectly healthy `200 OK` while redirecting to a
**different company's domain** — the signature of an acquisition or a shutdown:

| Listed URL | Now lands on |
|---|---|
| `segment.com/industry/startups/` | twilio.com |
| `sendgrid.com/accelerate/` | twilio.com |
| `instabug.com/startups` | luciq.ai |
| `www.gosquared.com/early-stage/` | ecosend.io |
| `www.getcloudapp.com/elevate` | zight.com |
| `deepsource.io/startup-program/` | deepsource.com |
| `developers.snapchat.com/accelerate/` | snap.com |
| `www.clever-cloud.com/en/early-stage` | clever.cloud |

A founder following the Segment link lands on a Twilio page that states plainly
that no additional startup credits are offered. The link "works". The offer does
not exist.

**This is the central point.** Status-code checking is close to worthless on its
own. Roughly 23% of that list (12 of 52 URLs) has rotted in one way or another,
and a link checker alone would report only 9.6% of it.

---

## What this repository does about it

1. **A 200 is never treated as proof.** `scripts/audit_list.py` follows every
   redirect and flags cross-domain hops and landings on a site root. It runs
   weekly in CI and files into the triage issue.
2. **Human re-verification on a 180-day cycle.** `last_verified` is only ever set
   by a person who opened the page. A separate `last_checked` records automated
   checks. The two are never conflated.
3. **Announcement pages cannot support an "active" status.** CI rejects it. A
   blog post can outlive the programme it describes by years.
4. **Closures are kept, dated, not deleted.** `status: discontinued` with a
   `discontinued_date`, and `status: no-program` where a vendor states it runs
   none. These records are the ones a stale list cannot give you.

### Our own rot, published for the same scrutiny

The self-audit is not clean, and pretending otherwise would defeat the purpose:

- **1 dead URL (0.7%)** — Railway's `startup.railway.app`, already recorded as
  `status: unverified` because only a dated changelog survives.
- **5 redirect signals** — Cohere, Groq and Redis programme pages now bounce to
  their site roots; DataStax redirects to ibm.com; Coda's application form
  redirects to superhuman.com after its acquisition. **All five are recorded as
  `unverified`, not active.**
- **3 blocked (403)** — Akamai, Algolia's support form and Salesforce's invite
  page reject automated clients. Flagged `bot_blocked` for permanent manual review.

Four of those five redirect cases were caught by the researchers during
verification. One — Coda — was caught by this script afterwards, which is
precisely the job it exists to do.

---

## Method and limits

- Program URLs only. GitHub links, badges and share buttons are excluded.
- `HEAD` then `GET`, real browser User-Agent, redirects followed, 25s timeout.
- **403/503 is reported as *blocked*, never as dead.** Bot protection is not
  evidence that a programme ended, and counting it as rot would inflate the
  figure. Three URLs in each list fall here.
- Registrable-domain comparison is a two-label heuristic, so `aws.amazon.com` →
  `aws.com` reads as a cross-domain hop when it is only an alias. Redirect counts
  are a triage signal for human review, not a verdict.
- **This measures link rot, not semantic rot.** A company can be liquidated while
  its site stays up. Only a human reading the page catches that.

## No criticism intended

`dakshshah96/awesome-startup-credits` was a genuinely useful list and earned its
2,954 stars. It has not been pushed since 2024-08-10, and unmaintained lists decay
— that is a property of the format, not a failing of its author.

The point of publishing these numbers is not that someone else's list decayed. It
is that **this one will too, unless the decay is measured continuously and in
public.** That is why the audit script points at this repository first.
