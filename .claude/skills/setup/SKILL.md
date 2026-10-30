---
name: setup
description: First-run setup. Checks this computer and installs what is missing, interviews her one question at a time to fill in Brain/Context and her work files, sets the quote header, and finishes with a test quote and a first focus list. Starts on its own in the first session; also use when she says "set up", "start over", or "check my computer".
---

# Setup

A conversation, not a form. One question per message, always.

## Part 0: my name and my home

0. If this is the first reply of the session, it opens with exactly: "I got it, and I'm starting to set up your AI kickstart environment."
   Do not run a quote, a rate, a product search or any other demo before Part 3.
   If `Brain/Context/me.md` already has a "My assistant" section naming this folder, skip to Part 1.
1. Ask: "Where do you want me to live, and what should I be called?" Say in one line that the
   name is hers to pick, and suggest her home folder (on Windows `C:\Users\<her name>`, on a Mac
   `/Users/<her name>`). Steer away from OneDrive, Dropbox or any company-synced folder: her keys
   file would sync with it.
2. On her own computer, run `python .claude/tools/rehome.py --name "<name>" --to "<parent folder>"`.
   It copies everything into `<parent folder>/<name>`, puts the name in, and points memory there.
   Then say, in plain words: "I've moved into <the new folder>. Close this window, open Claude Code
   in that folder, and say hello. We pick up right where we left off." Stop here; the rest of
   setup runs in the new folder.
3. In a cloud session, run `python .claude/tools/rehome.py --name "<name>" --here` instead and go
   straight on: say in one line that in the cloud she starts each session from this repository,
   and her own computer is where I can keep a permanent home.

## Part 1: check this computer (about 2 minutes)

1. Say in one short paragraph what is about to happen: a quick computer check, then about
   twenty minutes of questions she can answer by voice, then a test quote.
2. Run `python .claude/tools/env_check.py --fix`. If `python` is not found, try `py`, then
   `python3`. If none works, say Python is needed, give https://www.python.org/downloads/ and ask
   her to tick "Add python.exe to PATH" when installing, then run it again.
3. Read the result back in plain words, one line per row: what works today and what does not and
   why. Never paste the raw output. If memory was just switched on, say it starts next session.
   In the cloud, if USPS or SAGE "cannot reach" from here, the cloud environment's network
   setting is blocking them. Tell her how to open it up, once: at claude.ai/code, select the
   caret after this session's title, then Edit cloud environment, then Network access. Choose
   Custom, paste these into Allowed domains one per line: postcalc.usps.com, www.promoplace.com, *.pipedrive.com, api.fireflies.ai, tick "Also include default
   list of common package managers", and save. UPS live rates need her own computer either way.
   Then go straight on to Part 2. Do not ask whether to continue, and do not stop to fix
   something that does not work yet; note it and move on.

## Part 2: the interview (about 20 minutes)

4. Read `Brain/Context/me.md`, `work.md`, `team.md` and every `.md` file in
   `internal/Domains/Work/ASB/`. Note every "(confirm)" line and every blank under
   "Still to fill in".
5. Go topic by topic, in this order. For each: read back what is seeded and ask "is that right?",
   then ask for the blanks, one question at a time.
   1. Me (`Brain/Context/me.md`): contact details, where she works from, how she wants Claude to
      talk to her, anything Claude must never do.
   2. Work and team (`Brain/Context/work.md`, `team.md`): what sells most, team names and roles.
   3. Suppliers and pricing (`internal/Domains/Work/ASB/suppliers-and-pricing.md`): main
      suppliers, how each agreement works, markup rules by supplier and by customer, freight
      forwarder. Write "unknown" for anything she cannot state. Never fill a markup from a guess.
   4. Customers (`customers.md`): top customers, locations, terms, tiers, programs.
   5. Workflows (`workflows.md`): xlsx or PDF to customers, what the order-entry assistant needs.
   6. Current focus (`current-focus.md`): this week, what keeps falling through.
   7. Meetings (`Brain/Context/work.md`, under "Meetings"). Ask "How do you record meetings
      right now?" Then ask "Do you want me to work from your meetings?" and offer the ways in
      one short message, in plain words:
      - Teams meetings at work: Copilot can take the notes if her Copilot license includes it.
        To check: after a Teams meeting, open it from the Teams calendar; a Recap tab with AI
        notes means it does. Then `/meetings` works from a Copilot recap she pastes here.
      - Fireflies: records her calls on Zoom, Google Meet or Teams into her own Fireflies
        account, and Claude reads them with her Fireflies key (step 9). The free plan works.
      - Notion: if she keeps meeting notes in Notion, she connects Notion once at claude.ai,
        Settings, Connectors, and Claude reads them from there.
      - Anything else (Otter, Zoom's own summary, Wispr Flow, paper): she pastes or saves the
        transcript or summary, and `/meetings` works from that.
      - None of these: that is fine. Write "not recording meetings" and move on.
      If she wants an outside recorder in ASB's own Teams meetings, say in one sentence that
      this is the company's call, so she checks with IT first.
      Write under "Meetings": how she records now, the way she chose, and whether it is set up.
6. After each topic, rewrite that file: remove "(confirm)" from what she verified, correct what she
   changed, fill what she answered, leave "unknown" where she did not know. Keep the headings.
   Tell her the file name in one line.
7. Quote header: ask for the exact top line of her quote sheet (company, phone, email), her name
   as it appears under FROM, the company line, the city line and the website. Write them to
   `internal/Domains/Work/ASB/quote-header.json` (keys `header_line`, `from_name`,
   `from_company`, `from_city`, `from_web`).
8. Email exports: ask "When you want me to turn emails into quotes, are you allowed to hand me a
   saved email or an export, or should we only work from what Copilot summarizes?" Write her
   answer in place of the "Email exports" line in `.claude/rules/boundaries.md`.
9. Keys (optional; skip if she wants): SAGE product search and Pipedrive need her own details.
   Run `python .claude/tools/keys.py` first. Anything already filled in is ready: say so in one
   line and ask only for what is empty.
   Ask her to open `secrets/keys.example.xlsx`, save a copy in the same folder as `keys.xlsx`, and
   paste the values there herself. Never in chat. SAGE: account number, login and API key from
   sagemember.com, Users tab. Pipedrive: her company name before `.pipedrive.com`, and the token
   from Settings, Personal preferences, API. Fireflies, if she chose it in topic 7: the key from
   app.fireflies.ai, Integrations, Fireflies API, as `FIREFLIES_API_KEY`; then run
   `python .claude/skills/meetings/tools/fireflies.py check` and read back how many meetings it
   found. Then run `python .claude/tools/keys.py` and read
   back which names are filled (never values).
10. Never write anything from inside the firewall: no Outlook content, no M-Files data, no
    company logins. If she offers one, decline in one sentence and move on.

## Part 3: the test quote

11. Say: "Now a test, using your keyring quote." Run:

        python .claude/skills/quote/tools/build_quote.py --customer "Pat Sample" --company "Sample Contracting" --address "100 Sample St." --address "Hilo, HI 96720" --phone "(808) 555-0100" --item "Pull Apart Keyring" --qty 150 --unit-cost 3.95 --setup "Setup, laser engrave=80" --shipping 143 --destination Hilo --url https://us.stregisgrp.com/channel/home-office/detail/KC110 --turnaround "10-12 business days" --date 2026-10-25

12. The summary must read subtotal $815.50, tax $38.43, total $853.93, $5.69 each. Give her the
    full file path and ask her to open it beside her original sheet.

## Part 4: the first focus list

13. Ask "What should you focus on this week?" Offer the Copilot route: give her prompt 9
    ("Today's five") or prompt 1 ("Inbox triage") from
    `.claude/skills/copilot-inside/prompts.md` as one block to copy, and ask her to paste
    Copilot's answer back. Then run `/daily-focus` on it plus anything she says.
14. Close with the skills table from the root `CLAUDE.md` in five lines or fewer, and ask which
    real job she wants to do first.
