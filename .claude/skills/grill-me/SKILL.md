---
name: grill-me
description: Interview her one question at a time about a plan, an idea or a part of her life or work, saving every answer to a file so nothing is lost. Use when she says "grill me", "interview me", "help me think this through", "let's plan X", or wants what is in her head written down.
---

# Grill me

Ask until the topic is fully understood, one question at a time, and save every answer as you go.
The file is the point: it holds what she said even if the conversation runs long.

## Before the first question

1. Read the parts of `Brain/` and `internal/Domains/` that touch the topic, and any earlier
   brainstorm on it in `internal/Brainstorms/`. Reuse what is already known; ask only about gaps,
   changes and choices.
2. Create `internal/Brainstorms/YYYY-MM-DD-topic.md` (today's date; add a suffix if that name
   exists; never overwrite). Header: title, date, the goal in one line, "Status: in progress", and
   an empty "Open questions" section.
3. Tell her the file path in one line. Then ask question 1.

## After every answer, before the next question

- Add an entry: the question, what she said (her words where the wording matters), and anything
  she could not answer with who could.
- If an answer changes an earlier one, keep the earlier entry, mark it "replaced by Qn", and update
  the summary at the top.
- Only then ask the next question.

## How to ask

- One question per message. For a choice, offer your suggestion and label it as a suggestion; for a
  fact about her life or work, ask plainly and never put words in her mouth.
- Settle the big decision before the ones that depend on it.
- If a file can answer it, read the file instead of asking.
- Stop the moment she says stop. Near the end ask "Anything we have not touched?"

## At the end

- Re-read the file for contradictions and gaps; mark them. Set the status and where to pick up.
- If the session was about her context, move confirmed facts into the right file (for example
  `Brain/Context/me.md` or a domain's files) with a dated pointer back to the brainstorm. Decisions
  go in `Brain/Decisions/log.md`. Unconfirmed ideas stay only in the brainstorm.
- Give a short recap: the file path, what was updated, what is still open, the next step.
