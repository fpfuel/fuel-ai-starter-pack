"""One-shot sourcing: SAGE search -> candidate details -> USPS and UPS freight -> landed cost, in one run.

  python .claude/skills/product-search/tools/source.py "metal pen" --qty 500 --to 96813 --to-label Honolulu --min-price 1.5 --max-price 6
  python .claude/skills/product-search/tools/source.py "ceramic mug 11 oz" --qty 200 --to 96768 --to-label "Makawao, Maui" --candidates 3

Spends 1 + candidates SAGE queries. Reads the keys file once, runs the detail calls, the USPS calls and
one multi-lane UPS process in parallel. Writes the review JSON (schema karen-review/1) to
internal/Domains/Work/ASB/sourcing/, where the review page picks it up, and prints a compact table.
Retail freight only: the supplier ships on its own account and will quote lower.
"""

import argparse
import datetime as dt
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK_ROOT = HERE.parents[3]
SHIP_TOOLS = PACK_ROOT / ".claude" / "skills" / "shipping" / "tools"
REVIEW_DIR = PACK_ROOT / "internal" / "Domains" / "Work" / "ASB" / "sourcing"
SAGE_TMP = PACK_ROOT / ".tmp" / "sage"
REVIEW_SERVER = PACK_ROOT / ".claude" / "tools" / "review" / "server.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sage = load("sage_connect", HERE / "sage_connect.py")
usps = load("usps_rates", SHIP_TOOLS / "usps_rates.py")
cmp = load("compare_rates", SHIP_TOOLS / "compare_rates.py")


def f(v, default=None):
    try:
        return float(str(v).replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return default


def pick_candidates(products, n, distinct):
    """Top records in search order, preferring distinct suppliers when asked."""
    out, seen = [], set()
    for p in products:
        if distinct and p.get("suppID") in seen:
            continue
        out.append(p); seen.add(p.get("suppID"))
        if len(out) == n:
            return out
    for p in products:  # not enough distinct suppliers: fill from the rest
        if p not in out:
            out.append(p)
            if len(out) == n:
                break
    return out


def eligibility(k: dict) -> dict:
    """Published carton limits, checked the same way the carriers do. Rates still come from the
    carriers; this explains an empty or short list. USPS: 70 lb; Priority Mail length plus girth
    108 in, Ground Advantage 130 in; a carton over one cubic foot is rated on dimensional weight.
    UPS: 150 lb, length 108 in, length plus girth 165 in; dimensional weight on every carton."""
    L, W, H = sorted([float(k.get("L") or 0), float(k.get("W") or 0), float(k.get("H") or 0)], reverse=True)
    lbs = float(k.get("lbs") or 0)
    girth = L + 2 * (W + H)
    cubic = L * W * H
    usps_dim = math.ceil(cubic / 166) if cubic > 1728 else None
    ups_dim = math.ceil(cubic / 139)
    notes = []
    if lbs > 70:
        notes.append("over USPS 70 lb limit, USPS cannot take this carton")
    if girth > 130:
        notes.append("over USPS 130 in length plus girth, USPS cannot take this carton")
    elif girth > 108:
        notes.append("over 108 in length plus girth, USPS Priority Mail is out; Ground Advantage allows 130 in")
    if lbs > 150 or L > 108 or girth > 165:
        notes.append("over UPS small-package limits (150 lb, 108 in long, 165 in length plus girth)")
    if usps_dim and usps_dim > lbs:
        notes.append(f"USPS rates this carton at {usps_dim} lb dimensional weight (over one cubic foot)")
    if ups_dim > lbs:
        notes.append(f"UPS bills {ups_dim} lb dimensional weight")
    return {"lengthPlusGirthIn": round(girth, 1), "cubicIn": round(cubic), "uspsShape": "Large Package" if L > 12 else "Package",
            "uspsDimWeightLb": usps_dim, "upsDimWeightLb": ups_dim, "notes": notes}


def shape_candidate(prod, qty):
    p = prod["product"]
    qtys = [int(q) for q in p.get("qty", []) if str(q).strip() not in ("", "0")]
    nets, cats = p.get("net", []), p.get("catPrc", [])
    breaks = [{"qty": q, "net": f(nets[i]), "catalog": f(cats[i])} for i, q in enumerate(qtys) if i < len(nets)]
    use = max([b for b in breaks if b["qty"] <= qty], key=lambda b: b["qty"], default=breaks[0] if breaks else None)
    sup = p.get("supplier") or {}
    carton = {"units": int(f(p.get("unitsPerCarton"), 0) or 0), "lbs": f(p.get("weightPerCarton"), 0) or 0,
              "L": f(p.get("cartonL"), 0) or 0, "W": f(p.get("cartonW"), 0) or 0, "H": f(p.get("cartonH"), 0) or 0}
    carton["shown"] = bool(carton["units"] and carton["lbs"] and carton["L"] and carton["W"] and carton["H"])
    carton["assumedFrom"] = None
    pics = p.get("pics") or []
    images = [(x.get("url") if isinstance(x, dict) else x) for x in pics][:8]
    img = images[0] if images else None
    web = (sup.get("web") or "").strip()
    flags = []
    if not carton["shown"]:
        flags.append("carton data not shown in SAGE")
    if not (p.get("priceIncludes") or "").strip():
        flags.append("price includes is blank in SAGE; confirm the imprint is included")
    return {
        "id": str(p.get("prodEid")), "name": p.get("prName"), "supplier": sup.get("coName") or p.get("lineName"),
        "supplierSageId": str(p.get("suppId")), "itemNum": str(p.get("itemNum")),
        "supplierUrl": ("https://" + web if web and not web.startswith("http") else web) or None,
        "supplierPhone": sup.get("tel") or sup.get("tollFreeTel") or None, "sageProdEId": int(p.get("prodEid")),
        "imageUrl": img, "images": images,
        "imprintArea": p.get("imprintArea") or "", "decorationMethod": p.get("decorationMethod") or "",
        "description": (p.get("description") or "")[:400], "colors": p.get("colors") or "",
        "netAtQty": use["net"] if use else None, "catalogAtQty": use["catalog"] if use else None,
        "breakUsed": use["qty"] if use else None, "breaks": breaks,
        "setupChg": f(p.get("setupChg"), 0) or 0, "priceIncludes": p.get("priceIncludes") or "",
        "prodTime": p.get("prodTime") or "", "shipFromZip": str(p.get("shipPointZip") or "").zfill(5),
        "madeIn": p.get("madeInCountry") or "", "carton": carton, "cartons": 0, "goodsUSD": None, "setupUSD": None,
        "freight": {"options": [], "cheapest": None, "problems": []}, "landed": None, "flags": flags,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query")
    ap.add_argument("--qty", type=int, required=True)
    ap.add_argument("--to", required=True, help="ship-to ZIP")
    ap.add_argument("--to-label", default="")
    ap.add_argument("--min-price", type=float)
    ap.add_argument("--max-price", type=float)
    ap.add_argument("--candidates", type=int, default=20, help="how many products to detail and rate (one SAGE query each)")
    ap.add_argument("--n", type=int, default=24, help="search records to pull (one query regardless)")
    ap.add_argument("--prompt", default="", help="what she said, verbatim, stored with the run")
    ap.add_argument("--sort", default="POPULARITY")
    ap.add_argument("--distinct-suppliers", action="store_true", help="prefer one product per supplier instead of search order")
    ap.add_argument("--no-ups", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--html", action="store_true", help="also save the review page as one HTML file (for cloud sessions)")
    a = ap.parse_args()
    T = {}
    t0 = time.time()

    t = time.time(); sage.vault_auth(); T["keys"] = round(time.time() - t, 2)
    t = time.time()
    search = sage.api_search(a.query, qty=a.qty, n=a.n, min_price=a.min_price, max_price=a.max_price, sort=a.sort)
    T["search"] = round(time.time() - t, 2)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    SAGE_TMP.mkdir(parents=True, exist_ok=True)
    search_file = SAGE_TMP / f"{stamp}-search.json"
    search_file.write_text(json.dumps(search, indent=1), encoding="utf-8")
    picks = pick_candidates(search.get("products", []), a.candidates, a.distinct_suppliers)
    if not picks:
        sys.exit("no products found")

    t = time.time()
    with ThreadPoolExecutor(max_workers=len(picks)) as ex:
        details = list(ex.map(lambda p: sage.api_detail(p["prodEId"]), picks))
    T["detail"] = round(time.time() - t, 2)
    detail_files = []
    for p, d in zip(picks, details):
        fp = SAGE_TMP / f"{stamp}-detail-{p['prodEId']}.json"
        fp.write_text(json.dumps(d, indent=1), encoding="utf-8"); detail_files.append(str(fp))
    cands = [shape_candidate(d, a.qty) for d in details]

    # carton fallback: borrow the first shown carton from the same supplier, else from any candidate
    shown = [c for c in cands if c["carton"]["shown"]]
    for c in cands:
        if not c["carton"]["shown"] and shown:
            src = next((s for s in shown if s["supplierSageId"] == c["supplierSageId"]), shown[0])
            c["carton"] = {**src["carton"], "assumedFrom": src["name"]}
            c["flags"] = [x for x in c["flags"] if "carton" not in x] + [f"carton data not shown in SAGE; freight assumes the {src['name']} carton"]
        if c["carton"]["units"]:
            c["cartons"] = -(-a.qty // c["carton"]["units"])
        if c["netAtQty"] is not None:
            c["goodsUSD"] = round(c["netAtQty"] * a.qty, 2); c["setupUSD"] = round(c["setupChg"], 2)

    date = dt.date.today().strftime("%m/%d/%Y")
    rateable = [c for c in cands if c["cartons"] and c["carton"]["lbs"]]

    def usps_one(c):
        k = c["carton"]; dims = [k["L"], k["W"], k["H"]]
        lbs = int(k["lbs"]); oz = math.ceil((k["lbs"] - lbs) * 16)
        return usps.quote(c["shipFromZip"], a.to, max(lbs, 0), oz, dims, date)

    def ups_all():
        if a.no_ups or not rateable:
            return {}
        if not cmp.chrome_up():
            subprocess.run([sys.executable, str(SHIP_TOOLS / "ups_chrome.py")], capture_output=True, text=True, timeout=60)
        lanes = [{"id": c["id"], "from": c["shipFromZip"], "to": a.to, "weight": c["carton"]["lbs"],
                  "length": c["carton"]["L"], "width": c["carton"]["W"], "height": c["carton"]["H"]} for c in rateable]
        r = subprocess.run(["node", str(SHIP_TOOLS / "ups_rates.mjs"), "--lanes=" + json.dumps(lanes)], capture_output=True, text=True, timeout=90)
        i = r.stdout.find("{")
        try:
            return {l["id"]: l for l in json.loads(r.stdout[i:])["lanes"]} if i >= 0 else {"_err": r.stderr[-200:]}
        except (json.JSONDecodeError, KeyError):
            return {"_err": (r.stderr or r.stdout)[-200:]}

    t = time.time()
    with ThreadPoolExecutor(max_workers=len(rateable) + 1) as ex:
        ups_fut = ex.submit(ups_all)
        usps_res = list(ex.map(lambda c: _safe(usps_one, c), rateable))
        ups_res = ups_fut.result()
    T["freight"] = round(time.time() - t, 2)

    for c, u in zip(rateable, usps_res):
        k = c["carton"]; dims = [k["L"], k["W"], k["H"]]
        opts = c["freight"]["options"]
        c["freight"]["eligibility"] = eligibility(k)
        if isinstance(u, Exception) or not u or u.get("error"):
            c["freight"]["problems"].append("USPS: " + (str(u) if isinstance(u, Exception) else (u or {}).get("error", "no response")))
        else:
            for s in u["services"]:
                name = s.get("service") or ""
                if s.get("retailUSD") is None or "Media Mail" in name:
                    continue
                if "Flat Rate" in name and not cmp.flat_rate_fits(s.get("caption"), dims):
                    continue
                opts.append({"carrier": "USPS", "service": name, "totalUSD": round(s["retailUSD"] * c["cartons"], 2),
                             "onlineTotalUSD": round(s["clickNShipUSD"] * c["cartons"], 2) if s.get("clickNShipUSD") else None,
                             "perCartonUSD": s["retailUSD"], "delivery": s.get("delivery") or "", "transitDays": None,
                             "note": ("repack into USPS box: " + s["caption"]) if "Flat Rate" in name else (s.get("caption") or ""),
                             "source": u["citationUrl"]})
        lane = ups_res.get(c["id"]) if isinstance(ups_res, dict) else None
        if a.no_ups:
            pass
        elif not lane:
            c["freight"]["problems"].append("UPS: " + (ups_res.get("_err") if isinstance(ups_res, dict) and ups_res.get("_err") else "no lane result"))
        elif not lane["services"]:
            c["freight"]["problems"].append("UPS: System Temporarily Unavailable, the tab needs a real page load" if lane.get("unavailable") else "UPS: no services parsed")
        else:
            inputs = f"ship from {c['shipFromZip']} to {a.to}, My Packaging, {k['lbs']:g} lb, {k['L']:g}x{k['W']:g}x{k['H']:g} in, pay at a UPS location"
            for s in lane["services"]:
                opts.append({"carrier": "UPS", "service": s["service"], "totalUSD": round(s["totalUSD"] * c["cartons"], 2), "onlineTotalUSD": None,
                             "perCartonUSD": s["totalUSD"], "delivery": s.get("deliveredBy") or "", "transitDays": s.get("daysInTransit"),
                             "note": (f"billed at {s['billableWeight']}" if s.get("billableWeight") else ""),
                             "source": "https://wwwapps.ups.com/ctc/request?loc=en_US", "inputs": inputs})
        opts.sort(key=lambda o: o["totalUSD"])
        # landed basis: cheapest option that does not need repacking (supplier ships its own cartons)
        basis = next((o for o in opts if not o["note"].startswith("repack")), opts[0] if opts else None)
        c["freight"]["cheapest"] = opts[0] if opts else None
        if basis and c["goodsUSD"] is not None:
            total = round(c["goodsUSD"] + c["setupUSD"] + basis["totalUSD"], 2)
            c["landed"] = {"basis": f"{basis['carrier']} {basis['service']}", "goodsUSD": c["goodsUSD"], "setupUSD": c["setupUSD"],
                           "freightUSD": basis["totalUSD"], "totalUSD": total, "perUnitUSD": round(total / a.qty, 2)}
    for c in cands:
        if c not in rateable:
            c["freight"]["problems"].append("no carton data anywhere in this set; freight not rated")

    T["total"] = round(time.time() - t0, 2)
    cands.sort(key=lambda c: (c["landed"] or {}).get("perUnitUSD", 9e9))
    slug = re.sub(r"[^a-z0-9]+", "-", a.query.lower()).strip("-")[:40]
    result = {"schema": "karen-review/1", "generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
              "request": {"query": a.query, "qty": a.qty, "shipTo": a.to, "shipToLabel": a.to_label, "minPrice": a.min_price, "maxPrice": a.max_price, "prompt": a.prompt},
              "timingSec": T, "queriesSpent": 1 + len(picks), "totalFound": search.get("totalFound"),
              "sources": {"sageSearchFile": str(search_file), "sageDetailFiles": detail_files}, "candidates": cands}
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    out = REVIEW_DIR / f"{dt.datetime.now().strftime('%Y-%m-%d-%H%M')}-{slug}.json"
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")

    if a.json:
        print(json.dumps(result, indent=1)); return
    print(f"{a.qty} x {a.query} -> {a.to_label or a.to}: {len(cands)} candidates from {search.get('totalFound')} found, "
          f"{result['queriesSpent']} SAGE queries, {T['total']}s (keys {T['keys']}, search {T['search']}, detail {T['detail']}, freight {T['freight']})")
    print(f"{'landed/unit':>11} {'net':>6} {'setup':>6} {'freight basis':<34} {'freight':>9}  {'supplier':<14} item   name")
    for c in cands:
        L = c["landed"] or {}
        print(f"{('$%.2f' % L['perUnitUSD']) if L else 'n/a':>11} {('$%.2f' % c['netAtQty']) if c['netAtQty'] is not None else '-':>6} "
              f"{'$%.0f' % c['setupChg']:>6} {L.get('basis', '-')[:34]:<34} {('$%.2f' % L['freightUSD']) if L else '-':>9}  "
              f"{(c['supplier'] or '')[:14]:<14} {c['itemNum']:<6} {c['name'][:48]}")
        for fl in c["flags"]:
            print(f"{'':>11} ! {fl}")
        for pr in c["freight"]["problems"]:
            print(f"{'':>11} ! {pr}")
    print(f"review file: {out}")
    if a.html or os.environ.get("CLAUDE_CODE_REMOTE") or os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID"):
        subprocess.run([sys.executable, str(REVIEW_SERVER), "--export", out.name])


def _safe(fn, *args):
    try:
        return fn(*args)
    except Exception as e:  # reported per candidate, never hides the run
        return e


if __name__ == "__main__":
    main()
