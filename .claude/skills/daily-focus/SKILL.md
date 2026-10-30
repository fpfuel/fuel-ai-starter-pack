---
name: daily-focus
description: "Turn Karen's morning dictation (or a pasted Copilot inbox summary) into today's ordered focus list at internal/Domains/Work/ASB/daily/YYYY-MM-DD.md: quotes in priority order, orders to hand to the order-entry assistant, loops to close, plus a check against yesterday for anything that fell through. Use when Karen says \"here's my day\", \"what should I do first\", \"make my list\", or pastes a Copilot summary."
---

# Daily focus

## Steps

1. Take whatever she gives: a Wispr Flow dictation, a pasted Copilot summary from
   `/copilot-inside`, or both. Do not ask her to tidy it.
2. Sort every item into one of three buckets:
   - Quotes to do: customer, item, quantity, due date if known.
   - Orders for the order-entry assistant: customer, what they need (order form, proof, tracking).
   - Loops to close: a reply owed, a call to make, a question waiting on someone.
   Anything that is none of these goes under "Parked".
3. Order the quotes. Earliest in-hands date first, then customers who need a price before
   they can issue a PO, then shoppers. If no dates are known, keep her spoken order and
   say so.
4. Open yesterday's file in `internal/Domains/Work/ASB/daily/` (the most recent one). For every unchecked
   item there that does not appear today, ask one question: "Yesterday had X. Done,
   still open, or drop it?" Carry forward what is still open.
5. Write `internal/Domains/Work/ASB/daily/YYYY-MM-DD.md` in this shape:

       # Focus, Tuesday 2026-10-28

       ## Quotes, in order
       - [ ] Customer, item, qty, due
       ## Hand to the order-entry assistant
       - [ ] Customer, what he needs
       ## Loops to close
       - [ ] Who, what
       ## Carried from yesterday
       - [ ] ...
       ## Parked
       - ...

6. Read back the top three quotes in one line each and give her the file path.
7. During the day, when she says "add to my list" or "done with X", edit the file and
   confirm in one line.

## Never

- Never put anything from inside the firewall into the file beyond what Karen pasted or
  said herself.
- Never invent a due date. Unknown stays unknown.
