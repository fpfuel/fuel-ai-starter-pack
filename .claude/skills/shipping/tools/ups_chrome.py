"""Start the plain Chrome window the UPS tools talk to, if one is not already running.

UPS refuses browsers that Playwright launches and serves a download to a headless Chrome, so the
UPS tools attach over Chrome's remote-debugging port to a normal, headed Chrome. This starts one,
parked off-screen, on its own profile folder. Run it once; leave the window open. Microsoft Edge
is used when Chrome is not installed; UPS accepts it the same way. UPS_CHROME_PORT overrides 9222.

  python ups_chrome.py            start if needed, then print the status
  python ups_chrome.py --status   only report
"""

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PORT = int(os.environ.get("UPS_CHROME_PORT") or 9222)
PROFILE = Path(__file__).resolve().parents[3] / ".tmp" / "ups_chrome_profile"
CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def up() -> bool:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=2)
        return True
    except Exception:
        return False


def main() -> None:
    if "--status" in sys.argv:
        print("running" if up() else "not running")
        return
    if up():
        print(f"Chrome already listening on {PORT}")
        return
    chrome = next((c for c in CANDIDATES if Path(c).exists()), None)
    if not chrome:
        sys.exit("Neither Google Chrome nor Microsoft Edge was found; install one or set the path in ups_chrome.py")
    PROFILE.mkdir(parents=True, exist_ok=True)
    args = [chrome, f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}", "--no-first-run",
            "--no-default-browser-check", "--window-size=1280,900", "--window-position=2000,2000",
            "https://wwwapps.ups.com/ctc/request?loc=en_US"]
    flags = 0x00000008 if os.name == "nt" else 0  # DETACHED_PROCESS on Windows
    subprocess.Popen(args, creationflags=flags, close_fds=True)
    for _ in range(40):
        if up():
            print(f"{Path(chrome).stem} started on port {PORT}, parked off-screen, profile {PROFILE}")
            return
        time.sleep(0.5)
    sys.exit("Chrome did not come up on the debugging port")


if __name__ == "__main__":
    main()
