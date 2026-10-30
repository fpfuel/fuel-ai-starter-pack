# Workflows

Lines tagged "(confirm)" were seeded before setup and are not verified yet.

## A quote, start to finish

1. Request arrives: email, call, visit note, or memory (confirm)
2. Capture: customer, item, quantity, decoration, in-hands date, ship-to (confirm)
3. Search: `/product-search` compares two or three products through SAGE (confirm)
4. Freight: `/shipping` does the carton math and gets UPS and USPS rates (confirm)
5. Build: `/quote` writes the sheet in her layout to `External/Quotes/<customer>/`
6. Send: she reviews and sends from Outlook (confirm)
7. Log: contact and activity into Pipedrive with `/pipedrive` (confirm)

Many at once: `/quote-batch` runs steps 2 to 5 for every request in a pile.

## An order handoff

1. Customer approves the quote (confirm)
2. She does the artwork in Illustrator or Photoshop (confirm)
3. `/order-handoff` writes the order summary and the supplier PO text from the quote
4. PO to the supplier, both documents to the order-entry assistant (confirm)
5. The order-entry assistant enters it in billing, routes the proof, sends tracking (confirm)

## A field visit

1. Visits and paper notes (confirm)
2. Photograph the pages or dictate them
3. `/field-notes` turns them into tasks by customer, added to today's list

## The morning list

1. She dictates what is on her plate, or pastes a Copilot inbox summary
2. `/daily-focus` writes `daily/YYYY-MM-DD.md` and checks yesterday's for anything that did not move

## Still to fill in

- How quotes go to customers (xlsx, PDF, both):
- Whether the order-entry assistant wants the order summary in a set format:
- Where artwork files live and how they are named:
