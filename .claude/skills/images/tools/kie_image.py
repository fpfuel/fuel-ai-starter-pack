"""Make or change pictures on her KIE.ai account (Nano Banana 2). Standard library only.

  python kie_image.py check                      is the key there, and how many credits are left
  python kie_image.py make --prompt "..." [--ref FILE_OR_URL ...] [--aspect 1:1] [--size 1K]
                           [--name short-name] [--out FOLDER]
"""

import argparse
import base64
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PACK_ROOT / ".claude" / "tools"))
import keys  # noqa: E402

API = "https://api.kie.ai"
MODEL = "nano-banana-2"
UA = {"User-Agent": "starter-pack-images/1"}
ASPECTS = ("1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9", "auto")
PLAIN = {401: "KIE did not accept the key. Copy it again at https://kie.ai/api-key and rerun setup step 9b.",
         402: "Out of KIE credits. Add some at https://kie.ai/pricing, then try again.",
         429: "KIE says too many requests right now. Wait a minute and try again.",
         455: "KIE is down for maintenance. Try again later."}


def key():
    k = keys.get("KIE_API_KEY")
    if not k:
        sys.exit("No KIE key yet. Run setup step 9b, or put KIE_API_KEY in secrets/keys.xlsx.")
    return k


def call(method, path, body=None, params=""):
    req = urllib.request.Request(API + path + params, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {key()}", "Content-Type": "application/json", **UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read())
        except ValueError:
            sys.exit(PLAIN.get(e.code, f"KIE answered with an error ({e.code})."))
    except urllib.error.URLError as e:
        sys.exit(f"Could not reach KIE ({e.reason}).")
    code = data.get("code")
    if code != 200:
        sys.exit(PLAIN.get(code, f"KIE error {code}: {data.get('msg') or 'no message'}"))
    return data.get("data")


def credits():
    return float(call("GET", "/api/v1/chat/credit") or 0)


def upload(path):
    p = Path(path)
    if not p.is_file():
        sys.exit(f"Cannot find the picture: {p}")
    mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(p.suffix.lower(), "image/png")
    data = call("POST", "/api/file-base64-upload",
                {"base64Data": f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}",
                 "uploadPath": "starter-pack/refs", "fileName": p.name})
    url = (data or {}).get("downloadUrl")
    if not url:
        sys.exit(f"KIE did not take the picture {p.name}.")
    return url


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "image"


def make(a):
    if a.aspect not in ASPECTS:
        sys.exit(f"Aspect must be one of: {', '.join(ASPECTS)}")
    refs = [r if re.match(r"https?://", r) else upload(r) for r in (a.ref or [])][:10]
    task = call("POST", "/api/v1/jobs/createTask", {"model": MODEL, "input": {
        "prompt": a.prompt, "image_input": refs, "aspect_ratio": a.aspect,
        "resolution": a.size, "output_format": "png"}})
    tid = (task or {}).get("taskId")
    if not tid:
        sys.exit("KIE did not start the picture.")
    deadline = time.time() + 600
    while time.time() < deadline:
        time.sleep(4)
        info = call("GET", "/api/v1/jobs/recordInfo", params=f"?taskId={tid}") or {}
        state = info.get("state")
        if state == "fail":
            sys.exit(f"KIE could not make it: {info.get('failMsg') or 'no reason given'}")
        if state == "success":
            result = info.get("resultJson") or "{}"
            result = json.loads(result) if isinstance(result, str) else result
            urls = result.get("resultUrls") or []
            if not urls:
                sys.exit("KIE finished but sent no picture.")
            out_dir = Path(a.out) if a.out else PACK_ROOT / "External" / "Images"
            out_dir.mkdir(parents=True, exist_ok=True)
            dest = out_dir / f"{date.today():%Y-%m-%d}-{slug(a.name or a.prompt)}.png"
            n = 2
            while dest.exists():
                dest = dest.with_name(f"{date.today():%Y-%m-%d}-{slug(a.name or a.prompt)}-{n}.png")
                n += 1
            with urllib.request.urlopen(urllib.request.Request(urls[0], headers=UA), timeout=120) as r:
                dest.write_bytes(r.read())
            used = info.get("creditsConsumed")
            print(f"Saved {dest}")
            if used is not None:
                print(f"Used {used} credits (about ${float(used) * 0.005:.2f}).")
            return
    sys.exit("KIE took more than ten minutes. Try again, or use a smaller size.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    m = sub.add_parser("make")
    m.add_argument("--prompt", required=True)
    m.add_argument("--ref", action="append", help="a picture file or web address; repeat for more")
    m.add_argument("--aspect", default="1:1")
    m.add_argument("--size", default="1K", choices=("1K", "2K", "4K"))
    m.add_argument("--name")
    m.add_argument("--out")
    a = ap.parse_args()
    if a.cmd == "check":
        c = credits()
        print(f"KIE key works. Credits left: {c:g} (about ${c * 0.005:.2f}, roughly {int(c // 8)} pictures at 1K).")
    else:
        make(a)


if __name__ == "__main__":
    main()
