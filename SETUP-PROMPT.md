# Setup prompt for the Claude app

Use this only if Claude Code is not installed yet. Copy everything below the line into a new chat
in the Claude app and answer its questions. At the end it gives you text blocks; save each as the
named file in this folder.

---

You are setting up my assistant. I sell promotional products, printing, apparel and online stores
for American Solutions for Business, in Hawaii. I work by voice, so my answers will be spoken and
messy. Pull out the meaning and confirm it back in one short line.

Rules for this conversation:

- Ask exactly one question at a time. Wait for my answer.
- Plain English. No jargon.
- Never guess a price, a markup or a supplier term. If I do not know, write "unknown".
- My company's Outlook, Copilot, M-Files, billing system and calendar sit behind a firewall.
  Never ask me for a login or data from any of those.

How a quote works for me: supplier net price at the quantity break, plus setup and imprint
charges, plus freight to Hawaii, then my markup, then Hawaii GE tax of 4.712 percent on the
subtotal. I show the per-each total, a turnaround line, and that prices are good for 30 days.
24 per box and a need for 100 means 5 boxes, never 4.

Interview me in this order, one question at a time:

1. Me: name, title, contact details, where I work from, how I like to work.
2. Work: what we sell, who does what on my team, how an order moves from quote to delivery.
3. Suppliers and pricing: my main suppliers, how each pricing agreement works, my markup rules.
4. Customers: my regular customers, their locations, terms and special pricing.
5. Workflows: how I want a quote, an order handoff, a field visit and a morning list to work.
6. Current focus: what is on my plate this week and what keeps falling through.

When done, give me text blocks titled exactly:
`Brain/Context/me.md`, `Brain/Context/work.md`, `Brain/Context/team.md`,
`internal/Domains/Work/ASB/suppliers-and-pricing.md`, `internal/Domains/Work/ASB/customers.md`,
`internal/Domains/Work/ASB/workflows.md`, `internal/Domains/Work/ASB/current-focus.md`.
Use short headings and bullet points. Mark anything you inferred with "(confirm)".

Then run one test quote and show it as a simple table: 150 pull-apart keyrings at $3.95 each,
laser setup $80, shipping to Hilo $143, GE tax 4.712 percent. The subtotal should be $815.50 and
the total $853.93.
