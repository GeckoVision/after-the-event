# After the Event

Did the builders who checked in at IslandDAO v5 keep using stablecoins after their first day?

This repository holds one page and the method behind it. A guest list (a wallet and a check-in time per guest)
is joined to cleaned on-chain activity, and only counts are published.

## What the page shows

For each builder, day 0 is the first check-in. The page compares the 14 days before day 0 with the 14 days
after it:

- builders with at least one stablecoin payment;
- builders with at least one swap;
- builders with any stablecoin activity;
- the same, by week and by days spent at the event.

A payment is a stablecoin transfer to another wallet. Swaps, DeFi deposits, transfers between a builder's own
wallets and dust are filed separately and are not payments.

The numbers describe what happened after the first check-in. They do not show that the event caused it.

## Files

| File | What it is |
|---|---|
| `index.html` | The page. It reads only `data/site.json`. |
| `data/site.json` | The published counts, with the dataset version and read time. |
| `data/luma-template.csv` | The guest-list shape an event needs. The rows are made up. |
| `scripts/build_after_event.py` | Turns a masked dataset export into `data/site.json`. Standard library only. |

The export the script reads has one row per wallet, so it is private and is not in this repository.

## Rules

- Counts only: no wallet addresses, no names, no amounts.
- A count of 1 to 4 is withheld. So is a count that leaves 1 to 4 builders outside it.
- Numbers count check-in identifiers, one per account, not verified people.
- Stablecoins on Solana only: USDC, USDT, PYUSD and USDG.
- Check-in days are local days in Florianópolis. Activity days are UTC days.

## Run it on your event

Your event needs three settings in Luma: the Solana wallet field, guest check-in, and a tag on each invite link.
Open an issue with the event name and date.

## Credits

Attendance comes from IslandDAO's on-chain check-in system. The indexer started from Envio's open IslandDAO demo.
Built by [Gecko](https://geckovision.tech). MIT licence for the code in this repository.
