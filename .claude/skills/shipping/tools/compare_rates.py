"""Compare UPS and USPS retail rates for a promo shipment to Hawaii, cheapest first, with sources.

  python compare_rates.py --from 91730 --to 96768 --lbs 30 --length 20 --width 14 --height 12 --cartons 6
  python compare_rates.py --from 20109 --to 96817 --lbs 4 --length 12 --width 10 --height 8 --json

One carton is quoted and multiplied by --cartons (default 1). USPS comes from usps_rates.py
(no browser). UPS comes from ups_rates.mjs, which needs a plain Chrome open with remote debugging;
ups_chrome.py starts one if none is running. A carrier that fails is reported, never hidden.
Every USPS line carries a link that opens to the rendered rate page. UPS has no deep link; its
source line gives the page and the inputs, and `--show-ups` walks the real page in the Chrome
window and leaves it on screen.
"""

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CDP = "http://127.0.0.1:9222"


def _frac(s: str) -> float:
    s = s.replace('"', "").strip()
    m = re.fullmatch(r"(\d+)(?:-(\d+)/(\d+))?", s)
    return int(m.group(1)) + (int(m.group(2)) / int(m.group(3)) if m.group(2) else 0) if m else 0.0


def flat_rate_fits(caption: str, dims) -> bool:
    """True if the carton fits inside any box size named in a USPS flat-rate caption.
    Captions read like: USPS-Produced Box: 13-5/8" x 11-7/8" x 3-3/8" or 11" x 8-1/2" x 5-1/2"."""
    boxes = re.findall(r'([\d/-]+)"?\s*(?:\([LWH]\))?\s*[xX]\s*([\d/-]+)"?\s*(?:\([LWH]\))?\s*[xX]\s*([\d/-]+)', caption or "")
    if not boxes:
        return True  # nothing to measure against; keep the row
    carton = sorted(float(d) for d in dims)
    for b in boxes:
        box = sorted(_frac(x) for x in b)
        if all(c <= bx for c, bx in zip(carton, box)):
            return True
    return False


def run(cmd, timeout=120):
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    out = r.stdout
    i = out.find("{")
    try:
        data = json.loads(out[i:]) if i >= 0 else {}
    except json.JSONDecodeError:
        data = {}
    return r.returncode, data, (r.stderr or out)[-300:], round(time.time() - t0, 2)


def chrome_up() -> bool:
    try:
        urllib.request.urlopen(CDP + "/json/version", timeout=2)
        return True
    except Exception:
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="src", required=True, help="ship-from ZIP (the supplier's ship point)")
    ap.add_argument("--to", dest="dst", required=True, help="ship-to ZIP")
    ap.add_argument("--lbs", type=float, required=True, help="weight of ONE carton")
    ap.add_argument("--oz", type=int, default=0)
    ap.add_argument("--length", type=float)
    ap.add_argument("--width", type=float)
    ap.add_argument("--height", type=float)
    ap.add_argument("--cartons", type=int, default=1, help="number of identical cartons; totals are per-carton rate times this")
    ap.add_argument("--show-ups", action="store_true", help="also walk the UPS page in the Chrome window and leave it on screen")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    dims = [a.length, a.width, a.height] if a.length and a.width and a.height else None

    usps_cmd = [sys.executable, str(HERE / "usps_rates.py"), "--from", a.src, "--to", a.dst, "--lbs", str(int(a.lbs)), "--oz", str(a.oz), "--json"]
    ups_cmd = ["node", str(HERE / "ups_rates.mjs"), f"--from={a.src}", f"--to={a.dst}", f"--weight={a.lbs:g}"]
    if dims:
        usps_cmd += ["--length", str(a.length), "--width", str(a.width), "--height", str(a.height)]
        ups_cmd += [f"--length={a.length:g}", f"--width={a.width:g}", f"--height={a.height:g}"]

    rows, problems, timing, sources = [], [], {}, {}
    rc, d, err, t = run(usps_cmd); timing["usps"] = t
    if rc == 0 and d.get("services"):
        sources["USPS"] = d.get("citationUrl", "https://postcalc.usps.com/")
        for s in d["services"]:
            if s.get("retailUSD") is None or "Media Mail" in (s.get("service") or ""):
                continue  # Media Mail is books and media only; promo goods do not qualify
            if dims and "Flat Rate" in (s.get("service") or "") and not flat_rate_fits(s.get("caption"), dims):
                continue  # the carton does not fit in that USPS box
            rows.append({"carrier": "USPS", "service": s["service"], "perCartonUSD": s["retailUSD"], "onlinePerCartonUSD": s.get("clickNShipUSD"),
                         "delivery": s.get("delivery") or "", "transitDays": None, "note": s.get("caption") or "", "source": sources["USPS"]})
    else:
        problems.append(f"USPS failed: {err.strip()[-160:]}")

    if not chrome_up():
        subprocess.run([sys.executable, str(HERE / "ups_chrome.py")], capture_output=True, text=True, timeout=60)
    rc, d, err, t = run(ups_cmd); timing["ups"] = t
    if rc == 0 and d.get("services"):
        inputs = f"ship from {a.src} US, ship to {a.dst} US, Simple Rate off, My Packaging, {a.lbs:g} lb" + (f", {a.length:g}x{a.width:g}x{a.height:g} in" if dims else "") + ", pay at a UPS location"
        sources["UPS"] = "https://wwwapps.ups.com/ctc/request?loc=en_US  (enter: " + inputs + ")"
        for s in d["services"]:
            rows.append({"carrier": "UPS", "service": s["service"], "perCartonUSD": s["totalUSD"], "onlinePerCartonUSD": None,
                         "delivery": s.get("deliveredBy") or "", "transitDays": s.get("daysInTransit"),
                         "note": f"billed at {s.get('billableWeight')}" if s.get("billableWeight") else "", "source": sources["UPS"]})
    else:
        problems.append(f"UPS failed: {err.strip()[-160:]}")

    for r in rows:
        r["totalUSD"] = round(r["perCartonUSD"] * a.cartons, 2)
        r["onlineTotalUSD"] = round(r["onlinePerCartonUSD"] * a.cartons, 2) if r["onlinePerCartonUSD"] else None
    rows.sort(key=lambda r: r["totalUSD"])

    if a.show_ups and "UPS" in sources:
        subprocess.Popen(["node", str(HERE / "ups_ctc.mjs"), f"--from={a.src}", f"--to={a.dst}", f"--weight={a.lbs:g}", "--show"]
                         + ([f"--length={a.length:g}", f"--width={a.width:g}", f"--height={a.height:g}"] if dims else []),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    result = {"request": {"from": a.src, "to": a.dst, "cartonLbs": a.lbs, "oz": a.oz, "dims": dims, "cartons": a.cartons},
              "options": rows, "problems": problems, "latencySec": timing, "sources": sources}
    if a.json:
        print(json.dumps(result, indent=1))
        return
    shape = f"{a.length:g}x{a.width:g}x{a.height:g} in" if dims else "no dims"
    print(f"{a.src} -> {a.dst}: {a.cartons} carton(s) of {a.lbs:g} lb {a.oz} oz, {shape}")
    print(f"{'carrier':<6} {'service':<36} {'total':>10} {'online':>10} {'per ctn':>9}  {'arrives':<28} note")
    for r in rows:
        online = f"${r['onlineTotalUSD']:.2f}" if r["onlineTotalUSD"] else ""
        print(f"{r['carrier']:<6} {r['service'][:36]:<36} {'$%.2f' % r['totalUSD']:>10} {online:>10} {'$%.2f' % r['perCartonUSD']:>9}  {r['delivery'][:28]:<28} {r['note']}")
    for p in problems:
        print("!", p)
    print(f"(usps {timing.get('usps')}s, ups {timing.get('ups')}s)")
    for k, v in sources.items():
        print(f"source {k}: {v}")
    if a.show_ups and "UPS" in sources:
        print("UPS page is being walked in the Chrome window; it comes to the front in about 25 seconds.")


if __name__ == "__main__":
    main()
