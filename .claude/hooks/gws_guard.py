#!/usr/bin/env python3
"""
gws_guard.py — PreToolUse Bash hook. A redundant net that blocks outbound Google Workspace CLI (gws)
calls and known bypass paths before the Bash tool runs.

This is defense in depth, NOT the primary guarantee. The real guarantees are:
  - Layer 0: a gmail.readonly token cannot send, period (gws_verify_scopes.py proves it).
  - Layer 1: all skill code goes through gws_safe.py, which classifies + blocks at the call site.
The hook adds a third gate for direct command-line calls and for the exact incident shape
(a .py file that hides a gws send inside it, invoked as `python script.py`).

Contract (verified-robust for PreToolUse):
  - exit 0  -> allow.
  - exit 2  -> BLOCK; stderr is shown to the model. (The legacy {"decision":"block"} JSON FAILS OPEN
               for PreToolUse and is deliberately not used.)
  - any other exit / exception -> treated as non-blocking; we fail OPEN here so a hook bug never wedges
    the workflow, because Layers 0 and 1 still hold.

What it denies:
  1. Direct outbound gws verbs on the command line (derived from gws_risk_policy.yaml's outbound set
     so the hook and gws_safe can never disagree), plus the '+send/+reply/+forward/+invite/+watch/...'
     helper verbs. A `--dry-run` form of a '+' helper is allowed (with a note); raw outbound methods
     are never exempted.
  2. Bypass attempts: the native bin/gws.exe by full path, the .cmd shim, gws-real, run.js, or a
     `python -c "... shell=True ... gws ..."` one-liner.
  3. The incident shape: when the command is `python <file>` / `node <file>`, the hook reads <file>
     and denies if it contains a forbidden gws outbound pattern (heuristic; won't catch dynamically
     built verbs, hence "redundant net").
"""
from __future__ import annotations
import re
import sys
import json
import shlex
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
REPO_ROOT = HOOK_DIR.parent.parent
POLICY_FILE = REPO_ROOT / ".claude" / "skills" / "google" / "tools" / "gws_risk_policy.yaml"

# Reverse of gws_safe.SERVICE_ALIASES: discovery service prefix -> CLI command word(s).
REVERSE_ALIASES = {"reports": ["admin-reports", "reports"], "workflow": ["workflow", "wf"]}

# Core outbound resource phrases — the fallback if the yaml can't be read. Each is the resource path
# (everything after the service word) as it appears on the command line.
FALLBACK_OUTBOUND_PHRASES = [
    "users messages send", "users drafts send", "users messages import", "users watch",
    "users settings sendAs create", "users settings sendAs verify",
    "users settings forwardingAddresses create",
    "permissions create", "files watch", "changes watch",
    "acl insert", "events import", "events watch", "acl watch",
    "calendarList watch", "settings watch",
    "spaces messages create", "spaces members create",
    "activities watch",
]

# '+' convenience verbs that send/share/notify. Blocked unless it is a --dry-run of one of them.
PLUS_HELPER_RE = re.compile(r"(?<!\w)\+(send|reply|forward|invite|watch|import|share|notify|deliver)\b", re.I)

# Bypass / direct-binary patterns. Never exempt.
BYPASS_RES = [
    re.compile(r"node_modules[\\/].+?[\\/]gws\.exe", re.I),
    re.compile(r"bin[\\/]+gws\.exe", re.I),
    re.compile(r"gws-real(\.exe)?", re.I),
    re.compile(r"[\\/]gws\.cmd", re.I),
    re.compile(r"@googleworkspace[\\/]cli[\\/].+?run\.js", re.I),
]
SHELL_TRUE_RE = re.compile(r"shell\s*=\s*True", re.I)

GWS_MENTION_RE = re.compile(r"\bgws\b|gws\.exe|@googleworkspace", re.I)
INTERP_RE = re.compile(r"\b(?:python3?|py|node)\b", re.I)
DRYRUN_RE = re.compile(r"--dry-run\b", re.I)

MAX_SCAN_BYTES = 400_000


def _load_outbound_phrases() -> list[str]:
    """Build the resource-path phrases for every outbound method id in the policy yaml."""
    try:
        import yaml  # local import so a missing dep degrades to the fallback, not a crash
        data = yaml.safe_load(POLICY_FILE.read_text(encoding="utf-8"))
        phrases: list[str] = []
        for mid, rec in (data.get("methods") or {}).items():
            if (rec or {}).get("tier") != "outbound":
                continue
            toks = mid.split(".")
            if len(toks) < 2:
                continue
            phrases.append(" ".join(toks[1:]))  # resource path after the service word
        return phrases or FALLBACK_OUTBOUND_PHRASES
    except Exception:  # noqa: BLE001
        return FALLBACK_OUTBOUND_PHRASES


def _phrase_regexes(phrases: list[str]) -> list[re.Pattern]:
    out: list[re.Pattern] = []
    for p in phrases:
        toks = p.split()
        body = r"\s+".join(re.escape(t) for t in toks)
        out.append(re.compile(r"(?<!\w)" + body + r"(?!\w)", re.I))
    return out


OUTBOUND_RES = _phrase_regexes(_load_outbound_phrases())


def _deny(reason: str) -> None:
    sys.stderr.write(
        "BLOCKED by gws_guard (PreToolUse): " + reason + "\n"
        "Outbound Google Workspace actions (send / share / invite / notify / watch / import) must be "
        "done by a human in the web UI. Draft email via the Gmail MCP create_draft; for reads/private "
        "edits use gws_safe.run(). See .claude/skills/google/SKILL.md.\n"
    )
    sys.exit(2)


def _scan_text_for_outbound(text: str) -> str | None:
    """Return a human reason if the text contains a forbidden outbound gws pattern, else None."""
    if PLUS_HELPER_RE.search(text) and not DRYRUN_RE.search(text):
        m = PLUS_HELPER_RE.search(text)
        return f"contains gws '+{m.group(1)}' helper verb"
    for rx in OUTBOUND_RES:
        if rx.search(text):
            return f"contains outbound gws method phrase '{rx.pattern}'"
    return None


def _candidate_script_paths(command: str) -> list[Path]:
    """If the command runs a script (python/node <file>), return existing file paths to pre-scan."""
    paths: list[Path] = []
    try:
        tokens = shlex.split(command, posix=False)
    except Exception:  # noqa: BLE001
        tokens = command.split()
    i = 0
    while i < len(tokens):
        if INTERP_RE.fullmatch(tokens[i].strip('"').strip("'")):
            # first following non-flag token is the script
            j = i + 1
            while j < len(tokens):
                tok = tokens[j].strip('"').strip("'")
                if tok.startswith("-") or tok == "-c":
                    j += 1
                    continue
                p = Path(tok)
                if not p.is_absolute():
                    p = (REPO_ROOT / tok)
                if p.exists() and p.is_file() and p.suffix.lower() in (".py", ".js", ".mjs", ".cjs", ".ps1", ".sh"):
                    if p.resolve().parent != HOOK_DIR:
                        paths.append(p)
                break
        i += 1
    return paths


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:  # noqa: BLE001
        return 0  # can't parse -> let other layers handle it

    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command:
        return 0

    # 1. Bypass paths — checked regardless of whether 'gws' token appears.
    for rx in BYPASS_RES:
        if rx.search(command):
            _deny(f"references a gws bypass path ({rx.pattern}); call gws only through gws_safe.run().")
    if SHELL_TRUE_RE.search(command) and GWS_MENTION_RE.search(command):
        _deny("uses shell=True together with gws (the 2026-06-03 incident shape).")

    # 2. Direct outbound verbs on the command line (only meaningful when gws is invoked).
    if GWS_MENTION_RE.search(command):
        reason = _scan_text_for_outbound(command)
        if reason:
            _deny(f"command-line {reason}.")

    # 3. Static pre-scan of about-to-run scripts (closes the incident gap).
    for script in _candidate_script_paths(command):
        try:
            text = script.read_text(encoding="utf-8", errors="ignore")[:MAX_SCAN_BYTES]
        except Exception:  # noqa: BLE001
            continue
        if not GWS_MENTION_RE.search(text):
            continue
        reason = _scan_text_for_outbound(text)
        if reason:
            _deny(f"the script {script.name} {reason} (pre-scan of `{command.strip()[:80]}`).")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as ex:  # noqa: BLE001  -- fail OPEN: never wedge the workflow on a hook bug
        sys.stderr.write(f"gws_guard internal error (allowing; Layers 0/1 still apply): {ex}\n")
        sys.exit(0)
