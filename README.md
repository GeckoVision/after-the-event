# After the Event

Did the builders who checked in at IslandDAO v5 keep using stablecoins after their first day?

This repository holds one page and the method behind it. A guest list (a wallet and a check-in time per guest)
is joined to cleaned on-chain activity, and only counts are published.

## What the page shows

For each builder, day 0 is the first check-in. The page compares the 14 days before day 0 with the 14 days
after it:

- builders who sent at least one stablecoin payment;
- builders who received at least one;
- builders with at least one swap;
- builders with any of these, by week;
- payments sent, by days spent at the event.

A second comparison starts at the last check-in, so it holds no day at the event: the 14 days before the first
check-in against days 1-14 (and later 15-28) after the last one. A period is shown once at least 20 builders fit it.

A payment is a stablecoin transfer between a builder's wallet and a wallet outside the guest list. Sent and
received are counted apart, so a prize or a refund is a payment received, not a payment made. Swaps, DeFi
deposits, transfers between two guests and dust are filed separately and are not payments.

The numbers describe what happened after the first check-in. They do not show that the event caused it: the 14
days after include days at the event, and there is no comparison group yet.

## Files

| File | What it is |
|---|---|
| `index.html` | The page. It reads only `data/site.json`. |
| `data/site.json` | The published counts, with the dataset version and read time. |
| `data/luma-template.csv` | The guest-list shape an event needs. The rows are made up. |
| `scripts/build_after_event.py` | Turns a masked dataset export into `data/site.json`. Standard library only. |
| `scripts/check_site.py` | Fails if `data/site.json` holds an exact count or a string shaped like a wallet. |

The export the script reads has one row per wallet, so it is private and is not in this repository.

## Rules

- Counts only: no wallet addresses, no names, no amounts.
- Every count is rounded to the nearest 5, totals included. A count under 5, zero included, is published as
  "<5". A count that leaves fewer than 5 builders outside it is published as "nearly all".
- A split into groups is published only when every group has at least 20 builders.
- Percentages are computed from the rounded counts.
- The first version of this page (20 Nov 2026) hid small counts but showed exact totals, so some hidden counts
  could be worked out by subtraction. Rounding the totals closes that. The old file is still in the git history.
- Numbers count check-in identifiers, one per account, not verified people.
- Stablecoins on Solana only: USDC, USDT, PYUSD and USDG.
- Check-in days are local days in Florianópolis. Activity days are UTC days.

## Run it on your event

Your event needs three settings in Luma: the Solana wallet field, guest check-in, and a tag on each invite link.
Open an issue with the event name and date.

## Credits

Attendance comes from IslandDAO's on-chain check-in system. The indexer started from Envio's open IslandDAO demo.
Built by [Gecko](https://geckovision.tech). MIT licence for the code in this repository.
