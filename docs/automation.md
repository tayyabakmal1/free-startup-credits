# What runs automatically

A plain-language description of the five workflows in `.github/workflows/`.

Those files have to stay as `.yml` — GitHub only executes workflows written in
YAML, so renaming one to `.md` would silently switch that check off rather than
convert it. This page is the readable version.

The same goes for `.github/ISSUE_TEMPLATE/*.yml`: those are **issue forms**, and
the YAML is what produces the dropdowns and required fields a contributor fills
in. As Markdown they would collapse into a single free-text box.

Everything under `data/` is **not automation at all** — it is the dataset. Its
readable form is [the README](../README.md), the
[category pages](../categories/), the [collection pages](../collections/) and one
[detail page per programme](../programs/), all generated from it.

---

## On every pull request

### 1. Validate data — `validate.yml`

Runs `scripts/validate.py` and `scripts/test_integrity.py`. No network access, so
it is fast and cannot be broken by somebody else's vendor rate-limiting you.

It rejects:

- YAML that does not match the schema, with a message naming the field
- **tracking, referral or affiliate parameters** on any vendor link
- duplicate application URLs, and near-identical names on the same vendor domain
- an entry marked `verified` with no quote from the vendor's page
- a published amount on an entry whose page could not be read
- an **active status sourced only from a blog or changelog post** — a marketing
  post can outlive the programme it describes by years
- a collection filter that would let `unknown` count as eligible

And it asserts:

- no programme is silently invisible on a country page
- confirmed country sections match only `global` or a literal country code, never
  one of our own region groups
- every internal markdown link resolves
- StartupFlow AI links stay within their cap and never appear inside a category

### 2. Generated files are current — `build-check.yml`

Regenerates the README, category pages, collection pages, programme pages, the
JSON/CSV API and the schema, then fails if the committed output differs.

This catches two things at once: a stale build, and a hand-edit to a generated
file that the next build would silently wipe. It also re-runs the build twice to
confirm it is deterministic — a build that is not reproducible would fail at
random and train everyone to ignore it.

### 3. Link check (changed files only) — `links.yml`

Strict, but only over URLs in files that pull request actually changed. A
contributor is never blocked because an unrelated vendor was slow.

---

## On a schedule

### 4. Link check and redirect audit — `links.yml`, Mondays 06:00 UTC

Two passes over the whole dataset, neither of which blocks anyone:

- **lychee** checks every URL. Failures open or update a single rolling issue.
- **`scripts/audit_list.py`** follows every redirect and flags cross-domain hops
  and landings on a site root.

The second pass exists because the first is not enough. **A `200 OK` proves
nothing.** A vendor can be acquired or shut down while its marketing page stays
up for years — that is how Coda's application form ended up redirecting to
superhuman.com, and how Segment's startup pages ended up on a Twilio page stating
that no startup credits are offered. Both were caught this way.

`403` is reported as *blocked*, never as dead. Bot protection is not evidence a
programme ended, and counting it as rot would inflate the numbers.

### 5. Re-verification queue — `freshness.yml`, Mondays 07:00 UTC

Lists entries whose `last_verified` is approaching or past the 180-day cycle, into
**one rolling issue** rather than a new issue every week.

Staleness never fails a pull request. It is only ever surfaced here.

### 6. Traffic snapshot — `traffic.yml`, daily 05:00 UTC

Records stars, views, clones and referrers, appending to
`data-history/traffic.jsonl`.

This exists because **GitHub discards referrer data after 14 days.** Without a
daily snapshot there is no way to reconstruct which channel brought people here.

---

## Safeguards worth knowing about

- **Every scheduled job is pinned to this repository.** Without
  `if: github.repository == '...'`, every fork would inherit the schedule and
  hundreds of forks would hammer vendor sites nightly — which is how a project
  gets its User-Agent blocked and loses the ability to verify anything.
- **Every third-party action is pinned to a commit SHA**, not a tag.
- **GitHub disables scheduled workflows after 60 days of repository inactivity.**
  If this project goes quiet over a summer, the crons stop silently. The README's
  generated "data as of" line is the backstop: it keeps showing the real date, so
  the list degrades into an honestly-stale snapshot rather than a quiet lie.

## Running any of it yourself

```bash
make validate    # schema, hygiene, duplicates, integrity rules
make build       # regenerate every page and the API
make check       # validate + build + fail if generated output drifted
make links       # check every URL (needs lychee installed)
make audit       # follow redirects, flag dead links and brand hops
make freshness   # what is due for re-verification
make social      # regenerate the social preview card
```

You do not need any of this to contribute. Edit one file in `data/programs/`,
open a pull request, and CI runs the lot.
