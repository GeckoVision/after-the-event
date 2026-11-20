"""Build data/site.json: did event guests keep transacting after their first check-in?

Input: a MASKED export of a Gecko event dataset (one row per cell; wallets shown as ``7xKX..p9Qz``).
The export stays private: it has one row per wallet. Only the aggregates written here are public.

For each wallet, day 0 is its first check-in. The script compares the ``WINDOW`` days before day 0
with the ``WINDOW`` days after it (day 0 itself is in neither) and counts wallets, never dollars.

Small-group rule: a count of 1 to 4 is withheld, and so is a count that leaves 1 to 4 wallets
outside it. Standard library only. Prints counts, never a wallet.

    python3 scripts/build_after_event.py path/to/export.json --matching 153
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WINDOW = 14
K_MIN = 5
KINDS = ("any", "payment", "swap")
DAILY = {"daily_tx_n": "any", "daily_direct_usd": "payment", "daily_swap_n": "swap"}
BUCKETS = (("1 day", 1, 1), ("2-3 days", 2, 3), ("4-9 days", 4, 9), ("10+ days", 10, 10_000))


def load_rows(path: Path) -> tuple[list[dict], object]:
    doc = json.loads(path.read_text())
    rows = doc["rows"]
    if rows and isinstance(rows[0], list):
        rows = [dict(zip(doc["columns"], row)) for row in rows]
    return rows, doc.get("version")


def positive(row: dict) -> bool:
    """True when this daily item carries a value above zero."""
    attrs = row.get("item_attrs")
    if isinstance(attrs, str):
        try:
            attrs = json.loads(attrs)
        except ValueError:
            attrs = None
    raw = attrs.get("value") if isinstance(attrs, dict) else None
    try:
        return float(raw) > 0
    except (TypeError, ValueError):
        return False


def wallets_of(rows: list[dict]) -> tuple[dict[str, dict], str | None]:
    wallets: dict[str, dict] = {}
    fetched: list[str] = []
    for row in rows:
        wallet = wallets.setdefault(row["subject"], {"days": {kind: set() for kind in KINDS}})
        field, item = row["field"], row.get("item")
        if row.get("fetched_at"):
            fetched.append(row["fetched_at"])
        if field in DAILY:
            if item and positive(row):
                wallet["days"][DAILY[field]].add(date.fromisoformat(item[:10]))
        elif not item:
            wallet[field] = row.get("value")
            if field == "read_status":
                wallet["read_cell_status"] = row.get("status")
    return wallets, (max(fetched) if fetched else None)


def as_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def hide(count: int, total: int) -> int | None:
    """The small-group rule: withhold a count of 1-4 and a count whose complement is 1-4."""
    if 0 < count < K_MIN or 0 < total - count < K_MIN:
        return None
    return count


def summary(group: list[dict]) -> dict:
    total = len(group)
    out: dict = {"wallets": total}
    if total < K_MIN:
        return {"wallets": None}
    for kind in KINDS:
        before = sum(1 for w in group if w["before"][kind])
        after = sum(1 for w in group if w["after"][kind])
        started = sum(1 for w in group if w["after"][kind] and not w["before"][kind])
        kept = sum(1 for w in group if w["after"][kind] and w["before"][kind])
        stopped = sum(1 for w in group if w["before"][kind] and not w["after"][kind])
        shown = {"before": hide(before, total), "after": hide(after, total)}
        moves = {"started": started, "kept": kept, "stopped": stopped}
        # Any one move plus before and after gives the other two, so the three are shown or withheld together.
        safe = all(hide(value, total) is not None for value in moves.values())
        shown.update({name: (value if safe else None) for name, value in moves.items()})
        out[kind] = shown
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("export", type=Path, help="masked dataset export (JSON), kept private")
    parser.add_argument("--matching", type=int, default=None, help="attendees that matched before the read cap")
    parser.add_argument("--dataset", default="islanddao-after-event")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "site.json")
    args = parser.parse_args()

    rows, version = load_rows(args.export)
    wallets, fetched_at = wallets_of(rows)
    starts = sorted(d for w in wallets.values() if (d := as_date(w.get("window_start"))))
    ends = sorted(d for w in wallets.values() if (d := as_date(w.get("window_end"))))
    if not starts or not ends:
        print("no read window in the export", file=sys.stderr)
        return 1
    since, until = starts[0], ends[-1]

    left = {"no_check_in_date": 0, "not_fully_read": 0, "before_window_too_short": 0, "after_window_too_short": 0}
    cohort: list[dict] = []
    for wallet in wallets.values():
        day0 = as_date(wallet.get("first_check_in"))
        status = str(wallet.get("read_status") or "").lower()
        if day0 is None:
            left["no_check_in_date"] += 1
        elif status not in ("ok", "complete", "read") or str(wallet.get("truncated")).lower() == "true":
            left["not_fully_read"] += 1
        elif day0 - timedelta(days=WINDOW) < since:
            left["before_window_too_short"] += 1
        elif day0 + timedelta(days=WINDOW) > until:
            left["after_window_too_short"] += 1
        else:
            span = lambda days, lo, hi: any(day0 + timedelta(days=lo) <= d <= day0 + timedelta(days=hi) for d in days)  # noqa: E731
            wallet["before"] = {kind: span(wallet["days"][kind], -WINDOW, -1) for kind in KINDS}
            wallet["after"] = {kind: span(wallet["days"][kind], 1, WINDOW) for kind in KINDS}
            wallet["weeks"] = {
                label: span(wallet["days"]["any"], lo, hi)
                for label, lo, hi in (("-2", -14, -8), ("-1", -7, -1), ("+1", 1, 7), ("+2", 8, 14))
            }
            cohort.append(wallet)

    total = len(cohort)
    buckets = []
    for label, lo, hi in BUCKETS:
        group = [w for w in cohort if lo <= int(float(w.get("days_present") or 0)) <= hi]
        buckets.append({"label": label, **summary(group)})
    weeks = [{"week": label, "active": hide(sum(1 for w in cohort if w["weeks"][label]), total)} for label in ("-2", "-1", "+1", "+2")]

    site = {
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dataset": args.dataset,
        "version": version,
        "fetched_at": fetched_at,
        "window_days": WINDOW,
        "read_window": {"since": since.isoformat(), "until": until.isoformat()},
        "attendees": {"matching": args.matching, "in_dataset": len(wallets), "compared": total, "left_out": left},
        "all": summary(cohort),
        "by_days_present": buckets,
        "weeks": weeks,
        "unit": "check-in identifiers (one per account), not verified people",
    }
    args.out.write_text(json.dumps(site, indent=1) + "\n")
    print(f"dataset v{version}: {len(wallets)} wallets, {total} compared, left out {left}")
    print(json.dumps({"all": site["all"], "weeks": weeks}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
