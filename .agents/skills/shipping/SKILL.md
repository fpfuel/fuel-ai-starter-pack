---
name: shipping
description: Freight for a promo order to Hawaii. Carton math from the supplier's record (units per carton, weight, size, number of cartons), then live retail rates from both UPS and USPS to the customer's ZIP, cheapest first, each with a source link. Use when Karen asks "what will shipping be", "ship to Maui", "how many boxes", or before any quote that carries freight.
---

# Shipping

Two carriers, one command, about three seconds. Rates are retail: what the shipment would cost
paid at a counter today. The supplier ships the order, so the supplier's own freight quote is
the number that goes on the PO; these rates are the check against it and the figure for a quote
when the supplier has not quoted yet. Never estimate a rate; run the tool or ask.

## Steps

1. Carton facts come from the supplier record (`/product-search` leaves them in
   `internal/Domains/Work/ASB/suppliers-and-pricing.md`): units per carton, weight per carton, carton size, and
   the ship-from ZIP. If any of these is missing, ask Karen or check the supplier site. A weight
   that looks wrong (a 200-unit carton at 6,000 lb) is wrong; say so.
2. Cartons = units needed divided by units per carton, rounded UP. Write it out: 200 mugs at 36
   per carton is 36 + 36 + 36 + 36 + 36 + 20, six cartons, the last part full.
3. Run the comparison, one carton, times the count:

       python .agents/skills/shipping/tools/compare_rates.py --from 91730 --to 96768 --lbs 30 --length 20 --width 14 --height 12 --cartons 6

   Add `--json` to keep the structure. Add `--show-ups` to walk the real UPS page in the Chrome
   window and leave it on screen.
4. Read back the top three lines: carrier, service, total for all cartons, arrival day. Then say
   which one you would put on the quote and why (price, speed, guaranteed day).
5. Put the source links under the figures. USPS lines link to the rendered USPS page for that
   exact shipment. UPS has no link that opens a filled-in quote, so the source is a picture of
   UPS's own results page for that shipment (their logo, the shipment as entered, every service,
   and UPS's timestamp), saved under `internal/Domains/Work/ASB/sourcing/ups-pages/` about 20
   seconds after the rates print. The command prints its path; wait for the file before citing
   it. On the review page the UPS "source" link opens it, with a button that shows it live.
6. Record the quote in `internal/Domains/Work/ASB/suppliers-and-pricing.md` under freight seen so far, with the
   date, the lane, and the per-carton figures.

## What the tool needs

- USPS: nothing. Plain Python, no browser, no account.
- UPS: a normal Google Chrome window that the tool attaches to, or Microsoft Edge when Chrome is
  not installed. `compare_rates.py` starts one automatically (`tools/ups_chrome.py`), parked
  off-screen. Leave it open. UPS refuses automated browsers, so this window is the only way to get
  its rates without a UPS account. The first rate after the window starts takes a few seconds
  longer while UPS sets up its session; the tool waits and retries on its own.
- Both: Node.js installed, for the UPS script.

## Reading the numbers

- Hawaii is one UPS zone from the whole mainland and one USPS zone too, so origin barely moves
  the price; it moves the delivery day.
- USPS Priority Mail usually beats UPS Ground on price and speed under about 30 lb per carton.
  UPS earns its keep when a customer needs a guaranteed day.
- "Online" is the USPS Click-N-Ship price, what a shipper pays printing the label online.
- UPS bills dimensional weight; "billed at 32 lb" on a 10 lb box is the box size, not an error.
- Media Mail is excluded: promo goods do not qualify.
- Neighbor islands: both carriers deliver door to door on every island, so there is no separate
  interisland leg for parcels. The interisland leg only exists for freight that lands in
  Honolulu by consolidator or barge (Young Brothers), which is pallets, not cartons.

## How the order actually ships

Karen does not book the carrier. She writes the purchase order to the supplier with the ship-to
address, the ship method, and either "prepay and add" (the supplier bills freight on the invoice)
or ASB's own carrier account number for third-party billing. The supplier produces, ships, and
reports carrier and tracking; the order-entry assistant passes tracking to the customer. SAGE's order form carries
exactly these fields (ship method, shipping account, drop-ship flag, shipping charge or TBD), and
its Order Status feed returns the carrier and tracking number once a connected supplier ships.
So this skill's job is the freight line on the quote and the ship-method line on the PO.

## Never

- Never fill in a shipping figure that did not come from the tool, the supplier, or Karen.
- Never round cartons down.
- Never present the retail rate as the supplier's freight charge; label which it is.
