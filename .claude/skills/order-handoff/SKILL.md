---
name: order-handoff
description: When a customer accepts a quote, turn the quote into the order summary for the order-entry assistant and the purchase order text for the supplier, saved beside the quote. Use when she says "they said yes", "turn this into an order", "write the PO", or "hand this off".
---

# Order handoff

## Steps

1. Find the quote. She names the customer or the file; look in `External/Quotes/<customer>/`.
   Read it:

       python .claude/skills/order-handoff/tools/read_quote.py "External/Quotes/<customer>/<file>.xlsx"

   It prints the customer, item, quantity, prices and totals from the sheet as JSON.
2. Fill what the quote does not hold, one question at a time, skipping anything already known from
   the sourcing run or `internal/Domains/Work/ASB/suppliers-and-pricing.md`: the customer's PO
   number, the approved artwork file, imprint colors, in-hands date, ship-to address if it differs,
   ship method and who pays freight ("prepay and add", or the company's carrier account), supplier
   name and item number, and net cost per unit and for setup.
3. Write `<quote file name>-order.md` next to the quote with two parts:

   - **Order summary** (for the order-entry assistant): customer, contact, customer PO, item and
     item number, quantity, sell price, setup, freight, GE tax, total, decoration, imprint colors,
     artwork file, in-hands date, ship-to, ship method.
   - **Purchase order** (for the supplier): supplier, item number, description, quantity, net
     price, setup net, decoration and imprint colors, artwork file, ship-to, ship method and how
     freight is billed, in-hands date, and "Please confirm receipt and ship date."

4. Give her the full path. She pastes the summary into the order form and the PO into her email to
   the supplier. Nothing is sent from here.
5. Add "Hand to the order-entry assistant: <customer> order" to today's focus file.

## Never

- Never invent a net cost, an item number or a ship date. Ask.
- Never send anything.
