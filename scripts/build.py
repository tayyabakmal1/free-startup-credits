"""Render README.md, categories/, collections/ and api/ from data/.

The dataset in data/ is the single source of truth. Everything this script
writes is generated output: never hand-edit it. CI re-runs this and fails on a
diff, so a hand edit is caught rather than silently overwritten.

Determinism matters. Nothing here reads the wall clock -- freshness is measured
against the newest last_verified date in the dataset ("data as of"), so running
the build twice on the same data always produces identical bytes.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import sys

# Windows consoles default to cp1252 and would crash on the emoji in our tags.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from collections import Counter

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from common import (
    API_OUT,
    PROGRAMS_OUT,
    CATEGORIES_OUT,
    COLLECTIONS_OUT,
    GENERATED_BANNER,
    README_OUT,
    REVERIFY_DAYS,
    SCHEMA_OUT,
    ROOT,
    TEMPLATES_DIR,
    load_categories,
    load_collections,
    load_programs,
    load_regions,
    load_yaml,
    write_if_changed,
)

DATA_FIELDS_SKIP = ("_file", "_filename_slug")

# Statuses that mean "a founder can still get this today".
LIVE_STATUSES = {
    "active-self-serve", "active-partner-only", "active-sales-gated",
    "active-amount-undisclosed", "active-invite-only", "time-boxed",
}
CLOSED_STATUSES = {"discontinued", "no-program", "closed-to-new"}


# --------------------------------------------------------------------------
# Filter engine
# --------------------------------------------------------------------------
def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def matches(prog: dict, filt: dict | None) -> bool:
    """Apply one collection filter.

    A missing field is None, and None satisfies no affirmative operator. That is
    the mechanical form of "unknown is never eligible": an entry only joins a
    collection when the vendor's page gave us a real value to match on.
    """
    for field, clause in (filt or {}).items():
        value = prog.get(field)
        for op, arg in clause.items():
            if op == "in":
                if value is None or value not in arg:
                    return False
            elif op == "any_of":
                if not set(_as_list(value)) & set(arg):
                    return False
            elif op == "not_contains":
                if set(_as_list(value)) & set(arg):
                    return False
            elif op == "lte":
                if value is None or value > arg:
                    return False
            elif op == "gte":
                if value is None or value < arg:
                    return False
            elif op == "is_null":
                if (value is None) is not bool(arg):
                    return False
            else:
                raise ValueError(f"unknown filter operator '{op}' on '{field}'")
    return True


def matches_any(prog: dict, filters: list[dict] | None) -> bool:
    """True if ANY alternative filter matches.

    Vendors state the same fact in different ways -- one page says "no VC
    funding required", another says "bootstrapped founders welcome". Each
    alternative still requires an affirmative value, so `unknown` remains
    ineligible; this only stops us demanding that a vendor phrase it our way.
    """
    return any(matches(prog, f) for f in (filters or []))


def select(prog: dict, spec: dict) -> bool:
    if spec.get("match_any"):
        return matches_any(prog, spec["match_any"])
    return matches(prog, spec.get("filter"))


def expand_country_pages(collections_cfg: dict, regions: dict) -> list[dict]:
    """Build one collection per featured country from the shared template.

    Each renders exactly two sections, Confirmed first, matching only on 'global'
    or the literal ISO code -- never via a region group.
    """
    template = collections_cfg.get("country_page_template")
    if not template:
        return []

    pages = []
    for country in regions["featured_countries"]:
        code, name = country["code"], country["name"]
        sections = []
        for section in template["sections"]:
            spec = json.loads(
                json.dumps({k: v for k, v in section.items()
                            if k in ("filter", "match_any")})
                .replace("{country_code}", code)
                .replace("{country_name}", name)
            )
            sections.append({
                "id": section["id"],
                "title": section["title"].format(country_name=name, country_code=code),
                "blurb": " ".join(
                    section["blurb"].format(country_name=name, country_code=code).split()
                ),
                **spec,
            })
        pages.append({
            "id": f"country-{code.lower()}",
            "title": f"Startup Credits and {name}",
            "emoji": template.get("emoji", "📍"),
            "scope": "country",
            "grid_title": name,
            "country_code": code,
            "country_name": name,
            "sections": sections,
        })
    return pages


def resolve_collections(programs: list[dict]) -> list[dict]:
    cfg = load_collections()
    regions = load_regions()
    resolved = []

    for col in list(cfg["collections"]) + expand_country_pages(cfg, regions):
        entry = dict(col)
        if "sections" in col:
            sections = []
            for section in col["sections"]:
                members = [p for p in programs if select(p, section)]
                sections.append({**section, "programs": sort_programs(members),
                                 "count": len(members)})
            entry["sections"] = sections
            entry["count"] = sum(s["count"] for s in sections)
            # For a split page the headline count is the CONFIRMED number only.
            confirmed = next((s for s in sections if s["id"] == "confirmed"), None)
            entry["headline_count"] = confirmed["count"] if confirmed else entry["count"]
            entry["headline_label"] = "confirmed" if confirmed else ""
        else:
            members = [p for p in programs if select(p, col)]
            entry["programs"] = sort_programs(members)
            entry["count"] = len(members)
            entry["headline_count"] = len(members)
            entry["headline_label"] = ""
        # Normalise the shape so templates can rely on every key existing
        # (the environment uses StrictUndefined on purpose).
        entry.setdefault("scope", None)
        entry.setdefault("grid_title", entry.get("title"))
        entry.setdefault("sections", None)
        entry.setdefault("programs", None)
        entry.setdefault("emoji", "")
        entry["blurb"] = " ".join((col.get("blurb") or "").split())
        resolved.append(entry)
    return resolved


# --------------------------------------------------------------------------
# Presentation
# --------------------------------------------------------------------------
def sort_programs(programs: list[dict]) -> list[dict]:
    """Live programs first, then by company. Never by credit amount.

    Sorting by headline amount would put a $350k partner-gated tier above a $10k
    offer a reader can actually get today, which inverts the point of the list.
    """
    def key(p: dict):
        return (
            0 if p.get("status") in LIVE_STATUSES else 1,
            p.get("company", "").lower(),
            p.get("program", "").lower(),
        )
    return sorted(programs, key=key)


def fmt_amount(prog: dict) -> str:
    amount = prog.get("amount_max")
    if amount is None:
        return ""
    symbols = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹"}
    sym = symbols.get(prog.get("currency", "USD"), "")
    suffix = prog.get("currency", "") if not sym else ""
    if amount >= 1000 and amount % 1000 == 0:
        text = f"{sym}{int(amount / 1000)}k"
    else:
        text = f"{sym}{int(amount):,}"
    return f"{text}{(' ' + suffix) if suffix else ''}"


def eligibility_tags(prog: dict) -> list[str]:
    """Eligibility first, amount second. That ordering is the whole thesis:
    knowing you qualify for $5k beats seeing a $350k headline you cannot reach."""
    tags: list[str] = []
    gate = prog.get("partner_gate")
    if gate == "none":
        tags.append("🟢 no partner needed")
    elif gate == "improves-offer":
        tags.append("🤝 partner improves offer")
    elif gate in {"required-hard", "required-soft"}:
        tags.append("🤝 partner required")
    elif gate == "tiered":
        tags.append("🤝 partner gates higher tiers")

    if prog.get("funding_required") is False:
        tags.append("💡 no funding needed")
    elif prog.get("requires_vc_backing") is True:
        tags.append("💰 VC-backed only")
    if prog.get("open_to_bootstrapped") is True:
        tags.append("🥾 bootstrapped OK")
    if prog.get("requires_sales_call") is True:
        tags.append("📞 sales call")
    if prog.get("new_customer_only") is True:
        tags.append("🆕 new customers only")
    if prog.get("excluded_regions"):
        tags.append("🌍 region limits")
    return tags


def meta_tags(prog: dict) -> list[str]:
    tags: list[str] = []
    amount = fmt_amount(prog)
    if amount:
        tags.append(amount)
    elif prog.get("amount_is_published") is False:
        tags.append("amount not published")
    if prog.get("duration_months"):
        tags.append(f"{prog['duration_months']}mo")

    level = prog.get("verification_level")
    verified = prog.get("last_verified", "")
    if level == "verified":
        tags.append(f"✅ verified {verified}")
    elif level == "partially-verified":
        tags.append(f"➖ partly verified {verified}")
    else:
        tags.append("⚠️ needs manual check")
    return tags


def render_entry(prog: dict, depth: int = 0) -> str:
    """One markdown list item. Continuation lines are indented two spaces so the
    tags and links stay inside the list item on every markdown renderer."""
    title = f"{prog['company']} — {prog['program']}"
    badge = status_badge(prog)
    head = f"- **[{title}]({prog['apply_url']})**"
    if badge:
        head += f" `{badge}`"
    head += f" — {(prog.get('benefit_summary') or '').strip()}"

    lines = [head]
    tags = eligibility_tags(prog) + meta_tags(prog)
    if tags:
        lines.append("  " + " ".join(f"`{t}`" for t in tags))
    if prog.get("status") == "discontinued":
        closed = f"  Closed {prog.get('discontinued_date')}."
        if prog.get("replaced_by"):
            closed += f" {prog['replaced_by']}"
        lines.append(closed)
    up = "../" * depth
    links = [f"[Details]({up}programs/{prog['slug']}.md)",
             f"[Source]({prog['official_source']})"]
    if prog.get("apply_url") != prog.get("official_source"):
        links.append(f"[Apply]({prog['apply_url']})")
    lines.append("  " + " · ".join(links))
    return "\n".join(lines)


# Human labels for the fields a founder actually screens on. "Not stated by the
# vendor" is rendered explicitly rather than omitted: a blank row would read as
# "no restriction", which is the exact misreading this project exists to prevent.
ELIGIBILITY_ROWS = [
    ("accelerator_required", "Accelerator or partner needed"),
    ("partner_gate", "Partner gate"),
    ("funding_required", "Must have raised funding"),
    ("requires_vc_backing", "Must be VC-backed"),
    ("open_to_bootstrapped", "Bootstrapped founders qualify"),
    ("funding_min_usd", "Minimum raised"),
    ("funding_max_usd", "Maximum raised"),
    ("company_age_max_years", "Maximum company age"),
    ("employees_max", "Maximum employees"),
    ("revenue_max_usd", "Maximum revenue"),
    ("new_customer_only", "New customers only"),
    ("requires_incorporation", "Must be incorporated"),
    ("requires_company_email", "Company email required"),
]

TRI_LABEL = {True: "Yes", False: "No", "unknown": "_Not stated by the vendor_"}

GATE_LABEL = {
    "none": "No partner needed",
    "improves-offer": "A partner improves the offer, but is not required",
    "required-soft": "A partner introduction is effectively needed",
    "required-hard": "A partner code is required",
    "tiered": "Varies by tier",
    "unknown": "_Not stated by the vendor_",
}


def money(value, currency="USD") -> str:
    symbols = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹"}
    sym = symbols.get(currency, "")
    tail = "" if sym else f" {currency}"
    return f"{sym}{int(value):,}{tail}"


def eligibility_rows(prog: dict) -> list[tuple[str, str]]:
    rows = []
    for field, label in ELIGIBILITY_ROWS:
        value = prog.get(field, "unknown")
        if field == "partner_gate":
            rows.append((label, GATE_LABEL.get(value, GATE_LABEL["unknown"])))
        elif field.endswith("_usd"):
            rows.append((label, money(value) if isinstance(value, (int, float))
                         else "_Not stated by the vendor_"))
        elif field in ("company_age_max_years", "employees_max"):
            if isinstance(value, (int, float)):
                unit = "years" if "age" in field else "people"
                basis = prog.get("age_basis")
                extra = f" (from {basis})" if "age" in field and basis and basis != "unknown" else ""
                rows.append((label, f"{value:g} {unit}{extra}"))
            else:
                rows.append((label, "_Not stated by the vendor_"))
        else:
            rows.append((label, TRI_LABEL.get(value, TRI_LABEL["unknown"])))
    return rows


VERIFICATION_LABEL = {
    "verified": ("Verified", "A human opened the official page and confirmed this claim."),
    "partially-verified": ("Partially verified",
        "Official information was read, but some detail could not be inspected directly."),
    "needs-manual-verification": ("Needs manual verification",
        "The vendor's page is blocked, gated or otherwise unreadable. No amount is published."),
}

STATUS_LABEL = {
    "active-self-serve": "Open - apply directly",
    "active-partner-only": "Open, but needs an accelerator, VC or partner code",
    "active-sales-gated": "Open, but requires a sales conversation",
    "active-amount-undisclosed": "Open - the vendor publishes no amount",
    "active-invite-only": "Invite only",
    "time-boxed": "Time-boxed cohort or contest",
    "closed-to-new": "Closed to new applicants",
    "discontinued": "Discontinued",
    "no-program": "This vendor states it runs no startup programme",
    "unverified": "Unverified - could not confirm this is still running",
}


def program_view(prog: dict) -> dict:
    """A copy with every schema field present, for templates.

    The environment uses StrictUndefined on purpose, and program records omit
    fields the vendor never stated. This fills the gaps for rendering ONLY --
    the records used for collection filtering are left untouched, because there
    `None` is what makes "unknown is never eligible" work.
    """
    schema = json.loads(SCHEMA_OUT.read_text(encoding="utf-8"))
    view = {}
    for key, spec in schema["properties"].items():
        if spec.get("enum") == [True, False, "unknown"]:
            view[key] = "unknown"
        elif spec.get("type") == "array" or "array" in (spec.get("type") or []):
            view[key] = []
        else:
            view[key] = None
    view.update({k: v for k, v in prog.items()})

    # Nested objects need the same treatment for the same reason.
    tier_spec = schema["properties"]["tiers"]["items"]["properties"]
    view["tiers"] = [{**{k: None for k in tier_spec}, **t} for t in (view.get("tiers") or [])]
    src_spec = schema["properties"]["conflicting_sources"]["items"]["properties"]
    view["conflicting_sources"] = [{**{k: None for k in src_spec}, **c}
                                   for c in (view.get("conflicting_sources") or [])]
    return view


def status_badge(prog: dict) -> str:
    return {
        "discontinued": "💤 DISCONTINUED",
        "no-program": "🚫 NO PROGRAM",
        "closed-to-new": "🔒 CLOSED TO NEW",
        "time-boxed": "⏳ TIME-BOXED",
        "unverified": "⚠️ UNVERIFIED",
        "active-invite-only": "✉️ INVITE ONLY",
    }.get(prog.get("status", ""), "")


# --------------------------------------------------------------------------
# StartupFlow AI links
# --------------------------------------------------------------------------
def startupflow_context() -> dict:
    cfg = load_yaml(ROOT / "data" / "startupflow.yml")
    query = "&".join(f"{k}={v}" for k, v in cfg["utm"].items())

    def link(path: str, content: str) -> str:
        sep = "&" if "?" in path else "?"
        return f"{cfg['base_url']}{path}{sep}{query}&utm_content={content}"

    total = 0
    placements = {}
    for placement in cfg["placements"]:
        item = dict(placement)
        if "links" in placement:
            item["links"] = [
                {"label": l["label"], "url": link(l["path"], f"{placement['id']}-{i}")}
                for i, l in enumerate(placement["links"])
            ]
            total += len(placement["links"])
        else:
            item["url"] = link(placement["path"], placement["id"])
            total += 1
        item["blurb"] = " ".join((placement.get("blurb") or "").split())
        placements[placement["id"]] = item

    if len(cfg["placements"]) > 4:
        raise SystemExit(
            f"ERROR: {len(cfg['placements'])} StartupFlow AI placements declared; "
            "the agreed limit is 4 (header, matching, related, disclosure)."
        )
    if total > cfg["max_links"]:
        raise SystemExit(
            f"ERROR: {total} StartupFlow AI links exceeds max_links={cfg['max_links']}. "
            "Promotion must stay bounded; consolidate deep links into 'related'."
        )

    return {
        "placements": placements,
        "total_links": total,
        "positioning": cfg["positioning"],
        "disclosure": " ".join(cfg["disclosure"].split()),
    }


# --------------------------------------------------------------------------
# Stats
# --------------------------------------------------------------------------
def compute_stats(programs: list[dict]) -> dict:
    dates = [p["last_verified"] for p in programs if p.get("last_verified")]
    as_of = max(dates) if dates else None

    fresh = 0
    if as_of:
        as_of_date = dt.date.fromisoformat(as_of)
        for prog in programs:
            lv = prog.get("last_verified")
            if lv and (as_of_date - dt.date.fromisoformat(lv)).days <= REVERIFY_DAYS:
                fresh += 1

    levels = Counter(p.get("verification_level") for p in programs)
    return {
        "total": len(programs),
        "as_of": as_of,
        "fresh": fresh,
        "reverify_days": REVERIFY_DAYS,
        "live": sum(1 for p in programs if p.get("status") in LIVE_STATUSES),
        "closed": sum(1 for p in programs if p.get("status") in CLOSED_STATUSES),
        "verified": levels.get("verified", 0),
        "partially_verified": levels.get("partially-verified", 0),
        "needs_manual": levels.get("needs-manual-verification", 0),
    }


# --------------------------------------------------------------------------
# API artefacts
# --------------------------------------------------------------------------
CSV_COLUMNS = [
    "slug", "company", "program", "category", "status", "verification_level",
    "benefit_type", "benefit_summary", "amount_is_published", "amount_max",
    "currency", "duration_months", "partner_gate", "funding_required",
    "accelerator_required", "open_to_bootstrapped", "requires_vc_backing",
    "funding_min_usd", "funding_max_usd", "company_age_max_years",
    "application_mechanism", "requires_sales_call", "regions", "excluded_regions",
    "regions_basis", "apply_url", "official_source", "last_verified", "verified_by",
]


def write_api(programs: list[dict], stats: dict, categories: list[dict],
              collections: list[dict]) -> list[str]:
    written = []
    clean = [{k: v for k, v in p.items() if k not in DATA_FIELDS_SKIP} for p in programs]

    payload = {
        "$schema": "./program.schema.json",
        "generated_from": "data/programs/*.yml",
        "license": "CC-BY-4.0",
        "attribution": (
            "Data from free-startup-credits "
            "(https://github.com/tayyabakmal1/free-startup-credits), licensed CC BY 4.0."
        ),
        "data_as_of": stats["as_of"],
        "count": len(clean),
        "programs": clean,
    }
    if write_if_changed(API_OUT / "programs.json",
                        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n"):
        written.append("api/programs.json")

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="ignore",
                            lineterminator="\n")
    writer.writeheader()
    for prog in clean:
        row = dict(prog)
        for field in ("regions", "excluded_regions"):
            row[field] = ";".join(row.get(field) or [])
        writer.writerow(row)
    if write_if_changed(API_OUT / "programs.csv", buf.getvalue()):
        written.append("api/programs.csv")

    index = {
        "data_as_of": stats["as_of"],
        "counts": {k: stats[k] for k in
                   ("total", "live", "closed", "fresh", "verified",
                    "partially_verified", "needs_manual")},
        "reverify_days": REVERIFY_DAYS,
        "categories": [
            {"id": c["id"], "name": c["name"],
             "count": sum(1 for p in programs if p.get("category") == c["id"])}
            for c in categories
        ],
        "collections": [
            {"id": c["id"], "title": c["title"], "count": c["count"],
             "confirmed": c.get("headline_count") if c.get("scope") == "country" else None}
            for c in collections
        ],
    }
    if write_if_changed(API_OUT / "index.json",
                        json.dumps(index, indent=2, ensure_ascii=False) + "\n"):
        written.append("api/index.json")

    return written


# --------------------------------------------------------------------------
def main() -> int:
    programs = load_programs()
    categories = load_categories()
    collections = resolve_collections(programs)
    stats = compute_stats(programs)
    sfa = startupflow_context()

    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["amount"] = fmt_amount
    env.filters["elig_tags"] = eligibility_tags
    env.filters["meta_tags"] = meta_tags
    env.filters["status_badge"] = status_badge
    env.filters["render_entry"] = render_entry
    env.filters["elig_rows"] = eligibility_rows
    env.filters["money"] = money
    env.globals["money"] = money
    env.globals["VERIFICATION_LABEL"] = VERIFICATION_LABEL
    env.globals["STATUS_LABEL"] = STATUS_LABEL
    env.globals["GATE_LABEL"] = GATE_LABEL

    by_category = [
        {**cat, "programs": sort_programs(
            [p for p in programs if p.get("category") == cat["id"]])}
        for cat in categories
    ]
    ctx = {
        "banner": GENERATED_BANNER,
        "stats": stats,
        "categories": [c for c in by_category if c["programs"]],
        "all_categories": by_category,
        "collections": collections,
        "sfa": sfa,
        "programs": programs,
        "closed": sort_programs([p for p in programs
                                 if p.get("status") in CLOSED_STATUSES]),
    }

    written: list[str] = []

    if write_if_changed(README_OUT, env.get_template("README.md.j2").render(**ctx)):
        written.append("README.md")

    cat_tpl = env.get_template("category.md.j2")
    for cat in by_category:
        if write_if_changed(CATEGORIES_OUT / f"{cat['id']}.md",
                            cat_tpl.render(category=cat, **ctx)):
            written.append(f"categories/{cat['id']}.md")

    prog_tpl = env.get_template("program.md.j2")
    cat_by_id = {c["id"]: c for c in categories}
    for prog in programs:
        member_of = []
        for c in collections:
            if c.get("programs") and prog in c["programs"]:
                member_of.append({**c, "section": None})
                continue
            for sec in (c.get("sections") or []):
                if prog in (sec["programs"] or []):
                    # Being listed on a country page is NOT the same as being
                    # confirmed for that country. Carry the section through so
                    # the page can say which.
                    member_of.append({**c, "section": sec["id"]})
                    break
        if write_if_changed(PROGRAMS_OUT / f"{prog['slug']}.md",
                            prog_tpl.render(program=program_view(prog),
                                            category=cat_by_id.get(prog.get("category"), {}),
                                            member_of=member_of, **ctx)):
            written.append(f"programs/{prog['slug']}.md")

    col_tpl = env.get_template("collection.md.j2")
    for col in collections:
        if write_if_changed(COLLECTIONS_OUT / f"{col['id']}.md",
                            col_tpl.render(collection=col, **ctx)):
            written.append(f"collections/{col['id']}.md")

    written += write_api(programs, stats, categories, collections)

    print(f"build: {len(programs)} programs, {len(collections)} collections, "
          f"{len([c for c in by_category if c['programs']])} non-empty categories")
    print(f"       StartupFlow AI links: {sfa['total_links']} across "
          f"{len(sfa['placements'])} placements")
    if written:
        print(f"       wrote {len(written)} file(s): {', '.join(written[:6])}"
              + (" ..." if len(written) > 6 else ""))
    else:
        print("       no changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
