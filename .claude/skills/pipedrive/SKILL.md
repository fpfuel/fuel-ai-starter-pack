---
name: pipedrive
description: Turn a pasted email signature (plus what the activity is) into the exact Pipedrive person, organization and activity text for Karen to paste in. Use when Karen says "add this to Pipedrive", "add this contact", "log an activity", or pastes a signature block.
---

# Pipedrive

Two modes. With her API token on file, Claude creates the records in Pipedrive itself
(see "API mode" below). Without it, this produces paste-ready text and nothing needs a key.

## Steps

1. Take the pasted signature and her one-line note on the activity ("locker forms quote",
   "follow up Friday"). If the activity is missing, ask once.
2. Pull the fields out of the signature exactly as written: name, title, organization,
   email, phone (mobile and office if both), address, website. Do not fill a field the
   signature does not contain.
3. Produce three blocks she can paste:

       Person
       Name:
       Title:
       Email:
       Phone:
       Organization:

       Organization
       Name:
       Address:
       Website:

       Activity
       Type: (call, email, task, meeting)
       Subject:
       Due:
       Note:

4. Ask whether the activity has a due date. If she says a day ("Friday"), write the
   calendar date.
5. If the contact belongs to a customer in `internal/Domains/Work/ASB/customers.md`, say so. If not, offer
   to add a row with "(confirm)".

## API mode

Which mode: at the start, run `python .claude/skills/pipedrive/tools/pipedrive_api.py whoami`.
If it prints her name and company, the token was found and Claude uses API mode. If it says
no token was found, use the paste blocks above. Her token goes in `secrets/keys.xlsx` (copy
`secrets/keys.example.xlsx`, fill the value column; the token is under Settings, Personal
preferences, API in Pipedrive). That file never leaves her machine.

Adding a contact: pull the same fields out of the signature, then run, as one command:

    python .claude/skills/pipedrive/tools/pipedrive_api.py add
      --name "Pat Sample" --org "Sample Contracting"
      --email pat@example.com --phone 808-555-0100 --title "Owner"
      --activity "Locker forms quote" --type task --due 2026-11-03
      --note "what she asked for"

It finds the organization by exact name (or creates it), creates the person under it, and
creates the activity on both, then prints one line per record with its id and a link.
Activity types: call, meeting, task, deadline, email, lunch. The title goes at the top of
the activity note, since Pipedrive does not take a job title on the person here.

First use: add `--dry-run` and show Karen what would be sent before the live run. It prints
the exact calls and sends nothing. Then run it live and read back the three lines.

Undo: `... delete --person ID --org ID --activity ID` removes records by id (any one or
all three), for a test or a mistaken add.
