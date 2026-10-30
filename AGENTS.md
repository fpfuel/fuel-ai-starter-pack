# Instructions for Codex

This folder is set up for Claude Code first. Codex works here too.

At the start of every session, read:

1. `CLAUDE.md`, the map of this folder.
2. Every file in `.claude/rules/`. They are the rules that always apply.
3. `Brain/Context/me.md`, `Brain/Context/work.md` and `Brain/Context/team.md`.

Skills are mirrored for Codex in `.agents/skills/`. After changing a skill under
`.claude/skills/`, run `python .claude/tools/sync_codex_skills.py` so the copy matches.
