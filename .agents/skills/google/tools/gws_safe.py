"""
gws_safe.py — the ONE sanctioned way to invoke the Google Workspace CLI (gws).

Skill/automation code MUST call through this module. Do NOT shell out to gws (or gws.exe, or the
.cmd shim) directly — that bypasses every guardrail and is what caused the 2026-06-03 incident.

What it enforces (in order):
  1. Explicit account binding. `account` is required; resolved through gws_account_map.json; each
     account gets its own GOOGLE_WORKSPACE_CLI_CONFIG_DIR so one identity can't act as another.
  2. No '+' helper verbs. The gws "+send/+reply/+forward/+watch" convenience wrappers are refused
     outright; use raw resource methods (reads) or the Gmail MCP create_draft (drafts).
  3. Tier policy from gws_risk_policy.yaml:
        read           -> allowed; --json and --upload are refused (a GET cannot carry a body)
        write_private  -> allowed IF the target file is shared with nobody (runtime shared-check)
        write_shared   -> escalation of write_private when the target IS shared; needs confirm=True
        destructive    -> needs confirm=True
        outbound       -> BLOCKED unconditionally
        unknown        -> BLOCKED until classified
  4. Hard-coded regex backstop, independent of the yaml: outbound-looking ids are blocked even if
     the yaml were edited or mis-tiered. Two independent gates must both pass to fire anything.
  5. Param guards: dangerous query params inside --params ('sendUpdates', 'sendNotificationEmail')
     are forced to their safe value and refused if set dangerously.
  6. Shell-safe subprocess: resolves the native bin\\gws.exe and runs subprocess.run([...], shell=False).
  7. Append-only JSONL audit at .tmp/gws_audit.log.

There is deliberately NO send function in this module.
"""
from __future__ import annotations
import os
import re
import sys
import json
import atexit
import base64
import shutil
import hashlib
import tempfile
import importlib.util
import subprocess
from pathlib import Path
from typing import Optional, Sequence
from datetime import datetime, timezone

import yaml

SKILL_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[4]
POLICY_FILE = TOOLS_DIR / "gws_risk_policy.yaml"
ACCOUNT_MAP_FILE = TOOLS_DIR / "gws_account_map.json"
# Durable, outside the repo and outside .tmp (Bedrock Tier 2: an audit log must survive a
# repo clean / .tmp wipe). Records are hash-chained: each carries sha256 of the previous
# line, so truncation or in-place edits break the chain (tamper-evident, verifiable later).
AUDIT_LOG = Path(
    os.environ.get("GWS_AUDIT_LOG")
    or Path.home() / ".local" / "state" / "starter-pack" / "gws_audit.log"
)

# The native gws binary. NEVER "gws" (FileNotFoundError on Windows — no PATHEXT consult) and
# NEVER the .cmd shim (re-routes through cmd.exe and re-tokenizes Unicode/newlines, the incident bug).
GWS_EXE = Path(
    os.environ.get("GWS_EXE")
    or (str(Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules" / "@googleworkspace" / "cli" / "bin" / "gws.exe")
        if sys.platform == "win32" else (shutil.which("gws") or "/usr/local/bin/gws"))
)

# Discovery id prefix can differ from the gws service command word; normalize the few that do.
SERVICE_ALIASES = {"admin-reports": "reports", "wf": "workflow"}

# Services whose writes target a Drive-backed file and therefore get the shared-check.
FILE_SERVICES = {"drive", "docs", "sheets", "slides"}
FILE_ID_KEYS = ("fileId", "spreadsheetId", "documentId", "presentationId")

# ---------------------------------------------------------------------------
# Hard regex backstop — independent of the yaml. If ANY of these match the method id, the call is
# outbound and blocked, even if the yaml says otherwise. Mirrors ST's FORBIDDEN_PATTERNS.
# ---------------------------------------------------------------------------
BACKSTOP_OUTBOUND = [
    re.compile(r"\.send$"),
    re.compile(r"\.import$"),
    re.compile(r"\.watch$"),
    re.compile(r"\.permissions\.(create|insert)$"),
    re.compile(r"\.acl\.(insert|create)$"),
    re.compile(r"spaces\.(messages|members)\.(create|insert)$"),
    re.compile(r"sendAs\.(create|verify|update|patch)$"),
    re.compile(r"forwardingAddresses\.create$"),
    re.compile(r"\.invitations?\.(create|insert)$"),
    re.compile(r"\.invite$"),
    re.compile(r"\.notify$"),
    re.compile(r"\.share$"),
]

# Hardcoded request-body guards, independent of the yaml (like the backstop). Gmail label
# application from automation is addLabelIds-only: removeLabelIds could silently archive a
# message (remove INBOX) or strip labels, so it is refused outright — no override.
BODY_GUARDS: dict[str, list[str]] = {
    "gmail.users.messages.modify": ["removeLabelIds"],
    "gmail.users.threads.modify": ["removeLabelIds"],
}


class PolicyError(Exception):
    """The risk policy refused this call."""


class ConfirmRequired(Exception):
    """A destructive or shared-target write needs confirm=True (caller must get the account owner's OK first)."""


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------
_policy_cache: Optional[dict] = None
_accounts_cache: Optional[dict] = None


def _policy() -> dict:
    global _policy_cache
    if _policy_cache is None:
        if not POLICY_FILE.exists():
            raise PolicyError(f"Missing policy: {POLICY_FILE}. Run gen_gws_policy.py first.")
        _policy_cache = yaml.safe_load(POLICY_FILE.read_text(encoding="utf-8"))
    return _policy_cache


def _accounts() -> dict:
    global _accounts_cache
    if _accounts_cache is None:
        data = json.loads(ACCOUNT_MAP_FILE.read_text(encoding="utf-8"))
        _accounts_cache = data.get("accounts", {})
    return _accounts_cache


def _resolve_account(account: str) -> dict:
    accts = _accounts()
    if account not in accts:
        raise PolicyError(
            f"Unknown account '{account}'. Known: {', '.join(sorted(accts))}. "
            f"Add it to gws_account_map.json before use."
        )
    return accts[account]


# ---------------------------------------------------------------------------
# Proton Pass vault materialization (Bedrock v1.2 PROTON-VAULT-ONLY)
#
# An account whose map entry carries "vault_item" is VAULT-ONLY: its OAuth files
# (client_secret.json + credentials.enc) live in Proton Pass, are materialized into a
# per-process temp dir at first use, and are wiped at interpreter exit. There is
# deliberately NO fallback to the on-disk config_dir — vault unreachable = no Google.
# Every retrieval carries PROTON_PASS_AGENT_REASON, so Proton's vault access log is the
# audit trail for token use. NOTE: credentials.enc is decrypted by gws via the local OS
# keyring, so the vaulted blob only works on a machine that has done a gws login before;
# disaster recovery on a new machine = fresh `gws auth login`, then re-seed the vault.
# ---------------------------------------------------------------------------
PASS_CLI = Path(os.environ.get("PASS_CLI") or os.path.expanduser("~/bin/pass-cli.exe"))
VAULT_NAME = os.environ.get("GWS_VAULT_NAME", "")  # only used by accounts that name a vault item
VAULT_SESSION_DIR = Path(os.path.expanduser(os.environ.get("GWS_VAULT_SESSION_DIR", "~/.proton-pass-agent/gws")))
VAULT_FIELD_CLIENT_SECRET = "client_secret_json"
VAULT_FIELD_CREDENTIALS = "credentials_enc_b64"
VAULT_FIELD_CREDENTIALS_JSON = "credentials_json"  # optional: gws auth export --unmasked, for headless runs

_vault_dirs: dict[str, Path] = {}
_vault_oauth_bindings: dict[str, tuple[str, dict]] = {}
_vault_oauth_provider = None


def _cleanup_vault_dirs() -> None:
    for d in _vault_dirs.values():
        shutil.rmtree(d, ignore_errors=True)


atexit.register(_cleanup_vault_dirs)


def _vault_fields(item: dict) -> dict[str, str]:
    """Flatten a pass-cli item-view JSON into {field_name: text_value}.

    Tolerates the shapes pass-cli emits: top-level extra_fields (name/content.Text or
    Hidden), and custom-item sections with their own field lists. If a 'gws_bundle'
    field is present (single-paste UI seeding), its JSON payload is expanded into the
    individual field names.
    """
    out: dict[str, str] = {}

    def _take(f: dict) -> None:
        name = f.get("name") or f.get("field_name") or ""
        c = f.get("content", f.get("value"))
        if isinstance(c, dict):
            val = c.get("Text") or c.get("Hidden") or c.get("text") or c.get("hidden")
        else:
            val = c
        if name and isinstance(val, str):
            out[name] = val

    node = item.get("item", item)
    content = node.get("content", {}) or {}
    for f in content.get("extra_fields") or []:
        _take(f)
    for sec in content.get("sections") or []:
        for f in sec.get("section_fields") or sec.get("fields") or []:
            _take(f)
    # CLI-created custom items nest one level deeper: content.content.<Kind>.sections
    inner = content.get("content")
    if isinstance(inner, dict):
        for kind in inner.values():
            if isinstance(kind, dict):
                for sec in kind.get("sections") or []:
                    for f in sec.get("section_fields") or sec.get("fields") or []:
                        _take(f)

    # Expand a bundle field (single-paste UI seeding). The field NAME is whatever Sam
    # typed in the Proton UI — accept any field whose value is a JSON object carrying
    # the two required keys.
    for val in list(out.values()):
        if val.lstrip().startswith("{"):
            try:
                inner = json.loads(val)
            except Exception:  # noqa: BLE001
                continue
            if isinstance(inner, dict) and VAULT_FIELD_CLIENT_SECRET in inner and VAULT_FIELD_CREDENTIALS in inner:
                out.update({k: v for k, v in inner.items() if isinstance(v, str)})
                break
    return out


def _vault_config_dir(account: str, item_title: str) -> Path:
    """Materialize a vault-backed account's OAuth files into a per-process temp dir."""
    cached = _vault_dirs.get(account)
    if cached is not None and cached.exists():
        return cached
    if not PASS_CLI.exists():
        raise PolicyError(
            f"Account '{account}' is vault-backed but pass-cli was not found at {PASS_CLI}. "
            f"Fail closed — there is no disk fallback."
        )
    spec = importlib.util.spec_from_file_location('gws_vault_session', TOOLS_DIR / 'gws_vault_session.py')
    session = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(session)
    try:
        res = session.read_item(PASS_CLI, VAULT_NAME, item_title, VAULT_SESSION_DIR,
                                f"gws_safe: materialize gws OAuth token for account '{account}'")
    except session.VaultReadError as exc:
        raise PolicyError(str(exc)) from None
    try:
        fields = _vault_fields(json.loads(res.stdout or "{}"))
        client_secret = fields[VAULT_FIELD_CLIENT_SECRET]
        # Either sealed credentials (this PC's keyring) or the exported JSON must exist.
        if VAULT_FIELD_CREDENTIALS not in fields and not fields.get(VAULT_FIELD_CREDENTIALS_JSON):
            raise KeyError(VAULT_FIELD_CREDENTIALS)
        credentials = base64.b64decode(fields[VAULT_FIELD_CREDENTIALS]) if VAULT_FIELD_CREDENTIALS in fields else None
    except Exception as ex:  # noqa: BLE001
        raise PolicyError(
            f"Vault item '{item_title}' for account '{account}' is malformed "
            f"(need {VAULT_FIELD_CLIENT_SECRET} plus {VAULT_FIELD_CREDENTIALS} or {VAULT_FIELD_CREDENTIALS_JSON}): {ex}"
        )
    d = Path(tempfile.mkdtemp(prefix=f"gws_vault_{account}_"))
    (d / "client_secret.json").write_text(client_secret, encoding="utf-8")
    if credentials is not None:
        (d / "credentials.enc").write_bytes(credentials)
    # Headless machines (the morning-coffee cloud routine) cannot open credentials.enc: it
    # is sealed by the keyring of the PC that logged in. The item may also carry the
    # `gws auth export --unmasked` JSON under `credentials_json`; materialised as the
    # plaintext credentials file gws reads at precedence 4, it works anywhere. On a
    # machine whose keyring CAN open credentials.enc, that still wins (precedence 3).
    exported = fields.get(VAULT_FIELD_CREDENTIALS_JSON)
    if exported and exported.lstrip().startswith("{"):
        (d / "credentials.json").write_text(exported, encoding="utf-8")
    _vault_dirs[account] = d
    return d


def _vault_item_title(account: str, acct: dict) -> str:
    """Vault item holding this account's OAuth files.

    credentials.enc is sealed by the LOCAL OS keyring, so each machine needs its own
    item. GWS_VAULT_ITEM_<ACCOUNT> overrides the map's default for this machine only;
    set it in the machine-local settings, never in the tracked account map.
    """
    return os.environ.get(f"GWS_VAULT_ITEM_{account.upper()}") or acct["vault_item"]


def _env_config_dir(account: str) -> Path | None:
    """Headless runs (the morning-coffee cloud routine) carry the account's exported
    credentials (`gws auth export --unmasked` JSON) in GWS_CREDENTIALS_JSON_<ACCOUNT>
    instead of a vault session, as the JSON itself or base64 of it (the environment
    textarea holds one line per variable). Materialised exactly like the vault path: a
    per-process temp dir, wiped at exit. Returns None when the variable is absent."""
    cached = _vault_dirs.get(account)
    if cached is not None and cached.exists():
        return cached
    var = f"GWS_CREDENTIALS_JSON_{account.upper()}"
    exported = (os.environ.get(var) or "").strip()
    if not exported:
        return None
    if not exported.startswith("{"):
        try:
            exported = base64.b64decode(exported, validate=True).decode("utf-8").strip()
        except Exception as ex:  # noqa: BLE001
            raise PolicyError(f"{var} is set but is neither a JSON object nor base64 of one: {ex}")
    if not exported.startswith("{"):
        raise PolicyError(f"{var} does not hold a JSON object.")
    d = Path(tempfile.mkdtemp(prefix=f"gws_env_{account}_"))
    (d / "credentials.json").write_text(exported, encoding="utf-8")
    _vault_dirs[account] = d
    return d


def _config_dir_for(account: str, acct: dict) -> Path:
    # New accounts can keep refresh credentials entirely in the vault/in memory.
    # Only a short-lived, identity-checked access token reaches the child process.
    if acct.get("vault_oauth_item"):
        cached = _vault_dirs.get(account)
        if cached is not None and cached.exists():
            return cached
        d = Path(tempfile.mkdtemp(prefix=f"gws_oauth_{account}_"))
        _vault_dirs[account] = d
        _vault_oauth_bindings[str(d)] = (account, dict(acct))
        return d
    env_dir = _env_config_dir(account)
    if env_dir is not None:
        return env_dir
    if acct.get("vault_item"):
        return _vault_config_dir(account, _vault_item_title(account, acct))
    return Path(os.path.expanduser(acct["config_dir"]))


# ---------------------------------------------------------------------------
# arg parsing
# ---------------------------------------------------------------------------
def _split_args(args: Sequence[str]) -> tuple[list[str], dict[str, str], list[str]]:
    """Return (positional_tokens, flagvals, raw_flag_order).

    positional_tokens: leading non-flag command words (service/resource/method).
    flagvals: {flag: value} for --flag value and --flag=value forms (value '' for bare flags).
    """
    positionals: list[str] = []
    flags: dict[str, str] = {}
    i = 0
    n = len(args)
    seen_flag = False
    while i < n:
        a = args[i]
        if a.startswith("-"):
            seen_flag = True
            if "=" in a:
                k, v = a.split("=", 1)
                flags[k] = v
                i += 1
            else:
                # value is next arg if it isn't itself a flag
                if i + 1 < n and not args[i + 1].startswith("-"):
                    flags[a] = args[i + 1]
                    i += 2
                else:
                    flags[a] = ""
                    i += 1
        else:
            if not seen_flag:
                positionals.append(a)
            i += 1
    return positionals, flags, list(args)


def _method_id(positionals: Sequence[str]) -> str:
    if not positionals:
        raise PolicyError("No gws command tokens given.")
    toks = list(positionals)
    toks[0] = SERVICE_ALIASES.get(toks[0], toks[0])
    return ".".join(toks)


def _classify(method_id: str) -> str:
    methods = _policy().get("methods", {})
    rec = methods.get(method_id)
    tier = rec["tier"] if rec else "unknown"
    # Hard backstop: force outbound regardless of yaml.
    for pat in BACKSTOP_OUTBOUND:
        if pat.search(method_id):
            return "outbound"
    return tier


# ---------------------------------------------------------------------------
# shared-check
# ---------------------------------------------------------------------------
def _file_id(flags: dict[str, str]) -> Optional[str]:
    raw = flags.get("--params")
    if not raw:
        return None
    try:
        params = json.loads(raw)
    except Exception:  # noqa: BLE001
        return None
    for k in FILE_ID_KEYS:
        if params.get(k):
            return str(params[k])
    return None


def _is_shared(account: str, config_dir: Path, file_id: str) -> bool:
    """Return True if the file is shared beyond its owner. Fails CLOSED (True) if undeterminable."""
    params = json.dumps({"fileId": file_id, "fields": "permissions(id,type,role,emailAddress,domain)",
                         "supportsAllDrives": True})
    try:
        res = _exec(config_dir, ["drive", "permissions", "list", "--params", params])
    except Exception:  # noqa: BLE001
        return True  # cannot tell -> treat as shared (safe)
    if res.returncode != 0:
        return True  # API/permission error -> treat as shared (safe)
    try:
        data = json.loads(res.stdout or "{}")
    except Exception:  # noqa: BLE001
        return True
    perms = data.get("permissions", data if isinstance(data, list) else [])
    if not isinstance(perms, list):
        return True
    # Shared if any permission exists that is not the single owner.
    non_owner = [p for p in perms if (p.get("role") != "owner") or (p.get("type") != "user")]
    return len(non_owner) > 0


# ---------------------------------------------------------------------------
# param guards
# ---------------------------------------------------------------------------
def _apply_param_guards(method_id: str, flags: dict[str, str]) -> dict[str, str]:
    guards = _policy().get("param_guards", {}).get(method_id)
    if not guards:
        return flags
    raw = flags.get("--params") or "{}"
    try:
        params = json.loads(raw)
    except Exception as ex:  # noqa: BLE001
        raise PolicyError(f"--params is not valid JSON, cannot apply param guards: {ex}")
    for pname, rule in guards.items():
        cur = params.get(pname)
        if cur is not None and str(cur) in [str(x) for x in rule.get("refuse", [])]:
            raise PolicyError(
                f"BLOCKED: {method_id} param '{pname}={cur}' would notify/invite a real recipient. "
                f"Refused values: {rule['refuse']}. This guard cannot be overridden from automation."
            )
        params[pname] = rule["force"]  # force the safe value (inject if absent)
    flags = dict(flags)
    flags["--params"] = json.dumps(params)
    return flags


def _apply_body_guards(method_id: str, flags: dict[str, str]) -> None:
    """Refuse dangerous request-body keys (--json). Fail closed: unparseable body = refused."""
    refuse_keys = BODY_GUARDS.get(method_id)
    if not refuse_keys or "--json" not in flags:
        return
    try:
        body = json.loads(flags.get("--json") or "{}")
    except Exception as ex:  # noqa: BLE001
        raise PolicyError(f"--json is not valid JSON, cannot apply body guards for {method_id}: {ex}")
    for key in refuse_keys:
        if isinstance(body, dict) and body.get(key):
            raise PolicyError(
                f"BLOCKED: {method_id} body key '{key}' is refused from automation "
                f"(labels are additive-only; removing labels can archive/hide mail). "
                f"This guard cannot be overridden."
            )


# ---------------------------------------------------------------------------
# subprocess (shell-safe, the incident fix)
# ---------------------------------------------------------------------------
def _exec(config_dir: Path, final_args: Sequence[str], timeout: int = 120) -> subprocess.CompletedProcess:
    if not GWS_EXE.exists():
        raise PolicyError(f"gws.exe not found at {GWS_EXE}. Set GWS_EXE env or fix the path.")
    env = dict(os.environ)
    env["GOOGLE_WORKSPACE_CLI_CONFIG_DIR"] = str(config_dir)
    oauth_binding = _vault_oauth_bindings.get(str(config_dir))
    access_token = None
    if oauth_binding:
        global _vault_oauth_provider
        if _vault_oauth_provider is None:
            spec = importlib.util.spec_from_file_location("gws_vault_oauth", TOOLS_DIR / "gws_vault_oauth.py")
            _vault_oauth_provider = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_vault_oauth_provider)
        account, acct = oauth_binding
        try:
            access_token = _vault_oauth_provider.get_access_token(
                account, acct, pass_cli=PASS_CLI, vault_name=VAULT_NAME, session_dir=VAULT_SESSION_DIR
            )
        except Exception:
            raise PolicyError(f"Vault OAuth authorization unavailable for '{account}'; no credential fallback.") from None
        env.pop("GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE", None)
        env["GOOGLE_WORKSPACE_CLI_TOKEN"] = access_token
    if (config_dir / "credentials.json").exists() and not (config_dir / "credentials.enc").exists():
        # Exported credentials (headless runs) have no OS keyring to consult.
        env.setdefault("GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND", "file")
    result = subprocess.run(
        [str(GWS_EXE), *final_args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        shell=False,          # CRITICAL: never shell=True (the incident bug)
        env=env,
        timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    if access_token:
        # Defensive: a CLI error must not reveal the injected bearer token.
        result.stdout = (result.stdout or "").replace(access_token, "[REDACTED]")
        result.stderr = (result.stderr or "").replace(access_token, "[REDACTED]")
    return result


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------
def _flags_to_argv(flags: dict[str, str]) -> list[str]:
    out: list[str] = []
    for k, v in flags.items():
        if v == "":
            out.append(k)
        else:
            out.extend([k, v])
    return out


def _last_audit_line_hash() -> str:
    """sha256 of the last line in the audit log ('' for an empty/new log) — the chain link."""
    try:
        with open(AUDIT_LOG, "rb") as f:
            last = b""
            for line in f:
                if line.strip():
                    last = line.strip()
            return hashlib.sha256(last).hexdigest()[:16] if last else ""
    except FileNotFoundError:
        return ""


def _audit(account: str, method_id: str, tier: str, outcome: str, flags: dict[str, str]) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    body = flags.get("--json", "") or ""
    params = flags.get("--params", "") or ""
    # crude recipient count: emailAddress occurrences in params/body
    rcount = len(re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", params + body))
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "account": account,
        "method_id": method_id,
        "tier": tier,
        "recipient_count": rcount,
        "body_hash": hashlib.sha256(body.encode("utf-8")).hexdigest()[:16] if body else "",
        "outcome": outcome,
        "prev": _last_audit_line_hash(),
    }
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


# ---------------------------------------------------------------------------
# main entry
# ---------------------------------------------------------------------------
def run(account: str, args: Sequence[str], *, confirm: bool = False, intent: str = "", timeout: int = 120) -> subprocess.CompletedProcess:
    """The one sanctioned gws call.

    Args:
        account: required account name (key in gws_account_map.json). No default.
        args: the gws argv WITHOUT the leading binary, e.g.
              ["drive", "files", "get", "--params", '{"fileId":"abc"}'].
        confirm: required True for destructive and write_shared tiers.
        intent: short human description for the audit log.

    Returns:
        subprocess.CompletedProcess (returncode, stdout, stderr).

    Raises:
        PolicyError      — tier blocked / unknown account / read carrying a body / guard refusal.
        ConfirmRequired  — destructive or shared-target write without confirm=True.
    """
    acct = _resolve_account(account)
    config_dir = _config_dir_for(account, acct)

    positionals, flags, _ = _split_args(args)

    # Refuse '+' helper verbs entirely.
    for tok in positionals + list(flags.keys()):
        if tok.startswith("+"):
            _audit(account, "+helper", "blocked", "BLOCKED_plus_helper", flags)
            raise PolicyError(
                f"BLOCKED: gws '+' helper verbs (e.g. {tok}) are not allowed through gws_safe. "
                f"Use raw resource methods for reads; draft email via the Gmail MCP create_draft."
            )

    method_id = _method_id(positionals)
    tier = _classify(method_id)

    # --- tier gates ---
    if tier == "outbound":
        _audit(account, method_id, tier, "BLOCKED_outbound", flags)
        raise PolicyError(
            f"BLOCKED: {method_id} is outbound (send/share/invite/notify/watch/import). "
            f"This helper cannot put anything in front of another account. Do it in the web UI."
        )
    if tier == "unknown":
        _audit(account, method_id, tier, "BLOCKED_unknown", flags)
        raise PolicyError(
            f"BLOCKED: {method_id} is not classified in gws_risk_policy.yaml (tier=unknown). "
            f"Run gen_gws_policy.py and review it before use. Deny-by-default."
        )

    if tier == "read":
        if "--json" in flags:
            raise PolicyError(f"BLOCKED: read {method_id} cannot take --json (a request body). Reads are GET-only.")
        if "--upload" in flags or "--upload-content-type" in flags:
            raise PolicyError(f"BLOCKED: read {method_id} cannot take --upload (media). Reads are GET-only.")

    effective_tier = tier
    if tier == "write_private":
        svc = method_id.split(".")[0]
        if svc in FILE_SERVICES:
            fid = _file_id(flags)
            if fid is None:
                # No identifiable target file -> cannot prove it is private -> gate it (fail closed).
                effective_tier = "write_shared"
            elif _is_shared(account, config_dir, fid):
                effective_tier = "write_shared"

    if effective_tier == "write_shared" and not confirm:
        _audit(account, method_id, "write_shared", "BLOCKED_shared_needs_confirm", flags)
        raise ConfirmRequired(
            f"{method_id} targets a file that is shared with someone else (or whose sharing state "
            f"could not be confirmed). Editing shared files requires the account owner's explicit OK. "
            f"Get the OK, then pass confirm=True."
        )
    if tier == "destructive" and not confirm:
        _audit(account, method_id, "destructive", "BLOCKED_destructive_needs_confirm", flags)
        raise ConfirmRequired(
            f"{method_id} is destructive (delete/trash/clear). Get the account owner's OK, then pass confirm=True."
        )

    # --- param guards (force safe notify values, refuse dangerous) ---
    try:
        flags = _apply_param_guards(method_id, flags)
    except PolicyError:
        _audit(account, method_id, effective_tier, "BLOCKED_param_guard", flags)
        raise

    # --- body guards (refuse dangerous --json keys, e.g. removeLabelIds) ---
    try:
        _apply_body_guards(method_id, flags)
    except PolicyError:
        _audit(account, method_id, effective_tier, "BLOCKED_body_guard", flags)
        raise

    # --- execute ---
    final_args = positionals + _flags_to_argv(flags)
    res = _exec(config_dir, final_args, timeout=timeout)
    outcome = f"rc={res.returncode}"
    _audit(account, method_id, effective_tier, outcome, flags)
    return res


# ---------- thin convenience wrappers (reads only) ----------
def read_sheet(account: str, spreadsheet_id: str, a1_range: Optional[str] = None) -> subprocess.CompletedProcess:
    """Read a spreadsheet (GET). Demonstrates the read path; resolves account, classifies as read."""
    if a1_range:
        params = json.dumps({"spreadsheetId": spreadsheet_id, "range": a1_range})
        return run(account, ["sheets", "spreadsheets", "values", "get", "--params", params], intent="read_sheet")
    params = json.dumps({"spreadsheetId": spreadsheet_id})
    return run(account, ["sheets", "spreadsheets", "get", "--params", params], intent="read_sheet")


def classify(account_unused: str = "", *tokens: str) -> str:
    """Expose the tier for a command (for tests/scripts). Account-agnostic."""
    return _classify(_method_id(list(tokens)))


if __name__ == "__main__":
    # CLI shim: python gws_safe.py <account> <gws args...> [--confirm]
    argv = sys.argv[1:]
    if not argv:
        print("usage: python gws_safe.py <account> <gws args...>", file=sys.stderr)
        sys.exit(2)
    acct_name = argv[0]
    rest = argv[1:]
    do_confirm = False
    if "--confirm" in rest:
        rest = [a for a in rest if a != "--confirm"]
        do_confirm = True
    try:
        r = run(acct_name, rest, confirm=do_confirm, intent="cli")
    except (PolicyError, ConfirmRequired) as ex:
        print(f"[gws_safe blocked] {ex}", file=sys.stderr)
        sys.exit(2)
    sys.stdout.write(r.stdout or "")
    sys.stderr.write(r.stderr or "")
    sys.exit(r.returncode)
