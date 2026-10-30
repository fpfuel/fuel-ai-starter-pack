---
name: field-notes
description: Turn Karen's customer visit notes (a photo of the paper page or a Wispr Flow dictation) into a task list grouped by customer and typed as quote, order, or artwork, then append it to today's focus file. Use when Karen says "here are my notes from", "I visited", "big island notes", or shares a photo of handwritten notes.
---

# Field notes

## Steps

1. Take the input: a photo of each page, or her dictation of what the page says. If a
   photo is unreadable in places, ask about that line only; do not guess a name or a
   quantity.
2. For each customer on the page, list every item under it and type each one:
   - Quote: item, quantity, decoration, due date, anything she promised.
   - Order: what was approved, what the order-entry assistant needs to enter.
   - Artwork: what to fix or create, which file.
   - Follow-up: a question she owes them or they owe her.
3. Read back one customer at a time: "For Customer X I have: quote 200 microfiber
   towels with logo; artwork fix on the banner. Right?" Correct as she goes.
4. Append the result to today's file in `internal/Domains/Work/ASB/daily/` under a heading
   "## From visit notes, <date of visit>", using the same checkbox format. If today's file
   does not exist, create it with `/daily-focus` first.
5. For any customer not yet in `internal/Domains/Work/ASB/customers.md`, add a row with what the notes
   show (name, location, contact if written) and "(confirm)".
6. Offer the next step in one line: "Want me to start the first quote?"

## Never

- Never read a quantity, price or name from a smudge. Ask.
