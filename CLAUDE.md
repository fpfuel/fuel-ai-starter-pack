# Your starter pack: how Claude works here

This file loads at the start of every session. It is a map: it says where things live and which
rules never change. Facts about you live in the files it points to, not here.

## First session

If any file under `Brain/Context/` or `internal/Domains/Work/ASB/` still has a "(confirm)" tag or a
blank under "Still to fill in", your first reply in a session starts the `setup` skill, before
anything else. Nothing to type: setup checks this computer, interviews one question at a time, and
finishes with a test quote.

## Where things live

| If you need | Go to |
|---|---|
| Who she is, her work, her team | `Brain/Context/` (me, work and team load every session) |
| Dates and deadlines; promises with a date | `Brain/Context/calendar.md`, `Brain/Context/obligations.md` |
| Her own lessons and rules of thumb | `Brain/Me.md`. Read it before giving advice on a decision |
| What was decided and why | `Brain/Decisions/log.md` |
| Something learned in an earlier session | `Brain/memory/`, index at `Brain/memory/MEMORY.md` |
| Reference knowledge she has collected | `Brain/LLM Wikis/`, index at its `INDEX.md` |
| A template for a new folder, memory or skill | `Brain/Templates/` |
| Her work at American Solutions for Business: suppliers, customers, workflows, this week | `internal/Domains/Work/ASB/`. Start at its `CLAUDE.md` |
| Anything new she starts, at work or in life | a folder under `internal/Domains/`, with a `CLAUDE.md` from the template |
| A past brainstorm or interview | `internal/Brainstorms/` |
| Something old or replaced | `internal/Trash/`. Never delete; move things here |
| Finished quotes and anything she hands to someone | `External/`. Quotes at `External/Quotes/<customer>/` |
| Keys and passwords | `secrets/keys.xlsx`, read only through `.claude/tools/keys.py` |
| Whether this computer can do something | `python .claude/tools/env_check.py` |
| Rules that always apply | `.claude/rules/` (they load every session) |

## Skills

Type the name with a slash, or just say what you want and Claude picks the skill.

| Skill | What it does |
|---|---|
| `/setup` | First-run check and interview; ends with a test quote |
| `/quote` | Builds a quote in her own QUOTE sheet layout |
| `/quote-batch` | Turns a pile of requests (a Copilot summary, emails, notes) into quotes, one per customer |
| `/product-search` | Finds and compares two or three products through SAGE, with landed cost |
| `/shipping` | Carton math, then live UPS and USPS rates with sources |
| `/order-handoff` | Turns an accepted quote into the order summary and supplier PO text |
| `/daily-focus` | Turns her morning dictation into today's ordered list |
| `/field-notes` | Turns visit notes (photo or dictation) into tasks by customer |
| `/pipedrive` | Adds a contact and activity to Pipedrive, or gives paste-ready text |
| `/copilot-inside` | The handoff for Outlook and M-Files work through Copilot |
| `/grill-me` | An interview that saves every answer, to think something through |
| `/link` | Makes a new file or folder findable from the right map |
| `/google` | Gmail, Calendar and Drive through the Google Workspace command line, if she connects a Google account |

## Three rules that keep this file true

1. Nothing that can be listed lives here. A list goes in the folder it describes.
2. Nothing dated lives here. Dates go in `Brain/Context/calendar.md`.
3. When this file and what is on disk disagree, the disk wins. Say so and fix this file.

@Brain/Context/me.md
@Brain/Context/work.md
@Brain/Context/team.md
