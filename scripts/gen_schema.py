"""Generate schema/program.schema.json from the authored base plus data/ enums.

Run via `make schema` (and as part of `make build`). CI re-runs it and fails on
a diff, so the committed schema can never drift from data/categories.yml.
"""

from __future__ import annotations

import json
import sys

from common import SCHEMA_OUT, build_schema, write_if_changed


def main() -> int:
    schema = build_schema()
    content = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
    changed = write_if_changed(SCHEMA_OUT, content)
    cats = len(schema["properties"]["category"]["enum"])
    print(
        f"{'wrote' if changed else 'unchanged'} {SCHEMA_OUT.name} "
        f"({cats} categories, {len(schema['properties'])} properties)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
