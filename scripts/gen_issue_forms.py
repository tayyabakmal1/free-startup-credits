"""Generate .github/ISSUE_TEMPLATE/add-program.yml from data/categories.yml.

The category dropdown, the schema enum and the README section order all come from
one file. Hand-maintaining them in three places means the issue form eventually
offers an option the schema rejects, and a non-technical contributor's submission
fails for a reason they cannot see.
"""

from __future__ import annotations

import sys

# Windows consoles default to cp1252 and would crash on the emoji in our tags.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from common import ROOT, load_categories, write_if_changed

OUT = ROOT / ".github" / "ISSUE_TEMPLATE" / "add-program.yml"

HEADER = """# GENERATED from data/categories.yml by scripts/gen_issue_forms.py -- DO NOT EDIT.
name: Suggest a program
description: Add a startup credit, perk or discount that is missing from the list
title: "[Add] "
labels: ["new-program", "needs-verification"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for helping keep this list useful.

        **One rule:** everything here must come from the vendor's own page. Please
        do not copy figures from a blog post, a listicle, or another startup-deals
        site -- those are exactly what this list exists to replace.

        If you cannot find a figure on the vendor's page, leave it blank. An honest
        gap is far more useful than a guess.

  - type: input
    id: company
    attributes:
      label: Company
      description: The vendor's name as they write it
      placeholder: Cloudflare
    validations:
      required: true

  - type: input
    id: program
    attributes:
      label: Program name
      description: The official name of the program, not a description
      placeholder: Cloudflare for Startups
    validations:
      required: true

  - type: dropdown
    id: category
    attributes:
      label: Category
      description: Pick the closest fit
      options:
"""

FOOTER = """    validations:
      required: true

  - type: input
    id: official_source
    attributes:
      label: Official source URL
      description: >-
        The exact vendor page whose text contains the benefit you are quoting
        below. Not the prettiest landing page -- if the amount lives on a docs or
        help-centre page, link that one.
      placeholder: https://www.cloudflare.com/forstartups/
    validations:
      required: true

  - type: input
    id: apply_url
    attributes:
      label: Application URL
      description: >-
        Where a founder actually applies. Must be the canonical vendor link with
        no tracking, referral or affiliate parameters -- these are rejected
        automatically.
      placeholder: https://www.cloudflare.com/forstartups/
    validations:
      required: true

  - type: textarea
    id: evidence_quote
    attributes:
      label: Evidence quote
      description: >-
        Copy the SHORTEST exact sentence from that page that supports the benefit.
        Verbatim, under 200 characters. If you cannot copy a sentence, the entry
        cannot be marked verified -- which is fine, just say so below.
      placeholder: $10k in credits to build and launch your product
    validations:
      required: true

  - type: textarea
    id: benefit
    attributes:
      label: What is the benefit?
      description: >-
        One objective sentence describing the structure. If it is tiered, or if
        year two differs from year one, please say so rather than giving a single
        number -- flattening a tiered offer into one figure is the most common way
        these lists mislead people.
      placeholder: Up to $350k in credits across three tiers; the top two need a partner referral.
    validations:
      required: true

  - type: textarea
    id: eligibility
    attributes:
      label: Eligibility, exactly as stated
      description: >-
        Funding limits (note whether it is a minimum or a maximum), company age,
        headcount, revenue, whether an accelerator or VC referral is needed, and
        any country restrictions. **Only what the page actually says.** Please do
        not infer that something is unrestricted because it is not mentioned.
      placeholder: |
        - Under 10 years old
        - Funded up to Series B
        - Not a previous recipient
        - No country restriction stated on the page
    validations:
      required: false

  - type: dropdown
    id: geography
    attributes:
      label: Does the page say where it is available?
      options:
        - "No -- the page states no geographic restriction"
        - "Yes -- it names specific countries"
        - "Yes -- it says worldwide or global"
        - "It names a region (e.g. APAC) but not which countries"
    validations:
      required: true

  - type: checkboxes
    id: confirmations
    attributes:
      label: Confirmations
      options:
        - label: I opened the vendor's own page and read it myself
          required: true
        - label: The quote above is copied verbatim from that page
          required: true
        - label: The links contain no affiliate, referral or tracking parameters
          required: true
        - label: I have no undisclosed commercial relationship with this vendor
          required: true

  - type: textarea
    id: anything_else
    attributes:
      label: Anything you could not confirm
      description: >-
        Blocked pages, collapsed FAQs you could not open, or figures you saw
        elsewhere but not on the vendor's site. This is genuinely useful -- it
        tells a maintainer where to look.
    validations:
      required: false
"""


def main() -> int:
    options = "".join(
        f"        - {c['id']} — {c['name']}\n" for c in load_categories()
    )
    content = HEADER + options + FOOTER
    changed = write_if_changed(OUT, content)
    print(f"{'wrote' if changed else 'unchanged'} {OUT.relative_to(ROOT).as_posix()} "
          f"({len(load_categories())} category options)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
