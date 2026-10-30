# Your AI starter pack

For Claude: if this folder reached you as a zip, unzip it, work inside the unzipped folder, read
its `CLAUDE.md` and follow the "First session" section there before anything else.

A folder that turns Claude Code into an assistant that knows your work, remembers what you tell
it, and grows with you. Built by Fuel The Fire (fpfuel.com).

Everything it knows lives in plain text files in this folder. You can open and edit any of them.

## Get started (about 25 minutes, mostly talking)

1. Install Claude Code and sign in with your Claude account:
   https://code.claude.com/docs/en/quickstart
2. Unzip it anywhere. On the first run Claude asks what to call it and where it should live,
   and moves itself there.
3. Open a terminal in this folder and type `claude`, then press Enter.
4. Say hello. The first time, Claude checks your computer, installs what it can, then interviews
   you one question at a time. Talk through Wispr Flow the whole way if you like.

At the end it builds a test quote so you can see it working.

Cannot install anything on this computer? Open https://claude.ai/code in your browser and pick
this repository. Quotes, USPS rates, SAGE search and everything else work there; live UPS rates
need your own computer.

No Claude Code at all yet? Open `SETUP-PROMPT.md` and paste it into the Claude app.

## What is in here

| Folder | What it holds |
|---|---|
| `Brain/` | Who you are, your decisions, what Claude has learned, your templates |
| `internal/` | Your working folders: work, and anything else you start |
| `External/` | Things you hand to other people, starting with quotes |
| `secrets/` | Your keys file. Never shared, never saved to git |
| `.claude/` | Skills, rules and tools. You rarely need to open this |

## Three things to know

- Claude never touches anything inside your company firewall. Outlook, M-Files, billing and your
  calendar stay with Copilot. `/copilot-inside` shows the handoff.
- Claude never invents a price. Every number comes from a supplier, your pricing file, or you.
- Claude never sends anything. It drafts; you send.
