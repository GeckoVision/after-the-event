"""Build data/site.json: what did event guests do with stablecoins around their first check-in?

Input: a MASKED export of a Gecko event dataset (one row per cell; wallets shown as ``7xKX..p9Qz``).
The export stays private: it has one row per wallet. Only the rounded counts written here are public.

For each wallet, day 0 is its first check-in. The script compares the ``WINDOW`` days before day 0
with the ``WINDOW`` days after it (day 0 itself is in neither) and counts wallets, never dollars.
The days after include days spent at the event.

Disclosure rule, applied to every published count, totals included:
- a count is rounded to the nearest ``BASE``;
- a count under ``BASE`` (zero included) is published as ``"<5"``;
- a count that leaves fewer than ``BASE`` wallets outside it is published as ``"nearly all"``;
- a split into groups is published only when every group has at least ``MIN_GROUP`` wallets.
Rounding the totals too means a hidden group cannot be recovered by subtracting the shown ones.

Standard library only. Prints rounded counts, never a wallet.

    python3 scripts/build_after_event.py path/to/export.json --checked-in 153
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WINDOW = 14
BASE = 5
MIN_GROUP = 20
LOW, HIGH = "<5", "nearly all"
# sent and received are separate: a builder who was only paid has not made a payment.
KINDS = ("sent", "received", "swap", "any")
BUCKETS = (("1 day", 1, 1), ("2-3 days", 2, 3), ("4-9 days", 4, 9), ("10+ days", 10, 10_000))
WEEKS = (("-2", -14, -8), ("-1", -7, -1), ("+1", 1, 7), ("+2", 8, 14))


def load_rows(path: Path) -> tuple[list[dict], object]:
    doc = json.loads(path.read_text())
    rows = doc["rows"]
    if rows and isinstance(rows[0], list):
        rows = [dict(zip(doc["columns"], row)) for row in rows]
    return rows, doc.get("version")


def attr(row: dict, name: str) -> float:
    """One number from a daily item's attributes; 0 when missing or unreadable."""
    attrs = row.get("item_attrs")
    if isinstance(attrs, str):
        try:
            attrs = json.loads(attrs)
        except ValueError:
            attrs = None
    try:
        return float(attrs.get(name)) if isinstance(attrs, dict) else 0.0
    except (TypeError, ValueError):
        return 0.0


def wallets_of(rows: list[dict]) -> tuple[dict[str, dict], str | None]:
    wallets: dict[str, dict] = {}
    fetched: list[str] = []
    for row in rows:
        wallet = wallets.setdefault(row["subject"], {"days": {kind: set() for kind in KINDS}})
        field, item = row["field"], row.get("item")
        if row.get("fetched_at"):
            fetched.append(row["fetched_at"])
        if field in ("daily_direct_usd", "daily_swap_n"):
            if not item:
                continue
            day = date.fromisoformat(item[:10])
            hits = {"swap": attr(row, "value") > 0} if field == "daily_swap_n" else {
                "sent": attr(row, "out_usd") > 0,
                "received": attr(row, "in_usd") > 0,
            }
            for kind, hit in hits.items():
                if hit:
                    wallet["days"][kind].add(day)
                    # "any" is a payment sent, a payment received or a swap. Dust and program moves are not counted.
                    wallet["days"]["any"].add(day)
        elif not item:
            wallet[field] = row.get("value")
    return wallets, (max(fetched) if fetched else None)


def as_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def rounded(count: int) -> int:
    return BASE * ((count + BASE // 2) // BASE)


def publish(count: int, total: int | None = None) -> int | str:
    """The disclosure rule for one count; ``total`` is the group the count sits inside."""
    if count < BASE:
        return LOW
    if total is not None and total - count < BASE:
        return HIGH
    return rounded(count)


def summary(group: list[dict]) -> dict:
    total = len(group)
    out: dict = {"wallets": publish(total)}
    for kind in KINDS:
        out[kind] = {
            "before": publish(sum(1 for w in group if w["before"][kind]), total),
            "after": publish(sum(1 for w in group if w["after"][kind]), total),
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("export", type=Path, help="masked dataset export (JSON), kept private")
    parser.add_argument("--checked-in", type=int, default=None, help="check-in accounts in the indexer at read time")
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

    cohort: list[dict] = []
    for wallet in wallets.values():
        day0 = as_date(wallet.get("first_check_in"))
        since, until = as_date(wallet.get("window_start")), as_date(wallet.get("window_end"))
        status = str(wallet.get("read_status") or "").lower()
        if day0 is None or since is None or until is None:
            continue
        if status not in ("ok", "complete", "read") or str(wallet.get("truncated")).lower() == "true":
            continue
        # Each wallet is judged against its own read window, not the widest one in the file.
        if day0 - timedelta(days=WINDOW) < since or day0 + timedelta(days=WINDOW) > until:
            continue
        span = lambda days, lo, hi: any(day0 + timedelta(days=lo) <= d <= day0 + timedelta(days=hi) for d in days)  # noqa: E731
        wallet["before"] = {kind: span(wallet["days"][kind], -WINDOW, -1) for kind in KINDS}
        wallet["after"] = {kind: span(wallet["days"][kind], 1, WINDOW) for kind in KINDS}
        wallet["weeks"] = {label: span(wallet["days"]["any"], lo, hi) for label, lo, hi in WEEKS}
        cohort.append(wallet)

    total = len(cohort)
    if total < MIN_GROUP:
        print("too few wallets to publish", file=sys.stderr)
        return 1
    groups = [
        (label, [w for w in cohort if lo <= int(float(w.get("days_present") or 0)) <= hi]) for label, lo, hi in BUCKETS
    ]
    split_ok = all(len(group) >= MIN_GROUP for _, group in groups)
    buckets = [{"label": label, **summary(group)} for label, group in groups] if split_ok else []
    weeks = [{"week": label, "active": publish(sum(1 for w in cohort if w["weeks"][label]), total)} for label, _, _ in WEEKS]

    site = {
        "dataset": args.dataset,
        "version": version,
        "fetched_at": fetched_at,
        "window_days": WINDOW,
        "read_window": {"since": starts[0].isoformat(), "until": ends[-1].isoformat()},
        "rounding": {"base": BASE, "low": LOW, "high": HIGH, "min_group": MIN_GROUP},
        "attendees": {
            "checked_in": publish(args.checked_in) if args.checked_in is not None else None,
            "read": publish(len(wallets)),
            "compared": publish(total),
            "left_out": publish(len(wallets) - total),
        },
        "all": summary(cohort),
        "by_days_present": buckets,
        "weeks": weeks,
        "unit": "check-in identifiers (one per account), not verified people",
    }
    args.out.write_text(json.dumps(site, indent=1) + "\n")
    print(json.dumps({"attendees": site["attendees"], "all": site["all"], "weeks": weeks, "split_published": split_ok}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
