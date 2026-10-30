"""USPS retail rates in under a second, from the Postage Price Calculator's own JSON endpoint.

No browser, no account, no session. postcalc.usps.com renders its results page from a GET to
/Retail/GetMailServices; this calls it directly. Stdlib only.

  python usps_rates.py --from 60143 --to 96720 --lbs 10 --length 24 --width 18 --height 12
  python usps_rates.py --from 60143 --to 96720 --lbs 3 --oz 4        (no dims: plain Package)
  add --json for the raw structure, --date MM/DD/YYYY to postdate
"""

import argparse
import datetime as dt
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request

ENDPOINT = "https://postcalc.usps.com/Retail/GetMailServices"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://postcalc.usps.com/Calculator/MailServices",
}


def money(s):
    s = s or ""
    return float(re.sub(r"[^\d.]", "", s)) if re.search(r"\d", s) else None


def quote(src: str, dst: str, lbs: int, oz: int, dims, date: str) -> dict:
    large = bool(dims and max(dims) > 12)
    L, W, H = (sorted(dims, reverse=True) if dims else (0, 0, 0))
    q = {
        "countryID": 0, "countryCode": "US", "origin": src, "isOrigMil": "False", "destination": dst, "isDestMil": "False",
        "shippingDate": f"{date} 12:00:00 AM", "shippingTime": "12:00", "itemValue": "",
        "dayOldPoultry": "False", "groundTransportation": "False", "hazmat": "False", "liveAnimals": "False",
        "nonnegotiableDocument": "False", "crematedRemains": "False",
        "mailShapeAndSize": "7" if large else "Package",  # the endpoint takes the word for Package but only the code 7 for Large Package
        "pounds": lbs, "ounces": oz, "length": math.ceil(L) if large else 0, "height": math.ceil(H) if large else 0, "width": math.ceil(W) if large else 0,
        "girth": 0, "shape": "Rectangular", "nonmachinable": "False", "isEmbedded": "False",
    }
    req = urllib.request.Request(ENDPOINT + "?" + urllib.parse.urlencode(q), headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    page = data.get("Page") or {}
    # The same results, rendered on usps.com: this URL opens cold and shows exactly these rates.
    view = {"country": 0, "ccode": "US", "oz": src, "omil": "False", "dz": dst, "dmil": "False", "retail": "False",
            "mdt": date, "mdz": "12:00", "m": 7 if large else 6, "hscode": "False", "p": lbs, "o": oz}
    if large:
        view.update({"rect": "True", "l": math.ceil(L), "h": math.ceil(H), "w": math.ceil(W), "g": 0})
    out = {"error": data.get("PageError") or "", "shipment": " ".join(page.get("Breadcrumb") or []), "services": [],
           "footnotes": page.get("Footnotes") or [], "shape": "LargePackage" if large else "Package",
           "citationUrl": "https://postcalc.usps.com/Calculator/MailServices?" + urllib.parse.urlencode(view)}
    for s in page.get("MailServices") or []:
        opts = [{"option": o.get("Name"), "delivery": o.get("DeliveryDay"), "retailUSD": money(o.get("RetailPrice")),
                 "clickNShipUSD": money(o.get("CnSPrice"))} for o in s.get("DeliveryOptions") or []]
        normal = next((o for o in opts if "Normal" in (o["option"] or "")), opts[0] if opts else {})
        out["services"].append({"service": s.get("Title"), "caption": s.get("Dimensions") or "", "notes": s.get("Notes") or "",
                                "deliveryHeader": s.get("CommitmentLabel"), "delivery": normal.get("delivery"),
                                "retailUSD": normal.get("retailUSD"), "clickNShipUSD": normal.get("clickNShipUSD"), "options": opts})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="src", required=True, help="origin ZIP")
    ap.add_argument("--to", dest="dst", required=True, help="destination ZIP")
    ap.add_argument("--lbs", type=int, required=True)
    ap.add_argument("--oz", type=int, default=0)
    ap.add_argument("--length", type=float)
    ap.add_argument("--width", type=float)
    ap.add_argument("--height", type=float)
    ap.add_argument("--date", help="mail date MM/DD/YYYY, default today")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    dims = [a.length, a.width, a.height] if a.length and a.width and a.height else None
    t0 = time.time()
    data = quote(a.src, a.dst, a.lbs, a.oz, dims, a.date or dt.date.today().strftime("%m/%d/%Y"))
    data["request"] = {"from": a.src, "to": a.dst, "lbs": a.lbs, "oz": a.oz, "dims": dims,
                       "rateBasis": "retail counter price and Click-N-Ship online price, no account",
                       "latencySec": round(time.time() - t0, 2)}
    if a.json:
        print(json.dumps(data, indent=1))
    else:
        print(data["shipment"] or data["error"] or "(no shipment line)")
        print(f"{'service':<36} {'delivery':<24} {'retail':>9} {'online':>9}")
        for s in data["services"]:
            r = f"${s['retailUSD']:.2f}" if s["retailUSD"] is not None else "-"
            c = f"${s['clickNShipUSD']:.2f}" if s["clickNShipUSD"] is not None else "-"
            print(f"{(s['service'] or '')[:36]:<36} {(s['delivery'] or '')[:24]:<24} {r:>9} {c:>9}")
        print(f"({data['request']['latencySec']}s)")
        print(f"source: {data['citationUrl']}")
    if data["error"] or not data["services"]:
        sys.exit(f"USPS: {data['error'] or 'no services returned'}")


if __name__ == "__main__":
    main()
