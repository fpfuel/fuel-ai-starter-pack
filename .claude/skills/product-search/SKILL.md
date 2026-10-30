---
name: product-search
description: Find and compare promo products through SAGE (price breaks, setup, decoration, carton, ship-from, lead time), add live UPS and USPS freight to the customer's ZIP, and rank by landed cost per unit. Writes a sourcing run for the review page and records findings in the suppliers file. Use when she says "find me", "source this", "who has", "compare suppliers", or "find me $5 cups, 100 quantity, shipped to Maui".
---

# Product search

Goal: two or three products she can choose from, every number traceable to where it came from.

## Steps

1. Capture the ask in one line and confirm it: item, quantity, target price per unit, decoration,
   colors, in-hands date, and the ship-to ZIP. A city alone is not enough for freight; ask for
   the ZIP.
2. Run the one-shot search (SAGE search, product details, both carriers, landed cost), about ten
   seconds:

       python .claude/skills/product-search/tools/source.py "ceramic mug 11 oz" --qty 200 --to 96768 --to-label "Makawao, Maui" --max-price 6 --candidates 3 --prompt "what she said, word for word"

   It spends 1 + candidates SAGE queries from the account's monthly credit, so keep
   `--candidates` at 3 to 5 unless she asks for more. Add `--no-ups` when the env check says UPS
   rates do not work here (in the cloud, for example); USPS still runs.
3. Read back the top three in one line each: landed cost per unit, net, setup, freight basis,
   supplier, lead time. Then one line on which looks best and why. Do not apply markup here unless
   a rule is recorded in `internal/Domains/Work/ASB/suppliers-and-pricing.md`.
4. Point her at the review page. On her own computer: start it once with
   `python .claude/tools/review/server.py` and leave it running, then http://127.0.0.1:8765; it
   shows the newest run by itself. In the cloud, `source.py` also saves the page as one HTML file
   next to the run; give her that path to download and open.
5. Append a short table (supplier, item, net at her quantity, setup, lead time, ship-from) to the
   "Findings log" in `internal/Domains/Work/ASB/suppliers-and-pricing.md` with today's date. A new
   supplier gets a row with "agreement: unknown".
6. Ask which product to quote. Then `/quote` with that candidate's numbers and the freight option
   she picks, the freight labeled "retail estimate" until the supplier quotes it. She can also pick
   and build on the review page; the result is the same sheet in the same folder.

## Reading a run in chat

Runs are JSON files in `internal/Domains/Work/ASB/sourcing/`, newest last by name. Each candidate
has `name`, `supplier`, `itemNum`, `supplierUrl`, `netAtQty`, `setupChg`, `decorationMethod`,
`prodTime`, `shipFromZip`, `carton` (`units`, `lbs`, `L`, `W`, `H`), `cartons`, `landed`
(`perUnitUSD`, `basis`), and `freight.options` (`carrier`, `service`, `totalUSD`, `delivery`,
`source`, `inputs`). Quote from these fields; never from memory.

## When SAGE is not set up

The tool says so. Then search by hand: the supplier site she names, or hawaiipromo.com. For each of
two or three products capture only what the page shows (supplier and item number, price at each
break and which covers her quantity, setup and extra charges, decoration and imprint area, units
per carton with carton weight and size, ship-from ZIP, lead time, page URL), write "not shown" for
the rest, then run `/shipping` for freight.

## Never

- Never quote a price from memory or from a different quantity break.
- Never present a net price as a sell price.
