"""Validate data/programs/*.yml and data/collections.yml.

Runs on every pull request. Four jobs, cheapest first, no network access:

  1. Schema validation, with contributor-readable error messages
  2. URL hygiene    -- no affiliate/referral/utm parameters on vendor links
  3. Duplicate detection -- exact normalised-URL collisions and near-duplicate names
  4. Collection integrity -- "unknown is never eligible" and the geography rule,
     enforced structurally so a collection definition cannot circumvent them

Exits non-zero on any error. Warnings never fail the build.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys

# Windows consoles default to cp1252 and would crash on the emoji in our tags.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match

from common import (
    ROOT,
    SCHEMA_OUT,
    load_collections,
    load_programs,
    load_regions,
)

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover - fallback keeps CI working without the dep
    import difflib

    class fuzz:  # type: ignore[no-redef]
        @staticmethod
        def token_set_ratio(a: str, b: str) -> float:
            return difflib.SequenceMatcher(None, a, b).ratio() * 100


# Tracking parameters and referral patterns that must never appear on a vendor URL.
# In this niche readers actively check for these, and one is enough to be
# classified as affiliate spam.
BANNED_QUERY_KEYS = {
    "ref", "referrer", "referral", "aff", "affiliate", "affiliate_id",
    "click_id", "clickid", "fpr", "via", "partner", "partnerid", "partner_id",
    "irclickid", "mpid", "tap_a", "tap_s", "sscid",
}
BANNED_PATH_RE = re.compile(r"/r/[A-Za-z0-9_-]{4,}/?$")

# docs/verification-policy.md: "An entry whose only live artifact is a dated
# changelog or blog post may NEVER be marked active." A marketing post can sit
# online for years after the programme behind it closed.
ANNOUNCEMENT_RE = re.compile(r"/(blog|changelog|news|press|announcements?)(/|$)", re.I)
ACTIVE_STATUSES = {
    "active-self-serve", "active-partner-only", "active-sales-gated",
    "active-amount-undisclosed", "active-invite-only",
}
URL_FIELDS = ("apply_url", "official_source", "homepage", "partners_url")

NAME_DUPLICATE_THRESHOLD = 88


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, where: str, msg: str, hint: str = "") -> None:
        line = f"ERROR  {where}\n         {msg}"
        if hint:
            line += f"\n         hint: {hint}"
        self.errors.append(line)

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"WARN   {where}\n         {msg}")


def did_you_mean(value: str, options: list[str]) -> str:
    if not options or not isinstance(value, str):
        return ""
    best = max(options, key=lambda o: fuzz.token_set_ratio(value.lower(), o.lower()))
    if fuzz.token_set_ratio(value.lower(), best.lower()) >= 55:
        return f"did you mean '{best}'?"
    return f"allowed: {', '.join(options)}"


def humanise(err, schema: dict) -> tuple[str, str]:
    """Turn a jsonschema error into something a non-developer can act on."""
    path = ".".join(str(p) for p in err.absolute_path) or "(root)"
    validator, value = err.validator, err.instance

    if validator == "enum":
        opts = [str(o) for o in err.validator_value]
        return f"{path}: {value!r} is not an allowed value", did_you_mean(str(value), opts)
    if validator == "required":
        missing = re.search(r"'([^']+)'", err.message)
        field = missing.group(1) if missing else "?"
        prop = schema.get("properties", {}).get(field, {})
        return (f"missing required field '{field}'",
                (prop.get("description", "") or "")[:200])
    if validator == "additionalProperties":
        return (f"unknown field(s): {err.message}",
                "check the spelling, or add the field to schema/program.schema.base.json first")
    if validator == "maxLength":
        hint = ("evidence_quote must be the SHORTEST exact span that supports the "
                "claim -- never a paragraph or a full FAQ answer"
                if path.endswith("evidence_quote")
                else f"trim it to {err.validator_value} characters")
        return (f"{path}: too long ({len(value)} chars, max {err.validator_value})", hint)
    if validator == "pattern":
        return f"{path}: {value!r} has the wrong format", f"must match {err.validator_value}"
    if validator == "type" and isinstance(value, (dt.date, dt.datetime)):
        return (f"{path}: YAML parsed this as a date object, not a string",
                'wrap it in quotes: last_verified: "2026-09-14"')
    return f"{path}: {err.message}", ""


# --------------------------------------------------------------------------
# 1. Schema
# --------------------------------------------------------------------------
def check_schema(programs: list[dict], rep: Report) -> None:
    schema = json.loads(SCHEMA_OUT.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    for prog in programs:
        doc = {k: v for k, v in prog.items() if not k.startswith("_")}
        errors = list(validator.iter_errors(doc))
        if not errors:
            continue
        primary = best_match(validator.iter_errors(doc))
        msg, hint = humanise(primary, schema)
        rep.error(prog["_file"], msg, hint)
        for extra in errors:
            if extra is primary:
                continue
            emsg, _ = humanise(extra, schema)
            if emsg != msg:
                rep.error(prog["_file"], emsg)


# --------------------------------------------------------------------------
# 2. Identity and internal references
# --------------------------------------------------------------------------
def check_identity(programs: list[dict], rep: Report) -> None:
    slugs = {p.get("slug") for p in programs}
    for prog in programs:
        where = prog["_file"]
        if prog.get("slug") != prog["_filename_slug"]:
            rep.error(
                where,
                f"slug '{prog.get('slug')}' does not match the filename "
                f"'{prog['_filename_slug']}.yml'",
                "the filename is the authoritative slug -- rename the file or fix the field",
            )
        for ref in prog.get("related") or []:
            if ref not in slugs:
                rep.error(where, f"related: '{ref}' is not an existing program slug")
            if ref == prog.get("slug"):
                rep.error(where, "related: an entry cannot reference itself")


# --------------------------------------------------------------------------
# 3. URL hygiene
# --------------------------------------------------------------------------
def check_url_hygiene(programs: list[dict], rep: Report) -> None:
    for prog in programs:
        where = prog["_file"]
        for field in URL_FIELDS:
            url = prog.get(field)
            if not url or not isinstance(url, str):
                continue
            parts = urlsplit(url)

            bad_keys = []
            for pair in parts.query.split("&"):
                if not pair:
                    continue
                key = pair.split("=", 1)[0].lower()
                if key.startswith("utm_") or key in BANNED_QUERY_KEYS:
                    bad_keys.append(key)
            if bad_keys:
                rep.error(
                    where,
                    f"{field}: tracking or referral parameters are not allowed "
                    f"({', '.join(sorted(set(bad_keys)))})",
                    "link the canonical vendor URL with no query tracking. "
                    "Affiliate links are the fastest way for a credits list to lose trust.",
                )
            if BANNED_PATH_RE.search(parts.path):
                rep.error(where, f"{field}: looks like a referral short-link path",
                          "use the vendor's canonical URL, not a redirector")
            if parts.netloc.lower() in {"bit.ly", "tinyurl.com", "t.co", "lnkd.in", "rb.gy"}:
                rep.error(where, f"{field}: link shorteners are not allowed")


# --------------------------------------------------------------------------
# 4. Duplicates
# --------------------------------------------------------------------------
def normalise_url(url: str) -> str:
    parts = urlsplit(url)
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/").lower()
    return f"{host}{path}"


def check_duplicates(programs: list[dict], rep: Report) -> None:
    by_url: dict[str, list[str]] = defaultdict(list)
    for prog in programs:
        url = prog.get("apply_url")
        if isinstance(url, str):
            by_url[normalise_url(url)].append(prog["_file"])
    for url, files in by_url.items():
        if len(files) > 1:
            rep.error(
                files[-1],
                f"duplicate apply_url -- '{url}' is already used by {files[0]}",
                "if these are genuinely different offers, link them with `related` "
                "and give each its own canonical URL",
            )

    # Compare COMPANY names only. Including the programme name makes almost
    # every pair look alike, because "<X> for Startups" is the universal naming
    # convention here -- GitLab/GitHub and Close/Clerk scored as near-duplicates
    # purely on the shared suffix.
    labels = [(p, (p.get("company") or "").strip().lower()) for p in programs]
    for i, (prog_a, name_a) in enumerate(labels):
        for prog_b, name_b in labels[i + 1:]:
            if not name_a or not name_b:
                continue
            if fuzz.token_set_ratio(name_a, name_b) < NAME_DUPLICATE_THRESHOLD:
                continue
            # Same vendor domain as well as a similar name: a real collision.
            host_a = urlsplit(prog_a.get("apply_url") or "").netloc.lower().removeprefix("www.")
            host_b = urlsplit(prog_b.get("apply_url") or "").netloc.lower().removeprefix("www.")
            base_a = ".".join(host_a.split(".")[-2:])
            base_b = ".".join(host_b.split(".")[-2:])
            if base_a and base_a == base_b:
                rep.warn(
                    prog_b["_file"],
                    f"same vendor domain and a very similar name to {prog_a['_file']} "
                    f"('{prog_b.get('company')}' vs '{prog_a.get('company')}') -- "
                    "confirm these are genuinely different programmes",
                )


# --------------------------------------------------------------------------
# 5. Editorial and evidence rules the schema cannot express
# --------------------------------------------------------------------------
def check_evidence(programs: list[dict], rep: Report) -> None:
    for prog in programs:
        where = prog["_file"]
        level = prog.get("verification_level")

        if prog.get("regions_basis") == "asserted" and not prog.get("regions_quote"):
            rep.warn(
                where,
                "regions_basis is 'asserted' but regions_quote is empty -- a confirmed "
                "geography claim should carry the span that supports it",
            )
        if prog.get("status_basis") == "asserted" and not prog.get("status_quote"):
            rep.warn(where, "status_basis is 'asserted' but status_quote is empty")

        if level == "partially-verified" and not prog.get("eligibility_notes"):
            rep.error(
                where,
                "partially-verified entries must name what could not be inspected",
                "put the specific unverified detail in eligibility_notes",
            )
        if level == "needs-manual-verification" and prog.get("amount_max") is not None:
            rep.error(where, "a blocked page cannot support a published amount",
                      "set amount_max: null and amount_is_published: false")

        if prog.get("amount_max") is not None and prog.get("amount_is_published") is False:
            rep.error(where, "amount_max is set but amount_is_published is false",
                      "these contradict each other")
        if prog.get("amount_max") is not None and not prog.get("currency"):
            rep.error(where, "amount_max is set but currency is missing",
                      "vendors publish EUR and GBP too -- never silently assume USD")

        if prog.get("status") == "discontinued" and prog.get("verification_level") == "verified":
            if not prog.get("evidence_quote"):
                rep.error(where, "a discontinued entry marked verified still needs evidence")

        src = prog.get("official_source") or ""
        if ANNOUNCEMENT_RE.search(src) and prog.get("status") in ACTIVE_STATUSES:
            rep.error(
                where,
                f"status '{prog['status']}' is sourced only from an announcement page",
                "a dated blog or changelog post may never support an 'active' status -- "
                "it can outlive the programme by years. Use 'unverified' until a live "
                "programme page can be cited.",
            )

        apply_url = prog.get("apply_url")
        if isinstance(src, str) and isinstance(apply_url, str):
            src_host = urlsplit(src).netloc.lower().removeprefix("www.")
            homepage = prog.get("homepage")
            if isinstance(homepage, str):
                home_host = urlsplit(homepage).netloc.lower().removeprefix("www.")
                base = ".".join(home_host.split(".")[-2:])
                if base and not src_host.endswith(base):
                    rep.warn(
                        where,
                        f"official_source host '{src_host}' is outside the vendor domain "
                        f"'{home_host}' -- confirm this is still a first-party page",
                    )


# --------------------------------------------------------------------------
# 6. Collection integrity -- the rules that make the browse views trustworthy
# --------------------------------------------------------------------------
def check_collections(rep: Report) -> None:
    cols = load_collections()
    regions = load_regions()
    gate_fields = set(cols["eligibility_gate_fields"])
    group_ids = set(regions["groups"]) - {"global"}
    where = "data/collections.yml"

    def check_filter(filt: dict, label: str, *, confirmed_scope: str | None,
                     allowed_groups: set[str]) -> None:
        """confirmed_scope is 'country', 'region', or None for a non-confirmed filter."""
        for field, clause in (filt or {}).items():
            if not isinstance(clause, dict):
                rep.error(where, f"{label}: filter on '{field}' must be an operator mapping",
                          "use {in: [...]}, {any_of: [...]}, {not_contains: [...]}, {lte: n} or {gte: n}")
                continue
            for op in clause:
                # RULE 1: unknown is never eligible.
                if op == "is_null" and field in gate_fields:
                    rep.error(
                        where,
                        f"{label}: 'is_null' is not allowed on the eligibility gate '{field}'",
                        "UNKNOWN IS NEVER ELIGIBLE -- a collection must match an affirmative "
                        "value read off the vendor's page, never the absence of one",
                    )
                if op not in {"in", "any_of", "not_contains", "lte", "gte", "is_null"}:
                    rep.error(where, f"{label}: unknown filter operator '{op}' on '{field}'")

            # RULE 2: geography is proved by the vendor, never by our taxonomy.
            #
            # A COUNTRY page may confirm only on 'global' or the literal ISO code:
            # a vendor saying "APAC" does not establish that Pakistan qualifies,
            # even though our apac group contains PK.
            #
            # A REGION page may confirm on that region's own group ids, because a
            # vendor asserting "available in the EU" genuinely does confirm a
            # Europe page -- while still confirming no specific country inside it.
            if confirmed_scope and field == "regions":
                for value in clause.get("any_of", []):
                    if value not in group_ids:
                        continue  # 'global' or a literal ISO code: always fine
                    if confirmed_scope == "country":
                        rep.error(
                            where,
                            f"{label}: confirmed COUNTRY section matches region group '{value}'",
                            "a confirmed country section may match only 'global' or a literal "
                            "ISO country code. Region groups are a display aid and are never "
                            "proof that a vendor accepts a given country.",
                        )
                    elif value not in allowed_groups:
                        rep.error(
                            where,
                            f"{label}: confirmed REGION section matches unrelated group '{value}'",
                            f"this collection declares region_groups: "
                            f"{sorted(allowed_groups) or '[]'} -- it may confirm only on those",
                        )

    for col in cols["collections"]:
        scope = col.get("scope")
        allowed = set(col.get("region_groups") or [])
        if "sections" in col:
            for section in col["sections"]:
                check_filter(
                    section.get("filter"),
                    f"{col['id']}/{section['id']}",
                    confirmed_scope=scope if section["id"] == "confirmed" else None,
                    allowed_groups=allowed,
                )
        elif col.get("match_any"):
            for i, alt in enumerate(col["match_any"]):
                check_filter(alt, f"{col['id']}/any[{i}]",
                             confirmed_scope=None, allowed_groups=allowed)
        else:
            check_filter(col.get("filter"), col["id"],
                         confirmed_scope=None, allowed_groups=allowed)

    template = cols.get("country_page_template", {})
    if template.get("scope") != "country":
        rep.error(where, "country_page_template must declare scope: country",
                  "this is what restricts its confirmed section to ISO codes")
    for section in template.get("sections", []):
        scope = "country" if section["id"] == "confirmed" else None
        for i, alt in enumerate(section.get("match_any") or [section.get("filter") or {}]):
            label = f"country_page_template/{section['id']}"
            if section.get("match_any"):
                label += f"/any[{i}]"
            check_filter(alt, label, confirmed_scope=scope, allowed_groups=set())

    # A confirmed country section must also gate on regions_basis: asserted,
    # or "no stated restriction" would silently read as confirmation.
    for section in template.get("sections", []):
        if section["id"] != "confirmed":
            continue
        basis = (section.get("filter") or {}).get("regions_basis", {})
        if basis.get("in") != ["asserted"]:
            rep.error(
                where,
                "country_page_template confirmed section must require "
                "regions_basis: {in: [asserted]}",
                "otherwise an unstated geography becomes a confirmation",
            )


def main() -> int:
    rep = Report()
    programs = load_programs()

    if not programs:
        print("No programs found in data/programs/ -- nothing to validate.")
        return 0

    check_schema(programs, rep)
    check_identity(programs, rep)
    check_url_hygiene(programs, rep)
    check_duplicates(programs, rep)
    check_evidence(programs, rep)
    check_collections(rep)

    for line in rep.warnings:
        print(line)
    if rep.warnings and rep.errors:
        print()
    for line in rep.errors:
        print(line)

    print()
    print(
        f"{len(programs)} programs checked -- "
        f"{len(rep.errors)} error(s), {len(rep.warnings)} warning(s)"
    )

    summary = Path(__import__("os").environ.get("GITHUB_STEP_SUMMARY", ""))
    if str(summary):
        try:
            with summary.open("a", encoding="utf-8") as fh:
                fh.write(f"### Data validation\n\n"
                         f"- programs: **{len(programs)}**\n"
                         f"- errors: **{len(rep.errors)}**\n"
                         f"- warnings: **{len(rep.warnings)}**\n")
                if rep.errors:
                    fh.write("\n```\n" + "\n".join(rep.errors[:40]) + "\n```\n")
        except OSError:
            pass

    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
