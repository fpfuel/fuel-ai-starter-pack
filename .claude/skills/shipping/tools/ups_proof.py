"""Save UPS's own results page as a picture for each rated shipment: the source behind a UPS rate.

  python ups_proof.py LANES.json
      LANES.json: [{"from", "to", "weight", "length", "width", "height", "out": "...png"}, ...]

Walks the public Calculate Time and Cost page once per shipment, in its own tab of the UPS Chrome
window, about 20 seconds each, one after another. Next to each picture it keeps OUT.json:
{"state": "pending" | "saved" | "failed", "lane": {...}, "error": "..."}; the review page reads it.
Callers use start() so the rates come back at once and the pictures follow in the background.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK = HERE.parents[3]
PAGES_DIR = PACK / "internal" / "Domains" / "Work" / "ASB" / "sourcing" / "ups-pages"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
NEW_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def in_cloud() -> bool:
    return bool(os.environ.get("CLAUDE_CODE_REMOTE") or os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID"))


def status_path(png: Path) -> Path:
    return png.with_suffix(".json")


def write_status(png: Path, state: str, lane: dict, error: str = "") -> None:
    body = {"state": state, "lane": {k: lane.get(k) for k in ("from", "to", "weight", "length", "width", "height")},
            "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    if error:
        body["error"] = error
    status_path(png).write_text(json.dumps(body, indent=1), encoding="utf-8")


def start(lanes: list) -> list:
    """Mark each lane pending and capture them in a detached process. Returns the picture paths."""
    if in_cloud() or not lanes:
        return []
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    for lane in lanes:
        write_status(Path(lane["out"]), "pending", lane)
    job = PACK / ".tmp" / f"ups-pages-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}.json"
    job.parent.mkdir(parents=True, exist_ok=True)
    job.write_text(json.dumps(lanes), encoding="utf-8")
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), str(job)], cwd=str(PACK),
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=NO_WINDOW | NEW_GROUP, close_fds=True)
    return [lane["out"] for lane in lanes]


def capture(lane: dict) -> None:
    png = Path(lane["out"])
    cmd = ["node", str(HERE / "ups_ctc.mjs"), f"--from={lane['from']}", f"--to={lane['to']}",
           f"--weight={float(lane['weight']):g}", f"--shot={png}"]
    if lane.get("length") and lane.get("width") and lane.get("height"):
        cmd += [f"--length={float(lane['length']):g}", f"--width={float(lane['width']):g}", f"--height={float(lane['height']):g}"]
    error = ""
    for attempt in range(2):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, creationflags=NO_WINDOW)
            if png.exists():
                write_status(png, "saved", lane)
                return
            error = (r.stderr or r.stdout or "no picture written").strip().splitlines()[-1][:200]
        except subprocess.TimeoutExpired:
            error = "UPS page did not finish within two minutes"
        time.sleep(3)
    write_status(png, "failed", lane, error)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    job = Path(sys.argv[1])
    lanes = json.loads(job.read_text(encoding="utf-8"))
    subprocess.run([sys.executable, str(HERE / "ups_chrome.py")], capture_output=True, text=True, timeout=60,
                   creationflags=NO_WINDOW)
    for lane in lanes:
        capture(lane)
    try:
        job.unlink()
    except OSError:
        pass


if __name__ == "__main__":
    main()
