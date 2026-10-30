"""Check this computer for what the starter pack needs, fix what can be fixed, and say what
works. Setup runs it first; run it again any time something stops working.

  python .claude/tools/env_check.py          check only
  python .claude/tools/env_check.py --fix    also install what is missing and switch on memory
  python .claude/tools/env_check.py --json   machine-readable result

Never prints a key or password. Always exits 0: the report is the result.
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[2]
SHIP_TOOLS = PACK_ROOT / ".claude" / "skills" / "shipping" / "tools"
MEMORY_DIR = PACK_ROOT / "Brain" / "memory"
LOCAL_SETTINGS = PACK_ROOT / ".claude" / "settings.local.json"
HIDE = getattr(subprocess, "CREATE_NO_WINDOW", 0)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import keys  # noqa: E402


def run(cmd, cwd=None, timeout=60):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           creationflags=HIDE)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


def where():
    if os.environ.get("CLAUDE_CODE_REMOTE") or os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID"):
        return "cloud"
    if platform.system() == "Linux" and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return "cloud"
    return "local"


def find_chrome():
    candidates = []
    if platform.system() == "Windows":
        for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"),
                     os.environ.get("LOCALAPPDATA")):
            if base:
                candidates.append(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe")
    elif platform.system() == "Darwin":
        candidates.append(Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"))
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    return next((str(c) for c in candidates if c.exists()), None)


def reach(url):
    """True when the host answers at all; an error page still means the network path is open."""
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "starter-pack-check/1"})
        with urllib.request.urlopen(req, timeout=8):
            return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def git_ignored(path):
    if not shutil.which("git") or not (PACK_ROOT / ".git").exists():
        return None
    code, _ = run(["git", "check-ignore", "-q", str(path)], cwd=PACK_ROOT)
    return code == 0


def memory_state(fix):
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    target = str(MEMORY_DIR.resolve())
    settings = {}
    if LOCAL_SETTINGS.exists():
        try:
            settings = json.loads(LOCAL_SETTINGS.read_text(encoding="utf-8"))
        except ValueError:
            settings = {}
    if settings.get("autoMemoryDirectory") == target:
        return "on", False
    if not fix:
        return "off", False
    settings["autoMemoryDirectory"] = target
    LOCAL_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_SETTINGS.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return "on", True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    r = {"where": where(), "system": f"{platform.system()} {platform.release()}",
         "python": platform.python_version(), "fixed": []}
    r["python_ok"] = sys.version_info >= (3, 9)

    node = shutil.which("node")
    r["node"] = run(["node", "--version"])[1].strip() if node else None
    r["chrome"] = bool(find_chrome())
    playwright = (SHIP_TOOLS / "node_modules" / "playwright-core").exists()
    npm = shutil.which("npm")  # npm.cmd on Windows: launch it by full path
    if a.fix and node and not playwright and npm:
        code, _ = run([npm, "install", "--no-audit", "--no-fund"], cwd=SHIP_TOOLS, timeout=300)
        if code == 0:
            r["fixed"].append("installed the UPS rate tool's browser driver (npm install)")
        playwright = (SHIP_TOOLS / "node_modules" / "playwright-core").exists()
    r["ups_driver"] = playwright

    r["net_usps"] = reach("https://postcalc.usps.com/")
    r["net_sage"] = reach("https://www.promoplace.com/ws/ws.dll/ConnectAPI")
    r["net_pipedrive"] = reach("https://api.pipedrive.com/")

    r["keys_file"] = keys.KEYS_FILE.exists()
    r["keys_ignored"] = git_ignored(keys.KEYS_FILE) if r["keys_file"] else None
    r["keys_filled"] = keys.filled()

    r["memory"], changed = memory_state(a.fix)
    if changed:
        r["fixed"].append("pointed Claude's memory at Brain/memory (starts next session)")

    sage = all(n in r["keys_filled"] for n in ("SAGE_ACCT_ID", "SAGE_LOGIN_ID", "SAGE_API_KEY"))
    pipedrive = all(n in r["keys_filled"] for n in ("PIPEDRIVE_API_TOKEN", "PIPEDRIVE_DOMAIN"))
    local = r["where"] == "local"
    r["can"] = {
        "Quotes in your sheet": (r["python_ok"], "works" if r["python_ok"] else "needs Python 3.9 or newer"),
        "USPS rates": (r["net_usps"], "works" if r["net_usps"] else "cannot reach usps.com from here"),
        "UPS rates": (local and bool(node) and r["chrome"] and playwright,
                      "works" if local and node and r["chrome"] and playwright else
                      "only on your own computer" if not local else
                      "needs Node.js" if not node else "needs Google Chrome" if not r["chrome"] else
                      "needs its browser driver (run with --fix)"),
        "SAGE product search": (sage and r["net_sage"],
                                "works" if sage and r["net_sage"] else
                                "add your SAGE Connect details to secrets/keys.xlsx" if not sage else
                                "cannot reach SAGE from here"),
        "Sourcing page": (True, "opens in your browser" if local else "saved as a file you download"),
        "Pipedrive": (True, "adds contacts for you" if pipedrive and r["net_pipedrive"] else
                      "gives you text to paste (add a Pipedrive token to switch on)"),
        "Memory": (r["memory"] == "on", "on" if r["memory"] == "on" else "off (run with --fix)"),
    }
    if r["keys_file"] and r["keys_ignored"] is False:
        r["warning"] = "secrets/keys.xlsx is not ignored by git. Do not save or share until this is fixed."

    if a.json:
        print(json.dumps(r, indent=2))
        return
    print(f"Running {'in the cloud' if r['where'] == 'cloud' else 'on this computer'} "
          f"({r['system']}, Python {r['python']}, Node {r['node'] or 'not installed'}, "
          f"Chrome {'found' if r['chrome'] else 'not found'})")
    for item in r["fixed"]:
        print(f"  fixed: {item}")
    width = max(len(k) for k in r["can"])
    for name, (ok, says) in r["can"].items():
        print(f"  {'OK ' if ok else '-- '} {name.ljust(width)}  {says}")
    if r.get("warning"):
        print("  WARNING: " + r["warning"])


if __name__ == "__main__":
    main()
