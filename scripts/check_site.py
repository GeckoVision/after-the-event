"""Check data/site.json against the disclosure rule before it is published.

Every count must be a multiple of 5 that is at least 5, or one of the two labels ("<5", "nearly all").
A file that passes holds no exact count, so no group can be recovered by subtracting one table from another.
The file must also hold nothing that looks like a wallet address.

    python3 scripts/check_site.py [data/site.json]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COUNT_SECTIONS = ("attendees", "all", "by_days_present", "weeks", "after_last_check_in")
LABELS = ("<5", "nearly all")
ADDRESS = re.compile(r"[1-9A-HJ-NP-Za-km-z]{32,44}")


def bad_counts(node: object, path: str) -> list[str]:
    if isinstance(node, dict):
        return [msg for key, value in node.items() if key not in ("label", "week") for msg in bad_counts(value, f"{path}.{key}")]
    if isinstance(node, list):
        return [msg for i, value in enumerate(node) for msg in bad_counts(value, f"{path}[{i}]")]
    if node is None or node in LABELS:
        return []
    if isinstance(node, int) and not isinstance(node, bool) and node >= 5 and node % 5 == 0:
        return []
    return [f"{path} = {node!r}"]


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "site.json"
    text = path.read_text()
    site = json.loads(text)
    problems = [msg for section in COUNT_SECTIONS for msg in bad_counts(site.get(section), section)]
    if ADDRESS.search(text):
        problems.append("the file holds a string shaped like a wallet address")
    for problem in problems:
        print("FAIL", problem)
    print("ok" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
