---
name: quote
description: Build a customer quote in her own QUOTE sheet layout (her header and logo, line item, setup, shipping, subtotal, Hawaii GE tax 4.712%, total and per-each, product link, turnaround, 30-day validity). Use when she says "quote this", "build the quote", "make the spreadsheet", or gives a customer, item, quantity and prices.
---

# Quote

Writes `External/Quotes/<customer company>/<YYYY-MM-DD>-<item>.xlsx` by filling her own template
workbook cell by cell, so it opens in Excel looking exactly like hers, formulas live.

## Steps

1. Collect, one question at a time if any are missing: customer contact, company, address, phone,
   item description, quantity, sell price per unit, each setup or imprint charge with its label
   (up to three), shipping amount and destination, product URL, turnaround.
2. Check the sources. Unit cost and setup come from a supplier page, a sourcing run, or
   `internal/Domains/Work/ASB/suppliers-and-pricing.md`. Shipping comes from `/shipping`, the
   supplier, or her. If any number has no source, stop and ask. Never estimate.
3. Check the markup. If the price is a supplier net price and a markup rule for that supplier or
   customer is recorded, apply it and say so. If none is recorded, ask her for the sell price.
4. Run:

       python .claude/skills/quote/tools/build_quote.py --customer "Name" --company "Co" --address "Street" --address "City, HI 967xx" --phone "(808) 000-0000" --item "Item" --qty 150 --unit-cost 3.95 --setup "Setup, laser engrave=80" --shipping 143 --destination Hilo --url https://... --turnaround "10-12 business days"

   Repeat `--setup` for each charge. `--note` (up to three) puts carton count, weight and
   ship-from in the left margin, as she does. `--date YYYY-MM-DD` backdates. `--json file`
   takes every input from one JSON file instead.
5. Read the printed summary back: subtotal, tax, total, per each, and the full file path. Ask if
   anything looks off before she sends it.

## What the tool guarantees

- Her template's fonts, borders, column widths, merged cells and logo are untouched; only values
  change. Text too long for its box wraps and its row grows, so nothing is cut off; if that makes
  the sheet taller than a page, it prints scaled to one page. The product URL becomes the link on the "Product Link" label, as on her own sheet. The header comes from `internal/Domains/Work/ASB/quote-header.json`.
- GE tax is 4.712 percent of the subtotal (product plus setup plus shipping). Per-each is total
  divided by quantity. Formulas are written in, so she can change a number in Excel.
- Terms default to Net 30; validity reads 30 days.

## Test case

150 pull-apart keyrings at $3.95, laser setup $80, shipping to Hilo $143: subtotal $815.50,
tax $38.43, total $853.93, $5.69 each.
