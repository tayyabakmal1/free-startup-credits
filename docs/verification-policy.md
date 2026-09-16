# Verification Policy

This document is the reason to trust this list. It is deliberately published
before the data, and it describes what "verified" does and does not mean here.

Every predecessor list in this niche died the same way: entries were added, never
re-checked, and never removed. A link-check of the largest existing startup
credits list found **14% of its program URLs hard-dead**, and it still listed a
company that was liquidated in 2024 and another that was acquired — both
returning HTTP 200 the whole time. A 200 OK proves nothing.

So the rules below are not aspirational. They are enforced in CI.

---

## 1. The three verification levels

Every record carries a required `verification_level`. A search-engine snippet
never carries the same standing as a page a human opened.

| Level | What it means |
|---|---|
| **`verified`** | A human opened `official_source` — the vendor's own page or official documentation — and directly confirmed the claim. Carries a short `evidence_quote`. |
| **`partially-verified`** | Official information was read, but some eligibility or benefit detail could not be directly inspected: a collapsed FAQ, a figure on a page that would not render, or a vendor that contradicts itself. **The specific unverified detail must be named in `eligibility_notes`.** |
| **`needs-manual-verification`** | The official page is blocked, gated, account-only or otherwise inaccessible. **No financial amount may be published at this level** — CI rejects `amount_max` and `amount_is_published: true`. The record exists to say "this program exists, here is its official URL, and we could not read it." |

Expect roughly **70% / 20% / 10%**. Around 15% of vendors — Google Cloud, Oracle,
Carta, Cohere, JetBrains among them — actively block automated access and are
flagged `bot_blocked: true` so they are not re-triaged every cycle.

### Never publish a number nobody read

This is the single non-negotiable rule. If you cannot copy a sentence from the
vendor's page, you have not verified it. Omit the figure and say so.

---

## 2. Sourcing

**`official_source` must be the exact URL carrying the quoted fact** — not the
program's nicest-looking landing page. The most common real defect found in
competing datasets is a true number attached to a URL that does not contain it.

Source hierarchy:

1. The vendor's official program page
2. The vendor's own docs or help centre (frequently where the real eligibility lives)
3. A dated vendor changelog or blog post — **never sufficient to mark a program `active`**
4. Third-party aggregators — **useful for finding programs, never valid as a source**

### `evidence_quote`

The **shortest exact span** that supports the claim. Capped at 200 characters and
enforced by the schema. Never a paragraph, never a full FAQ answer. This keeps
quoting minimal, makes a stale entry checkable in one second, and means a
good-faith reporter can confirm or refute the record without guessing what we read.

### When a vendor contradicts itself

Record **both** readings in `conflicting_sources`, each with its own URL.

Real example: Algolia's main page states under 7 years old and under $15M raised,
while its own FAQ states under 3 years and under $5M. Silently picking the more
generous reading misleads founders about their rejection risk, and makes anyone
checking against the other page think the entry is fabricated.

---

## 3. Eligibility: unknown is never eligible

The browse collections are the main thing this list offers over its competitors,
and they are only trustworthy because of one rule:

> **A program joins a collection only on an affirmative value read off the
> vendor's page. Never on a null, never on a missing field, never on the absence
> of a stated restriction.**

The tri-state gates — `funding_required`, `accelerator_required`,
`open_to_bootstrapped`, `requires_vc_backing`, `new_customer_only`,
`requires_incorporation`, `requires_company_email`, `requires_sales_call` — are
`true`, `false`, or `unknown`, and default to `unknown`. Leaving one unknown
simply excludes the entry from that view. That is the correct outcome.

`scripts/validate.py` rejects `is_null` as a filter operator on any of these
fields, so the rule cannot be circumvented by a collection definition.

### There is no "Open to everyone" collection

No combination of fields establishes that claim. A program with no partner gate
and a self-serve form can still require VC backing, a minimum raise, a funding
ceiling, a company-age limit, a revenue cap, incorporation, or a specific
country. We publish **`No Partner or Accelerator Required`** and
**`Direct Application`** instead, because those are exactly what the data proves.

---

## 4. Geography: vendor evidence only

Country pages always render **two visibly separate sections**, Confirmed first.
They never share a heading, a count, or a table.

A program is **Confirmed** for a country only when the vendor's own page:

1. explicitly lists that country, **or**
2. states worldwide / global availability, **or**
3. names a region **and itself enumerates that country** within it.

Everything else is **Not confirmed**, which covers two distinct situations, both
stated plainly on the page:

- `regions_basis: unstated` — the vendor publishes no geographic restriction
- `regions_basis: inferred` — the vendor named a region (a bare "APAC") without
  saying which countries it covers

### `data/regions.yml` is never proof

Our region groups are a display and grouping aid. `apac` contains `PK`, but a
vendor saying "available in APAC" does **not** establish that a startup in
Pakistan can apply. Expanding our own group and calling that confirmation would
manufacture eligibility the vendor never granted.

CI enforces this: a confirmed-section filter may match only `global` or a literal
ISO country code. A region group id inside one is a build error.

Overstating country availability would be the most damaging error this project
could make, because eligibility is precisely what founders would rely on it for.

---

## 5. Freshness

**Re-verification cycle: 180 days.** This is a public commitment, and it is
deliberately not shorter.

| Age of `last_verified` | Treatment |
|---|---|
| under 120 days | fresh |
| 120–180 days | info — appears in the rolling re-verification issue |
| over 180 days | warning — flagged prominently |
| over 180 days | error in the weekly scheduled job only |

**A contributor's pull request never fails because somebody else's entry went
stale.** Staleness is fatal only in the scheduled job.

At ~100 entries on a 180-day cycle this costs 8–12 hours a month, which one or
two people can sustain. 150 entries on a 90-day cycle costs 15–20 hours a month
and, judging by the median active life of comparable lists, would not survive
first contact with real life. Promising 90 days and delivering silence is exactly
how the predecessors failed.

### `last_verified` vs `last_checked`

- **`last_verified`** — the date a **human** opened the page and confirmed the
  terms. Never written by a bot. Never backfilled.
- **`last_checked`** — the date a bot last confirmed the URL resolves.

A bot fetching a URL is not a human confirming that a $100,000 offer still exists
on those terms. Conflating the two is how the word "verified" becomes a lie.

### Graceful degradation

The README carries a generated line — *"Last full sweep: `<date>` · N of M
entries verified within 180 days"* — that is never hand-edited. If this project
goes quiet, it degrades into an honestly-dated historical snapshot rather than a
silently misleading list.

---

## 6. Detecting rot

1. **A 200 OK proves nothing.** Link-checking must be paired with scheduled human
   re-verification. Status codes cannot see that a company was acquired.
2. **Follow redirects.** A cross-domain 301 is the strongest discontinuation
   signal available. One vendor's three startup URLs now redirect to a parent
   brand page that states outright that no startup credits are offered.
3. **A dated changelog is not a live program.** If the only surviving artifact is
   a blog post or changelog entry, the status is `unverified` or `discontinued` —
   never `active`. One program's benefit text checked out perfectly while both of
   its application URLs returned 404.
4. **Hunt closures deliberately.** A confirmed, dated closure that every other
   aggregator still lists as live is the highest-value record in this dataset.
   Target two or three per cycle.

---

## 7. What is never accepted

- Affiliate links, referral parameters, `utm_*` tags or link shorteners on any
  vendor URL. CI rejects them. Stripping one is a maintainer edit, not a
  rejection of your contribution.
- Paid placement, sponsored entries, or ordering influenced by any commercial
  relationship. Nothing here is ranked for payment.
- A figure sourced from an aggregator, a listicle, or another list.
- Marketing language in `benefit_summary`. State the structure, not a claim.
- Programs that charge a fee to apply.
- Fully AI-generated entries submitted without human verification.

---

## 8. Reporting a problem

If an entry is wrong, stale, or a program has ended, open a
**Report an expired or changed program** issue. Include what happened — a
rejection, a dead link, a changed amount — and what the page says now.

A founder who just got rejected is the fastest rot signal this project has, and
that report is more valuable than a new entry.
