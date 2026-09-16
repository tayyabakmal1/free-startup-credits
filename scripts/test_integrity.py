"""Executable tests for the rules this project's credibility rests on.

These are not style checks. Each one corresponds to a way a startup-credits list
can mislead a founder, and each is enforced on every pull request.

Run: python scripts/test_integrity.py
"""

from __future__ import annotations

import json
import subprocess
import sys

# Windows consoles default to cp1252 and would crash on the emoji in our tags.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

from build import (
    LIVE_STATUSES,
    matches,
    render_entry,
    resolve_collections,
    sort_programs,
)
from common import (
    COLLECTIONS_OUT,
    ROOT,
    load_collections,
    load_programs,
    load_regions,
)

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((PASS if condition else FAIL, name, detail))


# --------------------------------------------------------------------------
def test_unknown_is_never_eligible(programs, collections) -> None:
    """The core rule. An entry with an unset gate must not appear in a view
    that claims something affirmative about that gate."""
    cfg = load_collections()
    gates = set(cfg["eligibility_gate_fields"])

    eligibility_cols = [c for c in collections
                        if not c.get("scope") and (c.get("filter") or c.get("match_any"))]
    for col in eligibility_cols:
        alts = col.get("match_any") or [col.get("filter") or {}]
        gate_fields = {f for alt in alts for f in alt} & gates
        if not gate_fields:
            continue
        for prog in col["programs"]:
            # The entry must satisfy at least one alternative entirely, and
            # every gate in that alternative must hold an affirmative value.
            ok = False
            detail = ""
            for alt in alts:
                alt_gates = set(alt) & gates
                if not alt_gates:
                    continue
                if all(prog.get(f) is not None and prog.get(f) in alt[f].get("in", [])
                       for f in alt_gates):
                    ok = True
                    break
                detail = ", ".join(f"{f}={prog.get(f)!r}" for f in sorted(alt_gates))
            check(
                f"{col['id']}: {prog['slug']} satisfies an affirmative gate",
                ok,
                detail,
            )


def test_all_unknown_entry_is_excluded(collections) -> None:
    """Snowflake publishes no eligibility at all. It must appear in zero
    eligibility collections and zero CONFIRMED country sections."""
    slug = "snowflake-for-startups"
    leaked = []
    for col in collections:
        if col.get("filter") and not col.get("scope"):
            # Pure category views are not eligibility claims.
            if set(col["filter"]) <= {"category", "benefit_type"}:
                continue
            if any(p["slug"] == slug for p in col["programs"]):
                leaked.append(col["id"])
        for section in col.get("sections") or []:
            if section["id"] == "confirmed" and any(
                p["slug"] == slug for p in section["programs"]
            ):
                leaked.append(f"{col['id']}/confirmed")
    check(
        "all-unknown entry appears in zero eligibility or confirmed views",
        not leaked,
        f"leaked into: {leaked}" if leaked else "correctly excluded everywhere",
    )


def test_country_pages_split(collections, programs) -> None:
    """Confirmed and Not-confirmed must always be separate, Confirmed first,
    and confirmation must never come from our own region taxonomy."""
    regions = load_regions()
    groups = {k: v.get("countries", []) for k, v in regions["groups"].items()}
    country_pages = [c for c in collections if c.get("scope") == "country"]

    check("country pages exist", len(country_pages) == len(regions["featured_countries"]))

    for page in country_pages:
        ids = [s["id"] for s in page["sections"]]
        check(f"{page['id']}: three sections, confirmed first",
              ids == ["confirmed", "not-available", "not-confirmed"], f"got {ids}")

        # No entry may fall through every section and vanish from the page.
        shown = {p["slug"] for s in page["sections"] for p in s["programs"]}
        missing = [p["slug"] for p in programs if p["slug"] not in shown]
        check(f"{page['id']}: no entry silently dropped", not missing,
              f"invisible on this page: {missing}" if missing else "")

        confirmed = next(s for s in page["sections"] if s["id"] == "confirmed")
        code = page["country_code"]
        for prog in confirmed["programs"]:
            regs = prog.get("regions") or []
            check(
                f"{page['id']}: {prog['slug']} confirmed on vendor evidence",
                ("global" in regs or code in regs)
                and prog.get("regions_basis") == "asserted",
                f"regions={regs}, basis={prog.get('regions_basis')}",
            )

    # The specific trap: our apac group contains PK, so a program recorded as
    # `apac` must NOT surface as confirmed for Pakistan.
    pk_page = next((c for c in country_pages if c["country_code"] == "PK"), None)
    if pk_page:
        check("regions.yml apac really does contain PK (the trap is live)",
              "PK" in groups.get("apac", []))
        fake = {"slug": "trap", "regions": ["apac"], "regions_basis": "asserted",
                "excluded_regions": []}
        confirmed_filter = next(
            s["filter"] for s in pk_page["sections"] if s["id"] == "confirmed")
        check(
            "a vendor saying only 'APAC' is NOT confirmed for Pakistan",
            not matches(fake, confirmed_filter),
            "region groups must never substitute for vendor evidence",
        )
        fake_ok = {"slug": "ok", "regions": ["PK"], "regions_basis": "asserted",
                   "excluded_regions": []}
        check("a vendor naming PK explicitly IS confirmed",
              matches(fake_ok, confirmed_filter))
        fake_unstated = {"slug": "u", "regions": [], "regions_basis": "unstated",
                         "excluded_regions": []}
        check("an unstated geography is NOT confirmed",
              not matches(fake_unstated, confirmed_filter))


def test_no_amount_without_evidence(programs) -> None:
    for prog in programs:
        if prog.get("verification_level") == "needs-manual-verification":
            check(f"{prog['slug']}: blocked entry publishes no amount",
                  prog.get("amount_max") is None
                  and prog.get("amount_is_published") is not True)
        if prog.get("amount_max") is not None:
            check(f"{prog['slug']}: published amount carries evidence",
                  bool(prog.get("evidence_quote")) and bool(prog.get("official_source")))


def test_no_tracking_on_vendor_links(programs) -> None:
    bad = []
    for prog in programs:
        for field in ("apply_url", "official_source", "homepage"):
            url = prog.get(field) or ""
            if "utm_" in url or "ref=" in url or "aff=" in url:
                bad.append(f"{prog['slug']}.{field}")
    check("no tracking parameters on any vendor link", not bad, str(bad))


def test_startupflow_links_bounded() -> None:
    """Promotion stays where it was agreed: four areas, no per-category links."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    count = readme.count("startupflowai.com")
    check("StartupFlow AI links stay within the cap",
          count <= 8, f"{count} links in README (max 8)")

    # No self-link may sit inside a category section.
    body = readme.split("## How to read an entry", 1)[-1]
    category_body = body.split("## Find credits for your startup", 1)[0]
    check("no StartupFlow AI link inside any category section",
          "startupflowai.com" not in category_body,
          "category sections must stay pure data")


def test_eligibility_before_amount(programs) -> None:
    """A founder needs to know they qualify before they see a headline number."""
    cf = next(p for p in programs if p["slug"] == "cloudflare-for-startups")
    line = render_entry(cf)
    tags = line.split("\n")[1]
    gate_pos, amount_pos = tags.find("partner"), tags.find("$350k")
    check("eligibility tags render before the credit amount",
          gate_pos != -1 and amount_pos != -1 and gate_pos < amount_pos,
          tags.strip()[:90])


def test_sorting_never_leads_with_amount(programs) -> None:
    ordered = sort_programs(programs)
    live = [p for p in ordered if p.get("status") in LIVE_STATUSES]
    closed = [p for p in ordered if p.get("status") not in LIVE_STATUSES]
    check("live programs sort above closed ones",
          ordered[:len(live)] == live and ordered[len(live):] == closed)
    amounts = [p.get("amount_max") or 0 for p in live]
    check("ordering is not by credit amount",
          amounts != sorted(amounts, reverse=True) or len(set(amounts)) <= 1,
          "a $350k partner-gated tier must not outrank a $10k open offer")


def test_internal_links_resolve() -> None:
    """Every relative markdown link must point at a file that exists.

    Generated pages sit at different depths, so a link written for the root
    README is wrong from categories/ or collections/. Nothing surfaces that
    except checking it.
    """
    import re
    LINK = re.compile(r"\[[^\]]*\]\((?!https?://|mailto:)([^)#\s]+)")
    # GitHub resolves ../../issues/... and ../../../issues/... against the repo,
    # not the filesystem. Those are correct on GitHub and unresolvable on disk.
    GH_RELATIVE = re.compile(r"^\.\./\.\./(\.\./)?(issues|pulls|discussions|wiki)/")

    broken, checked = [], 0
    for md in ROOT.rglob("*.md"):
        if any(part in md.parts for part in (".git", "templates", "node_modules")):
            continue
        if md.name == "LAUNCH-PLAYBOOK.md":
            continue
        for rel in LINK.findall(md.read_text(encoding="utf-8")):
            if GH_RELATIVE.match(rel):
                continue
            checked += 1
            if not (md.parent / rel).resolve().exists():
                broken.append(f"{md.relative_to(ROOT).as_posix()} -> {rel}")
    check("every internal markdown link resolves", not broken,
          f"{checked} checked" + (f"; broken: {broken[:5]}" if broken else ""))


def test_every_program_has_a_page() -> None:
    """A programme with no detail page is unreachable from the browse pages."""
    programs = load_programs()
    missing = [p["slug"] for p in programs
               if not (ROOT / "programs" / f"{p['slug']}.md").exists()]
    check("every programme has a detail page", not missing,
          f"{len(programs)} programmes" + (f"; missing: {missing[:5]}" if missing else ""))


def test_social_preview_matches_data() -> None:
    """The social card is built by a separate command, so it can go stale while
    everything else is current. It did exactly that once."""
    card = ROOT / ".github" / "social-preview.png"
    if not card.exists():
        check("social preview exists", False, "run: make social")
        return
    try:
        from PIL import Image
    except ImportError:
        return  # Pillow is optional; skip rather than fail the run
    with Image.open(card) as img:
        stamped = img.info.get("counts")
    if not stamped:
        check("social preview carries its counts", False,
              "regenerate with `make social` to stamp them")
        return
    live = json.loads((ROOT / "api" / "index.json").read_text(encoding="utf-8"))["counts"]
    expected = {k: live[k] for k in ("total", "verified", "closed")}
    check("social preview counts match the dataset",
          json.loads(stamped) == expected,
          f"card says {stamped}, data says {json.dumps(expected, sort_keys=True)}")


def test_build_is_deterministic() -> None:
    before = subprocess.run([sys.executable, "scripts/build.py"], cwd=ROOT,
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    again = subprocess.run([sys.executable, "scripts/build.py"], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    check("second build writes nothing (deterministic)",
          "no changes" in again.stdout, again.stdout.strip().splitlines()[-1])


def test_generated_files_are_committed() -> None:
    """The guard against a hand-edited README being silently overwritten."""
    proc = subprocess.run(
        ["git", "diff", "--exit-code", "--name-only", "--",
         "README.md", "categories/", "collections/", "api/", "schema/"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    check("generated output matches the data",
          proc.returncode == 0,
          f"drifted: {proc.stdout.strip() or '(untracked - expected before first commit)'}")


def main() -> int:
    programs = load_programs()
    collections = resolve_collections(programs)

    test_unknown_is_never_eligible(programs, collections)
    test_all_unknown_entry_is_excluded(collections)
    test_country_pages_split(collections, programs)
    test_no_amount_without_evidence(programs)
    test_no_tracking_on_vendor_links(programs)
    test_startupflow_links_bounded()
    test_eligibility_before_amount(programs)
    test_sorting_never_leads_with_amount(programs)
    test_social_preview_matches_data()
    test_internal_links_resolve()
    test_every_program_has_a_page()
    test_build_is_deterministic()

    failed = [r for r in results if r[0] == FAIL]
    width = max(len(n) for _, n, _ in results) if results else 0
    for status, name, detail in results:
        if status == FAIL or detail:
            print(f"  [{status}] {name:<{width}}  {detail}")
        else:
            print(f"  [{status}] {name}")
    print()
    print(f"{len(results) - len(failed)}/{len(results)} integrity checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
