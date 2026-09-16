# Contributing

Thank you. This list is only useful if it stays correct, and that is a job no one
person can do alone.

**The most valuable contribution is not a new program — it is telling us something
here is wrong.** If you applied and got rejected for a reason we do not list, or a
link is dead, or an amount has changed, please
[open a report](../../issues/new?template=report-expired.yml). A founder who just
got rejected is the fastest signal this project has.

---

## The one rule

> **Never publish anything you did not read on the vendor's own page.**

Not from a blog post, not from another startup-deals site, not from memory, not
from an AI summary. If you cannot copy a sentence out of the vendor's page, you
have not verified it — and the honest thing is to say so, which the schema
supports directly.

---

## Three ways to contribute

### 1. Report something wrong (no technical skill needed)

Open an issue:

- **[Report an expired or changed program](../../issues/new?template=report-expired.yml)** — a dead link, a closed program, a changed amount, or a rejection for an unlisted reason
- **[Correct a program's details](../../issues/new?template=amend-program.yml)** — eligibility, region, or benefit details that are wrong
- **[Suggest a new program](../../issues/new?template=add-program.yml)** — with the official URL

### 2. Edit one file

Every program is one file at `data/programs/<slug>.yml`. Two people adding two
programs never conflict.

The easiest route: open the repository, press <kbd>.</kbd> to launch github.dev,
and edit the file there. The schema reference on line 1 of every file gives you
**dropdowns and hover documentation for every field**, with no setup.

Copy an existing file, change the values, open a pull request. You never need to
run anything — CI does it all.

### 3. Re-verify a stale entry

Entries are re-verified on a **180-day cycle**. The rolling
"Re-verify stale entries" issue lists what is due. Pick one, open the page, and
either update `last_verified` or report what changed.

---

## Writing an entry

### Required fields

`slug` · `company` · `program` · `category` · `apply_url` · `official_source` ·
`benefit_type` · `benefit_summary` · `status` · `last_verified` · `verified_by` ·
`verification_level` (+ `evidence_quote` unless the page was inaccessible)

Everything else is optional — but each field you fill in truthfully lets the entry
appear in more browse collections, which is how founders find it.

### `official_source` is the exact URL carrying the fact

Not the prettiest landing page. If the amount lives on a docs or help-centre
subpage, link that subpage. The most common defect in competing datasets is a true
number attached to a page that does not contain it.

### `evidence_quote` is the shortest exact span

Capped at 200 characters. Never a paragraph, never a whole FAQ answer. Copy the
minimum text that supports the claim.

```yaml
evidence_quote: "$10k in credits to build and launch your product"   # good
evidence_quote: "Cloudflare for Startups is designed to help..."     # not evidence
```

### Unknown is not a failure — guessing is

The tri-state gates (`funding_required`, `accelerator_required`,
`open_to_bootstrapped`, `requires_vc_backing`, `new_customer_only`,
`requires_incorporation`, `requires_company_email`, `requires_sales_call`) are
`true`, `false`, or `unknown`, and default to `unknown`.

Set `false` **only** when the page affirmatively says so.

> **The absence of a stated restriction is not permission.**

A page that never mentions funding does not mean funding is not required. Leaving
it `unknown` simply keeps the entry out of the "No Funding Required" view, which is
the correct outcome. We would much rather under-claim than send someone to an
application they cannot win.

### Funding has a direction

```yaml
funding_min_usd: 500000   # "must have raised AT LEAST $500k"  -- a floor
funding_max_usd: 5000000  # "must have raised UNDER $5M"       -- a ceiling
```

Getting these backwards tells a bootstrapped founder to apply for something that
explicitly excludes them.

### Do not flatten a tiered or conditional offer

If year one is a grant and year two covers a percentage of your usage, `amount_max`
is the **year-one** figure and the year-two term goes in `after_credits`. Never sum
them. If tiers have different eligibility, use `tiers[]` with a quote per tier —
publishing a $350k headline while omitting that the top tier needs $5M raised shows
founders a number they can never reach.

### Geography: only what the vendor says

| `regions_basis` | When |
|---|---|
| `asserted` | The vendor names your country, says worldwide/global, or names a region **and enumerates its countries** |
| `inferred` | The vendor names a region ("APAC") without saying which countries |
| `unstated` | The vendor publishes no geographic restriction — **the common case** |

Our `data/regions.yml` groups are a display aid. `apac` contains `PK`, but a vendor
saying "APAC" has **not** confirmed that a startup in Pakistan can apply. CI
enforces this: only `global` or a literal country code can put a program in a
country's Confirmed section.

### When a vendor contradicts itself

Record both readings in `conflicting_sources`, each with its own URL. Silently
picking the more generous one misleads founders about their rejection risk.

---

## What is never accepted

- **Affiliate links, referral parameters, `utm_*` tags, or link shorteners** on any
  vendor URL. CI rejects them. (Stripping one is a maintainer edit, not a rejection
  of your contribution.)
- Paid placement, sponsored entries, or ordering influenced by any commercial
  relationship. Nothing here is ranked for payment.
- A figure sourced from an aggregator, a listicle, or another list.
- Marketing language in `benefit_summary`. Describe the structure, not a claim.
- Programs that charge a fee to apply.
- Entries generated by an AI and submitted without a human opening the page.
- **Hand-edits to `README.md`, `categories/`, `collections/` or `api/`.** These are
  generated from `data/` and CI will fail. Edit the YAML instead.

## Curation

We are not trying to be the biggest list. A new program should add real value —
a new provider, region, category, founder profile, eligibility pattern, or a
materially different benefit. Low-value duplicates and weak offers are declined.

Legitimate, verified programs are welcome regardless of the current count. What we
will not do is pad the list to look larger.

**Closures and negative results are first-class.** A vendor that explicitly states
it runs no startup program (`status: no-program`), or a dated `discontinued` entry,
is worth more than another live listing — every stale competitor still lists those
as available.

---

## Checks that run on your pull request

| Check | What it does |
|---|---|
| Schema | Validates your YAML with contributor-readable errors |
| URL hygiene | Rejects tracking, referral and shortened links |
| Duplicates | Exact URL collisions and near-identical names |
| Integrity | "Unknown is never eligible", country pages split, no amount without evidence |
| Build | Regenerates the README and fails if it drifted |

Link checking runs on a **schedule**, not on your pull request — you will never be
blocked because a vendor rate-limited our checker, or because somebody else's entry
went stale.

To run everything locally (optional):

```bash
python scripts/validate.py
python scripts/build.py
python scripts/test_integrity.py
```

## Licensing

By contributing you agree your contributions are licensed under
[MIT](LICENSE) for code and [CC BY 4.0](data/LICENSE) for data.

## Conduct

Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Be decent; assume good faith.
