---
name: quote-batch
description: Turn a pile of quote requests into finished quotes, one per customer. Takes a pasted Copilot summary, pasted emails, a saved email file or .csv she hands over, or a photo of notes; finds the products, gets freight, builds every sheet, and ends with one list of files. Use when she says "build quotes for these", "quote all of these", "take this export and quote these people", or pastes several requests at once.
---

# Quote batch

## Before starting

Read the "Email exports" line in `.claude/rules/boundaries.md`. If she has not said that files from
her inbox may come here, work only from what she pastes (a Copilot summary, or text she copies).
Never reach into Outlook and never ask for a login.

## Steps

1. Read everything she gave. Pasted text and `.eml` files read directly; for a `.csv`, read the
   rows. A `.msg` file (Outlook's own format) needs extra software, so ask her to paste the text or
   save it as `.eml` instead. A photo: read it, and ask about any line you cannot read rather than
   guess.
2. Pull out one request per customer: contact name, company, phone and address if they are in the
   text, item, quantity, decoration, colors, in-hands date, ship-to ZIP, target price. Anything
   missing stays blank. Never guess.
3. Show the whole list in one message, one numbered line per request, blanks marked "?". Ask her to
   confirm or correct it in one answer. Then ask, one at a time, only for blanks that block a
   quote: ZIP, quantity, and the sell price (or a markup rule for the batch).
4. For each request, in order: run `/product-search` with `--candidates 3`. Pick the lowest landed
   cost per unit that meets the in-hands date unless she said otherwise, and tell her the pick in
   one line. Stop and ask if nothing fits.
5. Sell price: if a markup rule for that supplier or customer is recorded in
   `internal/Domains/Work/ASB/suppliers-and-pricing.md`, apply it and say so. Otherwise use the
   price or batch markup she gave in step 3.
6. Build each quote with the `/quote` tool. Put cartons, weight and ship-from in the notes, and
   label freight "retail estimate".
7. Finish with one table: customer, item, quantity, total, per each, and the full file path. Add a
   line per quote under "Quotes ready to send" in today's focus file
   (`internal/Domains/Work/ASB/daily/YYYY-MM-DD.md`). Offer `/pipedrive` for any new contact.

## Never

- Never send anything. She reviews each sheet and sends it herself.
- Never guess a price, a ZIP or a quantity.
- Never keep whole emails. Only what lands in a quote or the focus list stays.
