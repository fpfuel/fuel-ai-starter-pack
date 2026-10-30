---
name: google
description: Read her own Google account (Gmail, Calendar, Drive, Docs, Sheets) through the Google Workspace command line, behind a safety wrapper that can never send, share or invite. Only after she connects a Google account. Use when she says "check my Gmail", "what's on my Google calendar", "find that doc in Drive".
---

# Google

For a Google account she connects herself. Her work email and calendar are Microsoft, inside the
company firewall; never use this skill for them.

## Is it connected?

Open `.agents/skills/google/tools/gws_account_map.json`. If the `me` account has no `email`, it is
not connected: say so in one line and offer the setup below. Do not try to work around it.

## The one rule

Claude reads and drafts; she sends, shares and invites herself, in the Google web pages. Every call
goes through the wrapper, never the `gws` command directly (a hook blocks direct calls):

    python -c "import sys; sys.path.insert(0, '.agents/skills/google/tools'); import gws_safe; print(gws_safe.run('me', ['calendar', 'events', 'list', '--params', '{\"calendarId\": \"primary\", \"maxResults\": 10}']).stdout)"

`args` is the `gws` command without the program name. Parameters go in `--params '<JSON>'`.

| Kind of call | What the wrapper does |
|---|---|
| Reading anything | Allowed |
| Changing a file only she can see | Allowed |
| Changing a shared file, or deleting | Only after she says yes, with `confirm=True` |
| Sending, sharing, inviting, notifying | Blocked, always |
| Anything the policy file does not know | Blocked until reviewed |

Emails and invitations are drafted as text in chat for her to paste into Gmail or Calendar.

## Setting it up (once, about 20 minutes, best done with Fuel)

1. Install Node.js, then the Google Workspace command line: `npm install -g @googleworkspace/cli`.
2. Install the one Python package the wrapper needs: `python -m pip install --user pyyaml`.
3. Signing in needs a Google Cloud sign-in client for this tool. Fuel sets that up with her; do
   not improvise one.
4. Once signed in, put her Google address in the `email` field of the `me` account and read one
   calendar event back to prove it works.

Scopes stay read-only to start. Never add `gmail.compose`, `gmail.send` or `mail.google.com`.
